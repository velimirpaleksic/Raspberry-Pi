from __future__ import annotations

from typing import Any, Dict, List

from project.core import config
from project.db.db_connection import get_connection
from project.db.db_init import initialize_database
from project.services.document_service import record_system_event
from project.services.network_service import forget_wifi_connection, get_saved_wifi_connections
from project.services.settings_service import set_active_template_path, set_bool_setting, set_counter_current, set_manual_year, set_setting, set_year_mode
from project.utils.settings_utils import hash_pin, parse_seed_djelovodni_broj


def _reset_common_markers() -> None:
    for key in [
        "printer_last_tested_at",
        "printer_last_tested_printer",
        "backup_last_tested_at",
        "backup_last_test_mount",
        "backup_last_restore_mode",
        "notifications_last_tested_at",
        "notifications_last_test_source",
        "template_last_validated_at",
        "template_last_validation_ok",
        "template_last_validation_summary",
        "template_last_validation_path",
        "display_last_applied_at",
        "network_last_connected_ssid",
        "network_last_tested_at",
        "telegram_last_update_id",
        "telegram_last_command_at",
        "telegram_last_command",
        "telegram_last_command_status",
    ]:
        set_setting(key, "")


def reset_setup_status_only() -> Dict[str, Any]:
    set_bool_setting("setup_completed", False)
    _reset_common_markers()
    record_system_event("factory_reset_setup_status", "Setup status reset through factory mode.", level="warning")
    return {"ok": True, "message": "Setup status je resetovan. Wizard će se ponovo nuditi na startu."}


def clear_bindings(*, clear_wifi: bool = True, clear_printer: bool = True) -> Dict[str, Any]:
    forgotten: List[Dict[str, Any]] = []
    if clear_printer:
        set_setting("active_printer_name", config.PRINTER_NAME)
        set_setting("printer_last_tested_at", "")
        set_setting("printer_last_tested_printer", "")
    if clear_wifi:
        for row in get_saved_wifi_connections():
            forgotten.append(forget_wifi_connection(str(row.get("name") or "")))
    record_system_event(
        "factory_clear_bindings",
        f"Bindings cleared: wifi={int(clear_wifi)} printer={int(clear_printer)} forgotten_wifi={sum(1 for r in forgotten if r.get('ok'))}",
        level="warning",
    )
    return {
        "ok": True,
        "message": "Wi‑Fi i printer binding su očišćeni." if clear_wifi and clear_printer else "Binding čišćenje završeno.",
        "wifi_results": forgotten,
        "active_printer": config.PRINTER_NAME,
    }


def clear_configuration(*, preserve_database: bool = True) -> Dict[str, Any]:
    seed_prefix, seed_counter, seed_year = parse_seed_djelovodni_broj(config.DJELOVODNI_BROJ_SEED)
    set_setting("counter_prefix", seed_prefix)
    set_counter_current(seed_counter)
    set_year_mode(config.DEFAULT_YEAR_MODE)
    set_manual_year(int(config.DEFAULT_MANUAL_YEAR or seed_year))
    set_setting("active_printer_name", config.PRINTER_NAME)
    set_active_template_path(str(config.TEMPLATE_FILE))
    set_bool_setting("telegram_enabled", False)
    set_setting("telegram_bot_token", "")
    set_setting("telegram_chat_id", "")
    set_bool_setting("discord_enabled", False)
    set_setting("discord_webhook_url", "")
    set_setting("terminal_name", config.APP_TITLE)
    set_setting("terminal_location", "")
    set_setting("idle_timeout_ms", str(config.IDLE_TIMEOUT_MS))
    set_setting("display_brightness_percent", "100")
    set_bool_setting("screensaver_enabled", False)
    set_setting("admin_pin_hash", hash_pin(config.DEFAULT_ADMIN_PIN))
    set_bool_setting("setup_completed", False)
    _reset_common_markers()

    wifi_result = clear_bindings(clear_wifi=True, clear_printer=True)
    deleted_rows = 0
    if not preserve_database:
        initialize_database()
        with get_connection() as conn:
            pa = conn.execute("DELETE FROM print_attempts").rowcount or 0
            docs = conn.execute("DELETE FROM documents").rowcount or 0
            logs = conn.execute("DELETE FROM print_logs").rowcount or 0
            ev = conn.execute("DELETE FROM system_events").rowcount or 0
            deleted_rows = int(pa) + int(docs) + int(logs) + int(ev)
    record_system_event(
        "factory_clear_configuration",
        f"Configuration cleared. preserve_database={int(preserve_database)} deleted_rows={deleted_rows}",
        level="warning",
    )
    return {
        "ok": True,
        "message": "Konfiguracija je vraćena na početno stanje." + (" Baza je zadržana." if preserve_database else " Evidencija je obrisana."),
        "preserve_database": bool(preserve_database),
        "deleted_rows": deleted_rows,
        "wifi_result": wifi_result,
    }
