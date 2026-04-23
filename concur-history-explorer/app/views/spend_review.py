"""
Departmental Spend Review — Story B1.
Browse historical expense data by department, cost center, and ICW category.
"""

from __future__ import annotations

import io
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app import theme
from app.db.connection import db_exists, get_connection
from app.db.queries import (
    ExpenseFilters,
    export_to_dataframe,
    get_filter_options,
    get_spend_summary,
    search_expenses,
)
from app.utils.formatters import fmt_currency, fmt_currency_compact

# ── Session-state keys ────────────────────────────────────────────────────────
_SS_YEAR       = "sr_year"
_SS_CUSTOM     = "sr_custom_range"
_SS_DATE_START = "sr_date_start"
_SS_DATE_END   = "sr_date_end"
_SS_GROUP1     = "sr_group1"
_SS_GROUP2     = "sr_group2"
_SS_EXP_GROUP  = "sr_exp_group"
_SS_COST_CTR   = "sr_cost_center"
_SS_DEPT       = "sr_dept"
_SS_RESULTS    = "sr_results"
_SS_DRILL_ROW  = "sr_drill_row"

_GROUP_OPTIONS = [
    "cost_center",
    "org_unit_1",
    "icw_expense_group",
    "icw_expense_category",
    "employee",
]
_GROUP_LABELS = {
    "cost_center":          "Cost Center",
    "org_unit_1":           "Department (ORG_UNIT_1)",
    "icw_expense_group":    "ICW Expense Group",
    "icw_expense_category": "ICW Expense Category",
    "employee":             "Employee",
}

_FISCAL_YEARS = [str(y) for y in range(date.today().year, 2017, -1)]


