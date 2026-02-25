import time
from pathlib import Path

from project.core import config
from project.db.db_connection import get_connection
from project.utils.file_utils import safe_remove_dir, safe_remove_file
from project.utils.logging_utils import log_error


def maintain_db() -> None:
    """Safely delete oldest rows if table exceeds MAX_ENTRIES using batch deletes."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM print_logs")
            total = cursor.fetchone()[0]

            if total <= config.MAX_ENTRIES:
                return

            overflow = total - config.MAX_ENTRIES
            while overflow > 0:
                delete_count = min(config.BATCH_DELETE_SIZE, overflow)
                cursor.execute(
                    "DELETE FROM print_logs WHERE id IN "
                    "(SELECT id FROM print_logs ORDER BY id ASC LIMIT ?)",
                    (delete_count,),
                )
                conn.commit()
                overflow -= delete_count

            cursor.execute("VACUUM;")

    except Exception as e:
        log_error(f"[DB] Maintenance failed: {e}")


def delete_old_or_empty_logs() -> None:
    """Delete empty or old .log files safely."""
    now = time.time()
    cutoff = now - (config.LOG_RETENTION_DAYS * 24 * 3600)

    for log_file in Path(config.ERROR_LOG_DIR).glob("*.log"):
        try:
            if not log_file.is_file():
                continue
            if log_file.stat().st_size == 0 or log_file.stat().st_mtime < cutoff:
                safe_remove_file(log_file)
        except Exception as e:
            log_error(f"[CLEANUP] Failed to delete log '{log_file}': {e}")


def cleanup_jobs(*, keep_days: int = 14, keep_last: int = 200) -> None:
    """Cleanup old job folders.

    - keep_last: always keep N newest jobs
    - keep_days: delete anything older than N days (except the N newest)
    """
    jobs_dir = Path(config.JOBS_DIR)
    if not jobs_dir.exists():
        return

    now = time.time()
    cutoff = now - (keep_days * 24 * 3600)

    job_dirs = [p for p in jobs_dir.iterdir() if p.is_dir()]
    job_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    protected = set(job_dirs[:keep_last])
    for d in job_dirs[keep_last:]:
        try:
            if d in protected:
                continue
            if d.stat().st_mtime < cutoff:
                safe_remove_dir(d, recursive=True)
        except Exception as e:
            log_error(f"[CLEANUP] Failed to cleanup job '{d}': {e}")


def warn_if_low_disk_space() -> None:
    import shutil

    total, used, free = shutil.disk_usage("/")
    if free < 512 * 1024 * 1024:
        log_error(f"[WARN] Low disk space: {free // (1024 * 1024)} MB free")


def full_cleanup() -> None:
    maintain_db()
    delete_old_or_empty_logs()
    cleanup_jobs()
    warn_if_low_disk_space()


if __name__ == "__main__":
    full_cleanup()
