from __future__ import annotations

import shutil
import socket
import subprocess
import time
import urllib.parse
from typing import Tuple

from project.core import config
from project.utils.logging_utils import log_error


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=config.SUBPROCESS_TIMEOUT,
    )


def _parse_printers_from_lpstat(stdout: str) -> list[str]:
    printers: list[str] = []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("printer "):
            continue
        parts = line.split()
        if len(parts) >= 2:
            printers.append(parts[1])
    return printers


def list_configured_printers() -> tuple[list[str], str, str, str]:
    try:
        if shutil.which("lpstat") is None:
            return [], "", "CUPS_MISSING", "CUPS printer tools are not installed or not available."

        default_name = ""
        default_proc = _run("lpstat", "-d")
        if default_proc.returncode == 0:
            out = (default_proc.stdout or "").strip()
            if ":" in out:
                default_name = out.split(":", 1)[1].strip()

        list_proc = _run("lpstat", "-p")
        if list_proc.returncode != 0:
            detail = (list_proc.stderr or list_proc.stdout or "").strip()
            return [], default_name, "PRN_LIST_FAILED", detail or "Could not read the printer list."

        return _parse_printers_from_lpstat(list_proc.stdout or ""), default_name, "OK", ""
    except subprocess.TimeoutExpired:
        return [], "", "PRN_CHECK_TIMEOUT", "Printer check timed out."
    except Exception as e:
        log_error(f"[PRINTER] listing failed: {e}")
        return [], "", "PRN_CHECK_FAILED", "Could not read the printer list."


def find_configured_printer(name: str) -> str:
    wanted = (name or "").strip()
    if not wanted:
        return ""

    printers, _, code, _ = list_configured_printers()
    if code != "OK":
        return ""
    for printer in printers:
        if printer == wanted:
            return printer
    wanted_l = wanted.lower()
    for printer in printers:
        if printer.lower() == wanted_l:
            return printer
    return ""


def set_cups_default_printer(printer_name: str) -> tuple[bool, str, str]:
    try:
        clean_name = find_configured_printer(printer_name)
        if not clean_name:
            return False, "PRN_NOT_FOUND", f"Printer '{printer_name}' was not found in CUPS."

        if shutil.which("lpoptions") is None:
            return False, "CUPS_MISSING", "Command 'lpoptions' is not available."

        proc = _run("lpoptions", "-d", clean_name)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            return False, "PRN_DEFAULT_FAILED", detail or f"Could not set '{clean_name}' as CUPS default."
        return True, "OK", clean_name
    except subprocess.TimeoutExpired:
        return False, "PRN_CHECK_TIMEOUT", "Setting the default printer timed out."
    except Exception as e:
        log_error(f"[PRINTER] set default failed: {e}")
        return False, "PRN_DEFAULT_FAILED", "Could not set the CUPS default printer."


def _parse_device_map(stdout: str) -> dict[str, str]:
    devices: dict[str, str] = {}
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line.lower().startswith("device for ") or ":" not in line:
            continue
        left, right = line.split(":", 1)
        name = left[len("device for ") :].strip()
        uri = right.strip()
        if name:
            devices[name] = uri
    return devices


def _parse_lpinfo_uris(stdout: str) -> list[str]:
    uris: list[str] = []
    for line in (stdout or "").splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and ("://" in parts[1] or ":/" in parts[1]):
            uris.append(parts[1].strip())
    return uris


def _device_uri_matches(configured_uri: str, available_uri: str) -> bool:
    configured = (configured_uri or "").strip().rstrip("/").lower()
    available = (available_uri or "").strip().rstrip("/").lower()
    if not configured or not available:
        return False
    if configured == available:
        return True

    configured_has_query = "?" in configured
    available_has_query = "?" in available
    if configured_has_query and available_has_query:
        return False

    configured_base = configured.split("?", 1)[0]
    available_base = available.split("?", 1)[0]
    return bool(configured_base and configured_base == available_base)


def _is_direct_usb_device(uri: str) -> bool:
    low = (uri or "").strip().lower()
    return low.startswith(("usb://", "hp:/usb/", "hpfax:/usb/"))


def _is_virtual_print_device(uri: str) -> bool:
    low = (uri or "").strip().lower()
    return low.startswith(("file:", "cups-pdf:", "pdf:")) or "cups-pdf" in low or "print-to-pdf" in low


def _network_target_from_uri(uri: str) -> tuple[str, int] | None:
    parsed = urllib.parse.urlparse((uri or "").strip())
    scheme = parsed.scheme.lower()
    if scheme not in {"socket", "ipp", "ipps", "http", "https", "lpd"}:
        return None

    host = parsed.hostname
    if not host:
        return None
    host_l = host.lower()
    if "._ipp._tcp" in host_l or "._ipps._tcp" in host_l or "._printer._tcp" in host_l:
        return None

    default_ports = {
        "socket": 9100,
        "ipp": 631,
        "ipps": 443,
        "http": 80,
        "https": 443,
        "lpd": 515,
    }
    return host, parsed.port or default_ports[scheme]


