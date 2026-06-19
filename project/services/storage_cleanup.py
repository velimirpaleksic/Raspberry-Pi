from __future__ import annotations

import json
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from project.core import config
from project.services.telegram_notify import notify_telegram_async
from project.utils.logging_utils import log_error, log_info


DOC_EXTENSIONS = {".docx", ".pdf"}
_alert_lock = threading.Lock()
_last_alert_at = 0.0
_last_alert_state = "ok"
_periodic_service: PeriodicCleanupService | None = None


@dataclass
class CleanupResult:
    deleted_files: int = 0
    deleted_dirs: int = 0
    bytes_freed: int = 0
    errors: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.errors.append(str(message)[:1000])


@dataclass(frozen=True)
class DiskInfo:
    path: str
    total: int = 0
    used: int = 0
    free: int = 0
    used_percent: float = 0.0
    error: str = ""


def format_bytes(value: int | float | None) -> str:
    try:
        size = float(value or 0)
    except Exception:
        return "unknown"
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    unit = units[0]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            break
        size /= 1024
    return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"


def _safe_resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except Exception:
        return path.absolute()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        resolved = _safe_resolve(path)
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def _job_roots() -> list[Path]:
    return _unique_paths(
        [
            config.JOBS_DIR,
            config.PROJECT_ROOT / "var" / "jobs",
            config.PROJECT_ROOT / "var" / config.APP_ID / "jobs",
        ]
    )


def _log_roots() -> list[Path]:
    return _unique_paths(
        [
            config.ERROR_LOG_DIR,
            config.PROJECT_ROOT / "var" / "logs",
            config.PROJECT_ROOT / "var" / config.APP_ID / "logs",
        ]
    )


def _allowed_roots(*extra: Path) -> list[Path]:
    roots = [*_job_roots(), *_log_roots(), config.PROJECT_ROOT / "var", *extra]
    return [_safe_resolve(path) for path in _unique_paths(roots)]


def _is_allowed(path: Path, roots: list[Path]) -> bool:
    resolved = _safe_resolve(path)
    return any(_is_within(resolved, root) for root in roots)


def _file_age_seconds(path: Path, now: float) -> float:
    try:
        return max(0.0, now - path.stat().st_mtime)
    except Exception:
        return 0.0


