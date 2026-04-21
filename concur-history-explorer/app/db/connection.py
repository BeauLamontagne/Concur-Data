import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "db" / "concur.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA cache_size=-64000")  # 64 MB page cache
    return conn


def db_exists() -> bool:
    return DB_PATH.exists() and DB_PATH.stat().st_size > 0
