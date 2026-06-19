from __future__ import annotations

import shutil
import socket
import subprocess
import time
from typing import Any

from project.core import config
from project.utils.logging_utils import log_error


def _run(command: list[str] | str, *, timeout: int = 20, shell: bool = False) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            command,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        output = (completed.stdout or "").strip()
        return completed.returncode == 0, output or f"Exit code: {completed.returncode}"
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        return False, f"Command timed out after {timeout} seconds.\n{output}"
    except Exception as exc:
        log_error(f"[NETWORK] command failed: {exc}")
        return False, repr(exc)


def check_internet() -> tuple[bool, str, str]:
    host = config.NETWORK_CHECK_HOST.strip() or "api.telegram.org"
    port = int(config.NETWORK_CHECK_PORT or 443)
    timeout = max(1, int(config.NETWORK_CHECK_TIMEOUT or 5))
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "OK", f"{host}:{port} reachable"
    except socket.gaierror as exc:
        return False, "DNS_FAILED", f"DNS failed for {host}: {exc}"
    except TimeoutError:
        return False, "NET_TIMEOUT", f"Connection to {host}:{port} timed out"
    except OSError as exc:
        return False, "NET_UNREACHABLE", f"Connection to {host}:{port} failed: {exc}"


def _first_ok(commands: list[list[str]]) -> str:
    for command in commands:
        if shutil.which(command[0]) is None:
            continue
        ok, output = _run(command, timeout=10)
        if ok and output:
            return output.strip()
    return ""


def collect_network_diagnostics() -> dict[str, Any]:
    internet_ok, internet_code, internet_message = check_internet()
    return {
        "internet": internet_ok,
        "internet_code": internet_code,
        "internet_message": internet_message,
        "ssid": _first_ok([["iwgetid", "-r"]]),
        "ip": _first_ok([["hostname", "-I"]]),
        "wifi_state": _first_ok([["nmcli", "-t", "-f", "WIFI", "general"]]),
    }


def reconnect_network() -> tuple[bool, str]:
    command = config.NETWORK_RECONNECT_COMMAND.strip()
    if command:
        return _run(command, timeout=90, shell=True)

    if shutil.which("nmcli") is not None:
        ok_off, out_off = _run(["nmcli", "radio", "wifi", "off"], timeout=20)
        time.sleep(3)
        ok_on, out_on = _run(["nmcli", "radio", "wifi", "on"], timeout=20)
        if ok_off and ok_on:
            return True, "\n".join(part for part in (out_off, out_on) if part).strip()

        nmcli_output = "\n".join(part for part in (out_off, out_on) if part).strip()
        if shutil.which("systemctl") is not None:
            ok_service, service_output = _run(
                "sudo -n systemctl restart NetworkManager || "
                "sudo -n systemctl restart dhcpcd || "
                "sudo -n systemctl restart networking",
                timeout=90,
                shell=True,
            )
            return ok_service, "\n".join(part for part in (nmcli_output, service_output) if part).strip()
        return False, nmcli_output

    return (
        False,
        "No network reconnect command is configured and 'nmcli' was not found. "
        "Set POTVRDE_NETWORK_RECONNECT_COMMAND in the env file.",
    )
