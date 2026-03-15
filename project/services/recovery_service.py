from __future__ import annotations

from typing import Any, Dict, List

from project.services.health_service import run_startup_checks
from project.services.network_service import get_network_snapshot
from project.services.printer_service import get_active_printer, get_printer_diagnostics


def _dedupe(values: List[str]) -> List[str]:
    out: List[str] = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return out


def build_printer_recovery_plan(diagnostics: Dict[str, Any] | None = None) -> Dict[str, Any]:
    diag = diagnostics or get_printer_diagnostics(get_active_printer())
    code = str(diag.get("code") or "").upper()
    steps: List[str] = []
    if diag.get("ready"):
        steps.extend([
            "Printer izgleda spreman. Ako korisnik i dalje javlja problem, uradi novi test print i potvrdi da je baš taj uređaj reagovao.",
            "Ako ima više printera, koristi setup printera i test print po uređaju prije selekcije.",
        ])
    else:
        steps.append(diag.get("message") or "Printer trenutno nije spreman.")
        if code in {"PRINTER_NAME_PLACEHOLDER", "PRINTER_NOT_FOUND", "NO_DEFAULT_PRINTER"}:
            steps.extend([
                "Otvori 'Setup printera' i prvo uradi test print za svaki printer koji CUPS vidi.",
                "Ako printer nije u listi, probaj 'Pronađi mrežne URI-jeve' ili ručno dodaj queue iz setupa.",
            ])
        elif code in {"PRINTER_NOT_ENABLED", "PRINTER_DISABLED", "PRINTER_PAUSED"}:
            steps.extend([
                "Provjeri da li je queue pauziran ili disable-an u CUPS-u.",
                "Provjeri papir, kabl, napajanje i eventualne poruke na samom printeru.",
                "Nakon toga uradi 'Test printera' iz admin panela.",
            ])
        elif code in {"LP_MISSING", "CUPS_MISSING"}:
            steps.extend([
                "CUPS/lp alat nije dostupan. Provjeri installer i systemd servise na Pi-u.",
                "Ako je novi uređaj, prvo završi deployment korake iz production dokumentacije.",
            ])
        else:
            steps.extend([
                "Uradi test print iz admin panela i pogledaj Printer dijagnostiku (lpstat -p / -v / -o).",
                "Ako printer i dalje ne reaguje, ponovo prođi setup printera i potvrdi aktivni queue.",
            ])
    return {"summary": diag.get("message") or "Printer status nije dostupan.", "steps": _dedupe(steps), "diagnostics": diag}


def build_network_recovery_plan(snapshot: Dict[str, Any] | None = None) -> Dict[str, Any]:
    snap = snapshot or get_network_snapshot()
    connected = bool(snap.get("current_connection") or snap.get("current_ssid") or snap.get("ip_addresses"))
    steps: List[str] = []
    if connected:
        steps.extend([
            "Mreža djeluje aktivno. Ako notifikacije ipak ne rade, provjeri Telegram/Discord token i uradi test notifikacije.",
            "Ako koristiš mrežni printer, potvrdi da je printer dostupan na istoj mreži.",
        ])
    else:
        steps.extend([
            snap.get("message") or "Trenutno nema aktivne mrežne veze.",
            "Otvori 'Mreža / Wi‑Fi', uradi scan i poveži se na odgovarajući SSID.",
            "Ako koristiš skriveni SSID, unesi ga ručno i označi da je mreža skrivena.",
            "Poslije povezivanja ponovo uradi test notifikacije i po potrebi setup mrežnog printera.",
        ])
    if not snap.get("nmcli_available"):
        steps.append("NetworkManager / nmcli nije dostupan. Za touchscreen Wi‑Fi setup instaliraj i omogući NetworkManager.")
    return {"summary": snap.get("message") or "Mrežni status nije dostupan.", "steps": _dedupe(steps), "snapshot": snap}


def build_startup_recovery_plan(health: Dict[str, Any] | None = None) -> Dict[str, Any]:
    result = health or run_startup_checks(notify_on_failure=False)
    failed = [row for row in result.get("checks", []) if not row.get("ok")]
    steps: List[str] = []
    if not failed:
        steps.append("Startup provjere su prošle. Ako korisnik ipak vidi grešku, idi na Printer dijagnostiku ili Mreža / Wi‑Fi i provjeri konkretan podsistem.")
    else:
        for row in failed:
            code = str(row.get("code") or "").upper()
            if code.startswith("TPL"):
                steps.append("Template nije ispravan. Idi na Template / USB, uvezi validan .docx ili vrati default template.")
            elif code.startswith("PRINTER") or code in {"LP_MISSING"}:
                steps.append("Printer provjera nije prošla. Otvori setup printera, uradi test print po uređaju i potvrdi aktivni queue.")
            elif code == "LOW_DISK":
                steps.append("Disk je ispod praga. Pokreni Cleanup iz admin panela i provjeri backup/export folder.")
            elif code == "DB_FAIL":
                steps.append("Baza nije dostupna. Provjeri var/db putanju, dozvole i stanje SD kartice prije nastavka rada.")
            elif code == "SOFFICE_MISSING":
                steps.append("LibreOffice nije dostupan. Ponovo pokreni installer ili dovrši deployment pakete na Pi-u.")
            elif code == "JOBS_DIR_FAIL":
                steps.append("Jobs folder nije upisiv. Provjeri VAR_DIR dozvole i slobodan prostor na disku.")
            else:
                steps.append(f"Provjeri stavku '{row.get('name')}' i poruku: {row.get('message')}")
    return {"summary": result.get("summary") or "Startup status nije dostupan.", "steps": _dedupe(steps), "health": result}


def build_recovery_snapshot() -> Dict[str, Any]:
    health = run_startup_checks(notify_on_failure=False)
    printer = get_printer_diagnostics(get_active_printer())
    network = get_network_snapshot()
    return {
        "health": health,
        "printer": printer,
        "network": network,
        "startup_plan": build_startup_recovery_plan(health),
        "printer_plan": build_printer_recovery_plan(printer),
        "network_plan": build_network_recovery_plan(network),
    }
