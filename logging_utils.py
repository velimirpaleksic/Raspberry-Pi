# logging_utils.py
import datetime

def write_log(logfile: str, message: str):
    timestamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    with open(logfile, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] ERROR: {message}\n")

# These dialog functions depend on tkinter and must accept root.
def error_logging(root, logfile: str, message: str, show_dialog_fn):
    """write logfile and then call a show-dialog callback that takes (root, message)."""
    write_log(logfile, message)
    # delegate UI/dialog to caller-provided function so this module remains UI-agnostic
    show_dialog_fn(root, message)