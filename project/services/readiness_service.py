from __future__ import annotations

from typing import Any, Dict, List

from project.services.admin_service import get_admin_snapshot, get_setup_checklist
from project.services.device_service import get_terminal_settings_snapshot
from project.services.health_service import run_startup_checks
from project.services.network_service import get_network_snapshot


def _health_percent(result: Dict[str, Any]) -> int:
    checks = result.get("checks") or []
    if not checks:
        return 0
    ok_count = sum(1 for row in checks if row.get("ok"))
    return int(round((ok_count / len(checks)) * 100))


def build_readiness_snapshot() -> Dict[str, Any]:
    checklist = get_setup_checklist()
    health = run_startup_checks(notify_on_failure=False)
    admin = get_admin_snapshot()
    terminal = get_terminal_settings_snapshot()
    network = get_network_snapshot()

    checklist_score = int(checklist.get("score_percent") or 0)
    health_score = _health_percent(health)
    readiness_score = int(round((checklist_score * 0.6) + (health_score * 0.4)))

    blockers: List[str] = []
    warnings: List[str] = []
    recommendations: List[str] = []

    for row in health.get("checks") or []:
        if row.get("ok"):
            continue
        blockers.append(f"{row.get('name')}: {row.get('message')}")

    for item in checklist.get("items") or []:
        if item.get("ok"):
            continue
        key = item.get("key")
        label = item.get("label") or key or "Stavka"
        detail = item.get("detail") or ""
        if key in {"pin_set", "template_valid", "setup_completed"}:
            if detail:
                blockers.append(f"{label}: {detail}")
            else:
                blockers.append(label)
        else:
            if detail:
                warnings.append(f"{label}: {detail}")
            else:
                warnings.append(label)

    if not str(terminal.get("terminal_location") or "").strip():
        warnings.append("Lokacija terminala nije postavljena u opštim postavkama.")
    if network.get("internet_ok") is False:
        warnings.append("Internet konekcija nije potpuna; Telegram/Discord notifikacije i network printer setup mogu biti otežani.")
    if int(admin.get("today_failed") or 0) >= 3:
        warnings.append(f"Danas ima {admin.get('today_failed')} neuspjela pokušaja printa; provjeri printer dijagnostiku i recovery hintove.")

    if blockers:
        recommendations.append("Prvo riješi sve BLOCKER stavke prije puštanja terminala u produkciju.")
    else:
        recommendations.append("Ključne produkcijske blokade nisu detektovane.")

    if warnings:
        recommendations.append("Preporuka: zatvori i WARNING stavke da bi setup bio zaokružen i lak za održavanje.")
    if not terminal.get("display_last_applied_at"):
        recommendations.append("Primijeni display postavke barem jednom da potvrdiš brightness/screensaver ponašanje na ovom Pi image-u.")
    if not network.get("wifi_networks") and not network.get("current_connection"):
        recommendations.append("Ako će uređaj koristiti Telegram/Discord ili mrežni printer, provjeri Wi-Fi / Ethernet setup u mrežnom ekranu.")

    acceptance_steps = [
        "Uradi startup check i potvrdi da su sve provjere zelene ili svjesno prihvaćene.",
        "Pošalji test print na aktivni printer i potvrdi da je fizički ispisao stranicu.",
        "Generiši jednu probnu potvrdu end-to-end i provjeri PDF → print tok.",
        "Uradi backup na USB i provjeri da je bundle kreiran.",
        "Pošalji test notifikaciju i potvrdi da je stigla na Telegram ili Discord fallback.",
        "Provjeri idle timeout i da se terminal vraća na početni ekran nakon neaktivnosti.",
    ]

    readiness_state = "READY" if not blockers else "NOT_READY"
    if not blockers and warnings:
        readiness_state = "READY_WITH_WARNINGS"

    return {
        "state": readiness_state,
        "readiness_score": readiness_score,
        "checklist_score": checklist_score,
        "health_score": health_score,
        "blockers": blockers,
        "warnings": warnings,
        "recommendations": recommendations,
        "acceptance_steps": acceptance_steps,
        "checklist": checklist,
        "health": health,
        "admin": admin,
        "terminal": terminal,
        "network": network,
    }


def format_readiness_snapshot(snapshot: Dict[str, Any]) -> str:
    lines = [
        f"State: {snapshot.get('state')}",
        f"Readiness score: {snapshot.get('readiness_score', 0)}%",
        f"Checklist score: {snapshot.get('checklist_score', 0)}%",
        f"Health score: {snapshot.get('health_score', 0)}%",
        "",
        f"Blockers: {len(snapshot.get('blockers') or [])}",
        f"Warnings: {len(snapshot.get('warnings') or [])}",
        "",
        f"Next document: {snapshot.get('admin', {}).get('next_document_number', '-')}",
        f"Printer: {snapshot.get('admin', {}).get('active_printer', '-')}",
        f"Template: {snapshot.get('admin', {}).get('template_path', '-')}",
        f"Terminal: {snapshot.get('terminal', {}).get('terminal_name', '-')} | {snapshot.get('terminal', {}).get('terminal_location', '-')}",
        f"Network: {snapshot.get('network', {}).get('message', '-')}",
    ]
    return "\n".join(lines)
