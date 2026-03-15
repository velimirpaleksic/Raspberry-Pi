from __future__ import annotations

import datetime
from typing import Any, Dict, Optional

from project.core import config
from project.db.db_connection import get_connection
from project.db.db_init import initialize_database
from project.utils.settings_utils import parse_seed_djelovodni_broj
from project.utils.logging_utils import log_error, log_info


def _normalize_form_data(form_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ime": str(form_data.get("ime", "")).strip(),
        "roditelj": str(form_data.get("roditelj", "")).strip(),
        "godina": int(form_data.get("godina", 0)),
        "mjesec": int(form_data.get("mjesec", 0)),
        "dan": int(form_data.get("dan", 0)),
        "mjesto": str(form_data.get("mjesto", "")).strip(),
        "opstina": str(form_data.get("opstina", "")).strip(),
        "razred": str(form_data.get("razred", "")).strip(),
        "struka": str(form_data.get("struka", "")).strip(),
        "razlog": str(form_data.get("razlog", "")).strip(),
    }


def build_document_number(prefix: str, counter_value: int, year_value: int) -> str:
    return f"{prefix}-{counter_value}/{year_value % 100:02d}"


def get_document(job_id: str):
    initialize_database()
    with get_connection() as conn:
        return conn.execute("SELECT * FROM documents WHERE job_id = ?", (job_id,)).fetchone()


def reserve_document(job_id: str, form_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a logical document once and reuse it across retries.

    The first call allocates the next document number. Later calls for the same
    ``job_id`` return the already-reserved number so retries do not consume a
    fresh number.
    """
    initialize_database()
    data = _normalize_form_data(form_data)

    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")

        existing = conn.execute("SELECT * FROM documents WHERE job_id = ?", (job_id,)).fetchone()
        if existing:
            return dict(existing)

        row = conn.execute("SELECT value FROM settings WHERE key = 'counter_prefix'").fetchone()
        if row and row[0]:
            prefix = str(row[0])
        else:
            prefix, _, _ = parse_seed_djelovodni_broj(config.DJELOVODNI_BROJ_SEED)

        row = conn.execute("SELECT value FROM settings WHERE key = 'counter_current'").fetchone()
        if row and row[0] not in (None, ""):
            current_counter = int(row[0])
        else:
            _, current_counter, _ = parse_seed_djelovodni_broj(config.DJELOVODNI_BROJ_SEED)

        next_counter = current_counter + 1

        year_mode_row = conn.execute("SELECT value FROM settings WHERE key = 'year_mode'").fetchone()
        manual_year_row = conn.execute("SELECT value FROM settings WHERE key = 'manual_year'").fetchone()
        year_mode = str(year_mode_row[0]).lower() if year_mode_row and year_mode_row[0] else config.DEFAULT_YEAR_MODE
        if year_mode == "manual" and manual_year_row and str(manual_year_row[0]).isdigit():
            year_value = int(manual_year_row[0])
        else:
            year_value = datetime.datetime.now().year

        document_number = build_document_number(prefix, next_counter, year_value)

        conn.execute(
            """
            INSERT INTO settings(key, value, updated_at)
            VALUES ('counter_current', ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
            (str(next_counter),),
        )

        conn.execute(
            """
            INSERT INTO documents (
                job_id, document_number, counter_value, year_value, status,
                ime, roditelj, godina, mjesec, dan, mjesto, opstina, razred, struka, razlog,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                job_id,
                document_number,
                next_counter,
                year_value,
                "created",
                data["ime"],
                data["roditelj"],
                data["godina"],
                data["mjesec"],
                data["dan"],
                data["mjesto"],
                data["opstina"],
                data["razred"],
                data["struka"],
                data["razlog"],
            ),
        )

        return {
            "job_id": job_id,
            "document_number": document_number,
            "counter_value": next_counter,
            "year_value": year_value,
            **data,
        }


def start_attempt(job_id: str, printer_name: str) -> int:
    initialize_database()
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT COALESCE(MAX(attempt_no), 0) AS max_attempt FROM print_attempts WHERE job_id = ?", (job_id,)).fetchone()
        attempt_no = int(row["max_attempt"] or 0) + 1
        conn.execute(
            """
            INSERT INTO print_attempts(job_id, attempt_no, started_at, status, printer_name)
            VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?)
            """,
            (job_id, attempt_no, "started", printer_name),
        )
        return attempt_no


def update_document_status(
    job_id: str,
    status: str,
    *,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    printed_at: Optional[str] = None,
) -> None:
    initialize_database()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE documents
               SET status = ?,
                   updated_at = CURRENT_TIMESTAMP,
                   last_error_code = ?,
                   last_error_message = ?,
                   printed_at = COALESCE(?, printed_at)
             WHERE job_id = ?
            """,
            (status, error_code, error_message, printed_at, job_id),
        )


def finish_attempt(
    job_id: str,
    attempt_no: int,
    *,
    status: str,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    docx_path: Optional[str] = None,
    pdf_path: Optional[str] = None,
) -> None:
    initialize_database()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE print_attempts
               SET finished_at = CURRENT_TIMESTAMP,
                   status = ?,
                   error_code = ?,
                   error_message = ?,
                   docx_path = COALESCE(?, docx_path),
                   pdf_path = COALESCE(?, pdf_path)
             WHERE job_id = ? AND attempt_no = ?
            """,
            (status, error_code, error_message, docx_path, pdf_path, job_id, attempt_no),
        )


def record_system_event(event_type: str, message: str, *, level: str = "info", job_id: Optional[str] = None) -> None:
    initialize_database()
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO system_events(event_type, level, message, job_id, created_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (event_type, level, message, job_id),
            )
    except Exception as e:
        log_error(f"[SYSTEM] Could not record event '{event_type}': {e}")


def mark_interrupted_documents() -> int:
    initialize_database()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE documents
               SET status = 'interrupted',
                   updated_at = CURRENT_TIMESTAMP,
                   last_error_code = COALESCE(last_error_code, 'INTERRUPTED'),
                   last_error_message = COALESCE(last_error_message, 'Prekinuto prethodnim gašenjem ili restartom.')
             WHERE status IN ('rendering', 'printing')
            """
        )
        count = cursor.rowcount if cursor.rowcount is not None else 0

    if count:
        record_system_event(
            "recovery_interrupted_jobs",
            f"Recovered {count} interrupted document(s) on startup.",
            level="warning",
        )
        log_info(f"[RECOVERY] Marked {count} interrupted document(s) on startup.")

    return count


def current_timestamp_sql() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
