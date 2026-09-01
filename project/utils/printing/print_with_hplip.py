from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass

from project.core import config
from project.core.runtime_settings import get_selected_printer
from project.utils.logging_utils import log_error
from project.utils.printing.printer_status import wait_for_printer_readiness


def _classify_lp_error(detail: str) -> tuple[str, str]:
    d = (detail or "").strip()
    low = d.lower()
    if "scheduler is not running" in low or "unable to connect to server" in low:
        return "CUPS_OFFLINE", "CUPS servis nije dostupan. Pokreni cups i pokušaj ponovo."
    if "no default destination" in low:
        return "PRN_NO_DEFAULT", "Nema default printera. Postavi jedan u CUPS-u i pokušaj ponovo."
    if "not accepting requests" in low:
        return "PRN_NOT_ACCEPTING", "Printer ne prima zahtjeve. Omogući ga u CUPS-u pa pokušaj ponovo."
    if "disabled" in low or "paused" in low:
        return "PRN_DISABLED", "Printer je pauziran ili onemogućen. Omogući ga pa pokušaj ponovo."
    if "unknown destination" in low or "does not exist" in low or "not found" in low:
        return "PRN_NOT_FOUND", "Printer nije pronađen. Provjeri vezu i CUPS podešavanje."
    return "PRINT_FAILED", "Štampanje nije uspjelo."


@dataclass(frozen=True)
class PrintCommandResult:
    ok: bool
    printer_name: str = ""
    error_code: str = ""
    user_message: str = ""
    detail: str = ""


def print_with_hplip(file_path: str, preferred_printer: str | None = None) -> PrintCommandResult:
    """Send a file to a CUPS printer using lp.

    Despite the historical name, this works for any configured CUPS queue.
    Default behavior: use configured printer if set, otherwise use the CUPS default printer.
    """
    try:
        if not file_path:
            return PrintCommandResult(False, error_code="FILE_MISSING", user_message="Nedostaje PDF za štampu.")

        if not os.path.exists(file_path):
            return PrintCommandResult(False, error_code="FILE_MISSING", user_message="PDF za štampu nije pronađen.")

        if shutil.which("lp") is None:
            return PrintCommandResult(False, error_code="CUPS_MISSING", user_message="Komanda 'lp' nije dostupna. Provjeri CUPS instalaciju.")

        selected_printer = get_selected_printer() if preferred_printer is None else preferred_printer.strip()
        ready, code, message, readiness_attempts = wait_for_printer_readiness(selected_printer)
        if not ready:
            log_error(f"Print failed - printer unavailable: {code} {message}")
            return PrintCommandResult(False, error_code=code, user_message=message)
        printer_name = message

        attempts = max(1, config.PRINT_RETRY_ATTEMPTS)
        last_error: PrintCommandResult | None = None
        for attempt in range(1, attempts + 1):
            proc = subprocess.run(
                ["lp", "-d", printer_name, "-o", "fit-to-page", file_path],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=config.PRINT_TIMEOUT,
            )
            if proc.returncode == 0:
                time.sleep(1.5)
                still_ready, ready_code, ready_message, _ = wait_for_printer_readiness(
                    printer_name,
                    attempts=1,
                    delay_seconds=0,
                )
                if not still_ready:
                    return PrintCommandResult(
                        False,
                        printer_name=printer_name,
                        error_code=ready_code,
                        user_message=ready_message,
                        detail=(proc.stdout or "").strip(),
                    )
                detail = (proc.stdout or "").strip()
                if readiness_attempts > 1:
                    detail = (detail + f"\nPrinter readiness attempts: {readiness_attempts}").strip()
                return PrintCommandResult(True, printer_name=printer_name, detail=detail)

            detail = (proc.stderr or proc.stdout or "").strip()
            error_code, user_message = _classify_lp_error(detail)
            if error_code == "PRINT_FAILED":
                user_message = f"Štampanje na printer '{printer_name}' nije uspjelo."
            last_error = PrintCommandResult(
                False,
                printer_name=printer_name,
                error_code=error_code,
                user_message=user_message,
                detail=f"{detail}\nPrint attempt {attempt}/{attempts}".strip(),
            )
            if attempt < attempts and config.PRINT_RETRY_DELAY_SECONDS > 0:
                time.sleep(config.PRINT_RETRY_DELAY_SECONDS)
        return last_error or PrintCommandResult(False, printer_name=printer_name, error_code="PRINT_FAILED", user_message="Štampanje nije uspjelo.")

    except subprocess.TimeoutExpired:
        return PrintCommandResult(False, error_code="PRINT_TIMEOUT", user_message="Slanje na štampu je isteklo. Pokušaj ponovo.")
    except Exception as e:
        log_error(f"Unexpected error while printing: {e}")
        return PrintCommandResult(False, error_code="PRINT_EXCEPTION", user_message="Došlo je do greške pri štampanju.", detail=repr(e))
