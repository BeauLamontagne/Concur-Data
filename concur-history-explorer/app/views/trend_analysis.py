"""Year-over-Year Cost Center Spend Comparison."""

from __future__ import annotations

import io
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import theme
from app.db.connection import db_exists, get_connection
from app.db.queries import ExpenseFilters, get_filter_options, get_spend_summary
from app.utils.formatters import fmt_currency, fmt_currency_compact

_SS_YEARS    = "ta_years"
_SS_COST_CTR = "ta_cost_center"
_SS_RESULTS  = "ta_results"


def _init_state() -> None:
    defaults = {
        _SS_YEARS:    [],
        _SS_COST_CTR: None,
        _SS_RESULTS:  None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _available_years(opts: dict) -> list[str]:
    dmin = opts.get("date_min") or "2018-01-01"
    dmax = opts.get("date_max") or str(date.today())
    try:
        y_min, y_max = int(dmin[:4]), int(dmax[:4])
    except Exception:
        y_min, y_max = 2018, date.today().year
    return [str(y) for y in range(y_max, y_min - 1, -1)]


def render() -> None:
    theme.apply_workday_theme()
    _init_state()

    theme.styled_header(
        "📈 Year-over-Year",
        subtitle="Compare a cost center's spend across multiple fiscal years.",
    )

    if not db_exists():
        st.info("No database found.")
        return

    conn = get_connection()
    opts = get_filter_options(conn)
    avail_years   = _available_years(opts)
    cost_centers  = opts.get("cost_centers", [])

    # ── Parameters ────────────────────────────────────────────────────────────
    with st.container():
        st.markdown('<div class="wd-card">', unsafe_allow_html=True)
        st.markdown('<div class="wd-card-header">Parameters</div>', unsafe_allow_html=True)

        c1, c2, c3 = st.columns([3, 3, 1])
        with c1:
            st.multiselect(
                "Years to compare",
                avail_years,
                default=st.session_state[_SS_YEARS],
                key=_SS_YEARS,
            )
        with c2:
            cc_options = ["(All)"] + cost_centers
            current_cc = st.session_state[_SS_COST_CTR] or "(All)"
            idx = cc_options.index(current_cc) if current_cc in cc_options else 0
            st.selectbox("Cost Center", cc_options, index=idx, key=_SS_COST_CTR)
        with c3:
            st.markdown("<br>", unsafe_allow_html=True)
            run = st.button("Run", type="primary", use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)

    if run:
        st.session_state[_SS_RESULTS] = "ready"
        st.rerun()

    if not st.session_state[_SS_RESULTS]:
        st.markdown(
            f'<div style="text-align:center;padding:2.5rem;color:{theme.MEDIUM_GRAY};">'
            f'Select years and a cost center, then click <b>Run</b>.</div>',
            unsafe_allow_html=True,
        )
        conn.close()
        return

    # ── Run the comparison ────────────────────────────────────────────────────
    years     = st.session_state[_SS_YEARS]
    cost_ctr  = st.session_state[_SS_COST_CTR]
    group_by  = "icw_expense_group"

    if len(years) < 2:
        st.warning("Select at least 2 years to compare.")
        conn.close()
        return

    dfs = []
    for yr in years:
        f: ExpenseFilters = {"date_start": f"{yr}-01-01", "date_end": f"{yr}-12-31"}
        if cost_ctr and cost_ctr != "(All)":
            f["cost_center"] = cost_ctr
        yr_df = get_spend_summary(conn, group_by=group_by, filters=f)
        if not yr_df.empty:
            yr_df["year"] = yr
            dfs.append(yr_df)

    if not dfs:
        st.info("No data for the selected parameters.")
        conn.close()
        return

    combined = pd.concat(dfs, ignore_index=True)
    pivot = combined.pivot_table(
        index=group_by, columns="year", values="total_amount", aggfunc="sum"
    ).reset_index().fillna(0)

    years_sorted = sorted(years)
    colors = theme.get_chart_colors()

    st.divider()

    # ── Grouped bar chart ─────────────────────────────────────────────────────
    fig = go.Figure()
    for i, yr in enumerate(years_sorted):
        if yr in pivot.columns:
            fig.add_trace(go.Bar(
                name=yr,
                x=pivot[group_by].astype(str),
                y=pivot[yr],
                marker_color=colors[i % len(colors)],
                hovertemplate=f"{yr}<br>%{{x}}<br>${{y:,.2f}}<extra></extra>",
            ))

    layout = theme.get_plotly_layout(height=400)
    layout["xaxis"] = {**layout.get("xaxis", {}), "tickangle": -30}
    fig.update_layout(
        **layout,
        title_text=f"Annual Spend by Expense Group"
                   + (f" — {cost_ctr}" if cost_ctr and cost_ctr != "(All)" else ""),
        barmode="group",
        xaxis_title="ICW Expense Group",
        yaxis_title="Posted Amount ($)",
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Numbers table ─────────────────────────────────────────────────────────
    st.markdown(
        '<div class="wd-section-label" style="margin-top:1rem;">Spend by Year — Detail</div>',
        unsafe_allow_html=True,
    )
    numbers_rows = []
    for _, row in pivot.iterrows():
        r: dict = {"Expense Group": row[group_by]}
        for yr in years_sorted:
            r[yr] = fmt_currency(row.get(yr, 0))
        numbers_rows.append(r)
    if numbers_rows:
        st.dataframe(pd.DataFrame(numbers_rows), use_container_width=True, hide_index=True)

    # ── Delta table ───────────────────────────────────────────────────────────
    st.markdown(
        '<div class="wd-section-label" style="margin-top:1rem;">Year-over-Year Change</div>',
        unsafe_allow_html=True,
    )

    delta_rows = []
    for _, row in pivot.iterrows():
        r: dict = {"Expense Group": row[group_by]}
        for yr in years_sorted:
            r[yr] = fmt_currency(row.get(yr, 0))
        if len(years_sorted) >= 2:
            prev_v = float(row.get(years_sorted[-2], 0))
            curr_v = float(row.get(years_sorted[-1], 0))
            chg = curr_v - prev_v
            pct = (chg / prev_v * 100) if prev_v else 0
            r["$ Change (YoY)"] = fmt_currency(chg)
            r["% Change (YoY)"] = f"{pct:+.1f}%"
            r["_pct_raw"] = pct
        delta_rows.append(r)

    if delta_rows:
        delta_df = pd.DataFrame(delta_rows)

        def _color_pct(val):
            try:
                v = float(str(val).replace("%", "").replace("+", ""))
                if v < 0:
                    return f"color: {theme.SUCCESS}; font-weight:600"
                if v > 0:
                    return f"color: {theme.DANGER}; font-weight:600"
            except Exception:
                pass
            return ""

        display_df = delta_df.drop(columns=["_pct_raw"], errors="ignore")
        pct_col = "% Change (YoY)"
        try:
            styled = (
                display_df.style.map(_color_pct, subset=[pct_col])
                if pct_col in display_df.columns else display_df.style
            )
        except AttributeError:
            styled = (
                display_df.style.applymap(_color_pct, subset=[pct_col])
                if pct_col in display_df.columns else display_df.style
            )
        st.dataframe(styled, use_container_width=True, hide_index=True)

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            display_df.to_excel(writer, sheet_name="YoY Comparison", index=False)
            combined.to_excel(writer, sheet_name="Raw Data", index=False)
        st.download_button(
            "📥 Export (Excel)",
            data=buf.getvalue(),
            file_name=f"yoy_{cost_ctr or 'all'}_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    conn.close()
