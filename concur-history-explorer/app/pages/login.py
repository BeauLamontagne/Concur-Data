"""Password gate — shown before any page renders if not authenticated."""

from __future__ import annotations

import streamlit as st

from app import theme

_FALLBACK_PASSWORD = "icw-concur-2024"


def _stored_password() -> str:
    try:
        return st.secrets["app_password"]
    except Exception:
        return _FALLBACK_PASSWORD


def is_authenticated() -> bool:
    stored = _stored_password()
    return (
        st.session_state.get("authenticated") is True
        and st.session_state.get("_auth_token") == stored
    )


def render_login() -> None:
    """Render the login form. Caller should stop rendering the main app until this returns."""
    theme.apply_workday_theme()

    _, col, _ = st.columns([1, 1.4, 1])

    with col:
        st.markdown(
            f"""
            <div style="text-align:center;margin-top:3rem;margin-bottom:1.75rem;">
                <div style="
                    display:inline-block;
                    background:{theme.DARK_BLUE};
                    border-radius:6px;
                    padding:10px 24px;
                    font-size:0.95rem;
                    font-weight:800;
                    letter-spacing:1.5px;
                    color:#fff;
                    margin-bottom:0.85rem;
                ">ICW GROUP</div>
                <div style="
                    font-size:1.15rem;
                    font-weight:700;
                    color:{theme.DARK_BLUE};
                    line-height:1.3;
                    margin-bottom:0.3rem;
                ">Concur History Explorer</div>
                <div style="font-size:0.8rem;color:{theme.MEDIUM_GRAY};">
                    Finance &amp; Expense Team — Authorized Access Only
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("login_form", clear_on_submit=True):
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter access password",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button(
                "Sign In", use_container_width=True, type="primary"
            )

        if submitted:
            stored = _stored_password()
            if password == stored:
                st.session_state["authenticated"] = True
                st.session_state["_auth_token"] = stored
                from app.utils.logger import get_logger
                get_logger("concur.auth").info("Successful login")
                st.rerun()
            else:
                from app.utils.logger import get_logger
                get_logger("concur.auth").warning("Failed login attempt")
                st.error("Incorrect password. Contact your Finance IT administrator.")

        st.markdown(
            f'<div style="text-align:center;font-size:0.72rem;color:{theme.MEDIUM_GRAY};'
            f'margin-top:1.5rem;">Read-only historical data — no write operations</div>',
            unsafe_allow_html=True,
        )
