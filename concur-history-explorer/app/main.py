"""Streamlit entry point — app shell and navigation."""

import streamlit as st
from app.db.connection import db_exists
from app import theme

st.set_page_config(
    page_title="Concur History Explorer",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(theme.METRIC_CARD_CSS, unsafe_allow_html=True)

# ── Sidebar navigation ──────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        f"""
        <div style="padding:1rem 0 0.5rem 0;">
            <span style="font-size:1.4rem;font-weight:700;color:{theme.PRIMARY};">
                💼 Concur Explorer
            </span><br>
            <span style="font-size:0.78rem;color:{theme.TEXT_MUTED};">
                ICW Group — Historical Expense Data
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    page = st.radio(
        "Navigate",
        options=[
            "🏠  Dashboard",
            "🔍  Audit Search",
            "📋  Expense Detail",
            "📊  Spend Review",
            "📈  Trend Analysis",
            "📥  Export",
        ],
        label_visibility="collapsed",
    )

    st.divider()
    if not db_exists():
        st.warning("No database found.\n\nRun ingest first:\n```\npython -m app.db.ingest --data-dir ./data\n```")

# ── Page routing ────────────────────────────────────────────────────────────

page_key = page.split("  ", 1)[-1].strip()

if page_key == "Dashboard":
    from app.pages.home import render
    render()
elif page_key == "Audit Search":
    from app.pages.audit_search import render
    render()
elif page_key == "Expense Detail":
    from app.pages.expense_detail import render
    render()
elif page_key == "Spend Review":
    from app.pages.spend_review import render
    render()
elif page_key == "Trend Analysis":
    from app.pages.trend_analysis import render
    render()
elif page_key == "Export":
    from app.pages.export import render
    render()
