# project/utils/print_hplip.py
import os
import subprocess
import traceback

from project.utils.logging_utils import error_logging
from project.core.config import SUBPROCESS_TIMEOUT, PRINTER_NAME


def print_with_hplip(file_path: str) -> bool:
    """
    Send a file to HP printer using HPLIP's hp-print command.
    Returns True on success, False on failure. All errors are logged via error_logging.
    """
    try:
        # Basic sanity checks
        if not file_path:
            error_logging("print_with_hplip called with empty file_path")
            return False

        if not os.path.exists(file_path):
            error_logging(f"Print failed - file not found: {file_path}")
            return False

        cmd = ["hp-print"]
        cmd += ["-d", PRINTER_NAME]
        cmd.append(file_path)

        # Run subprocess with capture and timeout for robustness
        try:
            proc = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=SUBPROCESS_TIMEOUT,
            )
            # Optionally inspect proc.stdout / proc.stderr if needed
            return True

        except subprocess.CalledProcessError as e:
            out = e.stdout or ""
            err = e.stderr or ""
            msg = (f"hp-print failed (returncode={e.returncode}). "
                   f"stdout: {out.strip()} stderr: {err.strip()}")
            error_logging(msg)
            return False

        except subprocess.TimeoutExpired as e:
            msg = f"hp-print timeout after {e.timeout} seconds for file {file_path}"
            error_logging(msg)
            return False

        except FileNotFoundError:
            # hp-print binary not installed / not in PATH
            error_logging("hp-print command not found. Is HPLIP installed?")
            return False

    except PermissionError as e:
        error_logging(f"Permission error while attempting to print {file_path}: {e}")
        return False

    except Exception as e:
        tb = traceback.format_exc()
        error_logging(f"Unexpected error in print_file_hplip: {e}\n{tb}")
        return False