from __future__ import annotations

import datetime
from typing import Optional

from project.core import config
from project.db.db_connection import get_connection
from project.db.db_init import initialize_database
from project.utils.logging_utils import log_error
from project.utils.settings_utils import hash_pin, parse_seed_djelovodni_broj


VALID_YEAR_MODES = {"auto", "manual"}


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    initialize_database()
    try:
        with get_connection() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default
    except Exception as e:
        log_error(f"[SETTINGS] Failed to read '{key}': {e}")
        return default


def set_setting(key: str, value: str) -> None:
    initialize_database()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO settings(key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
            (key, value),
        )


def get_effective_year() -> int:
    year_mode = (get_setting("year_mode", config.DEFAULT_YEAR_MODE) or "auto").lower()
    if year_mode == "manual":
        manual_year = get_setting("manual_year")
        if manual_year and manual_year.isdigit():
            return int(manual_year)
    return datetime.datetime.now().year


def get_year_mode() -> str:
    value = (get_setting("year_mode", config.DEFAULT_YEAR_MODE) or "auto").lower()
    return value if value in VALID_YEAR_MODES else "auto"


def set_year_mode(mode: str) -> str:
    normalized = (mode or "auto").strip().lower()
    if normalized not in VALID_YEAR_MODES:
        normalized = "auto"
    set_setting("year_mode", normalized)
    return normalized


def get_manual_year() -> int:
    value = get_setting("manual_year", str(config.DEFAULT_MANUAL_YEAR))
    try:
        return int(value) if value is not None else int(config.DEFAULT_MANUAL_YEAR)
    except Exception:
        return int(config.DEFAULT_MANUAL_YEAR)


def set_manual_year(year: int) -> int:
    safe_year = max(2000, min(2099, int(year)))
    set_setting("manual_year", str(safe_year))
    return safe_year


def get_counter_prefix() -> str:
    seed_prefix, _, _ = parse_seed_djelovodni_broj(config.DJELOVODNI_BROJ_SEED)
    return get_setting("counter_prefix", seed_prefix) or seed_prefix


def get_counter_current() -> int:
    _, seed_counter, _ = parse_seed_djelovodni_broj(config.DJELOVODNI_BROJ_SEED)
    value = get_setting("counter_current", str(seed_counter))
    try:
        return int(value) if value is not None else seed_counter
    except Exception:
        return seed_counter


def set_counter_current(value: int) -> int:
    safe_value = max(0, int(value))
    set_setting("counter_current", str(safe_value))
    return safe_value


def verify_admin_pin(candidate_pin: str) -> bool:
    stored = get_setting("admin_pin_hash")
    if not stored:
        return False
    return stored == hash_pin(candidate_pin)


def update_admin_pin(new_pin: str) -> None:
    normalized = (new_pin or "").strip()
    if len(normalized) < 4 or not normalized.isdigit():
        raise ValueError("PIN mora imati najmanje 4 cifre.")
    set_setting("admin_pin_hash", hash_pin(normalized))


def build_next_document_number_preview() -> str:
    prefix = get_counter_prefix()
    next_counter = get_counter_current() + 1
    year = get_effective_year()
    return f"{prefix}-{next_counter}/{year % 100:02d}"



def get_bool_setting(key: str, default: bool = False) -> bool:
    value = get_setting(key)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def set_bool_setting(key: str, value: bool) -> bool:
    set_setting(key, "1" if value else "0")
    return bool(value)




def get_active_printer_setting() -> str:
    return (get_setting("active_printer_name", config.PRINTER_NAME) or config.PRINTER_NAME).strip()


def set_active_printer_setting(printer_name: str) -> str:
    normalized = (printer_name or "").strip()
    if not normalized:
        raise ValueError("Printer name ne može biti prazan.")
    set_setting("active_printer_name", normalized)
    return normalized



def get_active_template_path() -> str:
    return (get_setting("active_template_path", str(config.TEMPLATE_FILE)) or str(config.TEMPLATE_FILE)).strip()


def set_active_template_path(template_path: str) -> str:
    normalized = str(template_path or "").strip()
    if not normalized:
        raise ValueError("Template path ne može biti prazan.")
    set_setting("active_template_path", normalized)
    return normalized


def is_setup_completed() -> bool:
    return get_bool_setting("setup_completed", False)


def set_setup_completed(value: bool) -> bool:
    set_bool_setting("setup_completed", bool(value))
    return bool(value)


def get_int_setting(key: str, default: int) -> int:
    value = get_setting(key, str(default))
    try:
        return int(str(value)) if value is not None else int(default)
    except Exception:
        return int(default)
