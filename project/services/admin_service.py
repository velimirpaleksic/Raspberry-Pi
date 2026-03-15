from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List
import datetime

from project.core import config
from project.db.db_connection import get_connection
from project.db.db_init import initialize_database
from project.services.history_service import get_daily_summary
from project.services.settings_service import (
    build_next_document_number_preview,
    get_active_template_path,
    get_bool_setting,
    get_counter_current,
    get_counter_prefix,
    get_effective_year,
    get_manual_year,
    get_setting,
    get_year_mode,
    is_setup_completed,
)
from project.utils.printing.printer_status import get_printer_readiness
from project.services.printer_service import get_active_printer, get_printer_diagnostics



def _row_to_dict(row) -> dict:
    return dict(row) if row is not None else {}



def get_admin_snapshot() -> Dict[str, Any]:
    initialize_database()
    stats: Dict[str, Any] = {
        "counter_prefix": get_counter_prefix(),
        "counter_current": get_counter_current(),
        "year_mode": get_year_mode(),
        "manual_year": get_manual_year(),
        "effective_year": get_effective_year(),
        "next_document_number": build_next_document_number_preview(),
        "printer_ready": None,
        "printer_code": "UNKNOWN",
        "printer_message": "",
        "disk_free_gb": 0.0,
        "disk_used_percent": 0,
        "today_attempts": 0,
        "today_printed": 0,
        "today_failed": 0,
        "last_failures": [],
        "recent_events": [],
        "daily_summary": [],
        "template_path": get_active_template_path(),
        "var_dir": str(config.VAR_DIR),
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "active_printer": get_active_printer(),
    }

    ready, code, message = get_printer_readiness(stats["active_printer"])
    stats["printer_ready"] = ready
    stats["printer_code"] = code
    stats["printer_message"] = message

    try:
        usage = shutil.disk_usage(config.VAR_DIR)
        stats["disk_free_gb"] = round(usage.free / (1024 ** 3), 2)
        stats["disk_used_percent"] = int((usage.used / usage.total) * 100) if usage.total else 0
    except Exception:
        pass

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS today_attempts,
                SUM(CASE WHEN status = 'printed' THEN 1 ELSE 0 END) AS today_printed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS today_failed
            FROM print_attempts
            WHERE date(started_at, 'localtime') = date('now', 'localtime')
            """
        ).fetchone()
        if row:
            stats["today_attempts"] = int(row["today_attempts"] or 0)
            stats["today_printed"] = int(row["today_printed"] or 0)
            stats["today_failed"] = int(row["today_failed"] or 0)

        failures = conn.execute(
            """
            SELECT d.document_number, d.ime, d.last_error_message, d.updated_at
            FROM documents d
            WHERE d.status = 'failed'
            ORDER BY d.updated_at DESC
            LIMIT 5
            """
        ).fetchall()
        stats["last_failures"] = [_row_to_dict(r) for r in failures]

        events = conn.execute(
            """
            SELECT event_type, level, message, created_at
            FROM system_events
            ORDER BY created_at DESC, id DESC
            LIMIT 8
            """
        ).fetchall()
        stats["recent_events"] = [_row_to_dict(r) for r in events]

    stats["daily_summary"] = get_daily_summary(7)
    return stats



def get_recent_documents(limit: int = 10) -> List[dict]:
    initialize_database()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT document_number, ime, status, created_at, printed_at
            FROM documents
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def get_setup_checklist() -> Dict[str, Any]:
    initialize_database()
    active_printer = get_active_printer()
    active_template = Path(get_active_template_path())
    printer_tested_at = (get_setting("printer_last_tested_at", "") or "").strip()
    printer_tested_printer = (get_setting("printer_last_tested_printer", "") or "").strip()
    backup_tested_at = (get_setting("backup_last_tested_at", "") or "").strip()
    notifications_tested_at = (get_setting("notifications_last_tested_at", "") or "").strip()
    notifications_enabled = get_bool_setting("telegram_enabled", False) or get_bool_setting("discord_enabled", False)
    template_validation_ok = (get_setting("template_last_validation_ok", "0") or "0") == "1"
    template_validation_at = (get_setting("template_last_validated_at", "") or "").strip()
    template_validation_summary = (get_setting("template_last_validation_summary", "") or "").strip()

    items = [
        {
            "key": "pin_set",
            "label": "PIN postavljen",
            "ok": bool((get_setting("admin_pin_hash", "") or "").strip()),
            "detail": "Admin PIN postoji u bazi." if (get_setting("admin_pin_hash", "") or "").strip() else "PIN nije postavljen.",
        },
        {
            "key": "printer_tested",
            "label": "Printer testiran",
            "ok": bool(printer_tested_at and active_printer and active_printer != config.PRINTER_NAME and printer_tested_printer == active_printer),
            "detail": f"Aktivni printer: {active_printer or '-'} | zadnji test: {printer_tested_at or 'nikad'}",
        },
        {
            "key": "template_valid",
            "label": "Template validan",
            "ok": active_template.exists() and active_template.is_file() and active_template.suffix.lower() == ".docx" and template_validation_ok,
            "detail": (template_validation_summary or str(active_template)) + (f" | validirano: {template_validation_at}" if template_validation_at else ""),
        },
        {
            "key": "backup_tested",
            "label": "Backup testiran",
            "ok": bool(backup_tested_at),
            "detail": backup_tested_at or "Backup export/restore još nije urađen.",
        },
        {
            "key": "notifications_tested",
            "label": "Notifikacije testirane",
            "ok": bool(notifications_enabled and notifications_tested_at),
            "detail": (notifications_tested_at if notifications_tested_at else "Uradi test Telegram/Discord notifikacije."),
        },
        {
            "key": "setup_completed",
            "label": "Setup completed",
            "ok": bool(is_setup_completed()),
            "detail": "Wizard završen." if is_setup_completed() else "Wizard još nije označen završenim.",
        },
    ]

    ok_count = sum(1 for item in items if item["ok"])
    total = len(items)
    score_percent = int(round((ok_count / total) * 100)) if total else 0
    missing = [item["label"] for item in items if not item["ok"]]
    return {
        "items": items,
        "ok_count": ok_count,
        "total": total,
        "score_percent": score_percent,
        "missing": missing,
        "summary": f"Setup score: {score_percent}% ({ok_count}/{total})",
        "printer_diagnostics_preview": get_printer_diagnostics(active_printer),
    }
