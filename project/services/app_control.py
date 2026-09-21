from __future__ import annotations

import os
import subprocess

from project.core import config


def launch_replacement_app() -> tuple[bool, str]:
    command = config.TELEGRAM_RELAUNCH_COMMAND.strip()
    if not command:
        return False, "Команда за поновно покретање није подешена."
    try:
        process = subprocess.Popen(
            command, cwd=str(config.APP_ROOT), shell=True, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        try:
            return_code = process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            return True, "Нова инстанца апликације је покренута."
        return False, f"Команда је прерано завршила (код {return_code})."
    except Exception as exc:
        return False, f"Апликација се не може поново покренути: {exc}"
