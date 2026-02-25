import subprocess
from typing import Tuple

from project.core.config import SUBPROCESS_TIMEOUT
from project.utils.logging_utils import log_error


def get_printer_readiness(printer_name: str) -> Tuple[bool, str, str]:
    """Best-effort printer readiness check using CUPS tools.

    Returns:
      (ready, error_code, user_message)

    Notes:
      CUPS error reporting varies by driver/model. We keep this conservative:
      - If CUPS says printer is disabled/paused -> not ready
      - If lpstat cannot find the printer -> not ready
      - Otherwise -> assume ready
    """
    try:
        if not printer_name or printer_name.strip() == "Printer_Name":
            return False, "PRN_NOT_CONFIGURED", "Printer nije podešen. Pozovi osoblje."

        # Example: "printer HP_LaserJet is idle.  enabled since ..."
        proc = subprocess.run(
            ["lpstat", "-p", printer_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )

        if proc.returncode != 0:
            # Typical stderr: "lpstat: Unknown destination \"X\"!"
            return False, "PRN_NOT_FOUND", "Printer nije pronađen. Provjeri da li je uključen."

        out = (proc.stdout or "").lower()
        if "disabled" in out or "paused" in out:
            return False, "PRN_DISABLED", "Printer je pauziran. Pozovi osoblje."

        # Optional: try queue state to catch 'stopped'
        proc2 = subprocess.run(
            ["lpstat", "-a"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
        if proc2.returncode == 0:
            lines = (proc2.stdout or "").splitlines()
            for line in lines:
                if line.lower().startswith(printer_name.lower() + " "):
                    if "not accepting requests" in line.lower():
                        return False, "PRN_NOT_ACCEPTING", "Printer ne prima zahtjeve. Pozovi osoblje."

        return True, "OK", ""
    except Exception as e:
        log_error(f"[PRINTER] readiness check failed: {e}")
        # If we cannot check, don't block printing; but allow UI to proceed
        return True, "OK", ""
