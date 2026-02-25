# project/utils/print_hplip.py
import os
import subprocess

from project.utils.logging_utils import log_error
from project.core.config import SUBPROCESS_TIMEOUT, PRINTER_NAME


def print_with_hplip(file_path: str) -> bool:
    """
    Send a file to HP printer using CUPS' lp command.
    Works on all Linux systems where hp-testpage succeeds.
    """
    try:
        # Sanity check
        if not file_path:
            log_error("print_with_hplip called with empty file path")
            return False

        if not os.path.exists(file_path):
            log_error(f"Print failed - file not found: {file_path}")
            return False

        cmd = ["lp", "-d", PRINTER_NAME, "-o", "fit-to-page", file_path]

        proc = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )

        # Debug
        #if proc.stdout:
        #    print(proc.stdout.strip())
        return True

    except subprocess.CalledProcessError as e:
        log_error(f"Print command failed: {e.stderr.strip()}")
        return False
    except Exception as e:
        log_error(f"Unexpected error while printing: {e}")
        return False