def _check_network_device_available(uri: str, printer_name: str) -> tuple[bool, str, str]:
    target = _network_target_from_uri(uri)
    if target is None:
        return True, "OK", ""

    host, port = target
    timeout = max(1, min(10, config.NETWORK_CHECK_TIMEOUT))
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "OK", ""
    except socket.gaierror as exc:
        return False, "PRN_NETWORK_DNS_FAILED", f"Printer '{printer_name}' hostname could not be resolved: {host} ({exc})."
    except TimeoutError:
        return False, "PRN_NETWORK_TIMEOUT", f"Printer '{printer_name}' did not respond at {host}:{port}."
    except OSError as exc:
        return False, "PRN_NETWORK_UNREACHABLE", f"Printer '{printer_name}' is not reachable at {host}:{port}: {exc}"


def _get_device_uri(printer_name: str) -> tuple[str, str, str]:
    if shutil.which("lpstat") is None:
        return "", "CUPS_MISSING", "CUPS printer tools are not installed or not available."

    try:
        proc = _run("lpstat", "-v", printer_name)
        if proc.returncode != 0:
            proc = _run("lpstat", "-v")
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            return "", "PRN_DEVICE_CHECK_FAILED", detail or "Could not read the printer device URI."

        devices = _parse_device_map(proc.stdout or "")
        uri = devices.get(printer_name, "")
        if not uri:
            wanted = printer_name.lower()
            for name, candidate_uri in devices.items():
                if name.lower() == wanted:
                    uri = candidate_uri
                    break
        if not uri:
            return "", "PRN_DEVICE_CHECK_FAILED", f"Could not find the device URI for printer '{printer_name}'."
        return uri, "OK", ""
    except subprocess.TimeoutExpired:
        return "", "PRN_CHECK_TIMEOUT", "Printer device check timed out."


def _check_physical_device_available(printer_name: str) -> tuple[bool, str, str]:
    uri, code, message = _get_device_uri(printer_name)
    if code != "OK":
        return False, code, message

    if _is_virtual_print_device(uri):
        return (
            False,
            "PRN_VIRTUAL",
            f"Printer '{printer_name}' is a PDF/file queue, not a physical printer.",
        )

    if not _is_direct_usb_device(uri):
        return _check_network_device_available(uri, printer_name)

    if shutil.which("lpinfo") is None:
        return (
            False,
            "PRN_DEVICE_CHECK_FAILED",
            "CUPS command 'lpinfo' is not available, so the USB printer connection cannot be verified.",
        )

    try:
        proc = _run("lpinfo", "-v")
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            return False, "PRN_DEVICE_CHECK_FAILED", detail or "Could not verify connected printer devices."

        available_uris = _parse_lpinfo_uris(proc.stdout or "")
        if any(_device_uri_matches(uri, available_uri) for available_uri in available_uris):
            return True, "OK", ""

        return (
            False,
            "PRN_OFFLINE",
            f"Printer '{printer_name}' is configured in CUPS, but the USB device is not currently connected or powered on.",
        )
    except subprocess.TimeoutExpired:
        return False, "PRN_CHECK_TIMEOUT", "Printer USB device check timed out."


def detect_available_printer(preferred_name: str = "") -> Tuple[str, str, str]:
    """Resolve a usable printer queue.

    Returns (printer_name, code, user_message). code == OK when resolved.
    Priority:
    1) explicit preferred printer from runtime/env config
    2) CUPS default printer
    3) the only available printer
    4) if multiple are available and exactly one is USB-backed, choose that USB printer
    5) otherwise fail as ambiguous
    """
    if shutil.which("lpstat") is None or shutil.which("lp") is None:
        return "", "CUPS_MISSING", "CUPS printer tools are not installed or not available."

    preferred = (preferred_name or "").strip()
    if preferred:
        proc = _run("lpstat", "-p", preferred)
        if proc.returncode == 0:
            return preferred, "OK", ""

    default_proc = _run("lpstat", "-d")
    if default_proc.returncode == 0:
        out = (default_proc.stdout or "").strip()
        if ":" in out:
            default_name = out.split(":", 1)[1].strip()
            if default_name:
                return default_name, "OK", ""

    list_proc = _run("lpstat", "-p")
    if list_proc.returncode == 0:
        printers = _parse_printers_from_lpstat(list_proc.stdout or "")
        if len(printers) == 1:
            return printers[0], "OK", ""
        if len(printers) > 1:
            device_proc = _run("lpstat", "-v")
            if device_proc.returncode == 0:
                devices = _parse_device_map(device_proc.stdout or "")
                usb_printers = [name for name in printers if (devices.get(name, "").lower().startswith("usb://"))]
                if len(usb_printers) == 1:
                    return usb_printers[0], "OK", ""

            joined = ", ".join(printers)
            return "", "PRN_AMBIGUOUS", f"Multiple printers are available ({joined}). Choose one with /setprinter."

    return "", "PRN_NOT_FOUND", "Printer was not found. Check USB, power, and CUPS setup."


