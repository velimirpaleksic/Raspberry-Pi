import logging
from logging.handlers import RotatingFileHandler

from project.core import config


logger = logging.getLogger("uvjerenja_terminal")
logger.setLevel(logging.INFO)


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
    _ensure_handlers()
    logger.error(message)
    if config.DEBUG_MODE:
        print(message)


def log_info(message: str) -> None:
    _ensure_handlers()
    logger.info(message)
    if config.DEBUG_MODE:
        print(message)
