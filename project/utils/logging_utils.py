import logging
import time
from logging.handlers import RotatingFileHandler

from project.core import config


logger = logging.getLogger("uvjerenja_terminal")
logger.setLevel(logging.INFO)

_last_telegram_error_at = 0.0
_last_telegram_error_message = ""


def _ensure_handlers() -> None:
    if logger.handlers:
        return

    # File log (persisted). Journald will also capture stdout/stderr via systemd.
    try:
        handler = RotatingFileHandler(
            str(config.ERROR_LOG_FILE),
            maxBytes=2_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        fmt = logging.Formatter("%(asctime)s %(levelname)s: %(message)s", "%d.%m.%Y %H:%M:%S")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    except Exception:
        # If file logging fails, we still want console logging.
        pass

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(console)


def log_error(message: str) -> None:
    global _last_telegram_error_at, _last_telegram_error_message

    _ensure_handlers()
    logger.error(message)
    if config.DEBUG_MODE:
        print(message)

    text = str(message or "").strip()
    if not text or text.startswith("[Telegram]"):
        return

    now = time.monotonic()
    cooldown = max(0, config.TELEGRAM_ERROR_COOLDOWN_SECONDS)
    if text == _last_telegram_error_message and now - _last_telegram_error_at < cooldown:
        return

    _last_telegram_error_message = text
    _last_telegram_error_at = now
    try:
        from project.services.telegram_notify import notify_telegram_async

        notify_telegram_async("Uvjerenja Terminal error:\n" + text[:3200], kind="error")
    except Exception:
        pass


def log_info(message: str) -> None:
    _ensure_handlers()
    logger.info(message)
    if config.DEBUG_MODE:
        print(message)
