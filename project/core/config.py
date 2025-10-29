# core/config.py
import datetime
import uuid
from pathlib import Path

# =========================
# Project root
# =========================
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# =========================
# Djelovodni broj
# =========================
DJELOVODNI_BROJ = "01-743/25"

# =========================
# Printer
# =========================
PRINTER_NAME = "Printer_Name"

# =========================
# Template & print queue
# =========================
TEMPLATE_FILE = PROJECT_ROOT / "docs" / "template.docx"

PRINT_QUEUE_DIR = PROJECT_ROOT / "print_queue"
PRINT_QUEUE_DIR.mkdir(exist_ok=True)

OUTPUT_FILE = PRINT_QUEUE_DIR / f"{uuid.uuid4()}.docx"

# =========================
# Date
# =========================
DANASNJI_DATUM = datetime.datetime.now().strftime("%d.%m.%Y")

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
DEBUG_MODE = True
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
DB_DIR = PROJECT_ROOT / "db"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "audit_log.db"
DB_SETUP_SCRIPT = DB_DIR / "db.py"

# Space estimates
# Per entry bytes = 410
# Entries per MB = 2557
# Entries per GB = 2618882

# If you want to change this
# You can use space_estimator.py script from admin/ folder

MAX_ENTRIES = 10475529 # ~4GB max entries
BATCH_DELETE_SIZE = 1000  # rows to delete per batch

# =========================
# Timeouts (seconds)
# =========================
SUBPROCESS_TIMEOUT = 60
DOCX_CONVERT_TIMEOUT = 45
PRINT_TIMEOUT = 30

# =========================
# Logging settings
# =========================
ERROR_LOG_DIR = PROJECT_ROOT / "error_logs"
ERROR_LOG_DIR.mkdir(exist_ok=True)

ERROR_LOG_FILENAME = ERROR_LOG_DIR / datetime.datetime.now().strftime("error_%d.%m.%Y_%H-%M.log")
LOG_RETENTION_DAYS = 90  # delete old logs