from __future__ import annotations

import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
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


def _redact_secret(text: str, secret: str) -> str:
    value = str(text or "")
    return value.replace(secret, "[REDACTED]") if secret else value


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
    wifi = active_wifi_details()
    return {
        "internet": internet_ok,
        "internet_code": internet_code,
        "internet_message": internet_message,
        "ssid": wifi.get("ssid") or _first_ok([["iwgetid", "-r"]]),
        "signal": wifi.get("signal"),
        "connection_name": wifi.get("connection_name") or "",
        "ip": _first_ok([["hostname", "-I"]]),
        "wifi_state": _first_ok([["nmcli", "-t", "-f", "WIFI", "general"]]),
    }


def active_wifi_details() -> dict[str, Any]:
    details: dict[str, Any] = {"connection_name": "", "ssid": "", "signal": None}
    if shutil.which("nmcli") is None:
        return details
    ok, output = _run(
        ["nmcli", "-t", "-e", "yes", "-f", "NAME,TYPE", "connection", "show", "--active"],
        timeout=10,
    )
    if ok:
        for line in output.splitlines():
            fields = _split_nmcli_escaped(line)
            if len(fields) >= 2 and fields[1].strip() in {"wifi", "802-11-wireless"}:
                details["connection_name"] = fields[0].strip()
                break
    ok, output = _run(
        ["nmcli", "-t", "-e", "yes", "-f", "IN-USE,SSID,SIGNAL", "device", "wifi", "list"],
        timeout=10,
    )
    if ok:
        for line in output.splitlines():
            fields = _split_nmcli_escaped(line)
            if len(fields) >= 3 and fields[0].strip() == "*":
                details["ssid"] = fields[1].strip()
                try:
                    details["signal"] = int(fields[2])
                except ValueError:
                    details["signal"] = None
                break
    return details


@dataclass(frozen=True)
class ConnectivityState:
    blocked: bool
    failures: int
    successes: int


class ConnectivityGate:
    """Debounce brief Wi-Fi drops before blocking or restoring the form."""

    def __init__(self, threshold: int = 2) -> None:
        self.threshold = max(1, int(threshold))
        self.blocked = False
        self.failures = 0
        self.successes = 0

    def observe(self, online: bool) -> ConnectivityState:
        if online:
            self.successes += 1
            self.failures = 0
            if self.blocked and self.successes >= self.threshold:
                self.blocked = False
        else:
            self.failures += 1
            self.successes = 0
            if not self.blocked and self.failures >= self.threshold:
                self.blocked = True
        return ConnectivityState(self.blocked, self.failures, self.successes)


def _split_nmcli_escaped(line: str) -> list[str]:
    fields: list[str] = []
    current: list[str] = []
    escaped = False
    for char in line:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
    current.append("\\" if escaped else "")
    fields.append("".join(current))
    return fields


def scan_wifi_networks() -> tuple[list[dict[str, Any]], str]:
    if shutil.which("nmcli") is None:
        return [], "NetworkManager (nmcli) није доступан."
    ok, output = _run(
        ["nmcli", "-t", "-e", "yes", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "yes"],
        timeout=30,
    )
    if not ok:
        return [], output
    best: dict[str, dict[str, Any]] = {}
    for line in output.splitlines():
        fields = _split_nmcli_escaped(line)
        if len(fields) < 4 or not fields[1].strip():
            continue
        ssid = fields[1].strip()
        try:
            signal = int(fields[2])
        except ValueError:
            signal = 0
        item = {"active": fields[0].strip() == "*", "ssid": ssid, "signal": signal, "security": fields[3].strip()}
        if ssid not in best or signal > int(best[ssid]["signal"]):
            best[ssid] = item
    return sorted(best.values(), key=lambda item: (not item["active"], -int(item["signal"]), str(item["ssid"]).lower())), ""


def connect_wifi(ssid: str, password: str = "") -> tuple[bool, str]:
    """Connect through NetworkManager without putting the password in argv."""

    clean_ssid = str(ssid or "").strip()
    if not clean_ssid:
        return False, "Назив Wi-Fi мреже није унесен."
    if shutil.which("nmcli") is None:
        return False, "NetworkManager (nmcli) није доступан."

    previous = active_wifi_details()
    previous_connection = str(previous.get("connection_name") or "").strip()
    command = ["nmcli", "--ask", "device", "wifi", "connect", clean_ssid]
    input_text = f"{password}\n" if password else "\n"
    try:
        completed = subprocess.run(
            command,
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        output = _redact_secret((completed.stdout or "").strip(), password)
        if completed.returncode != 0:
            rollback = ""
            if previous_connection:
                restored, restore_output = _run(["nmcli", "connection", "up", previous_connection], timeout=45)
                rollback = " Претходна мрежа је враћена." if restored else f" Повратак на претходну мрежу није успио: {restore_output}"
            return False, (output or "Повезивање није успјело.") + rollback
        online, _code, message = check_internet()
        if online:
            return True, output
        rollback = ""
        if previous_connection:
            restored, restore_output = _run(["nmcli", "connection", "up", previous_connection], timeout=45)
            rollback = " Претходна мрежа је враћена." if restored else f" Повратак није успио: {restore_output}"
        return False, f"Мрежа је активирана, али интернет није доступан: {message}.{rollback}"
    except subprocess.TimeoutExpired:
        return False, "Повезивање на Wi-Fi је трајало предуго."
    except Exception as exc:
        log_error(f"[NETWORK] Wi-Fi connection failed: {exc}")
        return False, "Повезивање на Wi-Fi није успјело."


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
