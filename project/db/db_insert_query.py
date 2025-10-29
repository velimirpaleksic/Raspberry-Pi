# db/db_insert_query.py
from project.db.db_init import initialize_database
from project.db.db_connection import get_connection

from project.utils.logging_utils import error_logging


def insert_entry(
    ime: str,
    roditelj: str,
    godina: int,
    mjesec: int,
    dan: int,
    mjesto: str,
    opstina: str,
    razred: str,
    struka: str,
    razlog: str
):
    """
    Insert a single entry into the print_logs table.

    Steps:
    1. Ensure database exists (via initialize_database()).
    2. Open a connection using get_connection().
    3. Insert the provided data safely using placeholders.
    4. Commit and close automatically (via 'with' context).
    """
    # Ensure database and table exist
    initialize_database()

    validate_entry(godina, mjesec, dan)

    try:
        # Use centralized connection setup
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO print_logs 
                (ime, roditelj, godina, mjesec, dan, mjesto, opstina, razred, struka, razlog)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (ime, roditelj, godina, mjesec, dan, mjesto, opstina, razred, struka, razlog))

            # Commit happens automatically when context exits
        print("[DB] New entry successfully added.")

    except Exception as e:
        error_logging(f"[DB] Failed to insert entry: {e}")
        raise


def validate_entry(godina, mjesec, dan):
    if not (1900 <= godina <= 2100):
        raise ValueError("invalid godina")
    if not (1 <= mjesec <= 12):
        raise ValueError("invalid mjesec")
    if not (1 <= dan <= 31):
        raise ValueError("invalid dan")