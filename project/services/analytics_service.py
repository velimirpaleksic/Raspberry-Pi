from __future__ import annotations

from typing import Any, Dict, List

from project.db.db_connection import get_connection
from project.db.db_init import initialize_database


def _row_to_dict(row) -> dict:
    return dict(row) if row is not None else {}


def _safe_days(days: int) -> int:
    try:
        return max(1, min(int(days), 365))
    except Exception:
        return 30


def get_analytics_snapshot(days: int = 30) -> Dict[str, Any]:
    initialize_database()
    safe_days = _safe_days(days)
    window = f"-{safe_days - 1} days"

    with get_connection() as conn:
        summary = conn.execute(
            """
            WITH doc_attempts AS (
                SELECT
                    d.job_id,
                    d.status,
                    d.created_at,
                    d.printed_at,
                    COALESCE(MAX(pa.attempt_no), 0) AS attempts_count,
                    MIN(pa.started_at) AS first_attempt_at,
                    MAX(pa.finished_at) AS last_attempt_finished_at
                FROM documents d
                LEFT JOIN print_attempts pa ON pa.job_id = d.job_id
                WHERE d.created_at >= datetime('now', 'localtime', ?)
                GROUP BY d.job_id
            )
            SELECT
                COUNT(*) AS total_documents,
                SUM(CASE WHEN status = 'printed' THEN 1 ELSE 0 END) AS printed_documents,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_documents,
                SUM(CASE WHEN status = 'interrupted' THEN 1 ELSE 0 END) AS interrupted_documents,
                SUM(CASE WHEN attempts_count > 1 THEN 1 ELSE 0 END) AS retry_documents,
                SUM(CASE WHEN attempts_count > 1 THEN attempts_count - 1 ELSE 0 END) AS retry_attempts,
                SUM(attempts_count) AS total_attempts,
                ROUND(AVG(CASE WHEN attempts_count > 0 THEN CAST(attempts_count AS REAL) END), 2) AS avg_attempts_per_document,
                ROUND(AVG(
                    CASE
                        WHEN status = 'printed' AND first_attempt_at IS NOT NULL AND printed_at IS NOT NULL
                        THEN MAX(0, (julianday(printed_at) - julianday(first_attempt_at)) * 86400.0)
                    END
                ), 1) AS avg_seconds_to_print,
                ROUND(MAX(
                    CASE
                        WHEN status = 'printed' AND first_attempt_at IS NOT NULL AND printed_at IS NOT NULL
                        THEN MAX(0, (julianday(printed_at) - julianday(first_attempt_at)) * 86400.0)
                    END
                ), 1) AS worst_seconds_to_print
            FROM doc_attempts
            """,
            (window,),
        ).fetchone()

        daily = conn.execute(
            """
            WITH doc_attempts AS (
                SELECT
                    d.job_id,
                    date(d.created_at, 'localtime') AS day,
                    d.status,
                    d.printed_at,
                    COALESCE(MAX(pa.attempt_no), 0) AS attempts_count,
                    MIN(pa.started_at) AS first_attempt_at
                FROM documents d
                LEFT JOIN print_attempts pa ON pa.job_id = d.job_id
                WHERE d.created_at >= datetime('now', 'localtime', ?)
                GROUP BY d.job_id
            )
            SELECT
                day,
                COUNT(*) AS documents,
                SUM(CASE WHEN status = 'printed' THEN 1 ELSE 0 END) AS printed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                SUM(CASE WHEN status = 'interrupted' THEN 1 ELSE 0 END) AS interrupted,
                SUM(attempts_count) AS attempts,
                SUM(CASE WHEN attempts_count > 1 THEN 1 ELSE 0 END) AS retry_documents,
                ROUND(AVG(
                    CASE
                        WHEN status = 'printed' AND first_attempt_at IS NOT NULL AND printed_at IS NOT NULL
                        THEN MAX(0, (julianday(printed_at) - julianday(first_attempt_at)) * 86400.0)
                    END
                ), 1) AS avg_seconds_to_print
            FROM doc_attempts
            GROUP BY day
            ORDER BY day DESC
            """,
            (window,),
        ).fetchall()

        errors = conn.execute(
            """
            SELECT
                COALESCE(NULLIF(pa.error_code, ''), NULLIF(d.last_error_code, ''), 'UNKNOWN') AS error_code,
                COALESCE(NULLIF(pa.error_message, ''), NULLIF(d.last_error_message, ''), '-') AS error_message,
                COUNT(*) AS hits
            FROM print_attempts pa
            JOIN documents d ON d.job_id = pa.job_id
            WHERE pa.status = 'failed'
              AND pa.started_at >= datetime('now', 'localtime', ?)
            GROUP BY error_code, error_message
            ORDER BY hits DESC, error_code ASC
            LIMIT 8
            """,
            (window,),
        ).fetchall()

        retry_buckets = conn.execute(
            """
            WITH doc_attempts AS (
                SELECT d.job_id, COALESCE(MAX(pa.attempt_no), 0) AS attempts_count
                FROM documents d
                LEFT JOIN print_attempts pa ON pa.job_id = d.job_id
                WHERE d.created_at >= datetime('now', 'localtime', ?)
                GROUP BY d.job_id
            )
            SELECT
                SUM(CASE WHEN attempts_count <= 1 THEN 1 ELSE 0 END) AS one_attempt,
                SUM(CASE WHEN attempts_count = 2 THEN 1 ELSE 0 END) AS two_attempts,
                SUM(CASE WHEN attempts_count >= 3 THEN 1 ELSE 0 END) AS three_plus_attempts
            FROM doc_attempts
            """,
            (window,),
        ).fetchone()

    summary_dict = _row_to_dict(summary)
    summary_dict.update(
        {
            "total_documents": int(summary_dict.get("total_documents") or 0),
            "printed_documents": int(summary_dict.get("printed_documents") or 0),
            "failed_documents": int(summary_dict.get("failed_documents") or 0),
            "interrupted_documents": int(summary_dict.get("interrupted_documents") or 0),
            "retry_documents": int(summary_dict.get("retry_documents") or 0),
            "retry_attempts": int(summary_dict.get("retry_attempts") or 0),
            "total_attempts": int(summary_dict.get("total_attempts") or 0),
            "avg_attempts_per_document": float(summary_dict.get("avg_attempts_per_document") or 0.0),
            "avg_seconds_to_print": float(summary_dict.get("avg_seconds_to_print") or 0.0),
            "worst_seconds_to_print": float(summary_dict.get("worst_seconds_to_print") or 0.0),
        }
    )

    total_docs = summary_dict["total_documents"] or 0
    printed_docs = summary_dict["printed_documents"] or 0
    failed_docs = summary_dict["failed_documents"] or 0
    retry_docs = summary_dict["retry_documents"] or 0
    success_rate = round((printed_docs / total_docs) * 100, 1) if total_docs else 0.0
    retry_rate = round((retry_docs / total_docs) * 100, 1) if total_docs else 0.0
    fail_rate = round((failed_docs / total_docs) * 100, 1) if total_docs else 0.0

    recommendations: List[str] = []
    if fail_rate >= 20:
        recommendations.append("Fail rate je visok. Pregledaj printer dijagnostiku i recovery hintove prije produkcijskog rada.")
    if retry_rate >= 25:
        recommendations.append("Mnogo dokumenata traži retry. Fokusiraj se na stabilnost printer queue-a i template validaciju.")
    if summary_dict["avg_seconds_to_print"] >= 90:
        recommendations.append("Prosječno vrijeme od starta do printa je dugo. Provjeri PDF konverziju, printer odziv i network latency.")
    if not recommendations:
        recommendations.append("Analitika izgleda stabilno. Nastavi pratiti trendove po danima i top greške.")

    return {
        "days": safe_days,
        "summary": summary_dict,
        "success_rate": success_rate,
        "retry_rate": retry_rate,
        "fail_rate": fail_rate,
        "daily": [_row_to_dict(r) for r in daily],
        "top_errors": [_row_to_dict(r) for r in errors],
        "retry_buckets": _row_to_dict(retry_buckets),
        "recommendations": recommendations,
    }