def _read_job_json(job_dir: Path) -> dict[str, Any]:
    job_json = job_dir / "job.json"
    try:
        if job_json.is_file() and not job_json.is_symlink():
            data = json.loads(job_json.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception as exc:
        log_error(f"[Cleanup] Could not read {job_json}: {exc}")
    return {}


def _job_age_seconds(job_dir: Path, payload: dict[str, Any], now: float) -> float:
    created_at = payload.get("created_at")
    if isinstance(created_at, (int, float)):
        return max(0.0, now - float(created_at))
    return _file_age_seconds(job_dir, now)


def _delete_file(path: Path, result: CleanupResult, roots: list[Path]) -> bool:
    try:
        if path.is_symlink():
            return False
        if not path.is_file():
            return False
        if not _is_allowed(path, roots):
            result.add_error(f"Blocked deletion outside app-owned paths: {path}")
            return False
        size = path.stat().st_size
        path.unlink()
        result.deleted_files += 1
        result.bytes_freed += max(0, int(size))
        return True
    except Exception as exc:
        message = f"Failed to delete file {path}: {exc}"
        result.add_error(message)
        log_error(f"[Cleanup] {message}")
        return False


def _delete_empty_dir(path: Path, result: CleanupResult, roots: list[Path]) -> bool:
    try:
        if path.is_symlink() or not path.is_dir():
            return False
        if not _is_allowed(path, roots):
            result.add_error(f"Blocked directory removal outside app-owned paths: {path}")
            return False
        path.rmdir()
        result.deleted_dirs += 1
        return True
    except OSError:
        return False
    except Exception as exc:
        message = f"Failed to remove directory {path}: {exc}"
        result.add_error(message)
        log_error(f"[Cleanup] {message}")
        return False


def _cleanup_job_root(job_root: Path, result: CleanupResult, roots: list[Path], *, pressure: bool, now: float) -> None:
    if not job_root.exists() or job_root.is_symlink() or not job_root.is_dir():
        return
    if not _is_allowed(job_root, roots):
        result.add_error(f"Blocked cleanup outside app-owned job root: {job_root}")
        return

    success_retention = max(0, config.SUCCESSFUL_JOB_DOCUMENT_RETENTION_MINUTES) * 60
    failed_retention = max(0, config.FAILED_JOB_RETENTION_DAYS) * 24 * 60 * 60
    job_json_retention = max(0, config.JOB_JSON_RETENTION_DAYS) * 24 * 60 * 60

    for job_dir in list(job_root.iterdir()):
        if job_dir.is_symlink() or not job_dir.is_dir():
            continue
        if not _is_allowed(job_dir, roots):
            continue

        payload = _read_job_json(job_dir)
        state = str(payload.get("state") or "").lower()
        is_success = state == "done" or bool(payload.get("printed")) or bool(payload.get("documents_cleaned"))
        is_failed = state == "failed"
        job_age = _job_age_seconds(job_dir, payload, now)

        for path in list(job_dir.rglob("*")):
            if path.is_symlink() or not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix not in DOC_EXTENSIONS:
                continue

            file_age = _file_age_seconds(path, now)
            should_delete = False
            if is_success:
                should_delete = file_age >= success_retention
            elif is_failed:
                should_delete = file_age >= failed_retention
            elif pressure:
                should_delete = file_age >= failed_retention

            if should_delete:
                _delete_file(path, result, roots)

        job_json = job_dir / "job.json"
        if job_json.exists() and not job_json.is_symlink() and job_age >= job_json_retention:
            remaining_docs = [
                path
                for path in job_dir.rglob("*")
                if path.is_file() and not path.is_symlink() and path.suffix.lower() in DOC_EXTENSIONS
            ]
            if not remaining_docs:
                _delete_file(job_json, result, roots)

        _delete_empty_dir(job_dir, result, roots)


def _cleanup_logs(result: CleanupResult, roots: list[Path], *, now: float) -> None:
    retention = max(1, config.LOG_RETENTION_DAYS) * 24 * 60 * 60
    for log_root in _log_roots():
        if not log_root.exists() or log_root.is_symlink() or not log_root.is_dir():
            continue
        if not _is_allowed(log_root, roots):
            continue
        for path in list(log_root.iterdir()):
            if path.is_symlink() or not path.is_file():
                continue
            name = path.name.lower()
            if not (name.endswith(".log") or ".log." in name or name.startswith("error_")):
                continue
            if _file_age_seconds(path, now) >= retention:
                _delete_file(path, result, roots)


def _dir_size_without_symlinks(path: Path) -> int:
    total = 0
    for child in path.rglob("*"):
        try:
            if child.is_symlink() or not child.is_file():
                continue
            total += child.stat().st_size
        except Exception:
            continue
    return total


def _cleanup_pycache(result: CleanupResult, roots: list[Path]) -> None:
    project_root = _safe_resolve(config.PROJECT_ROOT)
    for path in list(project_root.rglob("__pycache__")):
        try:
            if path.is_symlink() or not path.is_dir():
                continue
            if not _is_within(path, project_root):
                continue
            size = _dir_size_without_symlinks(path)
            shutil.rmtree(path)
            result.deleted_dirs += 1
            result.bytes_freed += max(0, int(size))
        except Exception as exc:
            message = f"Failed to remove pycache {path}: {exc}"
            result.add_error(message)
            log_error(f"[Cleanup] {message}")


def run_cleanup(*, pressure: bool = False, include_pycache: bool = False, force: bool = False, reason: str = "scheduled") -> CleanupResult:
    result = CleanupResult()
    if not config.CLEANUP_ENABLED and not force and not pressure:
        return result

    roots = _allowed_roots(config.PROJECT_ROOT)
    now = time.time()
    try:
        for job_root in _job_roots():
            _cleanup_job_root(job_root, result, roots, pressure=pressure, now=now)
        _cleanup_logs(result, roots, now=now)
        if include_pycache or pressure:
            _cleanup_pycache(result, roots)
        log_info(
            "[Cleanup] %s deleted %s file(s), %s dir(s), freed %s, errors=%s"
            % (reason, result.deleted_files, result.deleted_dirs, format_bytes(result.bytes_freed), len(result.errors))
        )
    except Exception as exc:
        result.add_error(str(exc))
        log_error(f"[Cleanup] Cleanup failed: {exc}")
    return result


def cleanup_print_job_documents(job_dir: Path, docx_path: Path | None, pdf_path: Path | None) -> dict[str, Any]:
    result = CleanupResult()
    roots = [_safe_resolve(job_dir)]
    metadata: dict[str, Any] = {
        "documents_cleaned": False,
        "docx_deleted": False,
        "pdf_deleted": False,
        "cleaned_at": time.time(),
    }

    for label, path in (("docx", docx_path), ("pdf", pdf_path)):
        if path is None:
            continue
        path = Path(path)
        if path.suffix.lower() not in DOC_EXTENSIONS:
            result.add_error(f"Skipped unexpected {label.upper()} cleanup path: {path}")
            continue
        deleted = _delete_file(path, result, roots)
        metadata[f"{label}_deleted"] = bool(deleted)

    metadata["documents_cleaned"] = bool(metadata["docx_deleted"] and metadata["pdf_deleted"])
    metadata["cleanup_deleted_files"] = result.deleted_files
    metadata["cleanup_bytes_freed"] = result.bytes_freed
    if result.errors:
        metadata["cleanup_errors"] = result.errors
    return metadata


def _disk_info(path: Path) -> DiskInfo:
    try:
        usage = shutil.disk_usage(str(path))
        used = usage.total - usage.free
        used_percent = 0.0 if usage.total <= 0 else (used / usage.total) * 100
        return DiskInfo(str(path), usage.total, used, usage.free, used_percent)
    except Exception as exc:
        return DiskInfo(str(path), error=str(exc))


def collect_storage_report() -> dict[str, DiskInfo]:
    return {
        "root": _disk_info(Path("/")),
        "app_data": _disk_info(config.VAR_DIR),
    }


def _format_disk(label: str, info: DiskInfo) -> str:
    if info.error:
        return f"{label}: error {info.error}"
    return (
        f"{label}: free {format_bytes(info.free)} / total {format_bytes(info.total)} "
        f"/ used {info.used_percent:.0f}%"
    )


def _storage_state(report: dict[str, DiskInfo]) -> tuple[str, list[str]]:
    warning_reasons: list[str] = []
    critical_reasons: list[str] = []
    warning_percent = max(1, config.STORAGE_ALERT_USED_PERCENT)
    critical_percent = max(warning_percent, config.STORAGE_CRITICAL_USED_PERCENT)
    min_free_bytes = max(0, config.STORAGE_ALERT_MIN_FREE_MB) * 1024 * 1024

    for label, info in report.items():
        if info.error:
            continue
        if info.used_percent >= critical_percent:
            critical_reasons.append(f"{label} used {info.used_percent:.0f}% >= {critical_percent}%")
        elif info.used_percent >= warning_percent:
            warning_reasons.append(f"{label} used {info.used_percent:.0f}% >= {warning_percent}%")
        if min_free_bytes and info.free <= min_free_bytes:
            warning_reasons.append(f"{label} free {format_bytes(info.free)} <= {format_bytes(min_free_bytes)}")

    if critical_reasons:
        return "critical", critical_reasons + warning_reasons
    if warning_reasons:
        return "warning", warning_reasons
    return "ok", []


def _should_send_alert(state: str) -> bool:
    global _last_alert_at, _last_alert_state
    if state == "ok":
        with _alert_lock:
            _last_alert_state = "ok"
        return False

    cooldown = max(0, config.STORAGE_ALERT_COOLDOWN_MINUTES) * 60
    now = time.monotonic()
    with _alert_lock:
        should_send = state != _last_alert_state or now - _last_alert_at >= cooldown
        if should_send:
            _last_alert_at = now
            _last_alert_state = state
        return should_send


def format_cleanup_summary(result: CleanupResult) -> str:
    lines = [
        f"Deleted files: {result.deleted_files}",
        f"Deleted directories: {result.deleted_dirs}",
        f"Freed: {format_bytes(result.bytes_freed)}",
    ]
    if result.errors:
        lines.append(f"Errors: {len(result.errors)}")
        lines.extend(result.errors[:5])
    return "\n".join(lines)


def format_storage_report(report: dict[str, DiskInfo]) -> str:
    return "\n".join(
        [
            _format_disk("/", report["root"]),
            _format_disk("App data", report["app_data"]),
        ]
    )


def _format_free_mib(value: int) -> str:
    return f"{value / (1024 * 1024):.0f} MiB"


def _compact_disk_line(label: str, info: DiskInfo) -> str:
    if info.error:
        return f"{label}: error"
    return f"{label}: free {_format_free_mib(info.free)}, used {info.used_percent:.0f}%"


def check_storage_pressure(*, reason: str = "periodic", notify: bool = True) -> tuple[str, CleanupResult | None]:
    before = collect_storage_report()
    state, reasons = _storage_state(before)
    cleanup_result: CleanupResult | None = None

    if state == "critical" and config.STORAGE_CLEANUP_ON_PRESSURE:
        cleanup_result = run_cleanup(pressure=True, include_pycache=True, reason=f"storage-pressure:{reason}")

    after = collect_storage_report() if cleanup_result is not None else before
    should_notify = _should_send_alert(state) if notify else False
    if state == "critical" and should_notify:
        title = "Storage critical on Uvjerenja Terminal"
        deleted_files = cleanup_result.deleted_files if cleanup_result is not None else 0
        bytes_freed = cleanup_result.bytes_freed if cleanup_result is not None else 0
        errors = len(cleanup_result.errors) if cleanup_result is not None else 0
        lines = [
            title,
            f"Reason: {reason}",
            _compact_disk_line("/", after["root"]),
            _compact_disk_line("App data", after["app_data"]),
            f"Critical threshold: {config.STORAGE_CRITICAL_USED_PERCENT}% used",
            f"Cleanup run: {'yes' if cleanup_result is not None else 'no'}",
            f"Deleted: {deleted_files} file(s), freed {format_bytes(bytes_freed)}",
        ]
        if reasons:
            lines.append("Trigger: " + "; ".join(reasons[:2]))
        if errors:
            lines.append(f"Cleanup errors: {errors}")
        notify_telegram_async("\n".join(lines), kind="error")

    return state, cleanup_result


def check_storage_pressure_async(*, reason: str = "async") -> None:
    def worker() -> None:
        try:
            check_storage_pressure(reason=reason, notify=True)
        except Exception as exc:
            log_error(f"[Cleanup] Storage pressure check failed: {exc}")

    threading.Thread(target=worker, name="storage-pressure-check", daemon=True).start()


class PeriodicCleanupService:
    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="storage-cleanup", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run(self) -> None:
        cleanup_interval = max(60, config.CLEANUP_INTERVAL_MINUTES * 60)
        storage_interval = max(60, config.STORAGE_CHECK_INTERVAL_MINUTES * 60)
        next_cleanup = 0.0
        next_storage = 0.0

        while not self._stop_event.is_set():
            now = time.monotonic()
            if now >= next_cleanup:
                try:
                    run_cleanup(reason="startup" if next_cleanup == 0.0 else "periodic")
                except Exception as exc:
                    log_error(f"[Cleanup] Periodic cleanup failed: {exc}")
                next_cleanup = now + cleanup_interval

            if now >= next_storage:
                try:
                    check_storage_pressure(reason="startup" if next_storage == 0.0 else "periodic", notify=True)
                except Exception as exc:
                    log_error(f"[Cleanup] Periodic storage check failed: {exc}")
                next_storage = now + storage_interval

            wait_seconds = max(30, min(next_cleanup, next_storage) - time.monotonic())
            self._stop_event.wait(wait_seconds)


def start_periodic_cleanup() -> PeriodicCleanupService | None:
    global _periodic_service
    if _periodic_service is not None:
        return _periodic_service
    if not config.CLEANUP_ENABLED and not config.STORAGE_CLEANUP_ON_PRESSURE:
        return None
    _periodic_service = PeriodicCleanupService()
    _periodic_service.start()
    return _periodic_service
