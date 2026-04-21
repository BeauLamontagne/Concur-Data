"""Dashboard home page — top-level KPIs and quick stats."""

import pandas as pd
import streamlit as st

from app.db.connection import db_exists, get_connection
from app.db.constants import TBL_EMPLOYEE, TBL_ENTRY, TBL_REPORT, Emp, Rpe, Rpt
from app import theme
from app.utils.formatters import fmt_currency_compact


def render() -> None:
    theme.apply_workday_theme()
    theme.styled_header("Dashboard", subtitle="ICW Group — Historical Expense Summary")

    if not db_exists():
        st.info("No expense data loaded yet. Run the ingest command to get started.")
        st.code("python -m app.db.ingest --data-dir ./data", language="bash")
        return

    conn = get_connection()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        n = conn.execute(f"SELECT COUNT(*) FROM {TBL_EMPLOYEE}").fetchone()[0]
        theme.styled_metric_card("Employees", f"{n:,}")

    with col2:
        n = conn.execute(f"SELECT COUNT(*) FROM {TBL_REPORT}").fetchone()[0]
        theme.styled_metric_card("Expense Reports", f"{n:,}", border_color=theme.MEDIUM_BLUE)

    with col3:
        n = conn.execute(f"SELECT COUNT(*) FROM {TBL_ENTRY}").fetchone()[0]
        theme.styled_metric_card("Line Items", f"{n:,}", border_color=theme.SUCCESS)

    with col4:
        row = conn.execute(f"SELECT SUM({Rpe.POSTED_AMOUNT}) FROM {TBL_ENTRY}").fetchone()
        total = row[0] if row and row[0] else 0
        theme.styled_metric_card("Total Posted", fmt_currency_compact(total), border_color=theme.ACCENT_TEAL)

    st.divider()
    theme.styled_header("Recent Reports", level=2)

    try:
        rows = conn.execute(
            f"""
            SELECT r.{Rpt.RPT_ID}       AS "Report ID",
                   e.{Emp.FIRST_NAME} || ' ' || e.{Emp.LAST_NAME} AS "Employee",
                   r.{Rpt.NAME}          AS "Report Name",
                   r.{Rpt.SUBMIT_DATE}   AS "Submit Date",
                   r.{Rpt.STATUS_CODE}   AS "Status",
                   r.{Rpt.TOTAL_APPROVED} AS "Approved Amount"
            FROM {TBL_REPORT} r
            JOIN {TBL_EMPLOYEE} e ON r.{Rpt.EMP_KEY} = e.{Emp.KEY}
            ORDER BY r.{Rpt.SUBMIT_DATE} DESC
            LIMIT 20
            """
        ).fetchall()
        if rows:
            theme.styled_dataframe(pd.DataFrame([dict(r) for r in rows]))
        else:
            st.info("No report data available.")
    except Exception as e:
        st.error(f"Could not load recent reports: {e}")

    conn.close()
