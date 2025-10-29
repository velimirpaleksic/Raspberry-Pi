# db/db_connection.py
import sqlite3
import os

from project.core.config import DB_PATH
from project.utils.logging_utils import error_logging


def _apply_pragmas(conn: sqlite3.Connection):
    # Configure per-connection settings
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=5000;")  # wait up to 5s for locks


def get_connection():
    """
    Returns a configured sqlite3.Connection.
    Use as:
        with get_connection() as conn:
            conn.execute(...)
    """
    try:
        # Ensure DB directory exists
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=30, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        _apply_pragmas(conn)
        return conn
    
    except Exception as e:
        error_logging(f"[DB] Connection failed: {e}")
        raise