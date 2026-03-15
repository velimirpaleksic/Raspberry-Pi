from __future__ import annotations

import re
import shutil
import subprocess
import datetime as dt
from pathlib import Path
from typing import Any, Dict, List

from project.core import config
from project.services.document_service import record_system_event
from project.services.settings_service import get_setting, set_setting
from project.utils.logging_utils import log_error
from project.utils.printing.printer_status import get_printer_readiness


NETWORK_URI_PREFIXES = ("socket://", "ipp://", "ipps://", "lpd://", "dnssd://", "mdns://")


def get_active_printer() -> str:
    value = (get_setting("active_printer_name", config.PRINTER_NAME) or config.PRINTER_NAME).strip()
    return value or config.PRINTER_NAME



def set_active_printer(printer_name: str) -> str:
    normalized = (printer_name or "").strip()
    if not normalized:
        raise ValueError("Printer name ne može biti prazan.")
    set_setting("active_printer_name", normalized)
    try:
        _run(["lpoptions", "-d", normalized], timeout=10)
    except Exception:
        pass
    record_system_event("active_printer_changed", f"Active printer set to: {normalized}")
    return normalized



def _run(args: List[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout or config.SUBPROCESS_TIMEOUT,
        check=False,
    )



def _parse_connection_type(device_uri: str) -> str:
    uri = (device_uri or "").lower()
    if uri.startswith("usb://") or uri.startswith("hp:/usb"):
        return "USB"
    if uri.startswith("socket://") or uri.startswith("ipp://") or uri.startswith("ipps://") or uri.startswith("lpd://"):
        return "Network"
    if uri.startswith("dnssd://") or uri.startswith("mdns://"):
        return "Bonjour"
    return "Unknown"



def build_printer_recovery_hint(code: str) -> str:
    normalized = (code or "").strip().upper()
    mapping = {
        "PRN_NOT_CONFIGURED": "Odaberi printer u setup wizardu ili admin panelu.",
        "PRN_NOT_FOUND": "Provjeri da li je printer uključen i klikni Osvježi listu printera.",
        "PRN_DISABLED": "Printer/queue je pauziran. U adminu uradi test ili provjeri CUPS stanje.",
        "PRN_NOT_ACCEPTING": "Queue ne prima zahtjeve. Pokušaj ponovo ili pozovi osoblje.",
        "LPADMIN_MISSING": "Nedostaje lpadmin. Pokreni installer ili provjeri CUPS pakete.",
        "LPINFO_MISSING": "Nedostaje lpinfo. Pokreni installer ili provjeri CUPS pakete.",
        "ADD_FAILED": "Provjeri URI printera i da li mrežni printer podržava driverless/IPP setup.",
        "OK": "Printer djeluje spremno.",
    }
    return mapping.get(normalized, "Provjeri napajanje, mrežu/kabl i uradi test print prije nove selekcije.")



def _slugify_queue_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", (value or "").strip())
    cleaned = cleaned.strip("_")
    return (cleaned or "printer")[:48]



def _queue_name_from_uri(device_uri: str) -> str:
    uri = (device_uri or "").strip()
    slug = _slugify_queue_name(uri.replace("://", "_").replace("/", "_"))
    if slug.lower().startswith(("ipp_", "ipps_", "socket_", "lpd_", "dnssd_", "mdns_")):
        return slug[:48]
    return f"net_{slug}"[:48]



def list_printers() -> List[Dict[str, Any]]:
    printers: Dict[str, Dict[str, Any]] = {}
    active = get_active_printer()

    try:
        proc = _run(["lpstat", "-p"])
        if proc.returncode == 0:
            for raw in (proc.stdout or "").splitlines():
                line = raw.strip()
                if not line.lower().startswith("printer "):
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                name = parts[1]
                lowered = line.lower()
                status = "ready"
                if "disabled" in lowered or "paused" in lowered:
                    status = "paused"
                elif "not accepting" in lowered:
                    status = "not_accepting"
                printers[name] = {
                    "name": name,
                    "status": status,
                    "summary": line,
                    "device_uri": "",
                    "connection_type": "Unknown",
                    "is_active": name == active,
                }

        proc_v = _run(["lpstat", "-v"])
        if proc_v.returncode == 0:
            for raw in (proc_v.stdout or "").splitlines():
                line = raw.strip()
                if not line.lower().startswith("device for "):
                    continue
                try:
                    head, uri = line.split(":", 1)
                    name = head.replace("device for ", "", 1).strip()
                    uri = uri.strip()
                except ValueError:
                    continue
                info = printers.setdefault(
                    name,
                    {
                        "name": name,
                        "status": "unknown",
                        "summary": "",
                        "device_uri": "",
                        "connection_type": "Unknown",
                        "is_active": name == active,
                    },
                )
                info["device_uri"] = uri
                info["connection_type"] = _parse_connection_type(uri)

        for name, row in list(printers.items()):
            ready, code, message = get_printer_readiness(name)
            row["ready"] = bool(ready)
            row["code"] = code
            row["message"] = message
            row["recovery_hint"] = build_printer_recovery_hint(code)
            if not ready and row.get("status") == "ready":
                row["status"] = "offline"
            row["is_active"] = name == active

        result = sorted(
            printers.values(),
            key=lambda p: (
                0 if p.get("is_active") else 1,
                0 if p.get("ready") else 1,
                str(p.get("name") or "").lower(),
            ),
        )
        return result
    except FileNotFoundError:
        return []
    except Exception as e:
        log_error(f"[PRINTER_SERVICE] list_printers failed: {e}")
        return []



def discover_network_printers() -> List[Dict[str, Any]]:
    try:
        proc = _run(["lpinfo", "-v"])
    except FileNotFoundError:
        return []
    except Exception as e:
        log_error(f"[PRINTER_SERVICE] discover_network_printers failed: {e}")
        return []

    rows: List[Dict[str, Any]] = []
    seen: set[str] = set()
    if proc.returncode != 0:
        return rows

    for raw in (proc.stdout or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        lower = line.lower()
        uri = ""
        for prefix in NETWORK_URI_PREFIXES:
            idx = lower.find(prefix)
            if idx >= 0:
                uri = line[idx:].strip()
                break
        if not uri:
            continue
        if uri in seen:
            continue
        seen.add(uri)
        conn_type = _parse_connection_type(uri)
        queue_name = _queue_name_from_uri(uri)
        label = uri
        if line.startswith("network "):
            label = line[len("network "):].strip()
        rows.append(
            {
                "uri": uri,
                "connection_type": conn_type,
                "suggested_queue_name": queue_name,
                "label": label,
            }
        )

    rows.sort(key=lambda r: (str(r.get("connection_type") or ""), str(r.get("uri") or "").lower()))
    return rows



def add_network_printer(queue_name: str, device_uri: str, *, make_active: bool = True) -> Dict[str, Any]:
    normalized_name = _slugify_queue_name(queue_name or _queue_name_from_uri(device_uri))
    normalized_uri = (device_uri or "").strip()
    if not normalized_uri:
        raise ValueError("URI printera ne može biti prazan.")
    if not normalized_uri.lower().startswith(NETWORK_URI_PREFIXES):
        raise ValueError("URI mora početi sa ipp://, ipps://, socket://, lpd://, dnssd:// ili mdns://")

    if not shutil.which("lpadmin"):
        return {
            "ok": False,
            "queue_name": normalized_name,
            "device_uri": normalized_uri,
            "code": "LPADMIN_MISSING",
            "message": "lpadmin nije pronađen.",
            "recovery_hint": build_printer_recovery_hint("LPADMIN_MISSING"),
        }

    mode = "everywhere"
    cmd = ["lpadmin", "-p", normalized_name, "-E", "-v", normalized_uri, "-m", "everywhere"]
    proc = _run(cmd)
    if proc.returncode != 0 and normalized_uri.lower().startswith(("socket://", "lpd://")):
        mode = "raw"
        proc = _run(["lpadmin", "-p", normalized_name, "-E", "-v", normalized_uri, "-m", "raw"])

    ok = proc.returncode == 0
    message = (proc.stderr or proc.stdout or "").strip()
    code = "OK" if ok else "ADD_FAILED"

    if ok:
        try:
            _run(["cupsenable", normalized_name], timeout=10)
            _run(["cupsaccept", normalized_name], timeout=10)
        except Exception:
            pass
        if make_active:
            set_active_printer(normalized_name)
        record_system_event("network_printer_added", f"Printer queue added: {normalized_name} -> {normalized_uri} ({mode})")
        message = message or f"Printer dodat: {normalized_name}"
    else:
        record_system_event("network_printer_add_failed", f"Add printer failed: {normalized_name} -> {normalized_uri} :: {message}", level="warning")
        message = message or "Dodavanje printera nije uspjelo."

    return {
        "ok": ok,
        "queue_name": normalized_name,
        "device_uri": normalized_uri,
        "mode": mode,
        "code": code,
        "message": message,
        "recovery_hint": build_printer_recovery_hint(code),
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
    }



def send_test_page(printer_name: str) -> Dict[str, Any]:
    normalized = (printer_name or "").strip()
    ready, code, message = get_printer_readiness(normalized)
    result: Dict[str, Any] = {
        "ok": bool(ready),
        "printer_name": normalized,
        "code": code,
        "message": message or "",
        "recovery_hint": build_printer_recovery_hint(code),
        "test_file": None,
        "stdout": "",
        "stderr": "",
    }
    if not ready:
        result["message"] = result["message"] or f"Printer nije spreman ({code})."
        return result

    test_file = Path("/usr/share/cups/data/testprint")
    result["test_file"] = str(test_file)
    if not test_file.exists():
        result["ok"] = True
        result["message"] = "Printer je spreman. CUPS test page nije pronađen, urađena je samo provjera spremnosti."
        return result

    try:
        completed = subprocess.run(
            ["lp", "-d", normalized, str(test_file)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=config.SUBPROCESS_TIMEOUT,
        )
        record_system_event("printer_test", f"Printer test page sent to: {normalized}")
        set_setting("printer_last_tested_at", dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        set_setting("printer_last_tested_printer", normalized)
        result["ok"] = True
        result["message"] = f"Test stranica je poslana na printer: {normalized}"
        result["stdout"] = (completed.stdout or "").strip()
        result["stderr"] = (completed.stderr or "").strip()
        return result
    except Exception as e:
        record_system_event("printer_test_failed", f"Printer test failed for {normalized}: {e}", level="warning")
        result["ok"] = False
        result["code"] = "ADD_FAILED"
        result["recovery_hint"] = build_printer_recovery_hint("ADD_FAILED")
        result["message"] = f"Test print nije uspio: {e}"
        return result



def get_printer_diagnostics(printer_name: str | None = None) -> Dict[str, Any]:
    target = (printer_name or get_active_printer()).strip()
    ready, code, message = get_printer_readiness(target)
    commands: Dict[str, Dict[str, Any]] = {}
    for key, args in {
        "lpstat_p": ["lpstat", "-p"],
        "lpstat_v": ["lpstat", "-v"],
        "lpstat_o": ["lpstat", "-o", target] if target else ["lpstat", "-o"],
    }.items():
        binary = args[0]
        if not shutil.which(binary):
            commands[key] = {"ok": False, "code": f"{binary.upper()}_MISSING", "stdout": "", "stderr": f"{binary} nije pronađen."}
            continue
        try:
            proc = _run(args, timeout=15)
            commands[key] = {
                "ok": proc.returncode == 0,
                "code": "OK" if proc.returncode == 0 else f"{binary.upper()}_FAILED",
                "stdout": (proc.stdout or "").strip(),
                "stderr": (proc.stderr or "").strip(),
            }
        except Exception as e:
            commands[key] = {"ok": False, "code": f"{binary.upper()}_ERROR", "stdout": "", "stderr": str(e)}

    last_tested_at = (get_setting("printer_last_tested_at", "") or "").strip()
    last_tested_printer = (get_setting("printer_last_tested_printer", "") or "").strip()
    hints = [
        build_printer_recovery_hint(code),
        "Ako ima više printera, uradi test print na svakom prije selekcije.",
        "Ako queue postoji ali printer ne reaguje, provjeri papir, kabl i da li je queue pauziran.",
    ]
    deduped_hints: List[str] = []
    for hint in hints:
        if hint and hint not in deduped_hints:
            deduped_hints.append(hint)

    return {
        "printer_name": target,
        "ready": bool(ready),
        "code": code,
        "message": message or "",
        "active_printer": get_active_printer(),
        "last_tested_at": last_tested_at,
        "last_tested_printer": last_tested_printer,
        "commands": commands,
        "hints": deduped_hints,
    }
