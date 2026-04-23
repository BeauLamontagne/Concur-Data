"""Search Center — main landing page with search bar and nav shortcuts."""

from __future__ import annotations

import streamlit as st

from app import theme


def render() -> None:
    theme.apply_workday_theme()
    theme.styled_header(
        "Search Center",
        subtitle="Search expense data or navigate to a report.",
    )

    # ── General search bar ────────────────────────────────────────────────────
    search_col, btn_col = st.columns([7, 1])
    with search_col:
        search_term = st.text_input(
            "search",
            placeholder="Search by employee, vendor, report name, or keyword…",
            label_visibility="collapsed",
            key="home_search",
        )
    with btn_col:
        do_search = st.button("🔍  Search", type="primary", use_container_width=True)

    if do_search and search_term.strip():
        st.session_state["_nav_search_term"] = search_term.strip()
        st.session_state["nav_page"] = "📋  Expense Search"
        st.rerun()

    st.divider()

    # ── Navigation cards ──────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)

    nav_items = [
        ("📊", "Department Spend",  "Analyze spend by cost center and department.",      "📊  Spend Review"),
        ("📈", "Year-over-Year",    "Compare historical spend across fiscal years.",       "📈  Trends & Forecasting"),
        ("🔍", "Expense Search",    "Search individual expense records and reports.",      "📋  Expense Search"),
    ]

    for col, (icon, label, desc, target) in zip([c1, c2, c3], nav_items):
        with col:
            st.markdown(
                f"""
                <div style="
                    background:{theme.LIGHT_GRAY};
                    border-left:4px solid {theme.PRIMARY};
                    border-radius:6px;
                    padding:24px 16px 14px 16px;
                    margin-bottom:8px;
                    text-align:center;
                ">
                    <div style="font-size:2.4rem;margin-bottom:10px;">{icon}</div>
                    <div style="font-size:1rem;font-weight:700;color:{theme.DARK_BLUE};
                        margin-bottom:5px;">{label}</div>
                    <div style="font-size:0.8rem;color:{theme.MEDIUM_GRAY};">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Open →", use_container_width=True, key=f"nav_{label}"):
                st.session_state["nav_page"] = target
                st.rerun()
