from __future__ import annotations

import json
import logging
import threading
import time
import urllib.parse
import urllib.request
from typing import Literal

from project.core import config


logger = logging.getLogger("uvjerenja_terminal")


PLACEHOLDER_TOKENS = {
    "",
    "PASTE_TELEGRAM_BOT_TOKEN_HERE",
    "YOUR_TELEGRAM_BOT_TOKEN_HERE",
}

NotificationKind = Literal["status", "error"]


def _base_can_notify() -> bool:
    token = config.TELEGRAM_BOT_TOKEN.strip()
    return (
        config.TELEGRAM_ENABLED
        and token not in PLACEHOLDER_TOKENS
        and ":" in token
        and config.TELEGRAM_ALLOWED_USER_ID > 0
    )


def _can_notify(kind: NotificationKind = "status") -> bool:
    if not _base_can_notify():
        return False
    if kind == "error":
        return config.TELEGRAM_ERROR_NOTIFICATIONS
    return config.TELEGRAM_STATUS_NOTIFICATIONS


def _send_message(text: str, *, kind: NotificationKind = "status") -> None:
    if not _can_notify(kind):
        return

    token = config.TELEGRAM_BOT_TOKEN.strip()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode(
        {
            "chat_id": str(config.TELEGRAM_ALLOWED_USER_ID),
            "text": text[:3500],
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(request, timeout=10) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(result.get("description") or "Telegram notification failed.")


def _send_message_with_retries(text: str, *, kind: NotificationKind = "status") -> None:
    attempts = max(1, config.TELEGRAM_SEND_RETRY_ATTEMPTS)
    delay = max(0, config.TELEGRAM_SEND_RETRY_DELAY_SECONDS)
    last_exc: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            _send_message(text, kind=kind)
            return
        except Exception as exc:
            last_exc = exc
            if attempt < attempts and delay > 0:
                time.sleep(delay * attempt)

    if last_exc is not None:
        raise last_exc


def notify_telegram_async(text: str, *, kind: NotificationKind = "status") -> None:
    if not _can_notify(kind):
        return

    def worker() -> None:
        try:
            _send_message_with_retries(text, kind=kind)
        except Exception as exc:
            logger.error("[Telegram] Notification failed: %s", exc)

    threading.Thread(target=worker, name=f"telegram-notify-{kind}", daemon=True).start()
