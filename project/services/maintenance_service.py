from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List

from project.core import config
from project.services.document_service import record_system_event
from project.services.printer_service import build_printer_recovery_hint, get_active_printer, send_test_page
from project.services.settings_service import get_int_setting
from project.utils.clean_project import delete_old_or_empty_logs, maintain_db
from project.utils.file_utils import safe_remove_dir
from project.utils.logging_utils import log_error



def cleanup_jobs_with_report(*, keep_days: int, keep_last: int) -> Dict[str, Any]:
    jobs_dir = Path(config.JOBS_DIR)
    if not jobs_dir.exists():
        return {"deleted": 0, "kept": 0, "errors": []}

    import time
    now = time.time()
    cutoff = now - (keep_days * 24 * 3600)
    job_dirs = [p for p in jobs_dir.iterdir() if p.is_dir()]
    job_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    protected = set(job_dirs[:keep_last])
    deleted = 0
    errors: List[str] = []
    for d in job_dirs[keep_last:]:
        try:
            if d in protected:
                continue
            if d.stat().st_mtime < cutoff:
                safe_remove_dir(d, recursive=True)
                deleted += 1
        except Exception as e:
            errors.append(f"{d.name}: {e}")
            log_error(f"[CLEANUP] Failed to cleanup job '{d}': {e}")
    return {"deleted": deleted, "kept": min(len(job_dirs), keep_last), "errors": errors}



def run_cleanup() -> Dict[str, Any]:
    keep_days = get_int_setting("cleanup_keep_days", 14)
    keep_last = get_int_setting("cleanup_keep_last", 200)

    maintain_db()
    delete_old_or_empty_logs()
    jobs_report = cleanup_jobs_with_report(keep_days=keep_days, keep_last=keep_last)

    usage = shutil.disk_usage(config.VAR_DIR)
    free_mb = int(usage.free / (1024 * 1024))
    result = {
        "keep_days": keep_days,
        "keep_last": keep_last,
        "jobs_deleted": jobs_report["deleted"],
        "errors": jobs_report["errors"],
        "free_mb": free_mb,
    }
    record_system_event(
        "cleanup_run",
        f"Cleanup completed: deleted_jobs={result['jobs_deleted']}, free_mb={free_mb}, keep_days={keep_days}, keep_last={keep_last}",
    )
    return result



def run_test_printer(printer_name: str | None = None) -> Dict[str, Any]:
    target = (printer_name or get_active_printer()).strip()
    result = send_test_page(target)
    result.setdefault("printer_name", target)
    result.setdefault("selected_printer", get_active_printer())
    result.setdefault("recovery_hint", build_printer_recovery_hint(result.get('code', '')))
    return result
