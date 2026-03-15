from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

from project.core import config
from project.db.db_connection import get_connection
from project.db.db_init import initialize_database
from project.services.admin_service import get_admin_snapshot, get_setup_checklist
from project.services.analytics_service import get_analytics_snapshot
from project.services.device_service import get_terminal_settings_snapshot
from project.services.document_service import record_system_event
from project.services.health_service import run_startup_checks
from project.services.network_service import get_network_snapshot
from project.services.printer_service import get_active_printer, get_printer_diagnostics
from project.services.readiness_service import build_readiness_snapshot
from project.services.settings_service import get_setting, set_setting

SUPPORT_PREFIX = "uvjerenja_support"


def _safe_write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _safe_write_text(path: Path, text: str) -> None:
    path.write_text(str(text or ""), encoding="utf-8")


def _settings_snapshot() -> Dict[str, str]:
    initialize_database()
    with get_connection() as conn:
        rows = conn.execute("SELECT key, value FROM settings ORDER BY key ASC").fetchall()
        return {str(r["key"]): str(r["value"]) for r in rows}


def _recent_events(limit: int = 50) -> List[Dict[str, Any]]:
    initialize_database()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT event_type, level, message, job_id, created_at
            FROM system_events
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        return [dict(r) for r in rows]


def _copy_logs(target_dir: Path) -> List[str]:
    copied: List[str] = []
    target_dir.mkdir(parents=True, exist_ok=True)
    if not config.ERROR_LOG_DIR.exists():
        return copied
    for path in sorted(config.ERROR_LOG_DIR.glob("*.log"))[-20:]:
        if path.is_file():
            dest = target_dir / path.name
            shutil.copy2(path, dest)
            copied.append(dest.name)
    return copied


def export_support_bundle_to_mount(mount_path: str, *, analytics_days: int = 30) -> Dict[str, Any]:
    base = Path(mount_path)
    if not base.exists() or not base.is_dir():
        raise ValueError("USB lokacija nije dostupna.")

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    bundle = base / f"{SUPPORT_PREFIX}_{timestamp}"
    bundle.mkdir(parents=True, exist_ok=True)

    health = run_startup_checks(notify_on_failure=False)
    readiness = build_readiness_snapshot()
    analytics = get_analytics_snapshot(int(analytics_days))
    terminal = get_terminal_settings_snapshot()
    network = get_network_snapshot()
    admin = get_admin_snapshot()
    checklist = get_setup_checklist()
    diagnostics = get_printer_diagnostics(get_active_printer())
    settings = _settings_snapshot()
    events = _recent_events(80)

    _safe_write_json(bundle / "health.json", health)
    _safe_write_json(bundle / "readiness.json", readiness)
    _safe_write_json(bundle / "analytics.json", analytics)
    _safe_write_json(bundle / "settings_snapshot.json", settings)
    _safe_write_json(bundle / "terminal_snapshot.json", terminal)
    _safe_write_json(bundle / "network_snapshot.json", network)
    _safe_write_json(bundle / "admin_snapshot.json", admin)
    _safe_write_json(bundle / "setup_checklist.json", checklist)
    _safe_write_json(bundle / "printer_diagnostics.json", diagnostics)
    _safe_write_json(bundle / "system_events.json", events)

    summary_lines = [
        f"Bundle created: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"App ID: {config.APP_ID}",
        f"Terminal: {terminal.get('terminal_name', '-')} | {terminal.get('terminal_location', '-')}",
        f"Printer: {admin.get('active_printer', '-')} | code={admin.get('printer_code', '-')}",
        f"Readiness: {readiness.get('state', '-')} | score={readiness.get('readiness_score', 0)}%",
        f"Health: {'OK' if health.get('ok') else 'FAIL'} | failed={health.get('failed_count', 0)}",
        f"Notifications tested: {get_setting('notifications_last_tested_at', '') or 'nikad'}",
        f"Backup tested: {get_setting('backup_last_tested_at', '') or 'nikad'}",
        "",
        "Top errors:",
    ]
    for row in analytics.get("top_errors", [])[:6]:
        summary_lines.append(f"- {row.get('error_code')}: {row.get('hits')}x | {row.get('error_message')}")
    if not analytics.get("top_errors"):
        summary_lines.append("- nema zabilježenih top grešaka")
    _safe_write_text(bundle / "support_summary.txt", "\n".join(summary_lines))

    copied_logs = _copy_logs(bundle / "logs")

    manifest = {
        "created_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "bundle_path": str(bundle),
        "app_id": config.APP_ID,
        "analytics_days": int(analytics_days),
        "copied_logs": copied_logs,
        "files": sorted(p.name for p in bundle.iterdir()),
    }
    _safe_write_json(bundle / "manifest.json", manifest)
    set_setting("support_bundle_last_exported_at", dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    set_setting("support_bundle_last_export_mount", str(base))
    record_system_event("support_bundle_exported", f"Support bundle exported: {bundle}")
    return {
        "ok": True,
        "bundle_path": str(bundle),
        "message": f"Support bundle izvezen na USB: {bundle}",
        "copied_logs": copied_logs,
        "files": manifest["files"],
    }
