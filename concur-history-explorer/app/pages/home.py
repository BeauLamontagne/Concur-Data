"""Dashboard home page — top-level KPIs and quick stats."""

import streamlit as st
from app.db.connection import db_exists, get_connection
from app import theme
from app.utils.formatters import fmt_currency_compact


def render() -> None:
    st.title("Dashboard")

    if not db_exists():
        st.info("No expense data loaded yet. Run the ingest command to get started.")
        st.code("python -m app.db.ingest --data-dir ./data", language="bash")
        return

    conn = get_connection()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        n = conn.execute("SELECT COUNT(*) FROM ct_employee").fetchone()[0]
        st.markdown(theme.metric_card_html(f"{n:,}", "Employees"), unsafe_allow_html=True)

    with col2:
        n = conn.execute("SELECT COUNT(*) FROM ct_report").fetchone()[0]
        st.markdown(theme.metric_card_html(f"{n:,}", "Expense Reports", theme.INFO), unsafe_allow_html=True)

    with col3:
        n = conn.execute("SELECT COUNT(*) FROM ct_report_entry").fetchone()[0]
        st.markdown(theme.metric_card_html(f"{n:,}", "Line Items", theme.SUCCESS), unsafe_allow_html=True)

    with col4:
        row = conn.execute("SELECT SUM(POSTED_AMOUNT) FROM ct_report_entry").fetchone()
        total = row[0] if row and row[0] else 0
        st.markdown(theme.metric_card_html(fmt_currency_compact(total), "Total Posted", theme.WARNING), unsafe_allow_html=True)

    st.divider()
    st.subheader("Recent Reports")

    try:
        df = conn.execute(
            """
            SELECT r.RPT_ID, e.FIRST_NAME || ' ' || e.LAST_NAME AS employee,
                   r.RPT_NAME, r.SUBMIT_DATE, r.APPROVAL_STATUS_CODE,
                   r.TOTAL_APPROVED_AMOUNT
            FROM ct_report r
            JOIN ct_employee e ON r.EMP_KEY = e.EMP_KEY
            ORDER BY r.SUBMIT_DATE DESC
            LIMIT 20
            """
        ).fetchall()
        import pandas as pd
        if df:
            import pandas as pd
            import sqlite3
            rows = [dict(row) for row in df]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No report data available.")
    except Exception as e:
        st.error(f"Could not load recent reports: {e}")

    conn.close()
