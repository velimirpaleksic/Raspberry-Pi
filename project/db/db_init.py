# db/db_init.py
import os
import sqlite3

from project.core.config import DB_PATH
from project.utils.logging_utils import error_logging


def initialize_database():
    """
    Creates the main database structure if not present.
    Should be safe to call multiple times (uses IF NOT EXISTS).
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    try:
        with sqlite3.connect(DB_PATH, timeout=30) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA foreign_keys=ON;")

            conn.execute("""
            CREATE TABLE IF NOT EXISTS print_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                         
                ime TEXT NOT NULL CHECK(length(ime) <=50),
                roditelj TEXT NOT NULL CHECK(length(roditelj) <=50),
                         
                godina INTEGER NOT NULL,
                mjesec INTEGER NOT NULL CHECK(mjesec BETWEEN 1 AND 12),
                dan INTEGER NOT NULL CHECK(dan BETWEEN 1 AND 31),
                         
                mjesto TEXT NOT NULL CHECK(length(mjesto) <=50),
                opstina TEXT NOT NULL CHECK(length(opstina) <=50),
                         
                razred TEXT NOT NULL CHECK(length(razred) <=10),
                struka TEXT NOT NULL CHECK(length(struka) <=50),
                razlog TEXT NOT NULL CHECK(length(razlog) <=50),
                         
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_created_at ON print_logs(created_at);"
            )

        print("[DB] Database initialized/checked successfully.")

    except Exception:
        error_logging("[DB] Initialization failed")
        raise