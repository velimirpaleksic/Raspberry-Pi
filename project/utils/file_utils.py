# utils/file_utils.py
import shutil
from pathlib import Path

from project.utils.logging_utils import error_logging


def safe_remove_file(path):
    """
    Safely remove a file if it exists.
    Logs errors if deletion fails.
    """
    try:
        path = Path(path)
        if path.is_file():
            path.unlink()

    except Exception as e:
        error_logging(f"[File Utils] Failed to delete file '{path}': {e}")


def safe_remove_dir(path, recursive=False):
    """
    Safely remove a directory.
    If recursive=True, removes all contents.
    """
    try:
        path = Path(path)
        if path.is_dir():
            if recursive:
                shutil.rmtree(path)
            else:
                path.rmdir()

    except Exception as e:
        error_logging(f"[File Utils] Failed to delete directory '{path}': {e}")