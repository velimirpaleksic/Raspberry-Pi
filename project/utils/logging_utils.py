# utils/logging_utils.py
import logging
import os

from project.core.config import ERROR_LOG_FILENAME, PROJECT_ROOT, DEBUG_MODE
from project.gui.ui_components import critical_error_window


LOG_PATH = os.path.join(PROJECT_ROOT, ERROR_LOG_FILENAME)
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logger = logging.getLogger("project")
logger.setLevel(logging.INFO)


if not logger.handlers:
    fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s %(levelname)s: %(message)s", "%d.%m.%Y %H:%M:%S")
    fh.setFormatter(fmt)
    logger.addHandler(fh)


def error_logging(message: str):
    critical_error_window()
    logger.error(message)

    if DEBUG_MODE:
        print(message)