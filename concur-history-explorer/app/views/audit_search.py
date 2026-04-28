"""
Audit & Compliance — Expense Search & Audit Lookup
Stories A1 (search), A2 (export), A3 (lineage / detail drill-down).
"""

from __future__ import annotations

import io
from datetime import date, datetime, timedelta

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
from app.utils.expense_categories import CATEGORIES_BY_GROUP
from app.utils.formatters import fmt_currency, fmt_date_short, fmt_approval_status, truncate
from app.utils.image_handler import find_receipt_image, get_image_bytes, image_mime_type

# ── Session state keys ────────────────────────────────────────────────────────
_SS_SEARCH      = "as_search_term"
_SS_FILTERS     = "as_filters"
_SS_PAGE        = "as_page"
_SS_SELECTED    = "as_selected_rpt_key"
_SS_SELECTED_RPE = "as_selected_rpe_key"
_SS_SHOW_DETAIL = "as_show_detail"

PAGE_SIZE = 25


def _init_state() -> None:
    defaults = {
        _SS_SEARCH:       "",
        _SS_FILTERS:      {},
        _SS_PAGE:         0,
        _SS_SELECTED:     None,
        _SS_SELECTED_RPE: None,
        _SS_SHOW_DETAIL:  False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ── Filter panel ──────────────────────────────────────────────────────────────

def _render_filter_panel(opts: dict) -> ExpenseFilters:
    current: dict = st.session_state[_SS_FILTERS]

    st.markdown('<div class="wd-filter-panel">', unsafe_allow_html=True)
    st.markdown('<div class="wd-section-label">Filters</div>', unsafe_allow_html=True)

    with st.container():
        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown('<div class="wd-section-label">Date Range</div>', unsafe_allow_html=True)
            date_min = opts.get("date_min")
            date_max = opts.get("date_max")
            try:
                min_d = datetime.strptime(date_min[:10], "%Y-%m-%d").date() if date_min else date(2018, 1, 1)
                max_d = datetime.strptime(date_max[:10], "%Y-%m-%d").date() if date_max else date.today()
            except Exception:
                min_d, max_d = date(2018, 1, 1), date.today()

            date_start = st.date_input(
                "From", value=current.get("date_start") or min_d,
                min_value=min_d, max_value=max_d, key="flt_date_start",
            )
            date_end = st.date_input(
                "To", value=current.get("date_end") or max_d,
                min_value=min_d, max_value=max_d, key="flt_date_end",
            )

        with c2:
            st.markdown('<div class="wd-section-label">Organization</div>', unsafe_allow_html=True)
            cost_centers = opts.get("cost_centers", [])
            sel_cc = st.multiselect(
                "Cost Center", cost_centers,
                default=[v for v in current.get("cost_center_list", []) if v in cost_centers],
                key="flt_cost_center",
            )

            departments = opts.get("org_units", {}).get("org_unit_1", [])
            sel_dept = st.multiselect(
                "Department (ORG_UNIT_1)", departments,
                default=[v for v in current.get("org_unit_1_list", []) if v in departments],
                key="flt_dept",
            )

        with c3:
            st.markdown('<div class="wd-section-label">Expense Type</div>', unsafe_allow_html=True)
            groups = opts.get("expense_groups", [])
            sel_group = st.selectbox(
                "ICW Expense Group", ["(All)"] + groups,
                index=0, key="flt_group",
            )

            cats_for_group = (
                CATEGORIES_BY_GROUP.get(sel_group, [])
                if sel_group != "(All)" else opts.get("expense_categories", [])
            )
            sel_cat = st.selectbox(
                "ICW Expense Category", ["(All)"] + cats_for_group,
                index=0, key="flt_cat",
            )

        c4, c5, c6 = st.columns(3)

        with c4:
            st.markdown('<div class="wd-section-label">Amount Range (Posted)</div>', unsafe_allow_html=True)
            amt_min = st.number_input(
                "Min $", min_value=0.0, value=float(current.get("amount_min") or 0),
                step=10.0, format="%.2f", key="flt_amt_min",
            )
            amt_max = st.number_input(
                "Max $", min_value=0.0, value=float(current.get("amount_max") or 0),
                step=10.0, format="%.2f", key="flt_amt_max",
            )

        with c5:
            st.markdown('<div class="wd-section-label">Employee</div>', unsafe_allow_html=True)
            emp_name = st.text_input(
                "Employee Name", value=current.get("employee_name", ""),
                placeholder="Last or first name…", key="flt_emp",
            )

        with c6:
            st.markdown('<div class="wd-section-label">Status</div>', unsafe_allow_html=True)
            statuses = opts.get("approval_statuses", [])
            status_labels = {s: fmt_approval_status(s) for s in statuses}
            sel_status = st.selectbox(
                "Approval Status",
                ["(All)"] + [status_labels.get(s, s) for s in statuses],
                index=0, key="flt_status",
            )
            # map display label back to code
            sel_status_code = None
            if sel_status != "(All)":
                inv = {v: k for k, v in status_labels.items()}
                sel_status_code = inv.get(sel_status)

        btn_col1, btn_col2, _ = st.columns([1, 1, 6])
        with btn_col1:
            apply = st.button("Apply Filters", type="primary", key="btn_apply")
        with btn_col2:
            clear = st.button("Clear All", key="btn_clear")

    st.markdown('</div>', unsafe_allow_html=True)

    # Build filters dict from widget state
    filters: ExpenseFilters = {}
    if date_start:
        filters["date_start"] = str(date_start)
    if date_end:
        filters["date_end"] = str(date_end)
    if sel_cc:
        filters["cost_center"] = sel_cc[0] if len(sel_cc) == 1 else None
        filters["cost_center_list"] = sel_cc
    if sel_dept:
        filters["org_unit_1"] = sel_dept[0] if len(sel_dept) == 1 else None
        filters["org_unit_1_list"] = sel_dept
    if sel_group != "(All)":
        filters["expense_group"] = sel_group
    if sel_cat != "(All)":
        filters["expense_category"] = sel_cat
    if amt_min and amt_min > 0:
        filters["amount_min"] = amt_min
    if amt_max and amt_max > 0:
        filters["amount_max"] = amt_max
    if emp_name:
        filters["employee_name"] = emp_name
    if sel_status_code:
        filters["approval_status"] = sel_status_code

    if apply:
        st.session_state[_SS_FILTERS] = filters
        st.session_state[_SS_PAGE] = 0
        st.session_state[_SS_SELECTED] = None
    if clear:
        st.session_state[_SS_FILTERS] = {}
        st.session_state[_SS_PAGE] = 0
        st.session_state[_SS_SELECTED] = None
        st.rerun()

    return st.session_state[_SS_FILTERS]


def _active_filter_count(filters: dict) -> int:
    skip = {"cost_center_list", "org_unit_1_list"}
    return sum(1 for k, v in filters.items() if v and k not in skip)


# ── Results table ─────────────────────────────────────────────────────────────

def _render_results(df: pd.DataFrame, total: int) -> None:
    page = st.session_state[_SS_PAGE]
    start = page * PAGE_SIZE + 1
    end = min(start + len(df) - 1, total)

    if total > 10_000:
        st.warning(
            f"⚠️  {total:,} results found. Consider narrowing your filters for faster export.",
            icon="⚠️",
        )

    # Pagination header
    pg_col1, pg_col2 = st.columns([3, 1])
    with pg_col1:
        st.markdown(
            f'<span style="color:{theme.MEDIUM_GRAY};font-size:0.85rem;">'
            f'Showing <b>{start:,}–{end:,}</b> of <b>{total:,}</b> results</span>',
            unsafe_allow_html=True,
        )
    with pg_col2:
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        if total_pages > 1:
            new_page = st.number_input(
                "Page", min_value=1, max_value=total_pages,
                value=page + 1, step=1, label_visibility="collapsed",
            ) - 1
            if new_page != page:
                st.session_state[_SS_PAGE] = new_page
                st.rerun()

    # Format display columns
    display = df.copy()
    display["Employee"] = display["last_name"].fillna("") + ", " + display["first_name"].fillna("")
    display["Amount"] = display["posted_amount"].apply(fmt_currency)
    display["Submit Date"] = display["submit_date"].apply(fmt_date_short)
    display["Tx Date"] = display["transaction_date"].apply(fmt_date_short)
    display["Status"] = display["approval_status"].apply(fmt_approval_status)
    display["Category"] = display["icw_category"].fillna(display["exp_key"]).fillna("—")
    display["Vendor"] = display["vendor_description"].apply(lambda x: truncate(x, 40))
    display["Report Name"] = display["report_name"].apply(lambda x: truncate(x, 45))

    show_cols = {
        "Employee":    "Employee",
        "rpt_id":      "Report ID",
        "Report Name": "Report Name",
        "Submit Date": "Submit Date",
        "Tx Date":     "Tx Date",
        "Category":    "ICW Category",
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

    # Row selector for drill-down
    if not df.empty:
        rpt_options = ["— select a report to view detail —"] + list(
            df.apply(lambda r: f"{r['rpt_id']}  |  {truncate(r['report_name'], 50)}  |  {r['last_name']}, {r['first_name']}", axis=1)
        )
        sel = st.selectbox("Open detail view for:", rpt_options, key="row_selector")
        if sel != rpt_options[0]:
            idx = rpt_options.index(sel) - 1
            rpt_key = df.iloc[idx]["rpt_key"]
            rpe_key = df.iloc[idx]["rpe_key"]
            if rpt_key != st.session_state.get(_SS_SELECTED):
                st.session_state[_SS_SELECTED]     = rpt_key
                st.session_state[_SS_SELECTED_RPE] = rpe_key
                st.session_state[_SS_SHOW_DETAIL]  = True
                st.rerun()


# ── Detail view ───────────────────────────────────────────────────────────────

def _render_detail(conn, rpt_key: str, highlight_rpe: str | None) -> None:
    detail = get_report_detail(conn, rpt_key)
    if not detail:
        st.error("Report not found.")
        return

    rpt = detail["report"]
    emp = detail["employee"]
    entries = detail["entries"]
    images  = detail["images"]

    close_col, _ = st.columns([1, 7])
    with close_col:
        if st.button("✕  Close Detail", key="close_detail"):
            st.session_state[_SS_SHOW_DETAIL] = False
            st.session_state[_SS_SELECTED]    = None
            st.rerun()

    # ── Audit trail breadcrumb ────────────────────────────────────────────────
    emp_key  = rpt.get(Rpt.EMP_KEY, "—")
    rpe_disp = highlight_rpe or "—"
    receipt  = next(
        (e.get(Rpe.RECEIPT_IMAGE_ID) or e.get(Rpe.ERECEIPT_IMAGE_ID)
         for e in entries if e.get(Rpe.KEY) == highlight_rpe),
        "—",
    )

    st.markdown(
        f"""
        <div class="wd-card" style="margin-bottom:0.75rem;">
          <div class="wd-card-header">Audit Trail / Lineage</div>
          <div style="display:flex;align-items:center;gap:0;flex-wrap:wrap;">
            {_crumb("Employee", emp_key, theme.DARK_BLUE, first=True)}
            {_arrow()}
            {_crumb("Report", rpt_key, theme.PRIMARY)}
            {_arrow()}
            {_crumb("Entry", rpe_disp, theme.MEDIUM_BLUE)}
            {_arrow()}
            {_crumb("Receipt", receipt if receipt != "—" else "No Image", theme.ACCENT_TEAL, last=True)}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Section 1: Report summary ─────────────────────────────────────────────
    with st.expander("📄  Report Summary", expanded=True):
        c1, c2, c3 = st.columns(3)
        fields = [
            ("Report ID",    rpt.get(Rpt.RPT_ID, "—")),
            ("Report Name",  rpt.get(Rpt.NAME, "—")),
            ("Employee",     f"{emp.get('first_name','')} {emp.get('last_name','')}".strip() or "—"),
            ("Email",        emp.get("email", "—")),
            ("Department",   emp.get("org_unit_1", "—")),
            ("Cost Center",  rpt.get(Rpt.COST_CENTER, "—")),
            ("Submit Date",  fmt_date_short(rpt.get(Rpt.SUBMIT_DATE))),
            ("Total Approved", fmt_currency(rpt.get(Rpt.TOTAL_APPROVED))),
            ("Status",       fmt_approval_status(rpt.get(Rpt.STATUS_CODE))),
        ]
        cols = [c1, c2, c3]
        for i, (label, value) in enumerate(fields):
            with cols[i % 3]:
                st.markdown(
                    f'<div style="margin-bottom:0.75rem;">'
                    f'<div class="wd-section-label">{label}</div>'
                    f'<div style="font-size:0.9rem;color:{theme.DARK_GRAY};font-weight:500;">{value}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ── Section 2: Line items ─────────────────────────────────────────────────
    with st.expander("📋  Expense Line Items", expanded=True):
        if not entries:
            st.info("No line items found for this report.")
        else:
            rows = []
            for e in entries:
                rows.append({
                    "Tx Date":    fmt_date_short(e.get(Rpe.TX_DATE)),
                    "ICW Category": e.get("icw_category") or e.get(Rpe.EXP_KEY) or "—",
                    "Description": truncate(e.get(Rpe.DESCRIPTION), 50),
                    "Vendor":     truncate(e.get(Rpe.VENDOR_DESC), 40),
                    "Amount":     fmt_currency(e.get(Rpe.POSTED_AMOUNT)),
                    "From":       truncate(e.get(Rpe.FROM_LOCATION), 25),
                    "To":         truncate(e.get(Rpe.TO_LOCATION), 25),
                    "_rpe_key":   e.get(Rpe.KEY, ""),
                })
            entry_df = pd.DataFrame(rows)
            display_df = entry_df.drop(columns=["_rpe_key"])

            def _highlight_row(row):
                match = entry_df.at[row.name, "_rpe_key"] == (highlight_rpe or "")
                return [f"background-color: {theme.LIGHT_BLUE}" if match else "" for _ in row]

            styled = display_df.style.apply(_highlight_row, axis=1)
            st.dataframe(styled, use_container_width=True, hide_index=True)

    # ── Section 3: Receipt images ─────────────────────────────────────────────
    with st.expander("🧾  Receipt Images", expanded=bool(images)):
        if not images:
            st.info("No receipt images available for this report.")
        else:
            img_cols = st.columns(min(len(images), 3))
            for i, img_ref in enumerate(images):
                path = img_ref.get("path")
                rpe_k = img_ref.get("rpe_key", "")
                with img_cols[i % 3]:
                    from pathlib import Path
                    p = Path(path)
                    mime = image_mime_type(p)
                    data = get_image_bytes(p)
                    if data and mime.startswith("image/"):
                        st.image(data, caption=f"Entry: {rpe_k}", use_container_width=True)
                        st.download_button(
                            "⬇ Download", data=data,
                            file_name=p.name, mime=mime,
                            key=f"dl_{rpe_k}_{i}",
                        )
                    elif data and mime == "application/pdf":
                        st.markdown(f"📄 PDF receipt: `{p.name}`")
                        st.download_button(
                            "⬇ Download PDF", data=data,
                            file_name=p.name, mime=mime,
                            key=f"dl_pdf_{rpe_k}_{i}",
                        )
                    else:
                        st.markdown(
                            f'<div style="padding:1rem;background:{theme.LIGHT_GRAY};'
                            f'border-radius:6px;text-align:center;color:{theme.MEDIUM_GRAY};">'
                            f'Receipt image not available</div>',
                            unsafe_allow_html=True,
                        )


def _crumb(label: str, value: str, color: str, first: bool = False, last: bool = False) -> str:
    border_r = "0" if not last else "6px"
    border_l = "6px" if first else "0"
    return (
        f'<div style="background:{color};color:#fff;padding:6px 14px;'
        f'border-radius:{border_l} {border_r} {border_r} {border_l};'
        f'font-size:0.78rem;">'
        f'<div style="opacity:0.75;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.5px;">{label}</div>'
        f'<div style="font-weight:600;">{truncate(str(value), 24)}</div>'
        f'</div>'
    )


def _arrow() -> str:
    return (
        f'<div style="width:24px;height:0;border-top:2px solid {theme.LIGHT_GRAY};'
        f'margin:auto 0;align-self:center;"></div>'
    )


# ── Export helpers ────────────────────────────────────────────────────────────

def _build_excel(conn, filters: dict, search_term: str) -> bytes:
    df = export_to_dataframe(conn, "search", filters)

    summary_data = {
        "Export Date": [datetime.now().strftime("%Y-%m-%d %H:%M")],
        "Search Term": [search_term or "(none)"],
        "Date From":   [filters.get("date_start", "(all)")],
        "Date To":     [filters.get("date_end", "(all)")],
        "Cost Center": [filters.get("cost_center") or filters.get("cost_center_list") or "(all)"],
        "Department":  [filters.get("org_unit_1") or filters.get("org_unit_1_list") or "(all)"],
        "ICW Group":   [filters.get("expense_group", "(all)")],
        "ICW Category":[filters.get("expense_category", "(all)")],
        "Status":      [fmt_approval_status(filters.get("approval_status"))],
        "Total Rows":  [len(df)],
    }

    receipt_df = df[["rpt_id", "receipt_image_id", "ereceipt_image_id"]].drop_duplicates() \
        if "receipt_image_id" in df.columns else pd.DataFrame()

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        pd.DataFrame(summary_data).T.reset_index().rename(
            columns={"index": "Field", 0: "Value"}
        ).to_excel(writer, sheet_name="Summary", index=False)
        df.to_excel(writer, sheet_name="Expense Detail", index=False)
        if not receipt_df.empty:
            receipt_df.to_excel(writer, sheet_name="Receipt References", index=False)
    return buf.getvalue()


# ── Empty state ───────────────────────────────────────────────────────────────

def _empty_state(message: str = "No expenses found") -> None:
    st.markdown(
        f"""
        <div style="text-align:center;padding:3rem 1rem;color:{theme.MEDIUM_GRAY};">
            <div style="font-size:2.5rem;margin-bottom:0.5rem;">🔍</div>
            <div style="font-size:1.1rem;font-weight:600;color:{theme.DARK_BLUE};">{message}</div>
            <div style="font-size:0.85rem;margin-top:0.4rem;">
                Try a different search term or adjust your filters.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Main render ───────────────────────────────────────────────────────────────

def render() -> None:
    theme.apply_workday_theme()
    _init_state()

    theme.styled_header(
        "📋 Expense Search & Audit Lookup",
        subtitle="Search historical expense data by employee, vendor, report, or keyword.",
    )

    if not db_exists():
        st.info("No database found. Run the ingest command first.")
        st.code("python -m app.db.ingest --data-dir ./data", language="bash")
        return

    conn = get_connection()

    # Load filter options once
    with st.spinner("Loading filter options…"):
        opts = get_filter_options(conn)

    # ── Search bar ────────────────────────────────────────────────────────────
    search_col, btn_col = st.columns([7, 1])
    with search_col:
        search_term = st.text_input(
            "search_input",
            value=st.session_state[_SS_SEARCH],
            placeholder="Search by employee, vendor, report name…",
            label_visibility="collapsed",
            key="search_box",
        )
    with btn_col:
        do_search = st.button("🔍  Search", type="primary", use_container_width=True)

    if do_search or (search_term != st.session_state[_SS_SEARCH]):
        st.session_state[_SS_SEARCH] = search_term
        st.session_state[_SS_PAGE]   = 0
        st.session_state[_SS_SELECTED] = None

    # ── Filter panel ──────────────────────────────────────────────────────────
    active_filters = _render_filter_panel(opts)
    active_count   = _active_filter_count(active_filters)

    if active_count:
        st.markdown(
            f'<span style="background:{theme.PRIMARY};color:#fff;padding:2px 10px;'
            f'border-radius:12px;font-size:0.78rem;font-weight:600;">'
            f'{active_count} filter{"s" if active_count != 1 else ""} active</span>',
            unsafe_allow_html=True,
        )

    # ── Query ─────────────────────────────────────────────────────────────────
    current_page = st.session_state[_SS_PAGE]
    with st.spinner("Searching…"):
        df, total = search_expenses(
            conn,
            search_term=st.session_state[_SS_SEARCH],
            filters=active_filters or None,
            offset=current_page * PAGE_SIZE,
            limit=PAGE_SIZE,
        )

    st.divider()

    # ── Results ───────────────────────────────────────────────────────────────
    if total == 0:
        _empty_state()
    else:
        _render_results(df, total)

        # ── Export buttons ────────────────────────────────────────────────────
        ex1, ex2, _ = st.columns([1.4, 1.6, 5])
        with ex1:
            csv_df = export_to_dataframe(conn, "search", active_filters or None)
            st.download_button(
                "📥 Export CSV",
                data=csv_df.to_csv(index=False).encode(),
                file_name=f"concur_export_{date.today()}.csv",
                mime="text/csv",
                key="export_csv",
            )
        with ex2:
            xlsx_data = _build_excel(conn, active_filters or {}, st.session_state[_SS_SEARCH])
            st.download_button(
                "📥 Export Excel",
                data=xlsx_data,
                file_name=f"concur_export_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="export_xlsx",
            )

    # ── Detail view ───────────────────────────────────────────────────────────
    if st.session_state[_SS_SHOW_DETAIL] and st.session_state[_SS_SELECTED]:
        st.divider()
        _render_detail(
            conn,
            st.session_state[_SS_SELECTED],
            st.session_state.get(_SS_SELECTED_RPE),
        )

    conn.close()
