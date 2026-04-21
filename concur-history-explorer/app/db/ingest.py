"""
CLI-driven ingest module.

Usage:
    python -m app.db.ingest --data-dir ./data

Expects the data directory to contain one or more of:
    - Disconnect.zip   (pipe-delimited .dat files)
    - DDL.zip          (SQL CREATE TABLE scripts)
    - Extract_images_*.zip  (receipt image files)

Or the extracted contents of any of the above already unzipped into subdirectories.
"""

import argparse
import logging
import re
import shutil
import sqlite3
import warnings
import zipfile
from pathlib import Path

import pandas as pd

from app.db.connection import DB_PATH, get_connection
from app.db.constants import TBL_CATEGORIES, TBL_EMPLOYEE, TBL_ENTRY, TBL_FTS, TBL_REPORT, Cat, Emp, Fts, Rpe, Rpt
from app.db.schema import apply_schema, translate_ddl_file
from app.utils.expense_categories import ICW_CATEGORIES

from app.utils.logger import setup_logging  # noqa: E402 (after stdlib imports)
setup_logging()
logger = logging.getLogger(__name__)

IMAGES_DIR = DB_PATH.parent / "images"


# ---------------------------------------------------------------------------
# Zip extraction helpers
# ---------------------------------------------------------------------------

def _extract_zip(zip_path: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)
    logger.info("Extracted %s → %s", zip_path.name, dest)


def _find_or_extract(data_dir: Path, zip_name_pattern: str, extract_subdir: str) -> Path:
    """Return extracted directory, extracting the zip first if necessary."""
    target = data_dir / extract_subdir
    if target.exists():
        return target

    matches = list(data_dir.glob(zip_name_pattern))
    if matches:
        _extract_zip(matches[0], target)
        return target

    return target  # may not exist — caller must handle


# ---------------------------------------------------------------------------
# DDL translation
# ---------------------------------------------------------------------------

def _load_ddl(data_dir: Path) -> list[str]:
    ddl_dir = _find_or_extract(data_dir, "DDL.zip", "ddl_extracted")
    statements: list[str] = []
    if not ddl_dir.exists():
        logger.warning("DDL.zip not found — using built-in core table DDL only.")
        return statements

    for sql_file in sorted(ddl_dir.rglob("*.sql")):
        text = sql_file.read_text(errors="replace")
        translated = translate_ddl_file(text)
        statements.extend(translated)
        logger.info("Translated %d statements from %s", len(translated), sql_file.name)

    return statements


# ---------------------------------------------------------------------------
# .dat file ingestion
# ---------------------------------------------------------------------------

_DATE_COLS_RE = re.compile(r"date|time|modified|created", re.IGNORECASE)


def _infer_dtype_overrides(columns: list[str]) -> dict:
    return {col: str for col in columns if _DATE_COLS_RE.search(col)}


def _load_dat_file(dat_path: Path, conn: sqlite3.Connection) -> tuple[int, int]:
    """Load a single .dat file. Returns (rows_loaded, bad_rows_skipped)."""
    table_name = dat_path.stem

    bad_rows = 0
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            df = pd.read_csv(
                dat_path,
                sep="|",
                dtype=str,
                keep_default_na=False,
                on_bad_lines="warn",
                encoding="utf-8",
                encoding_errors="replace",
            )
        bad_rows = sum(1 for w in caught if issubclass(w.category, Warning) and "bad lines" in str(w.message).lower())
        if bad_rows:
            logger.warning("  %s: skipped %d malformed row(s)", dat_path.name, bad_rows)
    except Exception as e:
        logger.error("Failed to read %s: %s", dat_path.name, e)
        return 0, 0

    df.columns = [c.strip().upper() for c in df.columns]

    # Coerce obviously numeric amount/count columns
    numeric_hints = ["AMOUNT", "RATE", "COUNT", "DAYS", "VERSION"]
    for col in df.columns:
        if any(h in col for h in numeric_hints):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    try:
        df.to_sql(table_name, conn, if_exists="replace", index=False, chunksize=5000)
    except Exception as e:
        logger.error("Failed to insert %s (%d rows): %s", table_name, len(df), e)
        return 0, bad_rows

    logger.info("  %-40s  %d rows", table_name, len(df))
    return len(df), bad_rows


def _ingest_disconnect(data_dir: Path, conn: sqlite3.Connection) -> dict[str, int]:
    disconnect_dir = _find_or_extract(data_dir, "Disconnect.zip", "disconnect_extracted")
    counts: dict[str, int] = {}

    if not disconnect_dir.exists():
        # Also check if .dat files are directly in data_dir
        dat_files = list(data_dir.glob("*.dat"))
        if not dat_files:
            logger.warning("No Disconnect.zip and no .dat files found in %s", data_dir)
            return counts
        source_dir = data_dir
    else:
        source_dir = disconnect_dir

    dat_files = sorted(source_dir.rglob("*.dat"))
    logger.info("Found %d .dat files", len(dat_files))

    total_bad = 0
    for dat_path in dat_files:
        n, bad = _load_dat_file(dat_path, conn)
        counts[dat_path.stem] = n
        total_bad += bad

    if total_bad:
        logger.warning("Total malformed rows skipped across all files: %d", total_bad)

    return counts


# ---------------------------------------------------------------------------
# Image extraction
# ---------------------------------------------------------------------------

def _ingest_images(data_dir: Path) -> int:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    total = 0

    image_zips = list(data_dir.glob("Extract_images_*.zip")) + list(data_dir.glob("extract_images_*.zip"))

    if not image_zips:
        logger.warning("No Extract_images_*.zip files found.")
        return 0

    for zip_path in image_zips:
        dest = IMAGES_DIR / zip_path.stem
        _extract_zip(zip_path, dest)
        count = sum(1 for _ in dest.rglob("*") if _.is_file())
        total += count
        logger.info("  %s: %d image files", zip_path.name, count)

    return total


