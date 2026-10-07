from __future__ import annotations

import os
import shlex
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


def request_system_reboot() -> tuple[bool, str]:
    """Request a full OS reboot without evaluating the configured command in a shell."""

    command = config.TELEGRAM_REBOOT_COMMAND.strip()
    if not command:
        return False, "Команда за поновно покретање система није подешена."
    try:
        args = shlex.split(command, posix=os.name != "nt")
        if not args:
            return False, "Команда за поновно покретање система није подешена."
        completed = subprocess.run(
            args,
            cwd=str(config.APP_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=15,
            shell=False,
        )
        if completed.returncode == 0:
            return True, "Систем се поново покреће."
        return False, f"Систем није прихватио поновно покретање (код {completed.returncode})."
    except subprocess.TimeoutExpired:
        return False, "Захтјев за поновно покретање је трајао предуго."
    except Exception as exc:
        return False, f"Систем се не може поново покренути: {exc}"
