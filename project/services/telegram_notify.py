from __future__ import annotations

import json
import logging
import threading
import time
import urllib.parse
import urllib.request

from project.core import config


logger = logging.getLogger("uvjerenja_terminal")


PLACEHOLDER_TOKENS = {
    "",
    "PASTE_TELEGRAM_BOT_TOKEN_HERE",
    "YOUR_TELEGRAM_BOT_TOKEN_HERE",
}


def _can_notify() -> bool:
    token = config.TELEGRAM_BOT_TOKEN.strip()
    return (
        config.TELEGRAM_ENABLED
        and config.TELEGRAM_ERROR_NOTIFICATIONS
        and token not in PLACEHOLDER_TOKENS
        and ":" in token
        and config.TELEGRAM_ALLOWED_USER_ID > 0
    )


def _send_message(text: str) -> None:
    if not _can_notify():
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


def _send_message_with_retries(text: str) -> None:
    attempts = max(1, config.TELEGRAM_SEND_RETRY_ATTEMPTS)
    delay = max(0, config.TELEGRAM_SEND_RETRY_DELAY_SECONDS)
    last_exc: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            _send_message(text)
            return
        except Exception as exc:
            last_exc = exc
            if attempt < attempts and delay > 0:
                time.sleep(delay * attempt)

    if last_exc is not None:
        raise last_exc


def notify_telegram_async(text: str) -> None:
    if not _can_notify():
        return

    def worker() -> None:
        try:
            _send_message_with_retries(text)
        except Exception as exc:
            logger.error("[Telegram] Notification failed: %s", exc)

    threading.Thread(target=worker, name="telegram-notify", daemon=True).start()
