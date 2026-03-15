from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List

from project.core import config
from project.db.db_connection import get_connection
from project.db.db_init import initialize_database
from project.services.document_service import record_system_event
from project.services.notification_service import send_notification
from project.services.settings_service import get_active_template_path, get_int_setting
from project.services.printer_service import get_active_printer
from project.utils.printing.printer_status import get_printer_readiness


HealthRow = Dict[str, Any]



def _check_database() -> HealthRow:
    try:
        initialize_database()
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"name": "Baza", "ok": True, "code": "OK", "message": "Baza dostupna."}
    except Exception as e:
        return {"name": "Baza", "ok": False, "code": "DB_FAIL", "message": f"Greška baze: {e}"}



def _check_template() -> HealthRow:
    try:
        path = Path(get_active_template_path())
        if not path.exists():
            return {"name": "Template", "ok": False, "code": "TPL_MISSING", "message": f"Template ne postoji: {path}"}
        if path.stat().st_size <= 0:
            return {"name": "Template", "ok": False, "code": "TPL_EMPTY", "message": f"Template je prazan: {path}"}
        return {"name": "Template", "ok": True, "code": "OK", "message": str(path)}
    except Exception as e:
        return {"name": "Template", "ok": False, "code": "TPL_ERROR", "message": str(e)}



def _check_jobs_dir() -> HealthRow:
    try:
        path = Path(config.JOBS_DIR)
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return {"name": "Jobs folder", "ok": True, "code": "OK", "message": str(path)}
    except Exception as e:
        return {"name": "Jobs folder", "ok": False, "code": "JOBS_DIR_FAIL", "message": str(e)}



def _check_command(binary: str, label: str, fail_code: str) -> HealthRow:
    found = shutil.which(binary)
    if found:
        return {"name": label, "ok": True, "code": "OK", "message": found}
    return {"name": label, "ok": False, "code": fail_code, "message": f"'{binary}' nije pronađen u PATH."}



def _check_printer() -> HealthRow:
    printer_name = get_active_printer()
    ready, code, message = get_printer_readiness(printer_name)
    return {
        "name": "Printer",
        "ok": bool(ready),
        "code": code,
        "message": message or f"Printer '{printer_name}' spreman.",
    }



def _check_disk() -> HealthRow:
    try:
        threshold_mb = get_int_setting("low_disk_threshold_mb", 512)
        usage = shutil.disk_usage(config.VAR_DIR)
        free_mb = int(usage.free / (1024 * 1024))
        used_pct = int((usage.used / usage.total) * 100) if usage.total else 0
        ok = free_mb >= threshold_mb
        msg = f"{free_mb} MB slobodno • {used_pct}% zauzeto • prag {threshold_mb} MB"
        return {"name": "Disk", "ok": ok, "code": "OK" if ok else "LOW_DISK", "message": msg}
    except Exception as e:
        return {"name": "Disk", "ok": False, "code": "DISK_FAIL", "message": str(e)}



def run_startup_checks(*, notify_on_failure: bool = False) -> Dict[str, Any]:
    checks: List[HealthRow] = [
        _check_database(),
        _check_template(),
        _check_jobs_dir(),
        _check_command("soffice", "LibreOffice", "SOFFICE_MISSING"),
        _check_command("lp", "CUPS lp", "LP_MISSING"),
        _check_printer(),
        _check_disk(),
    ]
    failed = [c for c in checks if not c["ok"]]
    result = {
        "ok": len(failed) == 0,
        "checks": checks,
        "failed_count": len(failed),
        "summary": "Sistem spreman." if not failed else f"{len(failed)} provjera nije prošlo.",
    }

    if failed:
        for row in failed:
            record_system_event(
                "startup_check_failed",
                f"{row['name']}: {row['code']} - {row['message']}",
                level="warning",
            )
        if notify_on_failure:
            lines = ["⚠️ Terminal startup check failed:"] + [f"- {r['name']}: {r['code']} ({r['message']})" for r in failed]
            send_notification("\n".join(lines))
    else:
        record_system_event("startup_check_ok", "Startup checks passed.")
    return result
