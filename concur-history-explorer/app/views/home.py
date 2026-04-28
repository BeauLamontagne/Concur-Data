"""Dashboard — filters first, then KPIs and charts reflecting the selection."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import theme
from app.db.connection import db_exists, get_connection
from app.db.queries import ExpenseFilters, get_filter_options, get_spend_summary
from app.utils.formatters import fmt_currency, fmt_currency_compact, fmt_date_short

# ── Session-state keys ────────────────────────────────────────────────────────
_SS_YEAR       = "home_year"
_SS_DATE_START = "home_date_start"
_SS_DATE_END   = "home_date_end"
_SS_COST_CTR   = "home_cc"
_SS_DEPT       = "home_dept"
_SS_EXP_GROUP  = "home_group"
_SS_EMP        = "home_emp"
_SS_STATUS     = "home_status"

_ALL = "(All)"
_FISCAL_YEARS = [_ALL] + [str(y) for y in range(date.today().year, 2017, -1)]


def _init_state() -> None:
    defaults = {
        _SS_YEAR:       _ALL,
        _SS_DATE_START: None,
        _SS_DATE_END:   None,
        _SS_COST_CTR:   _ALL,
        _SS_DEPT:       _ALL,
        _SS_EXP_GROUP:  _ALL,
        _SS_EMP:        "",
        _SS_STATUS:     _ALL,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _render_filters(opts: dict) -> None:
    st.markdown('<div class="wd-filter-panel">', unsafe_allow_html=True)
    st.markdown('<div class="wd-section-label">Filter Dashboard</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.selectbox("Year", _FISCAL_YEARS, key=_SS_YEAR)

        date_min = opts.get("date_min")
        date_max = opts.get("date_max")
        try:
            min_d = datetime.strptime(date_min[:10], "%Y-%m-%d").date() if date_min else date(2018, 1, 1)
            max_d = datetime.strptime(date_max[:10], "%Y-%m-%d").date() if date_max else date.today()
        except Exception:
            min_d, max_d = date(2018, 1, 1), date.today()

        st.date_input("From date", value=min_d, min_value=min_d, max_value=max_d, key=_SS_DATE_START)
        st.date_input("To date",   value=max_d, min_value=min_d, max_value=max_d, key=_SS_DATE_END)

    with c2:
        cost_centers = [_ALL] + opts.get("cost_centers", [])
        st.selectbox("Cost Center", cost_centers, key=_SS_COST_CTR)

        depts = [_ALL] + opts.get("org_units", {}).get("org_unit_1", [])
        st.selectbox("Department", depts, key=_SS_DEPT)

    with c3:
        groups = [_ALL] + opts.get("expense_groups", [])
        st.selectbox("Expense Group", groups, key=_SS_EXP_GROUP)

        statuses = [_ALL] + opts.get("approval_statuses", [])
        st.selectbox("Approval Status", statuses, key=_SS_STATUS)

    with c4:
        st.text_input("Employee Name", key=_SS_EMP, placeholder="Last or first name…")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Clear Filters", key="home_clear"):
            for k, v in {
                _SS_YEAR: _ALL, _SS_COST_CTR: _ALL, _SS_DEPT: _ALL,
                _SS_EXP_GROUP: _ALL, _SS_STATUS: _ALL, _SS_EMP: "",
            }.items():
                st.session_state[k] = v
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


def _build_filters() -> ExpenseFilters:
    f: ExpenseFilters = {}

    year = st.session_state.get(_SS_YEAR, _ALL)
    if year and year != _ALL:
        f["date_start"] = f"{year}-01-01"
        f["date_end"]   = f"{year}-12-31"
    else:
        ds = st.session_state.get(_SS_DATE_START)
        de = st.session_state.get(_SS_DATE_END)
        if ds:
            f["date_start"] = str(ds)
        if de:
            f["date_end"] = str(de)

    cc = st.session_state.get(_SS_COST_CTR, _ALL)
    if cc and cc != _ALL:
        f["cost_center"] = cc

    dept = st.session_state.get(_SS_DEPT, _ALL)
    if dept and dept != _ALL:
        f["org_unit_1"] = dept

    group = st.session_state.get(_SS_EXP_GROUP, _ALL)
    if group and group != _ALL:
        f["expense_group"] = group

    emp = st.session_state.get(_SS_EMP, "")
    if emp:
        f["employee_name"] = emp

    status = st.session_state.get(_SS_STATUS, _ALL)
    if status and status != _ALL:
        f["approval_status"] = status

    return f


def _render_kpis(conn, filters: ExpenseFilters) -> None:
    # Use get_spend_summary aggregated to get totals
    df = get_spend_summary(conn, group_by="cost_center", filters=filters if filters else None)

    total_spend  = df["total_amount"].sum() if not df.empty else 0
    total_rpts   = int(df["report_count"].sum()) if not df.empty else 0
    total_txns   = int(df["transaction_count"].sum()) if not df.empty else 0
    avg_txn      = (total_spend / total_txns) if total_txns else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        theme.styled_metric_card("Total Spend", fmt_currency_compact(total_spend))
    with c2:
        theme.styled_metric_card("Total Reports", f"{total_rpts:,}", border_color=theme.MEDIUM_BLUE)
    with c3:
        theme.styled_metric_card("Total Transactions", f"{total_txns:,}", border_color=theme.SUCCESS)
    with c4:
        theme.styled_metric_card("Avg Transaction", fmt_currency(avg_txn), border_color=theme.ACCENT_TEAL)


def _render_charts(conn, filters: ExpenseFilters) -> None:
    left, right = st.columns([1, 1])

    # Pie: spend by expense group
    with left:
        st.markdown('<div class="wd-card">', unsafe_allow_html=True)
        st.markdown('<div class="wd-card-header">Spend by Expense Group</div>', unsafe_allow_html=True)
        try:
            df_grp = get_spend_summary(conn, group_by="icw_expense_group", filters=filters if filters else None)
            if not df_grp.empty:
                labels = df_grp["icw_expense_group"].fillna("Uncategorized").tolist()
                values = df_grp["total_amount"].tolist()
                fig = go.Figure(go.Pie(
                    labels=labels, values=values,
                    hole=0.5,
                    marker_colors=theme.get_chart_colors(),
                    textinfo="percent",
                    hovertemplate="%{label}<br>%{value:$,.2f} (%{percent})<extra></extra>",
                ))
                fig.update_layout(**theme.get_plotly_layout(height=320))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No data for the selected filters.")
        except Exception as e:
            st.caption(f"Chart unavailable: {e}")
        st.markdown('</div>', unsafe_allow_html=True)

    # Bar: top 10 cost centers
    with right:
        st.markdown('<div class="wd-card">', unsafe_allow_html=True)
        st.markdown('<div class="wd-card-header">Top 10 Cost Centers by Spend</div>', unsafe_allow_html=True)
        try:
            df_cc = get_spend_summary(conn, group_by="cost_center", filters=filters if filters else None)
            df_cc = df_cc.dropna(subset=["cost_center"]).head(10)
            if not df_cc.empty:
                fig_cc = go.Figure(go.Bar(
                    x=df_cc["total_amount"],
                    y=df_cc["cost_center"].astype(str),
                    orientation="h",
                    marker_color=theme.PRIMARY,
                    text=df_cc["total_amount"].apply(fmt_currency_compact),
                    textposition="outside",
                    hovertemplate="%{y}<br>$%{x:,.2f}<extra></extra>",
                ))
                fig_cc.update_layout(
                    **theme.get_plotly_layout(height=320),
                    yaxis={"autorange": "reversed"},
                    xaxis_title="Posted Amount ($)",
                    margin={"l": 140, "r": 60, "t": 20, "b": 40},
                )
                st.plotly_chart(fig_cc, use_container_width=True)
            else:
                st.info("No data for the selected filters.")
        except Exception as e:
            st.caption(f"Chart unavailable: {e}")
        st.markdown('</div>', unsafe_allow_html=True)

    # Bar: top 10 departments
    st.markdown('<div class="wd-card">', unsafe_allow_html=True)
    st.markdown('<div class="wd-card-header">Top 10 Departments by Spend</div>', unsafe_allow_html=True)
    try:
        df_dept = get_spend_summary(conn, group_by="org_unit_1", filters=filters if filters else None)
        df_dept = df_dept.dropna(subset=["org_unit_1"]).head(10)
        if not df_dept.empty:
            fig_dept = go.Figure(go.Bar(
                x=df_dept["total_amount"],
                y=df_dept["org_unit_1"].astype(str),
                orientation="h",
                marker_color=theme.ACCENT_TEAL,
                text=df_dept["total_amount"].apply(fmt_currency_compact),
                textposition="outside",
                hovertemplate="%{y}<br>$%{x:,.2f}<extra></extra>",
            ))
            fig_dept.update_layout(
                **theme.get_plotly_layout(height=340),
                yaxis={"autorange": "reversed"},
                xaxis_title="Posted Amount ($)",
                margin={"l": 200, "r": 60, "t": 20, "b": 40},
            )
            st.plotly_chart(fig_dept, use_container_width=True)
        else:
            st.info("No data for the selected filters.")
    except Exception as e:
        st.caption(f"Chart unavailable: {e}")
    st.markdown('</div>', unsafe_allow_html=True)


def render() -> None:
    theme.apply_workday_theme()
    _init_state()

    theme.styled_header(
        "Dashboard",
        subtitle="Apply filters below, then review summary spend across all dimensions.",
    )

    if not db_exists():
        st.info("No expense data loaded yet.")
        st.code("python -m app.utils.sample_data --num-reports 50000", language="bash")
        return

    conn = get_connection()

    with st.spinner("Loading filter options…"):
        opts = get_filter_options(conn)

    _render_filters(opts)

    filters = _build_filters()

    st.divider()

    with st.spinner("Loading data…"):
        _render_kpis(conn, filters)

    st.divider()

    _render_charts(conn, filters)

    conn.close()
