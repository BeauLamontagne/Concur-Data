"""General Search — search expense history by keyword and filters."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st

from app import theme
from app.db.connection import db_exists, get_connection
from app.db.constants import Rpe, Rpt, Emp
from app.db.queries import (
    ExpenseFilters,
    export_to_dataframe,
    get_filter_options,
    get_report_detail,
    search_expenses,
)
from app.utils.formatters import fmt_currency, fmt_date_short, fmt_approval_status, truncate

PAGE_SIZE = 25

# Session state keys — widget values (persist across reruns)
_W_KEYWORD    = "gs_keyword"
_W_DATE_START = "gs_date_start"
_W_DATE_END   = "gs_date_end"
_W_COST_CTR   = "gs_cost_center"
_W_EMPLOYEE   = "gs_employee"
_W_STATUS     = "gs_status"

# Session state keys — search results / navigation
_SS_SUBMITTED = "gs_submitted"
_SS_PARAMS    = "gs_params"     # filter values locked in at search time
_SS_PAGE      = "gs_page"
_SS_RPT_KEY   = "gs_rpt_key"
_SS_RPE_KEY   = "gs_rpe_key"
_SS_DETAIL    = "gs_show_detail"


def _init_state(min_d: date, max_d: date) -> None:
    defaults: dict = {
        _W_KEYWORD:    "",
        _W_DATE_START: min_d,
        _W_DATE_END:   max_d,
        _W_COST_CTR:   "(All)",
        _W_EMPLOYEE:   "",
        _W_STATUS:     "(All)",
        _SS_SUBMITTED: False,
        _SS_PARAMS:    None,
        _SS_PAGE:      0,
        _SS_RPT_KEY:   None,
        _SS_RPE_KEY:   None,
        _SS_DETAIL:    False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _date_bounds(opts: dict) -> tuple[date, date]:
    try:
        min_d = datetime.strptime(opts["date_min"][:10], "%Y-%m-%d").date()
    except Exception:
        min_d = date(2018, 1, 1)
    try:
        max_d = datetime.strptime(opts["date_max"][:10], "%Y-%m-%d").date()
    except Exception:
        max_d = date.today()
    return min_d, max_d


def _render_filters(opts: dict, min_d: date, max_d: date) -> tuple[bool, bool]:
    """Render all filter inputs. Returns (search_clicked, clear_clicked)."""
    c1, c2, c3 = st.columns(3)

    with c1:
        st.text_input(
            "Keyword (employee, vendor, description, report name)",
            key=_W_KEYWORD,
            placeholder="Type to search…",
        )
        st.text_input(
            "Employee Name",
            key=_W_EMPLOYEE,
            placeholder="Last or first name…",
        )

    with c2:
        st.date_input("Date From", min_value=min_d, max_value=max_d, key=_W_DATE_START)
        st.date_input("Date To",   min_value=min_d, max_value=max_d, key=_W_DATE_END)

    with c3:
        cost_centers = ["(All)"] + opts.get("cost_centers", [])
        st.selectbox("Cost Center", cost_centers, key=_W_COST_CTR)

        statuses = opts.get("approval_statuses", [])
        status_labels = ["(All)"] + [fmt_approval_status(s) for s in statuses]
        st.selectbox("Approval Status", status_labels, key=_W_STATUS)

    btn_c1, btn_c2, _ = st.columns([1, 1, 6])
    with btn_c1:
        search_clicked = st.button("🔍 Search", type="primary", use_container_width=True)
    with btn_c2:
        clear_clicked = st.button("Clear", use_container_width=True)

    return search_clicked, clear_clicked


def _build_filters(params: dict, all_statuses: list[str]) -> tuple[str, ExpenseFilters]:
    """Convert locked params to (search_term, ExpenseFilters)."""
    keyword = params.get("keyword", "")
    filters: ExpenseFilters = {}

    if params.get("date_start"):
        filters["date_start"] = str(params["date_start"])
    if params.get("date_end"):
        filters["date_end"] = str(params["date_end"])

    cc = params.get("cost_center", "(All)")
    if cc and cc != "(All)":
        filters["cost_center"] = cc

    emp = params.get("employee", "")
    if emp:
        filters["employee_name"] = emp

    status_label = params.get("status", "(All)")
    if status_label and status_label != "(All)":
        label_to_code = {fmt_approval_status(s): s for s in all_statuses}
        code = label_to_code.get(status_label)
        if code:
            filters["approval_status"] = code

    return keyword, filters


def _render_results(df: pd.DataFrame, total: int) -> None:
    page = st.session_state[_SS_PAGE]
    start = page * PAGE_SIZE + 1
    end = min(start + len(df) - 1, total)

    pg_c1, pg_c2 = st.columns([3, 1])
    with pg_c1:
        st.markdown(
            f'<span style="color:{theme.MEDIUM_GRAY};font-size:0.85rem;">'
            f'Showing <b>{start:,}–{end:,}</b> of <b>{total:,}</b> results</span>',
            unsafe_allow_html=True,
        )
    with pg_c2:
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        if total_pages > 1:
            new_page = st.number_input(
                "Page", min_value=1, max_value=total_pages,
                value=page + 1, step=1, label_visibility="collapsed",
            ) - 1
            if new_page != page:
                st.session_state[_SS_PAGE] = new_page
                st.rerun()

    display = df.copy()
    display["Employee"]    = display["last_name"].fillna("") + ", " + display["first_name"].fillna("")
    display["Amount"]      = display["posted_amount"].apply(fmt_currency)
    display["Submit Date"] = display["submit_date"].apply(fmt_date_short)
    display["Tx Date"]     = display["transaction_date"].apply(fmt_date_short)
    display["Status"]      = display["approval_status"].apply(fmt_approval_status)
    display["Category"]    = display["icw_category"].fillna(display["exp_key"]).fillna("—")
    display["Vendor"]      = display["vendor_description"].apply(lambda x: truncate(x, 40))
    display["Report Name"] = display["report_name"].apply(lambda x: truncate(x, 45))

    show_cols = {
        "Employee":    "Employee",
        "rpt_id":      "Report ID",
        "Report Name": "Report Name",
        "Submit Date": "Submit Date",
        "Tx Date":     "Tx Date",
        "Category":    "Category",
        "Vendor":      "Vendor",
        "Amount":      "Amount",
        "cost_center": "Cost Center",
        "Status":      "Status",
    }
    table_df = display[list(show_cols.keys())].rename(columns=show_cols)
    st.dataframe(
        table_df,
        use_container_width=True,
        hide_index=True,
        height=min(600, max(200, (len(df) + 1) * 35 + 38)),
    )

    if not df.empty:
        options = ["— select a report to view detail —"] + list(
            df.apply(
                lambda r: f"{r['rpt_id']}  |  {truncate(r['report_name'], 50)}  |  {r['last_name']}, {r['first_name']}",
                axis=1,
            )
        )
        sel = st.selectbox("Open detail view:", options, key="gs_row_selector")
        if sel != options[0]:
            idx = options.index(sel) - 1
            rpt_key = df.iloc[idx]["rpt_key"]
            rpe_key = df.iloc[idx]["rpe_key"]
            if rpt_key != st.session_state.get(_SS_RPT_KEY):
                st.session_state[_SS_RPT_KEY] = rpt_key
                st.session_state[_SS_RPE_KEY] = rpe_key
                st.session_state[_SS_DETAIL]  = True
                st.rerun()


def _render_detail(conn, rpt_key: str, highlight_rpe: str | None) -> None:
    detail = get_report_detail(conn, rpt_key)
    if not detail:
        st.error("Report not found.")
        return

    rpt     = detail["report"]
    emp     = detail["employee"]
    entries = detail["entries"]

    close_col, _ = st.columns([1, 7])
    with close_col:
        if st.button("✕ Close Detail", key="gs_close_detail"):
            st.session_state[_SS_DETAIL]  = False
            st.session_state[_SS_RPT_KEY] = None
            st.rerun()

    with st.expander("📄 Report Summary", expanded=True):
        c1, c2, c3 = st.columns(3)
        fields = [
            ("Report ID",      rpt.get(Rpt.RPT_ID, "—")),
            ("Report Name",    rpt.get(Rpt.NAME, "—")),
            ("Employee",       f"{emp.get('first_name','')} {emp.get('last_name','')}".strip() or "—"),
            ("Email",          emp.get("email", "—")),
            ("Department",     emp.get("org_unit_1", "—")),
            ("Cost Center",    rpt.get(Rpt.COST_CENTER, "—")),
            ("Submit Date",    fmt_date_short(rpt.get(Rpt.SUBMIT_DATE))),
            ("Total Approved", fmt_currency(rpt.get(Rpt.TOTAL_APPROVED))),
            ("Status",         fmt_approval_status(rpt.get(Rpt.STATUS_CODE))),
        ]
        for i, (label, value) in enumerate(fields):
            with [c1, c2, c3][i % 3]:
                st.markdown(
                    f'<div style="margin-bottom:0.75rem;">'
                    f'<div class="wd-section-label">{label}</div>'
                    f'<div style="font-size:0.9rem;color:{theme.DARK_GRAY};font-weight:500;">{value}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    with st.expander("📋 Expense Line Items", expanded=True):
        if not entries:
            st.info("No line items found.")
        else:
            rows = [
                {
                    "Tx Date":    fmt_date_short(e.get(Rpe.TX_DATE)),
                    "Category":   e.get("icw_category") or e.get(Rpe.EXP_KEY) or "—",
                    "Description": truncate(e.get(Rpe.DESCRIPTION), 50),
                    "Vendor":     truncate(e.get(Rpe.VENDOR_DESC), 40),
                    "Amount":     fmt_currency(e.get(Rpe.POSTED_AMOUNT)),
                }
                for e in entries
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render() -> None:
    theme.apply_workday_theme()
    theme.styled_header(
        "General Search",
        subtitle="Set filters and click Search to query expense history.",
    )

    if not db_exists():
        st.info("No database found. Run the ingest command first.")
        st.code("python -m app.db.ingest --data-dir ./data", language="bash")
        return

    conn = get_connection()
    opts = get_filter_options(conn)
    min_d, max_d = _date_bounds(opts)
    _init_state(min_d, max_d)

    all_statuses = opts.get("approval_statuses", [])

    search_clicked, clear_clicked = _render_filters(opts, min_d, max_d)

    if clear_clicked:
        for k, v in {
            _W_KEYWORD: "", _W_DATE_START: min_d, _W_DATE_END: max_d,
            _W_COST_CTR: "(All)", _W_EMPLOYEE: "", _W_STATUS: "(All)",
            _SS_SUBMITTED: False, _SS_PARAMS: None, _SS_PAGE: 0,
            _SS_RPT_KEY: None, _SS_RPE_KEY: None, _SS_DETAIL: False,
        }.items():
            st.session_state[k] = v
        st.rerun()

    if search_clicked:
        st.session_state[_SS_PARAMS] = {
            "keyword":    st.session_state.get(_W_KEYWORD, ""),
            "date_start": st.session_state.get(_W_DATE_START),
            "date_end":   st.session_state.get(_W_DATE_END),
            "cost_center": st.session_state.get(_W_COST_CTR, "(All)"),
            "employee":   st.session_state.get(_W_EMPLOYEE, ""),
            "status":     st.session_state.get(_W_STATUS, "(All)"),
        }
        st.session_state[_SS_SUBMITTED] = True
        st.session_state[_SS_PAGE]      = 0
        st.session_state[_SS_RPT_KEY]   = None
        st.session_state[_SS_DETAIL]    = False

    if not st.session_state[_SS_SUBMITTED]:
        st.markdown(
            f'<div style="text-align:center;padding:3rem;color:{theme.MEDIUM_GRAY};">'
            f'Set filters above and click <b>Search</b> to load results.</div>',
            unsafe_allow_html=True,
        )
        conn.close()
        return

    st.divider()

    params  = st.session_state[_SS_PARAMS]
    keyword, filters = _build_filters(params, all_statuses)
    page    = st.session_state[_SS_PAGE]

    with st.spinner("Searching…"):
        df, total = search_expenses(
            conn,
            search_term=keyword,
            filters=filters or None,
            offset=page * PAGE_SIZE,
            limit=PAGE_SIZE,
        )

    if total == 0:
        st.info("No results found. Try adjusting your filters.")
    else:
        _render_results(df, total)
        st.divider()
        exp_df = export_to_dataframe(conn, "search", filters or None)
        st.download_button(
            "📥 Export Results (CSV)",
            data=exp_df.to_csv(index=False).encode(),
            file_name=f"expense_search_{date.today()}.csv",
            mime="text/csv",
        )

    if st.session_state[_SS_DETAIL] and st.session_state[_SS_RPT_KEY]:
        st.divider()
        _render_detail(conn, st.session_state[_SS_RPT_KEY], st.session_state.get(_SS_RPE_KEY))

    conn.close()
