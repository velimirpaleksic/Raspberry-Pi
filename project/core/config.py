"""Runtime configuration.

This project is designed to run on Raspberry Pi (Linux) as an appliance-style
"terminal". Configuration is primarily driven through environment variables
loaded by systemd (EnvironmentFile).

Key env vars (see install_uvjerenja_terminal.sh):
  - POTVRDE_APP_ID
  - POTVRDE_APP_TITLE
  - POTVRDE_PRINTER_NAME
  - POTVRDE_DJELOVODNI_BROJ
  - POTVRDE_VAR_DIR
  - POTVRDE_TEMPLATE_PATH
  - POTVRDE_DEBUG_MODE
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return v if v is not None and v != "" else default


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    try:
        return int(v)
    except Exception:
        return default


APP_ID = _env("POTVRDE_APP_ID", "uvjerenja-terminal")
APP_TITLE = _env("POTVRDE_APP_TITLE", "Uvjerenja Terminal")

# =========================
# Project root (code)
# =========================
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _ensure_dir(p: Path) -> Path:
    try:
        p.mkdir(parents=True, exist_ok=True)
        return p
    except Exception:
        # Fallback into project folder (dev mode)
        fallback = PROJECT_ROOT / "var" / p.name
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


# =========================
# Persisted runtime data
# =========================
VAR_DIR = Path(_env("POTVRDE_VAR_DIR", f"/var/lib/{APP_ID}"))
VAR_DIR = _ensure_dir(VAR_DIR)

JOBS_DIR = _ensure_dir(VAR_DIR / "jobs")


# =========================
# Business configuration
# =========================
DJELOVODNI_BROJ = _env("POTVRDE_DJELOVODNI_BROJ", "01-743/25")
PRINTER_NAME = _env("POTVRDE_PRINTER_NAME", "Printer_Name")


# =========================
# Template
# =========================
TEMPLATE_FILE = Path(_env("POTVRDE_TEMPLATE_PATH", str(PROJECT_ROOT / "docs" / "template.docx")))


# =========================
# Date
# =========================
def danasnji_datum() -> str:
    return datetime.datetime.now().strftime("%d.%m.%Y")


# =========================
# Placeholder examples
# =========================
MJESTO_PLACEHOLDER = "нпр. Касиндо"
OPSTINA_PLACEHOLDER = "нпр. Источна Илиџа"


# =========================
# Classes, Professions, Reasons
# =========================
RAZREDI = ["ПРВИ", "ДРУГИ", "ТРЕЋИ", "ЧЕТВРТИ"]
STRUKE = [
    "УГОСТИТЕЉСТВО И ТУРИЗАМ",
    "МАШИНСТВО И ОБРАДА МЕТАЛА",
    "ЕЛЕКТРОТЕХНИКА",
    "САОБРАЋАЈ",
]
RAZLOZI = [
    "УЧЛАЊЕЊА У ОМЛАДИНСКУ ЗАДРУГУ",
    "ПРЕПИС СВЈЕДОЧАНСТВА",
    "ПОТВРДА О СТАТУСУ",
]


# =========================
# Debug
# =========================
DEBUG_MODE = _env("POTVRDE_DEBUG_MODE", "0") in ("1", "true", "TRUE", "yes", "YES")
DEBUG_DATA = {
    "IME": "Велимир Палексић",
    "RODITELJ": "Велимир",
    "GODINA": "2000",
    "MJESEC": "1",
    "DAN": "1",
    "MJESTO": "Касиндо",
    "OPSTINA": "Источна Илиџа",
    "RAZRED": "ДРУГИ",
    "STRUKA": "МАШИНСТВО И ОБРАДА МЕТАЛА",
    "RAZLOG": "ПРЕПИС СВЈЕДОЧАНСТВА",
}


# =========================
# Audit log database
# =========================
DB_DIR = _ensure_dir(VAR_DIR / "db")
DB_PATH = DB_DIR / "audit_log.db"

MAX_ENTRIES = 10_475_529  # ~4GB max entries
BATCH_DELETE_SIZE = 1000


# =========================
# Timeouts (seconds)
# =========================
SUBPROCESS_TIMEOUT = _env_int("POTVRDE_SUBPROCESS_TIMEOUT", 60)
DOCX_CONVERT_TIMEOUT = _env_int("POTVRDE_DOCX_CONVERT_TIMEOUT", 45)
PRINT_TIMEOUT = _env_int("POTVRDE_PRINT_TIMEOUT", 30)


# =========================
# UX settings
# =========================
IDLE_TIMEOUT_MS = _env_int("POTVRDE_IDLE_TIMEOUT_MS", 60_000)


# =========================
# Logging settings
# =========================
ERROR_LOG_DIR = _ensure_dir(VAR_DIR / "logs")
ERROR_LOG_FILE = ERROR_LOG_DIR / datetime.datetime.now().strftime("error_%d.%m.%Y_%H-%M.log")
LOG_RETENTION_DAYS = 90