# ---------------------------------------------------------------------------
# FTS population
# ---------------------------------------------------------------------------

def _populate_fts(conn: sqlite3.Connection) -> int:
    conn.execute(f"DELETE FROM {TBL_FTS}")

    sql = f"""
        INSERT INTO {TBL_FTS}
            ({Fts.EMP_KEY}, {Fts.RPT_KEY}, {Fts.RPE_KEY},
             {Fts.FIRST_NAME}, {Fts.LAST_NAME},
             {Fts.RPT_NAME}, {Fts.VENDOR_DESC}, {Fts.DESCRIPTION},
             {Fts.ORG_UNIT_1}, {Fts.ORG_UNIT_2}, {Fts.ORG_UNIT_3},
             {Fts.ORG_UNIT_4}, {Fts.ORG_UNIT_5}, {Fts.ORG_UNIT_6})
        SELECT
            e.{Emp.KEY}, r.{Rpt.KEY}, re.{Rpe.KEY},
            COALESCE(e.{Emp.FIRST_NAME}, ''), COALESCE(e.{Emp.LAST_NAME}, ''),
            COALESCE(r.{Rpt.NAME}, ''), COALESCE(re.{Rpe.VENDOR_DESC}, ''),
            COALESCE(re.{Rpe.DESCRIPTION}, ''),
            COALESCE(re.{Rpe.ORG_UNIT_1}, ''), COALESCE(re.{Rpe.ORG_UNIT_2}, ''),
            COALESCE(re.{Rpe.ORG_UNIT_3}, ''), COALESCE(re.{Rpe.ORG_UNIT_4}, ''),
            COALESCE(re.{Rpe.ORG_UNIT_5}, ''), COALESCE(re.{Rpe.ORG_UNIT_6}, '')
        FROM {TBL_ENTRY} re
        JOIN {TBL_REPORT} r  ON re.{Rpe.RPT_KEY} = r.{Rpt.KEY}
        JOIN {TBL_EMPLOYEE} e ON r.{Rpt.EMP_KEY}  = e.{Emp.KEY}
    """
    try:
        cur = conn.execute(sql)
        conn.commit()
        return cur.rowcount
    except sqlite3.Error as e:
        logger.error("FTS population failed: %s", e)
        return 0


# ---------------------------------------------------------------------------
# ICW categories seed
# ---------------------------------------------------------------------------

def _seed_icw_categories(conn: sqlite3.Connection) -> None:
    conn.execute(f"DELETE FROM {TBL_CATEGORIES}")
    conn.executemany(
        f"INSERT INTO {TBL_CATEGORIES} ({Cat.GROUP_NAME}, {Cat.CATEGORY_NAME}, {Cat.DESCRIPTION}, {Cat.INSTRUCTIONS}) VALUES (?,?,?,?)",
        [(r["group_name"], r["category_name"], r["description"], r["instructions"]) for r in ICW_CATEGORIES],
    )
    conn.commit()
    logger.info("Seeded %d ICW expense categories.", len(ICW_CATEGORIES))


# ---------------------------------------------------------------------------
# Summary stats
# ---------------------------------------------------------------------------

def _print_summary(conn: sqlite3.Connection, table_counts: dict[str, int], image_count: int) -> None:
    print("\n" + "=" * 60)
    print("  INGEST SUMMARY")
    print("=" * 60)
    print(f"  {'Table':<40} {'Rows':>10}")
    print(f"  {'-'*40} {'-'*10}")
    for table, count in sorted(table_counts.items()):
        print(f"  {table:<40} {count:>10,}")

    # ICW categories
    row = conn.execute(f"SELECT COUNT(*) FROM {TBL_CATEGORIES}").fetchone()
    print(f"  {TBL_CATEGORIES:<40} {row[0]:>10,}")

    # FTS
    try:
        row = conn.execute(f"SELECT COUNT(*) FROM {TBL_FTS}").fetchone()
        print(f"  {TBL_FTS + ' (FTS index)':<40} {row[0]:>10,}")
    except Exception:
        pass

    print(f"\n  Receipt images extracted:   {image_count:>10,}")
    db_size_mb = DB_PATH.stat().st_size / 1_048_576 if DB_PATH.exists() else 0
    print(f"  Database file size:         {db_size_mb:>9.1f} MB")
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_ingest(data_dir: Path) -> None:
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    logger.info("Starting ingest from: %s", data_dir.resolve())

    # Fresh database
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
        logger.info("Removed existing database.")

    conn = get_connection()

    # 1. Schema
    extra_ddl = _load_ddl(data_dir)
    apply_schema(conn, extra_ddl)

    # 2. Seed ICW categories
    _seed_icw_categories(conn)

    # 3. Load .dat files
    logger.info("\nLoading .dat files:")
    table_counts = _ingest_disconnect(data_dir, conn)

    # 4. Rebuild indexes after bulk load
    logger.info("Rebuilding indexes...")
    conn.execute("ANALYZE")
    conn.commit()

    # 5. FTS index
    logger.info("Populating full-text search index...")
    fts_rows = _populate_fts(conn)
    logger.info("  FTS rows indexed: %d", fts_rows)

    # 6. Images
    logger.info("\nExtracting receipt images:")
    image_count = _ingest_images(data_dir)

    # 7. Summary
    _print_summary(conn, table_counts, image_count)
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Concur .dat files into SQLite")
    parser.add_argument("--data-dir", type=Path, default=Path("./data"), help="Path to folder with Concur zip/dat files")
    args = parser.parse_args()
    run_ingest(args.data_dir)


if __name__ == "__main__":
    main()