def get_printer_readiness(printer_name: str) -> Tuple[bool, str, str]:
    try:
        resolved_name, code, message = detect_available_printer(printer_name)
        if code != "OK":
            return False, code, message

        proc = _run("lpstat", "-p", resolved_name, "-l")
        if proc.returncode != 0:
            return False, "PRN_NOT_FOUND", "Printer was not found. Check that it is powered on."

        out = (proc.stdout or "").lower()
        err = (proc.stderr or "").lower()
        merged = out + "\n" + err
        if "disabled" in merged or "paused" in merged:
            return False, "PRN_DISABLED", f"Printer '{resolved_name}' is paused or disabled."
        if any(
            marker in merged
            for marker in (
                "offline",
                "not connected",
                "not responding",
                "unable to locate",
                "network host",
                "network unreachable",
                "no route to host",
                "connection refused",
                "timed out",
            )
        ):
            return False, "PRN_OFFLINE", f"Printer '{resolved_name}' is reported offline or unreachable by CUPS."

        proc2 = _run("lpstat", "-a")
        if proc2.returncode == 0:
            lines = (proc2.stdout or "").splitlines()
            for line in lines:
                line_l = line.lower()
                if line_l.startswith(resolved_name.lower() + " ") and "not accepting requests" in line_l:
                    return False, "PRN_NOT_ACCEPTING", f"Printer '{resolved_name}' is not accepting requests."

        physical_ready, physical_code, physical_message = _check_physical_device_available(resolved_name)
        if not physical_ready:
            return False, physical_code, physical_message

        return True, "OK", resolved_name
    except subprocess.TimeoutExpired:
        return False, "PRN_CHECK_TIMEOUT", "Printer check timed out."
    except Exception as e:
        log_error(f"[PRINTER] readiness check failed: {e}")
        return False, "PRN_CHECK_FAILED", "Could not check printer readiness."


def wait_for_printer_readiness(
    printer_name: str,
    *,
    attempts: int | None = None,
    delay_seconds: int | None = None,
) -> tuple[bool, str, str, int]:
    max_attempts = max(1, attempts if attempts is not None else config.PRINTER_CHECK_RETRY_ATTEMPTS)
    delay = max(0, delay_seconds if delay_seconds is not None else config.PRINTER_CHECK_RETRY_DELAY_SECONDS)
    last_code = "PRN_CHECK_FAILED"
    last_message = "Could not check printer readiness."

    for attempt in range(1, max_attempts + 1):
        ready, code, message = get_printer_readiness(printer_name)
        if ready:
            return True, code, message, attempt

        last_code = code
        last_message = message
        if attempt < max_attempts and delay > 0:
            time.sleep(delay)

    if max_attempts > 1:
        last_message = f"{last_message} Retried {max_attempts} times."
    return False, last_code, last_message, max_attempts


def collect_printer_diagnostics(preferred_name: str = "") -> dict:
    data = {
        "preferred": (preferred_name or "").strip(),
        "resolved": "",
        "detect_code": "",
        "detect_message": "",
        "ready": False,
        "ready_code": "",
        "ready_message": "",
        "default": "",
        "printers": [],
    }

    try:
        printers, default_name, list_code, list_message = list_configured_printers()
        data["default"] = default_name
        data["printers"] = printers
        if list_code != "OK":
            data["detect_code"] = list_code
            data["detect_message"] = list_message
            return data

        resolved, code, message = detect_available_printer(preferred_name)
        data["resolved"] = resolved
        data["detect_code"] = code
        data["detect_message"] = message

        ready, ready_code, ready_message = get_printer_readiness(preferred_name)
        data["ready"] = ready
        data["ready_code"] = ready_code
        data["ready_message"] = ready_message
        return data
    except subprocess.TimeoutExpired:
        data["detect_code"] = "PRN_CHECK_TIMEOUT"
        data["detect_message"] = "Printer check timed out."
        return data
    except Exception as e:
        log_error(f"[PRINTER] diagnostics failed: {e}")
        data["detect_code"] = "PRN_CHECK_FAILED"
        data["detect_message"] = "Could not read printer diagnostics."
        return data
