from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path
from typing import Any, Dict, List, Optional

from project.core import config
from project.db.db_connection import get_connection
from project.db.db_init import initialize_database


def _row_to_dict(row) -> dict:
    return dict(row) if row is not None else {}


def _normalize_date_start(value: str | None) -> Optional[str]:
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = dt.datetime.strptime(value, "%Y-%m-%d")
        return parsed.strftime("%Y-%m-%d 00:00:00")
    except Exception:
        return None


def _normalize_date_end(value: str | None) -> Optional[str]:
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = dt.datetime.strptime(value, "%Y-%m-%d")
        return parsed.strftime("%Y-%m-%d 23:59:59")
    except Exception:
        return None


def search_documents(
    *,
    query: str = "",
    status: str = "all",
    date_from: str = "",
    date_to: str = "",
    limit: int = 100,
) -> List[dict]:
    initialize_database()
    sql = [
        """
        SELECT
            d.job_id,
            d.document_number,
            d.status,
            d.ime,
            d.roditelj,
            d.razred,
            d.struka,
            d.razlog,
            d.created_at,
            d.printed_at,
            d.last_error_code,
            d.last_error_message,
            (SELECT COALESCE(MAX(pa.attempt_no), 0) FROM print_attempts pa WHERE pa.job_id = d.job_id) AS attempts_count
        FROM documents d
        WHERE 1=1
        """
    ]
    params: list[Any] = []

    q = (query or "").strip()
    if q:
        sql.append("AND (d.ime LIKE ? OR d.document_number LIKE ? OR d.job_id LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like])

    normalized_status = (status or "all").strip().lower()
    if normalized_status and normalized_status != "all":
        sql.append("AND LOWER(d.status) = ?")
        params.append(normalized_status)

    start = _normalize_date_start(date_from)
    if start:
        sql.append("AND d.created_at >= ?")
        params.append(start)

    end = _normalize_date_end(date_to)
    if end:
        sql.append("AND d.created_at <= ?")
        params.append(end)

    sql.append("ORDER BY d.created_at DESC, d.id DESC LIMIT ?")
    params.append(max(1, min(int(limit), 500)))

    with get_connection() as conn:
        rows = conn.execute("\n".join(sql), tuple(params)).fetchall()
        return [_row_to_dict(r) for r in rows]


def get_document_attempts(job_id: str) -> List[dict]:
    initialize_database()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT attempt_no, started_at, finished_at, status, error_code, error_message, printer_name, docx_path, pdf_path
            FROM print_attempts
            WHERE job_id = ?
            ORDER BY attempt_no ASC
            """,
            (job_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def get_daily_summary(days: int = 7) -> List[dict]:
    initialize_database()
    safe_days = max(1, min(int(days), 60))
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                date(created_at, 'localtime') AS day,
                COUNT(*) AS total_documents,
                SUM(CASE WHEN status = 'printed' THEN 1 ELSE 0 END) AS printed_documents,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_documents,
                SUM(
                    COALESCE(
                        (SELECT MAX(pa.attempt_no) FROM print_attempts pa WHERE pa.job_id = d.job_id),
                        0
                    )
                ) AS total_attempts
            FROM documents d
            WHERE created_at >= datetime('now', 'localtime', ?)
            GROUP BY date(created_at, 'localtime')
            ORDER BY day DESC
            """,
            (f"-{safe_days - 1} days",),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def export_documents_csv(
    *,
    query: str = "",
    status: str = "all",
    date_from: str = "",
    date_to: str = "",
    limit: int = 1000,
) -> Path:
    rows = search_documents(query=query, status=status, date_from=date_from, date_to=date_to, limit=limit)
    config.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = config.EXPORTS_DIR / f"evidencija_{ts}.csv"

    fieldnames = [
        "job_id",
        "document_number",
        "status",
        "ime",
        "roditelj",
        "razred",
        "struka",
        "razlog",
        "created_at",
        "printed_at",
        "attempts_count",
        "last_error_code",
        "last_error_message",
    ]
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    return out_path