def _init_state() -> None:
    defaults = {
        _SS_YEAR:       str(date.today().year - 1),
        _SS_CUSTOM:     False,
        _SS_DATE_START: None,
        _SS_DATE_END:   None,
        _SS_GROUP1:     "cost_center",
        _SS_GROUP2:     "(None)",
        _SS_EXP_GROUP:  "(All)",
        _SS_COST_CTR:   "(All)",
        _SS_DEPT:       "(All)",
        _SS_RESULTS:    None,
        _SS_DRILL_ROW:  None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _year_to_dates(year: str) -> tuple[str, str]:
    return f"{year}-01-01", f"{year}-12-31"


def _build_filters(opts: dict) -> ExpenseFilters:
    f: ExpenseFilters = {}
    if st.session_state[_SS_CUSTOM]:
        if st.session_state[_SS_DATE_START]:
            f["date_start"] = str(st.session_state[_SS_DATE_START])
        if st.session_state[_SS_DATE_END]:
            f["date_end"] = str(st.session_state[_SS_DATE_END])
    else:
        ds, de = _year_to_dates(st.session_state[_SS_YEAR])
        f["date_start"], f["date_end"] = ds, de

    cc = st.session_state[_SS_COST_CTR]
    if cc != "(All)":
        f["cost_center"] = cc
    dept = st.session_state[_SS_DEPT]
    if dept != "(All)":
        f["org_unit_1"] = dept
    eg = st.session_state[_SS_EXP_GROUP]
    if eg != "(All)":
        f["expense_group"] = eg
    return f


def _render_controls(opts: dict) -> None:
    with st.container():
        st.markdown('<div class="wd-card">', unsafe_allow_html=True)
        st.markdown('<div class="wd-card-header">Report Parameters</div>', unsafe_allow_html=True)

        r1c1, r1c2, r1c3, r1c4 = st.columns([2, 2, 2, 1])

        with r1c1:
            use_custom = st.toggle("Custom date range", key=_SS_CUSTOM)
            if use_custom:
                st.date_input("From", key=_SS_DATE_START, value=date(date.today().year - 1, 1, 1))
                st.date_input("To",   key=_SS_DATE_END,   value=date(date.today().year - 1, 12, 31))
            else:
                st.selectbox("Fiscal Year", _FISCAL_YEARS, key=_SS_YEAR)

        with r1c2:
            st.selectbox(
                "Primary Group By",
                _GROUP_OPTIONS,
                format_func=_GROUP_LABELS.get,
                key=_SS_GROUP1,
            )

        with r1c3:
            st.selectbox(
                "Secondary Group By (optional)",
                ["(None)"] + _GROUP_OPTIONS,
                format_func=lambda x: "(None)" if x == "(None)" else _GROUP_LABELS.get(x, x),
                key=_SS_GROUP2,
            )

        with r1c4:
            st.markdown("<br>", unsafe_allow_html=True)
            generate = st.button("Generate Report", type="primary", use_container_width=True)

        st.markdown("---")
        r2c1, r2c2, r2c3 = st.columns(3)

        with r2c1:
            exp_groups = ["(All)"] + opts.get("expense_groups", [])
            st.selectbox("ICW Expense Group", exp_groups, key=_SS_EXP_GROUP)

        with r2c2:
            cost_centers = ["(All)"] + opts.get("cost_centers", [])
            st.selectbox("Cost Center", cost_centers, key=_SS_COST_CTR)

        with r2c3:
            depts = ["(All)"] + opts.get("org_units", {}).get("org_unit_1", [])
            st.selectbox("Department", depts, key=_SS_DEPT)

        st.markdown('</div>', unsafe_allow_html=True)

    if generate:
        st.session_state[_SS_RESULTS] = "pending"
        st.session_state[_SS_DRILL_ROW] = None
        st.rerun()


def _render_summary_metrics(df: pd.DataFrame) -> None:
    total_spend   = df["total_amount"].sum() if "total_amount" in df.columns else 0
    total_reports = df["report_count"].sum() if "report_count" in df.columns else 0
    total_txns    = df["transaction_count"].sum() if "transaction_count" in df.columns else 0
    avg_txn       = (total_spend / total_txns) if total_txns else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        theme.styled_metric_card("Total Spend", fmt_currency_compact(total_spend))
    with c2:
        theme.styled_metric_card("Total Reports", f"{int(total_reports):,}", border_color=theme.MEDIUM_BLUE)
    with c3:
        theme.styled_metric_card("Total Transactions", f"{int(total_txns):,}", border_color=theme.SUCCESS)
    with c4:
        theme.styled_metric_card("Avg Transaction", fmt_currency(avg_txn), border_color=theme.ACCENT_TEAL)


def _render_table_tab(df: pd.DataFrame, group_cols: list[str]) -> None:
    if df.empty:
        st.info("No data for the selected filters.")
        return

    total_spend = df["total_amount"].sum() or 1
    display = df.copy()
    display["% of Total"] = (display["total_amount"] / total_spend * 100).map("{:.1f}%".format)
    display["Total Spend"] = display["total_amount"].apply(fmt_currency)
    display["Avg Transaction"] = display["avg_amount"].apply(fmt_currency)

    rename = {g: _GROUP_LABELS.get(g, g) for g in group_cols}
    rename.update({
        "transaction_count": "# Transactions",
        "report_count":      "# Reports",
    })
    show_cols = group_cols + ["Total Spend", "# Transactions", "# Reports", "Avg Transaction", "% of Total"]
    out = display.rename(columns=rename)[
        [rename.get(c, c) for c in show_cols if rename.get(c, c) in display.rename(columns=rename).columns]
    ]

    st.dataframe(out, use_container_width=True, hide_index=True)

    # Drill-down selector
    group_vals = df[group_cols[0]].dropna().unique().tolist()
    sel = st.selectbox(
        "Drill into group →",
        ["— select a group —"] + [str(v) for v in group_vals],
        key="sr_drill_select",
    )
    if sel != "— select a group —":
        st.session_state[_SS_DRILL_ROW] = sel
        st.session_state["audit_prefill_group"] = st.session_state[_SS_GROUP1]
        st.session_state["audit_prefill_value"] = sel


def _render_chart_tab(df: pd.DataFrame, group_cols: list[str]) -> None:
    if df.empty:
        st.info("No data to chart.")
        return

    label_col = group_cols[0]
    top15 = df.nlargest(15, "total_amount")

    colors = theme.get_chart_colors()

    # Donut chart
    c1, c2 = st.columns(2)
    with c1:
        fig_pie = go.Figure(go.Pie(
            labels=top15[label_col].astype(str),
            values=top15["total_amount"],
            hole=0.45,
            marker_colors=colors,
            textinfo="percent+label",
            hovertemplate="%{label}<br>$%{value:,.2f} (%{percent})<extra></extra>",
        ))
        fig_pie.update_layout(**theme.get_plotly_layout("Spend Distribution", height=360))
        st.plotly_chart(fig_pie, use_container_width=True)

    with c2:
        st.markdown(
            f'<div class="wd-card-header" style="margin-bottom:0.5rem;">Legend</div>',
            unsafe_allow_html=True,
        )
        for i, row in top15.iterrows():
            color = colors[list(top15.index).index(i) % len(colors)]
            pct = row["total_amount"] / (df["total_amount"].sum() or 1) * 100
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">'
                f'<span style="width:12px;height:12px;border-radius:2px;background:{color};flex-shrink:0;"></span>'
                f'<span style="font-size:0.8rem;color:{theme.DARK_GRAY};">{str(row[label_col])[:40]}</span>'
                f'<span style="margin-left:auto;font-size:0.8rem;font-weight:600;">{pct:.1f}%</span>'
                f'</div>',
                unsafe_allow_html=True,
            )


