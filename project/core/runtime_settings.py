from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from project.core import config
from project.utils.logging_utils import log_error


_LOCK = threading.RLock()


def _read_settings_unlocked() -> dict[str, Any]:
    try:
        if not config.SETTINGS_FILE.exists():
            return {}
        data = json.loads(config.SETTINGS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        log_error(f"[SETTINGS] Failed to read {config.SETTINGS_FILE}: {exc}")
        return {}


def _write_settings_unlocked(settings: dict[str, Any]) -> None:
    config.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = Path(str(config.SETTINGS_FILE) + ".tmp")
    tmp_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(config.SETTINGS_FILE)


def get_selected_printer() -> str:
    with _LOCK:
        settings = _read_settings_unlocked()
        if bool(settings.get("use_cups_default")):
            return ""
        selected = str(settings.get("printer_name") or "").strip()
        return selected or config.PRINTER_NAME.strip()


def set_selected_printer(printer_name: str) -> None:
    clean_name = printer_name.strip()
    with _LOCK:
        settings = _read_settings_unlocked()
        settings["printer_name"] = clean_name
        settings["use_cups_default"] = False
        _write_settings_unlocked(settings)
        config.PRINTER_NAME = clean_name


def clear_selected_printer() -> None:
    with _LOCK:
        settings = _read_settings_unlocked()
        settings["printer_name"] = ""
        settings["use_cups_default"] = True
        _write_settings_unlocked(settings)
        config.PRINTER_NAME = ""
