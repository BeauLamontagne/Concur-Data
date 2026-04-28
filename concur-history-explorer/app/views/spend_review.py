"""Dept Spend — aggregated spend by department, cost center, or category."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from app import theme
from app.db.connection import db_exists, get_connection
from app.db.queries import ExpenseFilters, get_filter_options, get_spend_summary
from app.utils.formatters import fmt_currency, fmt_currency_compact

# Session-state keys
_SS_YEAR    = "sr_year"
_SS_GROUP1  = "sr_group1"
_SS_RESULTS = "sr_results"

_GROUP_OPTIONS = [
    "cost_center",
    "org_unit_1",
    "icw_expense_group",
    "icw_expense_category",
]
_GROUP_LABELS = {
    "cost_center":          "Cost Center",
    "org_unit_1":           "Department",
    "icw_expense_group":    "ICW Expense Group",
    "icw_expense_category": "ICW Expense Category",
}

_FISCAL_YEARS = [str(y) for y in range(date.today().year, 2017, -1)]


def _init_state() -> None:
    defaults: dict = {
        _SS_YEAR:    str(date.today().year - 1),
        _SS_GROUP1:  "cost_center",
        _SS_RESULTS: None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _render_controls() -> bool:
    """Render parameter controls. Returns True when Generate is clicked."""
    st.markdown('<div class="wd-card">', unsafe_allow_html=True)
    st.markdown('<div class="wd-card-header">Report Parameters</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns([2, 3, 1])

    with c1:
        st.selectbox("Fiscal Year", _FISCAL_YEARS, key=_SS_YEAR)

    with c2:
        st.selectbox(
            "Group By",
            _GROUP_OPTIONS,
            format_func=_GROUP_LABELS.get,
            key=_SS_GROUP1,
        )

    with c3:
        st.markdown("<br>", unsafe_allow_html=True)
        generate = st.button("Generate Report", type="primary", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)
    return generate


def _render_table(df: pd.DataFrame, group_col: str) -> None:
    if df.empty:
        st.info("No data for the selected filters.")
        return

    total_spend = df["total_amount"].sum() or 1
    display = df.copy()
    display["% of Total"]      = (display["total_amount"] / total_spend * 100).map("{:.1f}%".format)
    display["Total Spend"]     = display["total_amount"].apply(fmt_currency)
    display["Avg Transaction"] = display["avg_amount"].apply(fmt_currency)

    group_label = _GROUP_LABELS.get(group_col, group_col)
    out = display.rename(columns={
        group_col:           group_label,
        "transaction_count": "# Transactions",
        "report_count":      "# Reports",
    })[[group_label, "Total Spend", "# Transactions", "# Reports", "Avg Transaction", "% of Total"]]

    st.dataframe(out, use_container_width=True, hide_index=True)


def render() -> None:
    theme.apply_workday_theme()
    _init_state()

    theme.styled_header(
        "Dept Spend",
        subtitle="Select a fiscal year and grouping, then click Generate Report.",
    )

    if not db_exists():
        st.info("No database found. Run the ingest command first.")
        st.code("python -m app.db.ingest --data-dir ./data", language="bash")
        return

    conn = get_connection()

    generate = _render_controls()

    if generate:
        st.session_state[_SS_RESULTS] = "pending"

    if st.session_state[_SS_RESULTS] is None:
        st.markdown(
            f'<div style="text-align:center;padding:2.5rem;color:{theme.MEDIUM_GRAY};">'
            f'Select a year and grouping above, then click <b>Generate Report</b>.</div>',
            unsafe_allow_html=True,
        )
        conn.close()
        return

    year    = st.session_state[_SS_YEAR]
    group1  = st.session_state[_SS_GROUP1]
    filters: ExpenseFilters = {
        "date_start": f"{year}-01-01",
        "date_end":   f"{year}-12-31",
    }

    with st.spinner("Generating report…"):
        df = get_spend_summary(conn, group_by=group1, filters=filters)

    st.session_state[_SS_RESULTS] = "done"

    if df.empty:
        st.warning("No data found for the selected year.")
        conn.close()
        return

    # Summary metrics
    st.divider()
    total_spend   = df["total_amount"].sum()
    total_reports = int(df["report_count"].sum())
    total_txns    = int(df["transaction_count"].sum())
    avg_txn       = total_spend / total_txns if total_txns else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        theme.styled_metric_card("Total Spend", fmt_currency_compact(total_spend))
    with c2:
        theme.styled_metric_card("Total Reports", f"{total_reports:,}", border_color=theme.MEDIUM_BLUE)
    with c3:
        theme.styled_metric_card("Total Transactions", f"{total_txns:,}", border_color=theme.SUCCESS)
    with c4:
        theme.styled_metric_card("Avg Transaction", fmt_currency(avg_txn), border_color=theme.ACCENT_TEAL)

    st.divider()
    _render_table(df, group1)

    st.download_button(
        "📥 Export CSV",
        data=df.to_csv(index=False).encode(),
        file_name=f"dept_spend_{year}_{date.today()}.csv",
        mime="text/csv",
    )

    conn.close()
