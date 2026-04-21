"""Administration page — database status, table browser, and about info."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from app import theme
from app.db.connection import DB_PATH, db_exists, get_connection
from app.db.constants import CORE_TABLES, TBL_CATEGORIES, TBL_EMPLOYEE, TBL_ENTRY, TBL_REPORT
from app.db.queries import clear_filter_cache


def _db_stats(conn) -> dict:
    stats: dict = {}
    stats["file_size_mb"] = round(DB_PATH.stat().st_size / 1_048_576, 2) if DB_PATH.exists() else 0
    stats["last_modified"] = (
        datetime.fromtimestamp(DB_PATH.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        if DB_PATH.exists() else "—"
    )
    for tbl in list(CORE_TABLES) + [TBL_CATEGORIES]:
        try:
            stats[tbl] = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        except Exception:
            stats[tbl] = "—"
    return stats


def _list_tables(conn) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


def render() -> None:
    theme.apply_workday_theme()
    theme.styled_header("⚙️ Administration", subtitle="Database management, table browser, and system info.")

    tab1, tab2, tab3 = st.tabs(["🗄️ Data Management", "🔍 Table Browser", "ℹ️ About"])

    # ── Tab 1: Data management ────────────────────────────────────────────────
    with tab1:
        if not db_exists():
            st.warning("No database found.")
            st.markdown("**Generate sample data:**")
            st.code("python -m app.utils.sample_data --num-reports 50000", language="bash")
            st.markdown("**Or ingest real Concur data:**")
            st.code("python -m app.db.ingest --data-dir ./data", language="bash")
            return

        conn = get_connection()
        stats = _db_stats(conn)

        # Status card
        st.markdown('<div class="wd-card">', unsafe_allow_html=True)
        st.markdown('<div class="wd-card-header">Database Status</div>', unsafe_allow_html=True)

        s1, s2, s3 = st.columns(3)
        with s1:
            theme.styled_metric_card("File Size", f"{stats['file_size_mb']} MB")
        with s2:
            theme.styled_metric_card("Last Modified", stats["last_modified"], border_color=theme.MEDIUM_BLUE)
        with s3:
            theme.styled_metric_card("Location", DB_PATH.name, border_color=theme.ACCENT_TEAL)

        st.markdown("<br>", unsafe_allow_html=True)

        row_data = [
            {"Table": tbl, "Row Count": f"{stats.get(tbl, '—'):,}" if isinstance(stats.get(tbl), int) else "—"}
            for tbl in list(CORE_TABLES) + [TBL_CATEGORIES]
        ]
        st.dataframe(pd.DataFrame(row_data), use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Re-ingest
        st.markdown('<div class="wd-card" style="margin-top:1rem;">', unsafe_allow_html=True)
        st.markdown('<div class="wd-card-header">Re-ingest Data</div>', unsafe_allow_html=True)
        st.markdown(
            f'<p style="font-size:0.85rem;color:{theme.MEDIUM_GRAY};">'
            f'Re-ingesting will drop and recreate all tables. Existing data will be lost.</p>',
            unsafe_allow_html=True,
        )

        ingest_col1, ingest_col2 = st.columns(2)
        with ingest_col1:
            st.markdown("**From Concur zip files:**")
            st.code("python -m app.db.ingest --data-dir ./data", language="bash")
        with ingest_col2:
            st.markdown("**From sample data generator:**")
            st.code("python -m app.utils.sample_data --num-reports 50000", language="bash")

        confirmed = st.checkbox("I understand this will delete all existing data", key="reingest_confirm")
        if st.button("🔄 Re-generate Sample Data", disabled=not confirmed, type="primary"):
            with st.spinner("Generating sample data… this may take a minute."):
                result = subprocess.run(
                    [sys.executable, "-m", "app.utils.sample_data", "--num-reports", "10000"],
                    capture_output=True, text=True,
                )
            clear_filter_cache()
            if result.returncode == 0:
                st.success("Sample data regenerated successfully.")
                st.rerun()
            else:
                st.error(f"Generation failed:\n{result.stderr[-500:]}")

        st.markdown('</div>', unsafe_allow_html=True)
        conn.close()

    # ── Tab 2: Table browser ──────────────────────────────────────────────────
    with tab2:
        if not db_exists():
            st.info("No database found.")
            return

        conn = get_connection()
        tables = _list_tables(conn)

        if not tables:
            st.info("No tables found in database.")
            conn.close()
            return

        selected_table = st.selectbox("Select table", tables, key="admin_table_select")
        row_limit = st.slider("Rows to preview", min_value=10, max_value=500, value=100, step=10)

        try:
            df = pd.read_sql_query(
                f"SELECT * FROM {selected_table} LIMIT {row_limit}", conn
            )
            st.markdown(
                f'<div style="font-size:0.8rem;color:{theme.MEDIUM_GRAY};margin-bottom:0.5rem;">'
                f'{len(df):,} rows shown &nbsp;·&nbsp; {len(df.columns)} columns</div>',
                unsafe_allow_html=True,
            )
            theme.styled_dataframe(df)

            st.download_button(
                f"📥 Export {selected_table} (CSV)",
                data=df.to_csv(index=False).encode(),
                file_name=f"{selected_table}_preview.csv",
                mime="text/csv",
            )
        except Exception as e:
            st.error(f"Could not query table: {e}")

        conn.close()

    # ── Tab 3: About ──────────────────────────────────────────────────────────
    with tab3:
        st.markdown('<div class="wd-card">', unsafe_allow_html=True)
        st.markdown('<div class="wd-card-header">System Information</div>', unsafe_allow_html=True)

        info = [
            ("Application",       "ICW Group Concur History Explorer"),
            ("Version",           "Prototype v0.1"),
            ("Data Source",       "SAP Concur Disconnect Extract"),
            ("Retention Period",  "7 years (per ICW Group policy)"),
            ("Access",            "Up to 3 business users from Finance Travel/Expense team"),
            ("Database Engine",   "SQLite (prototype) → AWS RDS Aurora (production)"),
            ("Interface",         "Read-only — no write operations permitted"),
        ]
        for label, value in info:
            st.markdown(
                f'<div style="display:flex;gap:1rem;padding:8px 0;border-bottom:1px solid {theme.LIGHT_GRAY};">'
                f'<div style="width:180px;font-size:0.8rem;font-weight:600;color:{theme.MEDIUM_GRAY};">{label}</div>'
                f'<div style="font-size:0.875rem;color:{theme.DARK_GRAY};">{value}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="wd-card" style="margin-top:1rem;">', unsafe_allow_html=True)
        st.markdown('<div class="wd-card-header">ICW Expense Category Taxonomy</div>', unsafe_allow_html=True)

        if db_exists():
            conn = get_connection()
            try:
                cat_df = pd.read_sql_query(
                    f"SELECT group_name AS 'Group', category_name AS 'Category', "
                    f"description AS 'Description' FROM {TBL_CATEGORIES} ORDER BY group_name, category_name",
                    conn,
                )
                theme.styled_dataframe(cat_df)
            except Exception:
                st.info("Category table not available.")
            finally:
                conn.close()

        st.markdown('</div>', unsafe_allow_html=True)
