"""Password gate with per-user credentials."""

from __future__ import annotations

import streamlit as st

from app import theme

USERS = ["Wendy", "Kim"]

_PASSWORDS = {
    "wendy": "wendy-1234",
    "kim":   "kim-1234",
}


def _get_password(username: str) -> str:
    return _PASSWORDS.get(username.lower(), "")


def is_authenticated() -> bool:
    username = st.session_state.get("username", "")
    token    = st.session_state.get("_auth_token", "")
    return bool(username and token and token == _get_password(username))


def render_login() -> None:
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
            username = st.selectbox("User", USERS)
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button(
                "Sign In", use_container_width=True, type="primary"
            )

        if submitted:
            if password == _get_password(username):
                st.session_state["username"]    = username
                st.session_state["_auth_token"] = password
                from app.utils.logger import get_logger
                get_logger("concur.auth").info("Login: %s", username)
                st.rerun()
            else:
                from app.utils.logger import get_logger
                get_logger("concur.auth").warning("Failed login attempt for: %s", username)
                st.error("Incorrect password. Contact your Finance IT administrator.")

        st.markdown(
            f'<div style="text-align:center;font-size:0.72rem;color:{theme.MEDIUM_GRAY};'
            f'margin-top:1.5rem;">Read-only historical data — no write operations</div>',
            unsafe_allow_html=True,
        )