def _build_excel(df: pd.DataFrame, filters: ExpenseFilters, conn) -> bytes:
    detail_df = export_to_dataframe(conn, "search", filters)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Spend Summary", index=False)
        detail_df.to_excel(writer, sheet_name="Transaction Detail", index=False)
    return buf.getvalue()


def render() -> None:
    theme.apply_workday_theme()
    _init_state()

    theme.styled_header(
        "📊 Departmental Spend Review",
        subtitle="Analyze historical expense data by department, cost center, and category.",
    )

    if not db_exists():
        st.info("No database found. Run the ingest command first.")
        st.code("python -m app.db.ingest --data-dir ./data", language="bash")
        return

    conn = get_connection()
    opts = get_filter_options(conn)

    _render_controls(opts)

    if st.session_state[_SS_RESULTS] is None:
        st.markdown(
            f'<div style="text-align:center;padding:2.5rem;color:{theme.MEDIUM_GRAY};">'
            f'Configure parameters above and click <b>Generate Report</b>.</div>',
            unsafe_allow_html=True,
        )
        conn.close()
        return

    filters = _build_filters(opts)
    group1  = st.session_state[_SS_GROUP1]
    group2  = st.session_state[_SS_GROUP2]
    group_by = [group1] if group2 == "(None)" else [group1, group2]

    with st.spinner("Generating report…"):
        df = get_spend_summary(conn, group_by=group_by, filters=filters)

    st.session_state[_SS_RESULTS] = "done"

    if df.empty:
        st.warning("No data found for the selected filters.")
        conn.close()
        return

    st.divider()
    _render_summary_metrics(df)
    st.divider()

    tab_table, tab_chart = st.tabs(["📊 Table View", "📈 Chart View"])

    with tab_table:
        _render_table_tab(df, group_by)

        ex1, ex2, _ = st.columns([1.2, 1.4, 5])
        with ex1:
            st.download_button(
                "📥 Export CSV",
                data=df.to_csv(index=False).encode(),
                file_name=f"spend_summary_{date.today()}.csv",
                mime="text/csv",
            )
        with ex2:
            st.download_button(
                "📥 Export Excel",
                data=_build_excel(df, filters, conn),
                file_name=f"spend_summary_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    with tab_chart:
        _render_chart_tab(df, group_by)

    conn.close()