def format_analytics_snapshot(snapshot: Dict[str, Any]) -> str:
    summary = snapshot.get("summary") or {}
    lines = [
        f"Period: zadnjih {snapshot.get('days', '-') } dana",
        f"Dokumenti: {summary.get('total_documents', 0)} | uspješno: {summary.get('printed_documents', 0)} | fail: {summary.get('failed_documents', 0)} | interrupted: {summary.get('interrupted_documents', 0)}",
        f"Ukupno attemptova: {summary.get('total_attempts', 0)} | retry dokumenata: {summary.get('retry_documents', 0)} | dodatni retry attempti: {summary.get('retry_attempts', 0)}",
        f"Success rate: {snapshot.get('success_rate', 0)}% | retry rate: {snapshot.get('retry_rate', 0)}% | fail rate: {snapshot.get('fail_rate', 0)}%",
        f"Prosjek attemptova po dokumentu: {summary.get('avg_attempts_per_document', 0)}",
        f"Prosječno vrijeme od starta do printa: {summary.get('avg_seconds_to_print', 0)} s | najgori slučaj: {summary.get('worst_seconds_to_print', 0)} s",
    ]
    recs = snapshot.get("recommendations") or []
    if recs:
        lines.append("")
        lines.append("Preporuke:")
        lines.extend(f"- {item}" for item in recs)
    return "\n".join(lines)
