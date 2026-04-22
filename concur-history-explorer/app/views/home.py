"""Search Center — primary landing page for accounting admins."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st

from app import theme
from app.db.connection import db_exists, get_connection
from app.db.constants import TBL_ENTRY, TBL_REPORT
from app.db.queries import ExpenseFilters, get_filter_options, search_expenses
from app.utils.formatters import fmt_currency

# ── Session-state keys ────────────────────────────────────────────────────────
_SS_SEARCH  = "sc_search_term"
_SS_RESULTS = "sc_search_results"
_SS_TOTAL   = "sc_search_total"
_SS_RECENT  = "sc_recent_searches"

# Logo discovery — drop icw_logo.png (or .svg) in app/assets/ to display it
_ASSETS_DIR  = Path(__file__).parent.parent / "assets"
_LOGO_PATHS  = [
    _ASSETS_DIR / "icw_logo.png",
    _ASSETS_DIR / "icw_logo.svg",
    _ASSETS_DIR / "logo.png",
]

_ICW_EXPENSE_GROUPS = [
    "Business Travel",
    "Agent/Insured",
    "Marketing/Recruiting",
    "Employee Relations",
    "Learning & Development",
    "Company Car",
    "Other",
]

_EXAMPLE_SEARCHES = [
    ("Claims department 2024", "Claims department 2024"),
    ("Marriott hotel",          "Marriott hotel"),
    ("RPT-00012345",            "RPT-00012345"),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _init_state() -> None:
    defaults: dict = {
        _SS_SEARCH:  "",
        _SS_RESULTS: None,
        _SS_TOTAL:   0,
        _SS_RECENT:  [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _navigate(page_label: str) -> None:
    st.session_state["_nav_pending"] = page_label
    st.rerun()


def _run_search(conn, term: str) -> None:
    if not term.strip():
        return
    with st.spinner("Searching…"):
        df, total = search_expenses(conn, search_term=term, limit=10, offset=0)
    st.session_state[_SS_RESULTS] = df
    st.session_state[_SS_TOTAL]   = total
    st.session_state[_SS_SEARCH]  = term.strip()

    # Prepend to recent (max 8, deduplicated by term)
    recent = [r for r in st.session_state[_SS_RECENT] if r["term"] != term.strip()]
    recent.insert(0, {"term": term.strip(), "timestamp": datetime.now(), "count": total})
    st.session_state[_SS_RECENT] = recent[:8]


# ── Hero search ───────────────────────────────────────────────────────────────

def _render_hero(conn) -> None:
    # Inject hero-specific input overrides (larger, pill-shaped)
    st.markdown(
        f"""
        <style>
        .sc-hero .stTextInput > div > div > input {{
            font-size: 1.1rem !important;
            height: 3.2rem !important;
            border-radius: 28px !important;
            border: 2px solid #D1D5DB !important;
            padding: 0 1.5rem !important;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08) !important;
        }}
        .sc-hero .stTextInput > div > div > input:focus {{
            border-color: {theme.PRIMARY} !important;
            box-shadow: 0 0 0 3px rgba(8,117,225,0.15), 0 2px 10px rgba(0,0,0,0.08) !important;
        }}
        .sc-hero .stTextInput label {{ display:none !important; }}
        .sc-example-btn .stButton > button {{
            background: transparent !important;
            color: {theme.MEDIUM_GRAY} !important;
            border: none !important;
            box-shadow: none !important;
            font-size: 0.82rem !important;
            font-weight: 400 !important;
            padding: 2px 8px !important;
            border-radius: 4px !important;
            text-decoration: underline;
            text-underline-offset: 2px;
        }}
        .sc-example-btn .stButton > button:hover {{
            color: {theme.PRIMARY} !important;
            background: transparent !important;
            box-shadow: none !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Logo
    logo_shown = False
    for p in _LOGO_PATHS:
        if p.exists():
            _, logo_col, _ = st.columns([2, 1, 2])
            with logo_col:
                st.image(str(p), use_container_width=True)
            logo_shown = True
            break

    if not logo_shown:
        st.markdown(
            f"""
            <div style="text-align:center;margin-bottom:0.25rem;">
              <span style="
                background:{theme.PRIMARY};color:#fff;
                font-size:1.3rem;font-weight:800;letter-spacing:2px;
                padding:5px 16px;border-radius:6px;
              ">ICW GROUP</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Page headline
    st.markdown(
        f"""
        <div style="text-align:center;margin:0.5rem 0 1.5rem 0;">
          <h2 style="color:{theme.DARK_BLUE};font-weight:700;font-size:1.6rem;
                     margin:0 0 0.25rem 0;letter-spacing:-0.3px;">
            Concur History Explorer
          </h2>
          <p style="color:{theme.MEDIUM_GRAY};font-size:0.875rem;margin:0;">
            Search 7 years of ICW Group expense history &mdash; 2019 to 2026
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Search bar — centered in a narrow column
    _, center, _ = st.columns([1, 4, 1])
    with center:
        st.markdown('<div class="sc-hero">', unsafe_allow_html=True)
        with st.form("sc_search_form", clear_on_submit=False):
            s_col, b_col = st.columns([11, 1])
            with s_col:
                term = st.text_input(
                    "Search",
                    value=st.session_state[_SS_SEARCH],
                    placeholder="Search by employee name, vendor, report ID, cost center…",
                    key="sc_search_input",
                    label_visibility="collapsed",
                )
            with b_col:
                st.markdown("<div style='padding-top:4px;'>", unsafe_allow_html=True)
                submitted = st.form_submit_button("🔍", use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # Example search links
        st.markdown(
            f'<div style="text-align:center;margin-top:0.35rem;'
            f'color:{theme.MEDIUM_GRAY};font-size:0.82rem;">Try:</div>',
            unsafe_allow_html=True,
        )
        ex_cols = st.columns(3)
        for i, (label, ex_term) in enumerate(_EXAMPLE_SEARCHES):
            with ex_cols[i]:
                st.markdown('<div class="sc-example-btn">', unsafe_allow_html=True)
                if st.button(f'"{label}"', key=f"sc_ex_{i}", use_container_width=True):
                    _run_search(conn, ex_term)
                st.markdown("</div>", unsafe_allow_html=True)

    if submitted and term.strip():
        _run_search(conn, term)

    # Inline results
    results = st.session_state.get(_SS_RESULTS)
    if results is not None:
        total        = st.session_state.get(_SS_TOTAL, 0)
        active_term  = st.session_state.get(_SS_SEARCH, "")
        _, res_col, _ = st.columns([1, 4, 1])
        with res_col:
            if results.empty:
                st.info(f'No results found for "{active_term}".')
            else:
                st.markdown(
                    f'<div style="color:{theme.MEDIUM_GRAY};font-size:0.8rem;margin:0.75rem 0 0.4rem 0;">'
                    f'Showing top {min(10, len(results))} of <strong style="color:{theme.DARK_BLUE};">'
                    f'{total:,}</strong> results for '
                    f'<strong style="color:{theme.DARK_BLUE};">&ldquo;{active_term}&rdquo;</strong>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                _RESULT_COLS = [
                    "first_name", "last_name", "rpt_id", "vendor_description",
                    "transaction_date", "posted_amount", "cost_center", "icw_group",
                ]
                display = results[[c for c in _RESULT_COLS if c in results.columns]].copy()
                display.columns = [c.replace("_", " ").title() for c in display.columns]
                if "Posted Amount" in display.columns:
                    display["Posted Amount"] = display["Posted Amount"].apply(
                        lambda v: fmt_currency(v) if v else ""
                    )
                st.dataframe(display, use_container_width=True, hide_index=True)

                if total > 10:
                    if st.button(
                        f"View all {total:,} results in Expense Search →",
                        key="sc_view_all",
                    ):
                        st.session_state["as_search_term"] = active_term
                        _navigate("📋  Expense Search")


# ── Task cards ────────────────────────────────────────────────────────────────

def _render_task_cards(opts: dict) -> None:
    st.markdown(
        f'<div style="color:{theme.MEDIUM_GRAY};font-size:0.72rem;font-weight:600;'
        f'text-transform:uppercase;letter-spacing:1px;margin-bottom:0.75rem;">Quick Access</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1.15, 1, 1], gap="medium")

    # ── Card 1: Department Spend Lookup (primary action) ──────────────────────
    with c1:
        st.markdown(
            f"""
            <div style="
                background:{theme.LIGHT_BLUE};
                border-left:4px solid {theme.PRIMARY};
                border-radius:8px;
                padding:16px 18px 10px 18px;
                box-shadow:0 1px 4px rgba(8,117,225,0.12);
                margin-bottom:0.5rem;
            ">
              <div style="font-size:1rem;font-weight:700;color:{theme.DARK_BLUE};margin-bottom:2px;">
                📊 Department Spend Lookup
              </div>
              <div style="font-size:0.8rem;font-weight:600;color:{theme.PRIMARY};margin-bottom:4px;">
                Pull historical spend by cost center, department, or category
              </div>
              <div style="font-size:0.76rem;color:{theme.MEDIUM_GRAY};">
                Answer budget planning requests from cost center managers
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        cost_centers = opts.get("cost_centers", [])
        fiscal_years = [str(y) for y in range(2026, 2018, -1)]

        cc = st.selectbox(
            "Cost center",
            ["— select cost center —"] + cost_centers,
            key="sc_c1_cc",
            label_visibility="collapsed",
        )
        yr = st.selectbox(
            "Fiscal year",
            ["— select fiscal year —"] + fiscal_years,
            key="sc_c1_yr",
            label_visibility="collapsed",
        )
        if st.button("Go →", key="sc_c1_go", type="primary", use_container_width=True):
            if cc != "— select cost center —":
                st.session_state["sr_cost_center"] = cc
            if yr != "— select fiscal year —":
                st.session_state["sr_year"] = yr
            _navigate("📊  Department Spend")

    # ── Card 2: Year-over-Year Comparison ─────────────────────────────────────
    with c2:
        st.markdown(
            f"""
            <div style="
                background:#fff;
                border-left:4px solid {theme.MEDIUM_BLUE};
                border-radius:8px;
                padding:16px 18px 10px 18px;
                box-shadow:0 1px 3px rgba(0,0,0,0.08);
                margin-bottom:0.5rem;
            ">
              <div style="font-size:1rem;font-weight:700;color:{theme.DARK_BLUE};margin-bottom:2px;">
                📈 Year-over-Year Comparison
              </div>
              <div style="font-size:0.8rem;font-weight:600;color:{theme.MEDIUM_BLUE};margin-bottom:4px;">
                Compare actual spend across fiscal years
              </div>
              <div style="font-size:0.76rem;color:{theme.MEDIUM_GRAY};">
                Support budget assumptions with historical evidence
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        fiscal_years = [str(y) for y in range(2026, 2018, -1)]
        ya_col, yb_col = st.columns(2)
        with ya_col:
            yr_a = st.selectbox(
                "Year A", fiscal_years,
                index=fiscal_years.index("2024") if "2024" in fiscal_years else 0,
                key="sc_c2_yra", label_visibility="collapsed",
            )
        with yb_col:
            yr_b = st.selectbox(
                "Year B", fiscal_years,
                index=fiscal_years.index("2025") if "2025" in fiscal_years else 1,
                key="sc_c2_yrb", label_visibility="collapsed",
            )
        if st.button("Compare →", key="sc_c2_go", use_container_width=True):
            st.session_state["ta_years"] = sorted({yr_a, yr_b})
            _navigate("📈  Year-over-Year Comparison")

    # ── Card 3: Audit Lookup ───────────────────────────────────────────────────
    with c3:
        st.markdown(
            f"""
            <div style="
                background:#fff;
                border-left:4px solid {theme.ACCENT_TEAL};
                border-radius:8px;
                padding:16px 18px 10px 18px;
                box-shadow:0 1px 3px rgba(0,0,0,0.08);
                margin-bottom:0.5rem;
            ">
              <div style="font-size:1rem;font-weight:700;color:{theme.DARK_BLUE};margin-bottom:2px;">
                🔍 Audit Lookup
              </div>
              <div style="font-size:0.8rem;font-weight:600;color:{theme.ACCENT_TEAL};margin-bottom:4px;">
                Find expense documentation and receipt images
              </div>
              <div style="font-size:0.76rem;color:{theme.MEDIUM_GRAY};">
                Retrieve evidence for internal or external audit sampling
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
        audit_term = st.text_input(
            "Report ID or Employee Name",
            placeholder="e.g. RPT-00012345 or Jane Smith",
            key="sc_c3_term",
            label_visibility="collapsed",
        )
        st.markdown("<div style='height:0.25rem;'></div>", unsafe_allow_html=True)
        if st.button("Search →", key="sc_c3_go", use_container_width=True):
            if audit_term.strip():
                st.session_state["as_search_term"] = audit_term.strip()
            _navigate("📋  Expense Search")


# ── Bottom section ────────────────────────────────────────────────────────────

def _render_bottom(conn) -> None:
    left_col, right_col = st.columns([3, 2], gap="large")

    # ── Recent Searches ────────────────────────────────────────────────────────
    with left_col:
        st.markdown(
            f'<div class="wd-card-header">Recent Searches</div>',
            unsafe_allow_html=True,
        )
        recent: list = st.session_state.get(_SS_RECENT, [])
        if not recent:
            st.markdown(
                f'<div style="color:{theme.MEDIUM_GRAY};font-size:0.85rem;'
                f'padding:0.5rem 0;">Your recent searches will appear here.</div>',
                unsafe_allow_html=True,
            )
        else:
            for i, r in enumerate(recent):
                ts = r.get("timestamp")
                ts_str = ts.strftime("%d %b, %I:%M %p") if isinstance(ts, datetime) else ""
                btn_c, meta_c = st.columns([3, 2])
                with btn_c:
                    if st.button(
                        f'🔍  {r["term"]}',
                        key=f"sc_rec_{i}",
                        use_container_width=True,
                    ):
                        _run_search(conn, r["term"])
                with meta_c:
                    st.markdown(
                        f'<div style="color:{theme.MEDIUM_GRAY};font-size:0.75rem;'
                        f'padding-top:9px;">{ts_str}'
                        + (f' &nbsp;·&nbsp; {r["count"]:,} results' if r.get("count") is not None else "")
                        + "</div>",
                        unsafe_allow_html=True,
                    )

    # ── Quick Filters ──────────────────────────────────────────────────────────
    with right_col:
        st.markdown(
            f'<div class="wd-card-header">Quick Filters</div>',
            unsafe_allow_html=True,
        )

        # Fiscal year buttons
        st.markdown(
            f'<div style="color:{theme.DARK_GRAY};font-size:0.75rem;font-weight:600;'
            f'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">'
            f'By Fiscal Year</div>',
            unsafe_allow_html=True,
        )
        yr_cols = st.columns(4)
        for i, yr in enumerate(range(2019, 2027)):
            with yr_cols[i % 4]:
                if st.button(str(yr), key=f"sc_qyr_{yr}", use_container_width=True):
                    st.session_state["sr_year"] = str(yr)
                    _navigate("📊  Department Spend")

        st.markdown("<div style='height:0.75rem;'></div>", unsafe_allow_html=True)

        # ICW Expense Group pills
        st.markdown(
            f'<div style="color:{theme.DARK_GRAY};font-size:0.75rem;font-weight:600;'
            f'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">'
            f'By ICW Expense Group</div>',
            unsafe_allow_html=True,
        )
        # Inject style to de-emphasize non-primary group buttons
        st.markdown(
            f"""
            <style>
            .sc-grp-secondary .stButton > button {{
                background: {theme.LIGHT_GRAY} !important;
                color: {theme.DARK_GRAY} !important;
                border: 1px solid #D1D5DB !important;
                box-shadow: none !important;
                font-weight: 500 !important;
            }}
            .sc-grp-secondary .stButton > button:hover {{
                background: {theme.LIGHT_BLUE} !important;
                color: {theme.PRIMARY} !important;
                border-color: {theme.PRIMARY} !important;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
        for i, grp in enumerate(_ICW_EXPENSE_GROUPS):
            is_hero = grp == "Business Travel"
            if not is_hero:
                st.markdown('<div class="sc-grp-secondary">', unsafe_allow_html=True)
            if st.button(
                grp,
                key=f"sc_qgrp_{i}",
                type="primary" if is_hero else "secondary",
                use_container_width=True,
            ):
                st.session_state["as_filters"] = {"expense_group": grp}
                st.session_state["as_search_term"] = ""
                _navigate("📋  Expense Search")
            if not is_hero:
                st.markdown("</div>", unsafe_allow_html=True)


# ── Main render ───────────────────────────────────────────────────────────────

def render() -> None:
    theme.apply_workday_theme()
    _init_state()

    if not db_exists():
        st.info("No expense data loaded yet.")
        st.code("python -m app.utils.sample_data --num-reports 50000", language="bash")
        return

    conn = get_connection()
    opts = get_filter_options(conn)

    _render_hero(conn)

    st.divider()
    _render_task_cards(opts)

    st.divider()
    _render_bottom(conn)

    # Footer bar
    try:
        n_reports = conn.execute(f"SELECT COUNT(*) FROM {TBL_REPORT}").fetchone()[0]
        n_entries = conn.execute(f"SELECT COUNT(*) FROM {TBL_ENTRY}").fetchone()[0]
    except Exception:
        n_reports = n_entries = 0
    conn.close()

    st.markdown(
        f'<div style="text-align:center;color:{theme.MEDIUM_GRAY};font-size:0.72rem;'
        f'margin-top:1.5rem;padding-top:0.75rem;border-top:1px solid {theme.LIGHT_GRAY};">'
        f'Concur Historical Archive: 2019&ndash;2026 &nbsp;&middot;&nbsp; '
        f'{n_reports:,} reports &nbsp;&middot;&nbsp; {n_entries:,} line items'
        f'</div>',
        unsafe_allow_html=True,
    )
