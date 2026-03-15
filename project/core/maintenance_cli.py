from __future__ import annotations

import argparse
import json
import sys

from project.services.health_service import run_startup_checks
from project.services.maintenance_service import run_cleanup
from project.services.notification_service import send_notification
from project.services.analytics_service import get_analytics_snapshot
from project.services.telegram_remote_service import process_updates_once


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Maintenance CLI for Uvjerenja terminal")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("cleanup", help="Run cleanup and print JSON result")
    health_p = sub.add_parser("health", help="Run startup checks and print JSON result")
    health_p.add_argument("--notify-on-failure", action="store_true")
    notify_p = sub.add_parser("notify", help="Send a plain notification message")
    notify_p.add_argument("message")
    analytics_p = sub.add_parser("analytics", help="Print analytics snapshot as JSON")
    analytics_p.add_argument('--days', type=int, default=30)
    tg_p = sub.add_parser("telegram-poll-once", help="Poll Telegram updates once and answer supported commands")
    tg_p.add_argument('--timeout-seconds', type=int, default=1)

    args = parser.parse_args(argv)
    if args.cmd == "cleanup":
        result = run_cleanup()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "health":
        result = run_startup_checks(notify_on_failure=bool(args.notify_on_failure))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    if args.cmd == "notify":
        ok, msg = send_notification(args.message)
        print(json.dumps({"ok": ok, "message": msg}, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    if args.cmd == "analytics":
        result = get_analytics_snapshot(int(args.days))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "telegram-poll-once":
        result = process_updates_once(timeout_seconds=int(args.timeout_seconds))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get('ok') else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
