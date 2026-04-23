"""Streamlit entry point — app shell, auth gate, and navigation."""

import streamlit as st
from app.utils.logger import setup_logging, get_logger
from app.db.connection import db_exists, get_connection, DB_PATH
from app import theme
from app.db.constants import TBL_REPORT, TBL_ENTRY, Rpe, Rpt

setup_logging()
_log = get_logger("concur.main")

st.set_page_config(
    page_title="Concur History Explorer",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

theme.apply_workday_theme()

# ── Auth gate ─────────────────────────────────────────────────────────────────

from app.views.login import is_authenticated, render_login  # noqa: E402

if not is_authenticated():
    render_login()
    st.stop()

# ── Sidebar ──────────────────────────────────────────────────────────────────

_NAV_OPTIONS = [
    "📊  Department Spend",
    "📈  Year-over-Year",
    "🔍  Expense Search",
]

with st.sidebar:
    st.markdown(
        f"""
        <div style="
            background:{theme.PRIMARY};
            border-radius:6px;
            padding:10px 14px;
            margin-bottom:10px;
            text-align:center;
            font-size:0.95rem;
            font-weight:800;
            letter-spacing:1.5px;
            color:#fff;
        ">ICW GROUP</div>
        <div style="
            color:#fff;
            font-size:1.05rem;
            font-weight:700;
            line-height:1.25;
            margin-bottom:3px;
        ">Concur History Explorer</div>
        <div style="
            color:{theme.MEDIUM_GRAY};
            font-size:0.75rem;
            margin-bottom:12px;
        ">Historical Expense Data Archive</div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    # Consume any pending nav request BEFORE the radio renders
    _pending = st.session_state.pop("_pending_nav", None)
    if _pending in _NAV_OPTIONS:
        st.session_state["_current_page_idx"] = _NAV_OPTIONS.index(_pending)

    # Persist the selected page across reruns (e.g. when a widget changes on the same page)
    _current_idx = st.session_state.get("_current_page_idx", None)

    page = st.radio(
        "nav",
        options=_NAV_OPTIONS,
        index=_current_idx,
        label_visibility="collapsed",
    )

    # Track whatever the radio is now showing
    if page is not None:
        st.session_state["_current_page_idx"] = _NAV_OPTIONS.index(page)
    else:
        st.session_state["_current_page_idx"] = None

    st.divider()

    # DB stats footer
    if db_exists():
        try:
            conn = get_connection()
            n_reports = conn.execute(f"SELECT COUNT(*) FROM {TBL_REPORT}").fetchone()[0]
            n_entries = conn.execute(f"SELECT COUNT(*) FROM {TBL_ENTRY}").fetchone()[0]
            row = conn.execute(
                f"SELECT MIN({Rpe.TX_DATE}), MAX({Rpe.TX_DATE}) FROM {TBL_ENTRY}"
            ).fetchone()
            yr_min = (row[0] or "")[:4]
            yr_max = (row[1] or "")[:4]
            conn.close()
            st.markdown(
                f'<div style="color:{theme.MEDIUM_GRAY};font-size:0.72rem;line-height:1.6;">'
                f'{n_reports:,} reports &nbsp;·&nbsp; {n_entries:,} entries<br>'
                f'{yr_min}–{yr_max}<br>'
                f'Prototype v0.1'
                f'</div>',
                unsafe_allow_html=True,
            )
        except Exception as exc:
            _log.warning("Sidebar stats unavailable: %s", exc)
            st.markdown(
                f'<div style="color:{theme.MEDIUM_GRAY};font-size:0.72rem;">Prototype v0.1</div>',
                unsafe_allow_html=True,
            )
    else:
        st.warning(
            "No database found.\n\nRun ingest or generate sample data:\n"
            "```\npython -m app.utils.sample_data\n```"
        )

    # Signed-in user + sign-out
    st.divider()
    username = st.session_state.get("username", "")
    if username:
        st.markdown(
            f'<div style="color:{theme.MEDIUM_GRAY};font-size:0.72rem;margin-bottom:6px;">'
            f'Signed in as <strong style="color:#fff;">{username}</strong></div>',
            unsafe_allow_html=True,
        )
    if st.button("Sign out", use_container_width=True):
        st.session_state.pop("username", None)
        st.session_state.pop("_auth_token", None)
        _log.info("User signed out: %s", username)
        st.rerun()

# ── Page routing ─────────────────────────────────────────────────────────────

page_key = page.split("  ", 1)[-1].strip() if page else "Home"
_log.info("Page rendered: %s", page_key)

# When switching pages, clear the state of the page being LEFT so each
# page always starts fresh with no carry-over from a previous visit.
_prev_page = st.session_state.get("_prev_page_key", "")
if page_key != _prev_page:
    _prefix_map = {
        "Department Spend": "sr_",
        "Expense Search":   "as_",
        "Year-over-Year":   "ta_",
    }
    _leave_prefix = _prefix_map.get(_prev_page)
    if _leave_prefix:
        for _k in list(st.session_state.keys()):
            if _k.startswith(_leave_prefix):
                del st.session_state[_k]
    # Search term passed from the Search Center search bar
    _nav_search = st.session_state.pop("_nav_search_term", None)
    if _nav_search is not None and page_key == "Expense Search":
        st.session_state["as_search_term"] = _nav_search
    st.session_state["_prev_page_key"] = page_key

if page_key == "Home":
    from app.views.home import render
    render()
elif page_key == "Department Spend":
    from app.views.spend_review import render
    render()
elif page_key == "Year-over-Year":
    from app.views.trend_analysis import render
    render()
elif page_key == "Expense Search":
    from app.views.audit_search import render
    render()
