"""Dashboard — welcome page with KPIs and quick-action cards."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import theme
from app.db.connection import db_exists, get_connection
from app.db.constants import TBL_CATEGORIES, TBL_EMPLOYEE, TBL_ENTRY, TBL_REPORT, Cat, Emp, Rpe, Rpt
from app.utils.formatters import fmt_currency, fmt_currency_compact, fmt_date_short


def render() -> None:
    theme.apply_workday_theme()
    theme.styled_header(
        "Welcome to Concur History Explorer",
        subtitle="Search, analyze, and export 7 years of historical ICW Group expense data.",
    )

    if not db_exists():
        st.info("No expense data loaded yet.")
        st.markdown("Generate sample data to get started:")
        st.code("python -m app.utils.sample_data --num-reports 50000", language="bash")
        return

    conn = get_connection()

    # ── Metric cards ──────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        n = conn.execute(f"SELECT COUNT(*) FROM {TBL_REPORT}").fetchone()[0]
        theme.styled_metric_card("Total Expense Reports", f"{n:,}")

    with c2:
        row = conn.execute(f"SELECT SUM({Rpe.POSTED_AMOUNT}) FROM {TBL_ENTRY}").fetchone()
        total = row[0] if row and row[0] else 0
        theme.styled_metric_card("Total Spend", fmt_currency_compact(total), border_color=theme.MEDIUM_BLUE)

    with c3:
        n = conn.execute(
            f"SELECT COUNT(DISTINCT {Emp.KEY}) FROM {TBL_EMPLOYEE} WHERE {Emp.ACTIVE} = '1'"
        ).fetchone()[0]
        theme.styled_metric_card("Employees on Record", f"{n:,}", border_color=theme.SUCCESS)

    with c4:
        row = conn.execute(
            f"SELECT MIN({Rpe.TX_DATE}), MAX({Rpe.TX_DATE}) FROM {TBL_ENTRY}"
        ).fetchone()
        date_range = f"{fmt_date_short(row[0])} – {fmt_date_short(row[1])}" if row and row[0] else "—"
        theme.styled_metric_card("Data Date Range", date_range, border_color=theme.ACCENT_TEAL)

    st.divider()

    # ── Two-column section ────────────────────────────────────────────────────
    left, right = st.columns([1, 2])

    with left:
        st.markdown('<div class="wd-card">', unsafe_allow_html=True)
        st.markdown('<div class="wd-card-header">Quick Actions</div>', unsafe_allow_html=True)

        actions = [
            ("🔍", "Search Expenses",            "Switch to Expense Search in the sidebar to find individual transactions."),
            ("📊", "View Spend by Department",   "Switch to Spend Review to see aggregated spend by cost center or department."),
            ("📈", "Compare Year-over-Year",      "Switch to Trends & Forecasting for multi-year comparisons and budget validation."),
        ]
        for icon, label, tooltip in actions:
            st.markdown(
                f"""
                <div title="{tooltip}" style="
                    display:flex;align-items:center;gap:10px;
                    padding:10px 12px;border-radius:6px;
                    margin-bottom:6px;cursor:default;
                    background:{theme.LIGHT_GRAY};
                    border-left:3px solid {theme.PRIMARY};
                ">
                    <span style="font-size:1.1rem;">{icon}</span>
                    <span style="font-size:0.875rem;font-weight:500;
                        color:{theme.DARK_BLUE};">{label}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Export all button
        st.markdown("<br>", unsafe_allow_html=True)
        try:
            from app.db.queries import export_to_dataframe
            if st.button("📥 Export All Data", use_container_width=True):
                with st.spinner("Preparing export…"):
                    df = export_to_dataframe(conn, "search", None)
                st.download_button(
                    "⬇ Download CSV",
                    data=df.to_csv(index=False).encode(),
                    file_name="concur_full_export.csv",
                    mime="text/csv",
                    key="home_export",
                )
        except Exception as e:
            st.caption(f"Export unavailable: {e}")

        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="wd-card">', unsafe_allow_html=True)
        st.markdown('<div class="wd-card-header">Spend by ICW Expense Group</div>', unsafe_allow_html=True)

        try:
            rows = conn.execute(
                f"""
                SELECT c.{Cat.GROUP_NAME} AS grp,
                       SUM(re.{Rpe.POSTED_AMOUNT}) AS total
                FROM {TBL_ENTRY} re
                LEFT JOIN {TBL_CATEGORIES} c ON re.{Rpe.EXP_KEY} = c.{Cat.CATEGORY_NAME}
                WHERE re.{Rpe.POSTED_AMOUNT} IS NOT NULL
                GROUP BY grp
                ORDER BY total DESC
                """
            ).fetchall()

            if rows:
                labels = [r["grp"] or "Uncategorized" for r in rows]
                values = [r["total"] for r in rows]
                fig = go.Figure(go.Pie(
                    labels=labels, values=values,
                    hole=0.5,
                    marker_colors=theme.get_chart_colors(),
                    textinfo="percent",
                    hovertemplate="%{label}<br>%{value:$,.2f} (%{percent})<extra></extra>",
                ))
                fig.update_layout(**theme.get_plotly_layout(height=300))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No category data available.")
        except Exception as e:
            st.caption(f"Chart unavailable: {e}")

        st.markdown('</div>', unsafe_allow_html=True)

    # ── Top 10 cost centers bar chart ─────────────────────────────────────────
    st.divider()
    st.markdown('<div class="wd-card">', unsafe_allow_html=True)
    st.markdown('<div class="wd-card-header">Top 10 Cost Centers by Spend</div>', unsafe_allow_html=True)

    try:
        cc_rows = conn.execute(
            f"""
            SELECT r.{Rpt.COST_CENTER} AS cc,
                   SUM(re.{Rpe.POSTED_AMOUNT}) AS total
            FROM {TBL_ENTRY} re
            JOIN {TBL_REPORT} r ON re.{Rpe.RPT_KEY} = r.{Rpt.KEY}
            WHERE re.{Rpe.POSTED_AMOUNT} IS NOT NULL
              AND r.{Rpt.COST_CENTER} IS NOT NULL
            GROUP BY cc
            ORDER BY total DESC
            LIMIT 10
            """
        ).fetchall()

        if cc_rows:
            cc_df = pd.DataFrame([dict(r) for r in cc_rows])
            fig_cc = go.Figure(go.Bar(
                x=cc_df["total"],
                y=cc_df["cc"],
                orientation="h",
                marker_color=theme.PRIMARY,
                text=cc_df["total"].apply(fmt_currency_compact),
                textposition="outside",
                hovertemplate="%{y}<br>$%{x:,.2f}<extra></extra>",
            ))
            fig_cc.update_layout(
                **theme.get_plotly_layout(height=360),
                yaxis={"autorange": "reversed"},
                xaxis_title="Posted Amount ($)",
                margin={"l": 140, "r": 40, "t": 20, "b": 40},
            )
            st.plotly_chart(fig_cc, use_container_width=True)
        else:
            st.info("No cost center data available.")
    except Exception as e:
        st.caption(f"Chart unavailable: {e}")

    st.markdown('</div>', unsafe_allow_html=True)
    conn.close()
