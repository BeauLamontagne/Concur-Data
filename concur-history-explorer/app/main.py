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

    page = st.radio(
        "nav",
        options=[
            "🔍  General Search",
            "📊  Dept Spend",
            "📈  Year-over-Year",
            "⚙️  Administration",
        ],
        label_visibility="collapsed",
    )

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

page_key = page.split("  ", 1)[-1].strip()
_log.info("Page rendered: %s", page_key)

if page_key == "General Search":
    from app.views.audit_search import render
    render()
elif page_key == "Dept Spend":
    from app.views.spend_review import render
    render()
elif page_key == "Year-over-Year":
    from app.views.trend_analysis import render
    render()
elif page_key == "Administration":
    from app.views.admin import render
    render()
