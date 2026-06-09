"""Runtime configuration for the kiosk MVP."""

from __future__ import annotations

import datetime
import os
from pathlib import Path


CONFIG_FILE = Path(__file__).resolve()
PROJECT_ROOT = CONFIG_FILE.parent.parent
APP_ROOT = PROJECT_ROOT.parent


def _load_dotenv_file(path: Path) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    except Exception:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ[key] = value


def _load_dotenv_files() -> None:
    seen: set[Path] = set()
    for path in (APP_ROOT / ".env", PROJECT_ROOT / ".env", Path.cwd() / ".env"):
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        if resolved in seen:
            continue
        seen.add(resolved)
        _load_dotenv_file(resolved)


_load_dotenv_files()


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


def _ensure_dir(path: Path) -> Path:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path
    except Exception:
        fallback = PROJECT_ROOT / "var" / path.name
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


VAR_DIR = _ensure_dir(Path(_env("POTVRDE_VAR_DIR", f"/var/lib/{APP_ID}")))
JOBS_DIR = _ensure_dir(VAR_DIR / "jobs")
SETTINGS_FILE = VAR_DIR / "settings.json"

PRINTER_NAME = _env("POTVRDE_PRINTER_NAME", "")
TEMPLATE_FILE = Path(_env("POTVRDE_TEMPLATE_PATH", str(PROJECT_ROOT / "docs" / "template.docx")))


def danasnji_datum() -> str:
    return datetime.datetime.now().strftime("%d.%m.%Y")


MJESTO_PLACEHOLDER = "нпр. Касиндо"
OPSTINA_PLACEHOLDER = "нпр. Источна Илиџа"

RAZREDI = ["ПРВИ", "ДРУГИ", "ТРЕЋИ", "ЧЕТВРТИ"]
STRUKE = [
    "Електротехника",
    "Машинство и обрада метала",
    "Саобраћај",
    "Угоститељство и туризам",
    "Козметички техничар",
    "Фризер",
]
RAZLOZI = [
    "Здравствено осигурање",
    "Омладинску задругу",
    "Алиментација",
    "Дјечији доплатак",
    "Отварање рачуна у банци",
    "Превоз",
    "Стипендију брата/сестре",
    "Пензију",
    "Новчана средства за уџбенике",
    "Регулисање уписнине",
    "Давање изјаве у полицији",
    "Возачки испит",
    "Конкурс полицијска академија",
    "Социјална помоћ",
]

# Keep debug data off by default on the kiosk.
DEBUG_MODE = _env("POTVRDE_DEBUG_MODE", "0") in ("1", "true", "TRUE", "yes", "YES")
DEBUG_DATA = {
    "IME": "",
    "PREZIME": "",
    "RODITELJ": "Петар",
    "GODINA": "2008",
    "MJESEC": "5",
    "DAN": "17",
    "MJESTO": "Касиндо",
    "OPSTINA": "Источна Илиџа",
    "RAZRED": "ДРУГИ",
    "STRUKA": "Електротехника",
    "RAZLOG": "Здравствено осигурање",
}

SUBPROCESS_TIMEOUT = _env_int("POTVRDE_SUBPROCESS_TIMEOUT", 60)
DOCX_CONVERT_TIMEOUT = _env_int("POTVRDE_DOCX_CONVERT_TIMEOUT", 45)
PRINT_TIMEOUT = _env_int("POTVRDE_PRINT_TIMEOUT", 30)
IDLE_TIMEOUT_MS = _env_int("POTVRDE_IDLE_TIMEOUT_MS", 60_000)
PRINTER_CHECK_RETRY_ATTEMPTS = _env_int("POTVRDE_PRINTER_CHECK_RETRY_ATTEMPTS", 5)
PRINTER_CHECK_RETRY_DELAY_SECONDS = _env_int("POTVRDE_PRINTER_CHECK_RETRY_DELAY_SECONDS", 3)
PRINT_RETRY_ATTEMPTS = _env_int("POTVRDE_PRINT_RETRY_ATTEMPTS", 3)
PRINT_RETRY_DELAY_SECONDS = _env_int("POTVRDE_PRINT_RETRY_DELAY_SECONDS", 3)

TELEGRAM_ENABLED = _env("POTVRDE_TELEGRAM_ENABLED", "1") in ("1", "true", "TRUE", "yes", "YES")
TELEGRAM_BOT_TOKEN = _env("POTVRDE_TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_ALLOWED_USER_ID = _env_int("POTVRDE_TELEGRAM_ALLOWED_USER_ID", 6598155929)
TELEGRAM_ERROR_NOTIFICATIONS = _env("POTVRDE_TELEGRAM_ERROR_NOTIFICATIONS", "1") in ("1", "true", "TRUE", "yes", "YES")
TELEGRAM_ERROR_COOLDOWN_SECONDS = _env_int("POTVRDE_TELEGRAM_ERROR_COOLDOWN_SECONDS", 60)
TELEGRAM_POLL_TIMEOUT = _env_int("POTVRDE_TELEGRAM_POLL_TIMEOUT", 25)
TELEGRAM_POLL_BACKOFF_MAX_SECONDS = _env_int("POTVRDE_TELEGRAM_POLL_BACKOFF_MAX_SECONDS", 60)
TELEGRAM_SEND_RETRY_ATTEMPTS = _env_int("POTVRDE_TELEGRAM_SEND_RETRY_ATTEMPTS", 5)
TELEGRAM_SEND_RETRY_DELAY_SECONDS = _env_int("POTVRDE_TELEGRAM_SEND_RETRY_DELAY_SECONDS", 2)
TELEGRAM_COMMAND_TIMEOUT = _env_int("POTVRDE_TELEGRAM_COMMAND_TIMEOUT", 900)
TELEGRAM_REBOOT_COMMAND = _env("POTVRDE_REBOOT_COMMAND", "sudo -n shutdown -r now")
TELEGRAM_UPDATE_COMMAND = _env("POTVRDE_UPDATE_COMMAND", "")
TELEGRAM_RELAUNCH_AFTER_UPDATE = _env("POTVRDE_RELAUNCH_AFTER_UPDATE", "1") in ("1", "true", "TRUE", "yes", "YES")
TELEGRAM_RELAUNCH_COMMAND = _env("POTVRDE_RELAUNCH_COMMAND", f"/usr/local/bin/{APP_ID}-run")
NETWORK_CHECK_HOST = _env("POTVRDE_NETWORK_CHECK_HOST", "api.telegram.org")
NETWORK_CHECK_PORT = _env_int("POTVRDE_NETWORK_CHECK_PORT", 443)
NETWORK_CHECK_TIMEOUT = _env_int("POTVRDE_NETWORK_CHECK_TIMEOUT", 5)
NETWORK_RECONNECT_COMMAND = _env("POTVRDE_NETWORK_RECONNECT_COMMAND", "")
CUPS_RESTART_COMMAND = _env("POTVRDE_CUPS_RESTART_COMMAND", "sudo -n systemctl restart cups")
TELEGRAM_LOG_TAIL_LINES = _env_int("POTVRDE_TELEGRAM_LOG_TAIL_LINES", 80)

ERROR_LOG_DIR = _ensure_dir(VAR_DIR / "logs")
ERROR_LOG_FILE = ERROR_LOG_DIR / datetime.datetime.now().strftime("error_%d.%m.%Y_%H-%M.log")
LOG_RETENTION_DAYS = 90


def configured_printer_missing() -> bool:
    return PRINTER_NAME.strip() == ""
