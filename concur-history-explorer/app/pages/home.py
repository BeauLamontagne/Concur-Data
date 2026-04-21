"""Dashboard home page — top-level KPIs and quick stats."""

import streamlit as st
from app.db.connection import db_exists, get_connection
from app.db.constants import TBL_EMPLOYEE, TBL_ENTRY, TBL_REPORT, Emp, Rpe, Rpt
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
        n = conn.execute(f"SELECT COUNT(*) FROM {TBL_EMPLOYEE}").fetchone()[0]
        st.markdown(theme.metric_card_html(f"{n:,}", "Employees"), unsafe_allow_html=True)

    with col2:
        n = conn.execute(f"SELECT COUNT(*) FROM {TBL_REPORT}").fetchone()[0]
        st.markdown(theme.metric_card_html(f"{n:,}", "Expense Reports", theme.INFO), unsafe_allow_html=True)

    with col3:
        n = conn.execute(f"SELECT COUNT(*) FROM {TBL_ENTRY}").fetchone()[0]
        st.markdown(theme.metric_card_html(f"{n:,}", "Line Items", theme.SUCCESS), unsafe_allow_html=True)

    with col4:
        row = conn.execute(f"SELECT SUM({Rpe.POSTED_AMOUNT}) FROM {TBL_ENTRY}").fetchone()
        total = row[0] if row and row[0] else 0
        st.markdown(theme.metric_card_html(fmt_currency_compact(total), "Total Posted", theme.WARNING), unsafe_allow_html=True)

    st.divider()
    st.subheader("Recent Reports")

    try:
        df = conn.execute(
            f"""
            SELECT r.{Rpt.RPT_ID}, e.{Emp.FIRST_NAME} || ' ' || e.{Emp.LAST_NAME} AS employee,
                   r.{Rpt.NAME}, r.{Rpt.SUBMIT_DATE}, r.{Rpt.STATUS_CODE},
                   r.{Rpt.TOTAL_APPROVED}
            FROM {TBL_REPORT} r
            JOIN {TBL_EMPLOYEE} e ON r.{Rpt.EMP_KEY} = e.{Emp.KEY}
            ORDER BY r.{Rpt.SUBMIT_DATE} DESC
            LIMIT 20
            """
        ).fetchall()
        import pandas as pd
        if df:
            rows = [dict(row) for row in df]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No report data available.")
    except Exception as e:
        st.error(f"Could not load recent reports: {e}")

    conn.close()
