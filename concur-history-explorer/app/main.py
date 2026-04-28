"""Streamlit entry point — app shell, auth gate, and navigation."""

import streamlit as st
from app.utils.logger import setup_logging, get_logger
from app.db.connection import db_exists, get_connection
from app import theme

setup_logging()
_log = get_logger("concur.main")

st.set_page_config(
    page_title="Concur History Explorer",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="collapsed",
)

theme.apply_workday_theme()

# ── Auth gate ──────────────────────────────────────────────────────────────────
from app.views.login import is_authenticated, render_login  # noqa: E402

if not is_authenticated():
    render_login()
    st.stop()

# ── Initialize page state (always Dashboard on fresh login) ───────────────────
if "page" not in st.session_state:
    st.session_state["page"] = "Dashboard"

# ── Top navigation bar ─────────────────────────────────────────────────────────
_PAGES = ["Dashboard", "Dept Spend", "Year-over-Year", "Expense Search"]
_PAGE_LABELS = {
    "Dashboard":      "🏠  Dashboard",
    "Dept Spend":     "📊  Dept Spend",
    "Year-over-Year": "📈  Year-over-Year",
    "Expense Search": "🔍  Expense Search",
}

cur_page = st.session_state["page"]

brand_col, nav1, nav2, nav3, nav4, spacer, signout_col = st.columns([3, 1, 1, 1, 1, 1, 1])

with brand_col:
    st.markdown(
        f'<div style="padding-top:6px;line-height:1.2;">'
        f'<span style="font-weight:800;font-size:0.95rem;color:{theme.DARK_BLUE};'
        f'letter-spacing:1px;">ICW GROUP</span>'
        f'<span style="color:{theme.MEDIUM_GRAY};font-size:0.8rem;"> · Concur History Explorer</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

for col, key in zip([nav1, nav2, nav3, nav4], _PAGES):
    with col:
        btn_type = "primary" if cur_page == key else "secondary"
        if st.button(_PAGE_LABELS[key], use_container_width=True, type=btn_type, key=f"nav_{key}"):
            st.session_state["page"] = key
            st.rerun()

with signout_col:
    username = st.session_state.get("username", "")
    if st.button("Sign Out", use_container_width=True, key="nav_signout"):
        for k in ["username", "_auth_token", "page"]:
            st.session_state.pop(k, None)
        _log.info("User signed out: %s", username)
        st.rerun()

st.divider()

# ── Page routing ───────────────────────────────────────────────────────────────
page = st.session_state["page"]
_log.info("Page rendered: %s", page)

if page == "Dashboard":
    from app.views.home import render
    render()
elif page == "Expense Search":
    from app.views.audit_search import render
    render()
elif page == "Dept Spend":
    from app.views.spend_review import render
    render()
elif page == "Year-over-Year":
    from app.views.trend_analysis import render
    render()
