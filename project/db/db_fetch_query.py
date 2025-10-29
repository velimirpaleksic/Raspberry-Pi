# db/db_fetch_query.py
from project.db.db_connection import get_connection
from project.db.db_init import initialize_database

from project.utils.logging_utils import error_logging


def fetch_all_entries():
    """
    Fetches all records from the print_logs table, ordered by creation time (newest first).
    
    Returns:
        list[sqlite3.Row]: a list of rows, accessible by column name (since row_factory is set).
    """
    initialize_database()

    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT *
                FROM print_logs
                ORDER BY created_at DESC
            """)
            results = cursor.fetchall()
            return results

    except Exception as e:
        error_logging(f"[DB] Could not fetch all entries: {e}")
        return []


def fetch_entry_by_id(entry_id: int):
    """
    Fetch a single record by ID.

    Args:
        entry_id (int): Primary key of the record to retrieve.

    Returns:
        sqlite3.Row | None: the matching record, or None if not found.
    """
    initialize_database()

    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT *
                FROM print_logs
                WHERE id = ?
            """, (entry_id,))
            result = cursor.fetchone()
            return result

    except Exception as e:
        error_logging(f"[DB] Could not fetch entry {entry_id}: {e}")
        return None


def fetch_entries_by_field(field: str, value: str):
    """
    Fetch all records where a given column matches the provided value.

    Args:
        field (str): The column name (e.g. 'ime', 'opstina').
        value (str): The value to match.

    Returns:
        list[sqlite3.Row]: All matching records.
    """
    initialize_database()

    # Validate input - never directly interpolate user input into SQL
    allowed_fields = {"ime", "roditelj", "mjesto", "opstina", "razred", "struka", "razlog"}
    if field not in allowed_fields:
        error_logging(f"[DB] Invalid field name: {field}")
        return []

    try:
        with get_connection() as conn:
            query = f"SELECT * FROM print_logs WHERE {field} = ? ORDER BY created_at DESC"
            cursor = conn.execute(query, (value,))
            results = cursor.fetchall()
            return results

    except Exception as e:
        error_logging(f"[DB] Could not fetch by field '{field}': {e}")
        return []