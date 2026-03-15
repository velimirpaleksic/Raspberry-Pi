from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Tuple

from project.services.analytics_service import get_analytics_snapshot
from project.services.health_service import run_startup_checks
from project.services.network_service import format_network_snapshot, get_network_snapshot
from project.services.notification_service import HTTP_TIMEOUT_SECONDS, send_telegram_message
from project.services.printer_service import get_active_printer, get_printer_diagnostics
from project.services.readiness_service import build_readiness_snapshot
from project.services.settings_service import get_bool_setting, get_setting, set_setting

MAX_REPLY_CHARS = 3500


def _telegram_ready() -> Tuple[bool, str, str]:
    enabled = get_bool_setting("telegram_enabled", False)
    token = (get_setting("telegram_bot_token", "") or "").strip()
    chat_id = (get_setting("telegram_chat_id", "") or "").strip()
    if not enabled or not token or not chat_id:
        return False, token, chat_id
    return True, token, chat_id


def _api_request(method: str, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS + 10) as response:
        body = response.read().decode("utf-8", errors="replace")
    return json.loads(body)


def fetch_updates(*, timeout_seconds: int = 2, limit: int = 20) -> Dict[str, Any]:
    ready, token, _chat_id = _telegram_ready()
    if not ready:
        return {"ok": False, "message": "Telegram nije podešen za remote polling.", "updates": []}
    try:
        offset_raw = (get_setting("telegram_last_update_id", "") or "").strip()
        offset = int(offset_raw) + 1 if offset_raw.isdigit() else None
    except Exception:
        offset = None
    payload: Dict[str, Any] = {"timeout": max(0, int(timeout_seconds)), "limit": max(1, min(int(limit), 100))}
    if offset is not None:
        payload["offset"] = offset
    try:
        result = _api_request("getUpdates", token, payload)
        return {"ok": bool(result.get("ok")), "message": "Telegram updates fetched.", "updates": result.get("result") or []}
    except urllib.error.HTTPError as e:
        return {"ok": False, "message": f"Telegram HTTP error: {e}", "updates": []}
    except Exception as e:
        return {"ok": False, "message": f"Telegram poll failed: {e}", "updates": []}


def _truncate(text: str) -> str:
    text = str(text or "")
    return text if len(text) <= MAX_REPLY_CHARS else text[: MAX_REPLY_CHARS - 3] + "..."


def _build_help() -> str:
    return (
        "Dostupne komande:\n"
        "/status - kratki sažetak terminala\n"
        "/health - startup health checks\n"
        "/readiness - production readiness sažetak\n"
        "/printer - aktivni printer i dijagnostika\n"
        "/network - mrežni sažetak\n"
        "/analytics - analytics zadnjih 30 dana\n"
        "/help - ova pomoć"
    )


