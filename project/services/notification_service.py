from __future__ import annotations

import json
import datetime as dt
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional, Tuple

from project.services.settings_service import get_bool_setting, get_setting, set_setting
from project.utils.logging_utils import log_error


HTTP_TIMEOUT_SECONDS = 8


def _telegram_config() -> tuple[bool, str, str]:
    enabled = get_bool_setting("telegram_enabled", False)
    token = (get_setting("telegram_bot_token", "") or "").strip()
    chat_id = (get_setting("telegram_chat_id", "") or "").strip()
    return enabled, token, chat_id



def _discord_config() -> tuple[bool, str]:
    enabled = get_bool_setting("discord_enabled", False)
    webhook_url = (get_setting("discord_webhook_url", "") or "").strip()
    return enabled, webhook_url



def send_telegram_message(text: str) -> Tuple[bool, str]:
    enabled, token, chat_id = _telegram_config()
    if not enabled:
        return False, "Telegram not enabled."
    if not token or not chat_id:
        return False, "Telegram token/chat_id missing."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8", errors="replace")
        if '"ok":true' in body or '"ok": true' in body:
            return True, "Telegram sent."
        return False, f"Telegram API unexpected response: {body[:160]}"
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = str(e)
        return False, f"Telegram HTTP error: {body[:160]}"
    except Exception as e:
        return False, f"Telegram send failed: {e}"



def send_discord_message(text: str) -> Tuple[bool, str]:
    enabled, webhook_url = _discord_config()
    if not enabled:
        return False, "Discord not enabled."
    if not webhook_url:
        return False, "Discord webhook missing."

    payload = json.dumps({"content": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as response:
            _ = response.read()
        return True, "Discord sent."
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = str(e)
        return False, f"Discord HTTP error: {body[:160]}"
    except Exception as e:
        return False, f"Discord send failed: {e}"



def send_notification(text: str) -> Tuple[bool, str]:
    ok, msg = send_telegram_message(text)
    if ok:
        return True, msg

    fallback_ok, fallback_msg = send_discord_message(text)
    if fallback_ok:
        return True, f"Telegram failed; Discord fallback ok. {msg}"

    log_error(f"[NOTIFY] Both Telegram and Discord failed. telegram='{msg}' discord='{fallback_msg}'")
    return False, f"Telegram: {msg} | Discord: {fallback_msg}"



def send_test_notification(source: str = "admin") -> Tuple[bool, str]:
    ok, msg = send_notification(f"✅ Test notifikacija sa terminala ({source}).")
    if ok:
        set_setting("notifications_last_tested_at", dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        set_setting("notifications_last_test_source", source)
    return ok, msg
