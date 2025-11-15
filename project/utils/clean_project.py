# utils/clean_project.py
import time
from pathlib import Path

from project.core.config import ERROR_LOG_DIR, PRINT_QUEUE_DIR, LOG_RETENTION_DAYS, MAX_ENTRIES, BATCH_DELETE_SIZE
from project.db.db_connection import get_connection
from project.utils.file_utils import safe_remove_file
from project.utils.logging_utils import error_logging


def maintain_db():
    """Safely delete oldest rows if table exceeds MAX_ENTRIES using batch deletes."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Get approximate count (might be slow)
            cursor.execute("SELECT COUNT(*) FROM print_logs")
            total = cursor.fetchone()[0]

            if total <= MAX_ENTRIES:
                print(f"[DB] {total} entries - within limit.")
                return

            overflow = total - MAX_ENTRIES
            print(f"[DB] Deleting {overflow} oldest rows in batches of {BATCH_DELETE_SIZE}...")

            while overflow > 0:
                delete_count = min(BATCH_DELETE_SIZE, overflow)
                cursor.execute(
                    "DELETE FROM print_logs WHERE id IN "
                    "(SELECT id FROM print_logs ORDER BY id ASC LIMIT ?)",
                    (delete_count,)
                )
                conn.commit()
                overflow -= delete_count

            # VACUUM - only once at the end
            cursor.execute("VACUUM;")
            print("[DB] Maintenance complete.")

    except Exception as e:
        error_logging(f"[DB] Maintenance failed: {e}")


def delete_old_or_empty_logs():
    """Delete empty or old .log files safely"""
    now = time.time()
    cutoff = now - (LOG_RETENTION_DAYS * 24 * 3600)
    deleted_files = []

    for log_file in Path(ERROR_LOG_DIR).glob("*.log"):
        try:
            if not log_file.is_file():
                continue

            # Delete if empty or older than cutoff
            if log_file.stat().st_size == 0 or log_file.stat().st_mtime < cutoff:
                safe_remove_file(log_file)
                deleted_files.append(log_file.name)

        except Exception as e:
            error_logging(f"[CLEANUP] Failed to delete log '{log_file}': {e}")

    if deleted_files:
        print(f"[CLEANUP] Deleted logs: {', '.join(deleted_files)}")
    else:
        print("[CLEANUP] No old or empty logs to delete.")


def delete_print_queue():
    """Delete all .docx and .pdf in print_queue folder safely"""
    if not Path(PRINT_QUEUE_DIR).exists():
        print(f"[CLEANUP] Print queue '{PRINT_QUEUE_DIR}' does not exist.")
        return

    deleted_files, skipped_files = [], []

    for ext in ("*.docx", "*.pdf"):
        for file_path in Path(PRINT_QUEUE_DIR).glob(ext):
            try:
                safe_remove_file(file_path)
                deleted_files.append(file_path.name)
            except Exception:
                skipped_files.append(file_path.name)

    if deleted_files:
        print(f"[CLEANUP] Deleted print queue files: {', '.join(deleted_files)}")
    if skipped_files:
        error_logging(f"[CLEANUP] Skipped locked files: {', '.join(skipped_files)}")


def warn_if_low_disk_space():
    import shutil
    total, used, free = shutil.disk_usage("/")

    if free < 512*1024*1024:  # Less than 512MB (0.5GB) free
        print(f"[WARN] Low disk space: {free // (1024*1024)} MB free, consider cleanup")


def full_cleanup():
    print("[CLEANUP] Starting project cleanup...")
    maintain_db()
    delete_old_or_empty_logs()
    delete_print_queue()
    warn_if_low_disk_space()
    print("[CLEANUP] Cleanup complete.")


if __name__ == "__main__":
    full_cleanup()