def _handle_command(command_text: str) -> str:
    cmd = (command_text or "").strip().split()[0].lower()
    if cmd in {"/start", "/help"}:
        return _build_help()
    if cmd == "/status":
        readiness = build_readiness_snapshot()
        network = get_network_snapshot()
        printer = get_printer_diagnostics(get_active_printer())
        return _truncate(
            "\n".join([
                f"Terminal: {readiness.get('terminal', {}).get('terminal_name', '-')} | {readiness.get('terminal', {}).get('terminal_location', '-')}",
                f"State: {readiness.get('state', '-')} | score {readiness.get('readiness_score', 0)}%",
                f"Printer: {get_active_printer()} | {printer.get('readiness_code', '-')} | {printer.get('readiness_message', '-')}",
                f"Mreža: {network.get('message', '-')}",
                f"Danas attempts/printed/failed: {readiness.get('admin', {}).get('today_attempts', 0)}/{readiness.get('admin', {}).get('today_printed', 0)}/{readiness.get('admin', {}).get('today_failed', 0)}",
                f"Sljedeći broj: {readiness.get('admin', {}).get('next_document_number', '-')}",
            ])
        )
    if cmd == "/health":
        health = run_startup_checks(notify_on_failure=False)
        lines = [f"Health: {'OK' if health.get('ok') else 'FAIL'} | failed={health.get('failed_count', 0)}"]
        for row in health.get('checks', []):
            icon = '✅' if row.get('ok') else '❌'
            lines.append(f"{icon} {row.get('name')}: {row.get('code')} | {row.get('message')}")
        return _truncate("\n".join(lines))
    if cmd == "/readiness":
        snap = build_readiness_snapshot()
        lines = [
            f"Readiness: {snap.get('state')} | {snap.get('readiness_score', 0)}%",
            f"Checklist: {snap.get('checklist_score', 0)}% | Health: {snap.get('health_score', 0)}%",
        ]
        if snap.get('blockers'):
            lines.append("Blockers:")
            lines.extend(f"- {x}" for x in snap.get('blockers', [])[:5])
        if snap.get('warnings'):
            lines.append("Warnings:")
            lines.extend(f"- {x}" for x in snap.get('warnings', [])[:5])
        return _truncate("\n".join(lines))
    if cmd == "/printer":
        diag = get_printer_diagnostics(get_active_printer())
        lines = [
            f"Printer: {diag.get('printer_name', '-')}",
            f"Readiness: {diag.get('readiness_code', '-')} | {diag.get('readiness_message', '-')}",
            f"Hint: {diag.get('recovery_hint', '-')}",
        ]
        return _truncate("\n".join(lines))
    if cmd == "/network":
        return _truncate(format_network_snapshot(get_network_snapshot()))
    if cmd == "/analytics":
        data = get_analytics_snapshot(30)
        s = data.get('summary', {})
        lines = [
            "Analytics (30 dana)",
            f"Docs: {s.get('total_documents', 0)} | success rate: {data.get('success_rate', 0)}% | fail rate: {data.get('fail_rate', 0)}%",
            f"Retry rate: {data.get('retry_rate', 0)}% | avg sec to print: {s.get('avg_seconds_to_print', 0)}",
        ]
        for row in data.get('top_errors', [])[:4]:
            lines.append(f"- {row.get('error_code')}: {row.get('hits')}x")
        return _truncate("\n".join(lines))
    return "Nepoznata komanda. Pošalji /help"


def process_updates_once(*, timeout_seconds: int = 1) -> Dict[str, Any]:
    ready, _token, chat_id = _telegram_ready()
    if not ready:
        return {"ok": False, "message": "Telegram nije spreman za remote komande.", "processed": 0, "replied": 0}
    fetched = fetch_updates(timeout_seconds=timeout_seconds)
    if not fetched.get("ok"):
        return {"ok": False, "message": fetched.get("message", "Telegram fetch failed."), "processed": 0, "replied": 0}

    processed = 0
    replied = 0
    last_update_id = None
    for update in fetched.get("updates", []):
        processed += 1
        update_id = update.get("update_id")
        if update_id is not None:
            last_update_id = int(update_id)
        message = update.get("message") or update.get("edited_message") or {}
        text = (message.get("text") or "").strip()
        incoming_chat_id = str((message.get("chat") or {}).get("id") or "")
        if not text.startswith("/"):
            continue
        if chat_id and incoming_chat_id and incoming_chat_id != chat_id:
            continue
        reply = _handle_command(text)
        ok, _msg = send_telegram_message(reply)
        replied += 1 if ok else 0
        set_setting("telegram_last_command", text.split()[0].lower())
        set_setting("telegram_last_command_at", time.strftime("%Y-%m-%d %H:%M:%S"))
        set_setting("telegram_last_command_status", "ok" if ok else "failed")
    if last_update_id is not None:
        set_setting("telegram_last_update_id", str(last_update_id))
    return {
        "ok": True,
        "message": f"Telegram poll processed={processed} replied={replied}",
        "processed": processed,
        "replied": replied,
        "last_update_id": last_update_id,
    }
