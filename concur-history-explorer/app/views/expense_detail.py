"""
Expense Detail — standalone drill-down for a single entry.
Accepts rpe_key via st.session_state["detail_rpe_key"].
"""

import streamlit as st

from app import theme
from app.db.connection import db_exists, get_connection
from app.db.constants import Rpe, Rpt
from app.db.queries import get_expense_entry_detail
from app.utils.formatters import fmt_currency, fmt_date_short, fmt_approval_status, fmt_bool, truncate
from app.utils.image_handler import find_receipt_image, get_image_bytes, image_mime_type
from pathlib import Path


def render() -> None:
    theme.apply_workday_theme()
    theme.styled_header("📋 Expense Detail", subtitle="Full detail view for a single expense entry.")

    if not db_exists():
        st.info("No database found.")
        return

    rpe_key = st.session_state.get("detail_rpe_key", "")

    if not rpe_key:
        st.markdown(
            f"""
            <div style="text-align:center;padding:3rem;color:{theme.MEDIUM_GRAY};">
                <div style="font-size:2rem;margin-bottom:0.5rem;">📋</div>
                <div style="font-size:1rem;font-weight:600;color:{theme.DARK_BLUE};">
                    No entry selected
                </div>
                <div style="font-size:0.85rem;margin-top:0.4rem;">
                    Select a row in Audit Search to view its full detail here.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        rpe_key = st.text_input("Or enter an Entry Key (RPE_KEY) directly:", key="direct_rpe_input")
        if not rpe_key:
            return

    conn = get_connection()
    detail = get_expense_entry_detail(conn, rpe_key)

    if not detail:
        st.error(f"Entry `{rpe_key}` not found.")
        conn.close()
        return

    entry    = detail["entry"]
    report   = detail["report"]
    employee = detail["employee"]
    category = detail["category"]

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(
        f'<div class="wd-card-header" style="font-size:1rem;">'
        f'{category.get("icw_category") or entry.get(Rpe.EXP_KEY) or "Expense"}'
        f' &nbsp;·&nbsp; {fmt_currency(entry.get(Rpe.POSTED_AMOUNT))}'
        f' &nbsp;·&nbsp; {fmt_date_short(entry.get(Rpe.TX_DATE))}'
        f'</div>',
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3 = st.tabs(["Entry Details", "Parent Report", "Receipt"])

    # ── Tab 1: entry ──────────────────────────────────────────────────────────
    with tab1:
        c1, c2, c3 = st.columns(3)
        fields = [
            ("Entry Key",       rpe_key),
            ("Transaction Date", fmt_date_short(entry.get(Rpe.TX_DATE))),
            ("Expense Type",    entry.get(Rpe.EXP_KEY, "—")),
            ("ICW Category",    category.get("icw_category") or "—"),
            ("ICW Group",       category.get("icw_group") or "—"),
            ("Vendor",          entry.get(Rpe.VENDOR_DESC, "—")),
            ("Description",     truncate(entry.get(Rpe.DESCRIPTION), 80)),
            ("Transaction Amt", fmt_currency(entry.get(Rpe.TX_AMOUNT))),
            ("Claimed Amount",  fmt_currency(entry.get(Rpe.CLAIMED_AMOUNT))),
            ("Posted Amount",   fmt_currency(entry.get(Rpe.POSTED_AMOUNT))),
            ("Approved Amount", fmt_currency(entry.get(Rpe.APPROVED_AMOUNT))),
            ("Currency",        entry.get(Rpe.CRN_KEY, "—")),
            ("Personal",        fmt_bool(entry.get(Rpe.IS_PERSONAL))),
            ("Billable",        fmt_bool(entry.get(Rpe.IS_BILLABLE))),
            ("From Location",   entry.get(Rpe.FROM_LOCATION, "—")),
            ("To Location",     entry.get(Rpe.TO_LOCATION, "—")),
            ("Hotel Check-In",  fmt_date_short(entry.get(Rpe.HOTEL_CHECKIN))),
            ("Hotel Check-Out", fmt_date_short(entry.get(Rpe.HOTEL_CHECKOUT))),
            ("Car Rental Days", entry.get(Rpe.CAR_RENTAL_DAYS, "—")),
            ("Attendees",       entry.get(Rpe.ATTENDEE_COUNT, "—")),
            ("Exceptions",      entry.get(Rpe.EXCEPTION_COUNT, "—")),
            ("Receipt Required", fmt_bool(entry.get(Rpe.RECEIPT_REQUIRED))),
            ("Receipt Received", fmt_bool(entry.get(Rpe.RECEIPT_RECEIVED))),
        ]
        for i, (label, value) in enumerate(fields):
            with [c1, c2, c3][i % 3]:
                st.markdown(
                    f'<div style="margin-bottom:0.75rem;">'
                    f'<div class="wd-section-label">{label}</div>'
                    f'<div style="font-size:0.875rem;color:{theme.DARK_GRAY};">{value or "—"}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        if category.get("icw_instructions"):
            st.info(f"**Policy note:** {category['icw_instructions']}")

    # ── Tab 2: parent report / employee ───────────────────────────────────────
    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f'<div class="wd-card-header">Report</div>', unsafe_allow_html=True)
            for label, value in [
                ("Report ID",      report.get("rpt_id", "—")),
                ("Report Name",    report.get("report_name", "—")),
                ("Submit Date",    fmt_date_short(report.get("submit_date"))),
                ("Status",         fmt_approval_status(report.get("approval_status"))),
                ("Cost Center",    report.get("cost_center", "—")),
                ("Total Approved", fmt_currency(report.get("report_total_approved"))),
            ]:
                st.markdown(
                    f'<div style="margin-bottom:0.6rem;">'
                    f'<div class="wd-section-label">{label}</div>'
                    f'<div style="font-size:0.875rem;">{value}</div></div>',
                    unsafe_allow_html=True,
                )
        with c2:
            st.markdown(f'<div class="wd-card-header">Employee</div>', unsafe_allow_html=True)
            for label, value in [
                ("Name",       f"{employee.get('first_name','')} {employee.get('last_name','')}".strip()),
                ("Email",      employee.get("email", "—")),
                ("Employee ID", employee.get("emp_id", "—")),
                ("Department", employee.get("org_unit_1", "—")),
                ("Org Unit 2", employee.get("org_unit_2", "—")),
                ("Org Unit 3", employee.get("org_unit_3", "—")),
            ]:
                st.markdown(
                    f'<div style="margin-bottom:0.6rem;">'
                    f'<div class="wd-section-label">{label}</div>'
                    f'<div style="font-size:0.875rem;">{value or "—"}</div></div>',
                    unsafe_allow_html=True,
                )

    # ── Tab 3: receipt ────────────────────────────────────────────────────────
    with tab3:
        img_path = find_receipt_image(
            entry.get(Rpe.RECEIPT_IMAGE_ID),
            entry.get(Rpe.ERECEIPT_IMAGE_ID),
        )
        if img_path:
            p = Path(img_path)
            mime = image_mime_type(p)
            data = get_image_bytes(p)
            if data and mime.startswith("image/"):
                st.image(data, use_container_width=True)
                st.download_button("⬇ Download Receipt", data=data, file_name=p.name, mime=mime)
            elif data:
                st.markdown(f"📄 Receipt file: `{p.name}`")
                st.download_button("⬇ Download Receipt", data=data, file_name=p.name, mime=mime)
        else:
            st.info("No receipt image available for this entry.")

    conn.close()
