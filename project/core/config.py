"""Runtime configuration for the kiosk MVP."""

from __future__ import annotations

import datetime
import logging
import os
from pathlib import Path


CONFIG_FILE = Path(__file__).resolve()
PROJECT_ROOT = CONFIG_FILE.parent.parent
APP_ROOT = PROJECT_ROOT.parent
_CONFIG_LOGGER = logging.getLogger("uvjerenja_terminal.config")
_CONFIG_WARNINGS: set[str] = set()


def _warn_config_once(message: str) -> None:
    if message in _CONFIG_WARNINGS:
        return
    _CONFIG_WARNINGS.add(message)
    try:
        _CONFIG_LOGGER.warning(message)
    except Exception:
        pass


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


def _env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean env flag with a real default.

    Missing or empty values use the default, so notification flags can stay
    enabled even when the deploy environment does not define them. Explicit
    false values like 0/false/no/off still disable the flag intentionally.
    """
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


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
DEBUG_MODE = _env_bool("POTVRDE_DEBUG_MODE", False)
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

WORKING_HOURS_ENABLED = _env_bool("POTVRDE_WORKING_HOURS_ENABLED", True)
WORKING_HOURS_START = _env("POTVRDE_WORKING_HOURS_START", "08:00").strip() or "08:00"
WORKING_HOURS_END = _env("POTVRDE_WORKING_HOURS_END", "15:00").strip() or "15:00"

CLEANUP_ENABLED = _env_bool("POTVRDE_CLEANUP_ENABLED", True)
CLEANUP_INTERVAL_MINUTES = _env_int("POTVRDE_CLEANUP_INTERVAL_MINUTES", 30)
SUCCESSFUL_JOB_DOCUMENT_RETENTION_MINUTES = _env_int("POTVRDE_SUCCESSFUL_JOB_DOCUMENT_RETENTION_MINUTES", 0)
FAILED_JOB_RETENTION_DAYS = _env_int("POTVRDE_FAILED_JOB_RETENTION_DAYS", 7)
JOB_JSON_RETENTION_DAYS = _env_int("POTVRDE_JOB_JSON_RETENTION_DAYS", 30)

STORAGE_ALERT_USED_PERCENT = _env_int("POTVRDE_STORAGE_ALERT_USED_PERCENT", 90)
STORAGE_CRITICAL_USED_PERCENT = _env_int("POTVRDE_STORAGE_CRITICAL_USED_PERCENT", 95)
STORAGE_ALERT_MIN_FREE_MB = _env_int("POTVRDE_STORAGE_ALERT_MIN_FREE_MB", 512)
STORAGE_CLEANUP_ON_PRESSURE = _env_bool("POTVRDE_STORAGE_CLEANUP_ON_PRESSURE", True)
STORAGE_ALERT_COOLDOWN_MINUTES = _env_int("POTVRDE_STORAGE_ALERT_COOLDOWN_MINUTES", 60)
STORAGE_CHECK_INTERVAL_MINUTES = _env_int("POTVRDE_STORAGE_CHECK_INTERVAL_MINUTES", 30)

TELEGRAM_ENABLED = _env_bool("POTVRDE_TELEGRAM_ENABLED", True)
TELEGRAM_BOT_TOKEN = _env("POTVRDE_TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_ALLOWED_USER_ID = _env_int("POTVRDE_TELEGRAM_ALLOWED_USER_ID", 6598155929)
TELEGRAM_ERROR_NOTIFICATIONS = _env_bool("POTVRDE_TELEGRAM_ERROR_NOTIFICATIONS", True)
TELEGRAM_STATUS_NOTIFICATIONS = _env_bool("POTVRDE_TELEGRAM_STATUS_NOTIFICATIONS", True)
TELEGRAM_NOTIFY_ONLINE = _env_bool("POTVRDE_TELEGRAM_NOTIFY_ONLINE", True)
TELEGRAM_NOTIFY_PRINT_JOBS = _env_bool("POTVRDE_TELEGRAM_NOTIFY_PRINT_JOBS", True)
TELEGRAM_NOTIFY_UPDATE_EVENTS = _env_bool("POTVRDE_TELEGRAM_NOTIFY_UPDATE_EVENTS", True)
TELEGRAM_ERROR_COOLDOWN_SECONDS = _env_int("POTVRDE_TELEGRAM_ERROR_COOLDOWN_SECONDS", 60)
TELEGRAM_POLL_TIMEOUT = _env_int("POTVRDE_TELEGRAM_POLL_TIMEOUT", 25)
TELEGRAM_POLL_BACKOFF_MAX_SECONDS = _env_int("POTVRDE_TELEGRAM_POLL_BACKOFF_MAX_SECONDS", 60)
TELEGRAM_SEND_RETRY_ATTEMPTS = _env_int("POTVRDE_TELEGRAM_SEND_RETRY_ATTEMPTS", 5)
TELEGRAM_SEND_RETRY_DELAY_SECONDS = _env_int("POTVRDE_TELEGRAM_SEND_RETRY_DELAY_SECONDS", 2)
TELEGRAM_COMMAND_TIMEOUT = _env_int("POTVRDE_TELEGRAM_COMMAND_TIMEOUT", 900)
TELEGRAM_REBOOT_COMMAND = _env("POTVRDE_REBOOT_COMMAND", "sudo -n shutdown -r now")
TELEGRAM_UPDATE_COMMAND = _env("POTVRDE_UPDATE_COMMAND", "")
TELEGRAM_RELAUNCH_AFTER_UPDATE = _env_bool("POTVRDE_RELAUNCH_AFTER_UPDATE", True)
TELEGRAM_RELAUNCH_COMMAND = _env("POTVRDE_RELAUNCH_COMMAND", f"/usr/local/bin/{APP_ID}-run")
NETWORK_CHECK_HOST = _env("POTVRDE_NETWORK_CHECK_HOST", "api.telegram.org")
NETWORK_CHECK_PORT = _env_int("POTVRDE_NETWORK_CHECK_PORT", 443)
NETWORK_CHECK_TIMEOUT = _env_int("POTVRDE_NETWORK_CHECK_TIMEOUT", 5)
NETWORK_RECONNECT_COMMAND = _env("POTVRDE_NETWORK_RECONNECT_COMMAND", "")
CUPS_RESTART_COMMAND = _env("POTVRDE_CUPS_RESTART_COMMAND", "sudo -n systemctl restart cups")
TELEGRAM_LOG_TAIL_LINES = _env_int("POTVRDE_TELEGRAM_LOG_TAIL_LINES", 80)

ERROR_LOG_DIR = _ensure_dir(VAR_DIR / "logs")
ERROR_LOG_FILE = ERROR_LOG_DIR / datetime.datetime.now().strftime("error_%d.%m.%Y_%H-%M.log")
LOG_RETENTION_DAYS = _env_int("POTVRDE_LOG_RETENTION_DAYS", 90)


def _parse_hhmm(value: str, default: str, name: str) -> datetime.time:
    raw = str(value or "").strip() or default
    try:
        hour_text, minute_text = raw.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
        return datetime.time(hour=hour, minute=minute)
    except Exception:
        _warn_config_once(f"[Config] Invalid {name}={raw!r}; using {default}.")
        hour_text, minute_text = default.split(":", 1)
        return datetime.time(hour=int(hour_text), minute=int(minute_text))


def working_hours_bounds() -> tuple[datetime.time, datetime.time]:
    return (
        _parse_hhmm(WORKING_HOURS_START, "08:00", "POTVRDE_WORKING_HOURS_START"),
        _parse_hhmm(WORKING_HOURS_END, "15:00", "POTVRDE_WORKING_HOURS_END"),
    )


def working_hours_window_text() -> str:
    start, end = working_hours_bounds()
    return f"{start.strftime('%H:%M')} до {end.strftime('%H:%M')}"


def is_within_working_hours(now: datetime.datetime | datetime.time | None = None) -> bool:
    if not WORKING_HOURS_ENABLED:
        return True

    start, end = working_hours_bounds()
    if now is None:
        current = datetime.datetime.now().time()
    elif isinstance(now, datetime.datetime):
        current = now.time()
    elif isinstance(now, datetime.time):
        current = now
    else:
        _warn_config_once(f"[Config] Unsupported working-hours timestamp {now!r}; using current local time.")
        current = datetime.datetime.now().time()

    if start == end:
        _warn_config_once("[Config] Working-hours start and end are equal; treating terminal as available all day.")
        return True
    if start < end:
        return start <= current < end
    return current >= start or current < end


def working_hours_status_text(now: datetime.datetime | datetime.time | None = None) -> str:
    if not WORKING_HOURS_ENABLED:
        return "disabled"
    return f"{'open' if is_within_working_hours(now) else 'closed'} ({working_hours_window_text()})"


def working_hours_unavailable_message() -> str:
    return f"Терминал је доступан од {working_hours_window_text()}, у радно вријеме секретаријата."


def configured_printer_missing() -> bool:
    return PRINTER_NAME.strip() == ""
