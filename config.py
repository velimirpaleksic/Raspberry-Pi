# config.py
import datetime
import os

# DEBUG mode
DEBUG = True

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
    "REASON": "ПРЕПИС СВЈЕДОЧАНСТВА",
}

# Bitno
DJELOVODNI_BROJ = "01-743/25"

RAZREDI = ["ПРВИ", "ДРУГИ", "ТРЕЋИ", "ЧЕТВРТИ"]
STRUKE = ["МАШИНСТВО И ОБРАДА МЕТАЛА", "ЕЛЕКТРОТЕХНИКА", "УГОСТИТЕЉСТВО И ТУРИЗАМ", "САОБРАЋАЈ"]
RAZLOZI = ["УЧЛАЊЕЊА У ОМЛАДИНСКУ ЗАДРУГУ", "ПРЕПИС СВЈЕДОЧАНСТВА", "ПОТВРДА О СТАТУСУ"]

# ---

# Template file names
TEMPLATE_FILE = "docs/template.docx"
OUTPUT_FILE = "docs/output.docx"

# Printer name
PRINTER_NAME = "Printer_Name"

# Today's date
DANASNJI_DATUM = datetime.datetime.now().strftime("%d.%m.%Y")

# Logs
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILENAME = datetime.datetime.now().strftime(LOG_DIR + "/error_%d.%m.%Y_%H-%M-%S.log")

# Placeholders (UI)
MJESTO_PLACEHOLDER = "нпр. Касиндо"
OPSTINA_PLACEHOLDER = "нпр. Источна Илиџа"