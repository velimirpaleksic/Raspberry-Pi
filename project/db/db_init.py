# db/db_init.py
import os
import sqlite3

from project.core import config
from project.core.config import DB_PATH
from project.utils.settings_utils import hash_pin, parse_seed_djelovodni_broj
from project.utils.logging_utils import log_error


def initialize_database():
    """
    Creates the main database structure if not present.
    Should be safe to call multiple times (uses IF NOT EXISTS).
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    seed_prefix, seed_counter, seed_year = parse_seed_djelovodni_broj(config.DJELOVODNI_BROJ_SEED)

    try:
        with sqlite3.connect(DB_PATH, timeout=30) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA foreign_keys=ON;")

            # Legacy table kept for backward compatibility.
            conn.execute("""
            CREATE TABLE IF NOT EXISTS print_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ime TEXT NOT NULL CHECK(length(ime) <=50),
                roditelj TEXT NOT NULL CHECK(length(roditelj) <=50),
                godina INTEGER NOT NULL,
                mjesec INTEGER NOT NULL CHECK(mjesec BETWEEN 1 AND 12),
                dan INTEGER NOT NULL CHECK(dan BETWEEN 1 AND 31),
                mjesto TEXT NOT NULL CHECK(length(mjesto) <=50),
                opstina TEXT NOT NULL CHECK(length(opstina) <=50),
                razred TEXT NOT NULL CHECK(length(razred) <=10),
                struka TEXT NOT NULL CHECK(length(struka) <=50),
                razlog TEXT NOT NULL CHECK(length(razlog) <=50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_created_at ON print_logs(created_at);"
            )

            conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL UNIQUE,
                document_number TEXT NOT NULL UNIQUE,
                counter_value INTEGER NOT NULL,
                year_value INTEGER NOT NULL,
                status TEXT NOT NULL,
                ime TEXT NOT NULL CHECK(length(ime) <= 100),
                roditelj TEXT NOT NULL CHECK(length(roditelj) <= 100),
                godina INTEGER NOT NULL,
                mjesec INTEGER NOT NULL CHECK(mjesec BETWEEN 1 AND 12),
                dan INTEGER NOT NULL CHECK(dan BETWEEN 1 AND 31),
                mjesto TEXT NOT NULL CHECK(length(mjesto) <= 100),
                opstina TEXT NOT NULL CHECK(length(opstina) <= 100),
                razred TEXT NOT NULL CHECK(length(razred) <= 30),
                struka TEXT NOT NULL CHECK(length(struka) <= 100),
                razlog TEXT NOT NULL CHECK(length(razlog) <= 100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                printed_at TIMESTAMP NULL,
                last_error_code TEXT NULL,
                last_error_message TEXT NULL
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_name ON documents(ime);")

            conn.execute("""
            CREATE TABLE IF NOT EXISTS print_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                attempt_no INTEGER NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                finished_at TIMESTAMP NULL,
                status TEXT NOT NULL,
                error_code TEXT NULL,
                error_message TEXT NULL,
                printer_name TEXT NULL,
                docx_path TEXT NULL,
                pdf_path TEXT NULL,
                UNIQUE(job_id, attempt_no),
                FOREIGN KEY(job_id) REFERENCES documents(job_id) ON DELETE CASCADE
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_attempts_job_id ON print_attempts(job_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_attempts_status ON print_attempts(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_attempts_started_at ON print_attempts(started_at DESC);")

            conn.execute("""
            CREATE TABLE IF NOT EXISTS system_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                level TEXT NOT NULL DEFAULT 'info',
                message TEXT NOT NULL,
                job_id TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_system_events_created_at ON system_events(created_at DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_system_events_type ON system_events(event_type);")

            defaults = {
                "counter_prefix": seed_prefix,
                "counter_current": str(seed_counter),
                "year_mode": config.DEFAULT_YEAR_MODE,
                "manual_year": str(config.DEFAULT_MANUAL_YEAR or seed_year),
                "admin_pin_hash": hash_pin(config.DEFAULT_ADMIN_PIN),
                "telegram_enabled": "0",
                "telegram_bot_token": "",
                "telegram_chat_id": "",
                "discord_enabled": "0",
                "discord_webhook_url": "",
                "cleanup_keep_days": "14",
                "cleanup_keep_last": "200",
                "low_disk_threshold_mb": "512",
                "active_printer_name": config.PRINTER_NAME,
                "active_template_path": str(config.TEMPLATE_FILE),
                "setup_completed": "0",
                "template_last_validated_at": "",
                "template_last_validation_ok": "0",
                "template_last_validation_summary": "",
                "template_last_validation_path": "",
                "terminal_name": config.APP_TITLE,
                "terminal_location": "",
                "idle_timeout_ms": str(config.IDLE_TIMEOUT_MS),
                "display_brightness_percent": "100",
                "screensaver_enabled": "0",
                "telegram_last_update_id": "",
                "telegram_last_command": "",
                "telegram_last_command_at": "",
                "telegram_last_command_status": "",
                "support_bundle_last_exported_at": "",
                "support_bundle_last_export_mount": "",
            }

            for key, value in defaults.items():
                conn.execute(
                    "INSERT OR IGNORE INTO settings(key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (key, value),
                )

        print("[DB] Database initialized/checked successfully.")

    except Exception:
        log_error("[DB] Initialization failed")
        raise
