from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from project.core import config
from project.core.runtime_settings import clear_selected_printer, get_selected_printer, set_selected_printer
from project.utils.logging_utils import log_error, log_info
from project.utils.network_status import collect_network_diagnostics, reconnect_network
from project.utils.printing.printer_status import (
    collect_printer_diagnostics,
    find_configured_printer,
    list_configured_printers,
    set_cups_default_printer,
)


PLACEHOLDER_TOKENS = {
    "",
    "PASTE_TELEGRAM_BOT_TOKEN_HERE",
    "YOUR_TELEGRAM_BOT_TOKEN_HERE",
}


class TelegramControlBot:
    def __init__(self, manager: Any | None = None) -> None:
        self.token = config.TELEGRAM_BOT_TOKEN
        self.allowed_user_id = str(config.TELEGRAM_ALLOWED_USER_ID)
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.poll_timeout = max(1, config.TELEGRAM_POLL_TIMEOUT)
        self.manager = manager
        self._offset: int | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._command_lock = threading.Lock()
        self._active_command: str | None = None
        self._started_at = time.time()
        self._last_poll_ok_at: float | None = None
        self._poll_failures = 0
        self._last_poll_error = ""

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="telegram-control-bot", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run(self) -> None:
        log_info("[Telegram] Control bot starting.")
        self._discard_backlog()
        backoff_seconds = 5

        while not self._stop_event.is_set():
            try:
                updates = self._api_call(
                    "getUpdates",
                    {
                        "timeout": str(self.poll_timeout),
                        "allowed_updates": json.dumps(["message"]),
                        **({"offset": str(self._offset)} if self._offset is not None else {}),
                    },
                    timeout=self.poll_timeout + 10,
                )
                if self._poll_failures:
                    log_info(f"[Telegram] Polling recovered after {self._poll_failures} failure(s).")
                    self._send_message(
                        self.allowed_user_id,
                        "Telegram connection recovered.\n"
                        f"Failures: {self._poll_failures}\n"
                        f"Last error: {self._last_poll_error}",
                    )
                self._last_poll_ok_at = time.time()
                self._poll_failures = 0
                self._last_poll_error = ""
                backoff_seconds = 5
                for update in updates.get("result", []):
                    update_id = update.get("update_id")
                    if isinstance(update_id, int):
                        self._offset = update_id + 1
                    self._handle_update(update)
            except Exception as exc:
                self._poll_failures += 1
                self._last_poll_error = str(exc)
                log_error(f"[Telegram] Polling failed: {exc}")
                wait_seconds = min(backoff_seconds, max(5, config.TELEGRAM_POLL_BACKOFF_MAX_SECONDS))
                self._stop_event.wait(wait_seconds)
                backoff_seconds = min(wait_seconds * 2, max(5, config.TELEGRAM_POLL_BACKOFF_MAX_SECONDS))

    def _discard_backlog(self) -> None:
        try:
            updates = self._api_call(
                "getUpdates",
                {"timeout": "0", "allowed_updates": json.dumps(["message"])},
                timeout=10,
            )
        except Exception as exc:
            log_error(f"[Telegram] Could not discard pending updates: {exc}")
            return

        highest_update_id = None
        for update in updates.get("result", []):
            update_id = update.get("update_id")
            if isinstance(update_id, int):
                highest_update_id = update_id if highest_update_id is None else max(highest_update_id, update_id)
        if highest_update_id is not None:
            self._offset = highest_update_id + 1

    def _handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message")
        if not isinstance(message, dict) or not self._is_authorized(message):
            return

        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        text = str(message.get("text") or "").strip()
        if not text:
            return

        command = text.split()[0].split("@", 1)[0].lower()
        if command in ("/start", "/help"):
            self._send_help(chat_id)
        elif command == "/ping":
            self._send_message(chat_id, "pong")
        elif command in ("/status", "/appstatus"):
            self._send_status(chat_id)
        elif command in ("/space", "/disk", "/storage"):
            self._send_space_status(chat_id)
        elif command in ("/network", "/internet", "/wifi"):
            self._send_network_status(chat_id)
        elif command in ("/reconnectwifi", "/reconnectnetwork"):
            self._start_background_command("reconnectwifi", chat_id, self._reconnect_wifi)
        elif command in ("/restartcups", "/cuprestart"):
            self._start_background_command("restartcups", chat_id, self._restart_cups)
        elif command in ("/openapp", "/showapp", "/appopen"):
            self._show_app(chat_id)
        elif command in ("/closeapp", "/hideapp", "/appclose"):
            self._hide_app(chat_id)
        elif command in ("/restartapp", "/apprestart", "/reopen", "/reopenapp"):
            self._start_background_command("restartapp", chat_id, self._reopen_app)
        elif command == "/unlock":
            self._set_update_input_locked(False)
            self._send_message(chat_id, "Input lock cleared.")
        elif command in ("/logs", "/errors"):
            self._send_logs(chat_id)
        elif command == "/restart":
            self._start_background_command("restart", chat_id, self._restart_pi)
        elif command == "/update":
            self._start_background_command("update", chat_id, self._update_project_then_relaunch)
        elif command in ("/printers", "/printer", "/printercheck", "/testprinter"):
            self._send_printer_status(chat_id)
        elif command in ("/setprinter", "/defaultprinter"):
            self._set_printer(chat_id, text.partition(" ")[2].strip())
        elif command in ("/usecupsdefault", "/clearprinter"):
            self._use_cups_default(chat_id)
        else:
            self._send_message(chat_id, "Unknown command. Send /help for available commands.")

    def _is_authorized(self, message: dict[str, Any]) -> bool:
        sender = message.get("from") or {}
        chat = message.get("chat") or {}
        sender_id = str(sender.get("id", ""))
        chat_id = str(chat.get("id", ""))
        return sender_id == self.allowed_user_id and chat_id == self.allowed_user_id

    def _send_help(self, chat_id: int | str | None) -> None:
        self._send_message(
            chat_id,
            "\n".join(
                [
                    "Uvjerenja Terminal controls:",
                    "/help - show this message",
                    "/status - app, Telegram, disk space, network and printer status",
                    "/space - available Raspberry Pi disk space",
                    "/ping - quick Telegram roundtrip test",
                    "/network - internet/Wi-Fi diagnostics",
                    "/reconnectwifi - reconnect Wi-Fi/network",
                    "/restartcups - restart CUPS printing service",
                    "/logs - show latest app errors",
                    "/openapp - show the kiosk window if it is hidden",
                    "/closeapp - hide the kiosk window but keep Telegram alive",
                    "/restartapp - restart/reopen the kiosk app",
                    "/reopen - alias for /restartapp",
                    "/unlock - clear update/input lock if the kiosk gets stuck",
                    "/restart - restart the Raspberry Pi",
                    "/update - update the project, lock inputs, then open the new app version",
                    "/printers - list printers and show the active printer",
                    "/setprinter <name> - set the active printer and CUPS default",
                    "/usecupsdefault - clear app printer override and use CUPS default",
                ]
            ),
        )

    def _send_printer_status(self, chat_id: int | str | None) -> None:
        selected = get_selected_printer()
        info = collect_printer_diagnostics(selected)
        printers = info.get("printers") or []
        preferred = info.get("preferred") or "(uses CUPS default)"
        default = info.get("default") or "(not set)"
        resolved = info.get("resolved") or "(not resolved)"
        ready = "yes" if info.get("ready") else "no"
        message = [
            "Printer status:",
            f"App printer: {preferred}",
            f"CUPS default: {default}",
            f"Resolved printer: {resolved}",
            f"Ready: {ready}",
            f"Available printers: {', '.join(printers) if printers else '(none)'}",
        ]
        if not info.get("ready"):
            message.append(f"Reason: {info.get('ready_message') or info.get('detect_message') or 'unknown'}")
        self._send_message(chat_id, "\n".join(message))

    def _format_time(self, timestamp: float | None) -> str:
        if not timestamp:
            return "never"
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

    def _send_status(self, chat_id: int | str | None) -> None:
        printer = collect_printer_diagnostics(get_selected_printer())
        network = collect_network_diagnostics()
        storage = self._collect_storage_diagnostics()
        uptime_seconds = int(time.time() - self._started_at)
        hidden = False
        try:
            hidden = bool(self.manager.is_kiosk_hidden()) if self.manager is not None else False
        except Exception:
            hidden = False
        lines = [
            "Uvjerenja Terminal status:",
            f"Uptime: {uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m",
            f"Kiosk window: {'hidden' if hidden else 'visible'}",
            f"Active command: {self._active_command or 'none'}",
            f"Disk free /: {storage.get('root_free')} of {storage.get('root_total')} ({storage.get('root_used_percent')} used)",
            f"Disk free app data: {storage.get('var_free')} of {storage.get('var_total')} ({storage.get('var_used_percent')} used)",
            f"Telegram last OK: {self._format_time(self._last_poll_ok_at)}",
            f"Telegram failures: {self._poll_failures}",
            f"Internet: {'yes' if network.get('internet') else 'no'} - {network.get('internet_message')}",
            f"Wi-Fi SSID: {network.get('ssid') or '(unknown)'}",
            f"IP: {network.get('ip') or '(unknown)'}",
            f"App printer: {printer.get('preferred') or '(uses CUPS default)'}",
            f"CUPS default: {printer.get('default') or '(not set)'}",
            f"Resolved printer: {printer.get('resolved') or '(not resolved)'}",
            f"Printer ready: {'yes' if printer.get('ready') else 'no'}",
        ]
        if not printer.get("ready"):
            lines.append(f"Printer reason: {printer.get('ready_message') or printer.get('detect_message') or 'unknown'}")
        if self._last_poll_error:
            lines.append(f"Last Telegram error: {self._last_poll_error}")
        self._send_message(chat_id, "\n".join(lines))

    def _format_bytes(self, value: int | float | None) -> str:
        try:
            size = float(value or 0)
        except Exception:
            return "unknown"
        units = ("B", "KiB", "MiB", "GiB", "TiB")
        unit = units[0]
        for unit in units:
            if size < 1024 or unit == units[-1]:
                break
            size /= 1024
        return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"

    def _disk_usage_dict(self, path: Path) -> dict[str, str]:
        try:
            usage = shutil.disk_usage(str(path))
            used_percent = 0.0 if usage.total <= 0 else ((usage.total - usage.free) / usage.total) * 100
            return {
                "path": str(path),
                "total": self._format_bytes(usage.total),
                "used": self._format_bytes(usage.used),
                "free": self._format_bytes(usage.free),
                "used_percent": f"{used_percent:.0f}%",
            }
        except Exception as exc:
            return {
                "path": str(path),
                "total": "unknown",
                "used": "unknown",
                "free": "unknown",
                "used_percent": "unknown",
                "error": str(exc),
            }

    def _collect_storage_diagnostics(self) -> dict[str, str]:
        root = self._disk_usage_dict(Path("/"))
        var = self._disk_usage_dict(config.VAR_DIR)
        result = {
            "root_path": root.get("path", "/"),
            "root_total": root.get("total", "unknown"),
            "root_used": root.get("used", "unknown"),
            "root_free": root.get("free", "unknown"),
            "root_used_percent": root.get("used_percent", "unknown"),
            "var_path": var.get("path", str(config.VAR_DIR)),
            "var_total": var.get("total", "unknown"),
            "var_used": var.get("used", "unknown"),
            "var_free": var.get("free", "unknown"),
            "var_used_percent": var.get("used_percent", "unknown"),
        }
        if root.get("error"):
            result["root_error"] = root["error"]
        if var.get("error"):
            result["var_error"] = var["error"]
        return result

    def _send_space_status(self, chat_id: int | str | None) -> None:
        storage = self._collect_storage_diagnostics()
        lines = [
            "Raspberry Pi disk space:",
            f"/: free {storage.get('root_free')} / total {storage.get('root_total')} / used {storage.get('root_used_percent')}",
            f"App data ({storage.get('var_path')}): free {storage.get('var_free')} / total {storage.get('var_total')} / used {storage.get('var_used_percent')}",
        ]
        if storage.get("root_error"):
            lines.append(f"Root check error: {storage.get('root_error')}")
        if storage.get("var_error"):
            lines.append(f"App data check error: {storage.get('var_error')}")
        self._send_message(chat_id, "\n".join(lines))

    def _send_network_status(self, chat_id: int | str | None) -> None:
        info = collect_network_diagnostics()
        lines = [
            "Network status:",
            f"Internet: {'yes' if info.get('internet') else 'no'}",
            f"Check: {info.get('internet_message')}",
            f"SSID: {info.get('ssid') or '(unknown)'}",
            f"IP: {info.get('ip') or '(unknown)'}",
            f"Wi-Fi state: {info.get('wifi_state') or '(unknown)'}",
        ]
        self._send_message(chat_id, "\n".join(lines))

    def _send_logs(self, chat_id: int | str | None) -> None:
        try:
            log_files = sorted(config.ERROR_LOG_DIR.glob("*.log"), key=lambda path: path.stat().st_mtime)
            if not log_files:
                self._send_message(chat_id, "No log files found.")
                return

            log_file = log_files[-1]
            lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
            tail_lines = max(10, config.TELEGRAM_LOG_TAIL_LINES)
            text = "\n".join(lines[-tail_lines:]) or "(log is empty)"
            self._send_message(chat_id, f"Latest log: {log_file.name}\n\n{text}")
        except Exception as exc:
            log_error(f"[Telegram] reading logs failed: {exc}")
            self._send_message(chat_id, f"Could not read logs: {exc}")

    def _reconnect_wifi(self, chat_id: int | str | None) -> None:
        self._send_message(chat_id, "Network reconnect command started. Telegram may be unavailable briefly.")
        ok, output = reconnect_network()
        time.sleep(5)
        network = collect_network_diagnostics()
        message = [
            "Network reconnect finished.",
            f"Command OK: {'yes' if ok else 'no'}",
            f"Internet: {'yes' if network.get('internet') else 'no'} - {network.get('internet_message')}",
            f"SSID: {network.get('ssid') or '(unknown)'}",
            f"IP: {network.get('ip') or '(unknown)'}",
        ]
        if output:
            message.append("")
            message.append(self._tail(output, limit=1500))
        self._send_message(chat_id, "\n".join(message))

    def _hide_app(self, chat_id: int | str | None) -> None:
        manager = self.manager
        if manager is None or not hasattr(manager, "request_hide_kiosk"):
            self._send_message(chat_id, "Kiosk window cannot be hidden because no UI manager is available.")
            return
        try:
            manager.request_hide_kiosk()
            self._send_message(chat_id, "Kiosk window hidden. Telegram control stays active. Use /openapp to show it again.")
        except Exception as exc:
            log_error(f"[Telegram] hide app failed: {exc}")
            self._send_message(chat_id, f"Could not hide the kiosk window: {exc}")

    def _show_app(self, chat_id: int | str | None) -> None:
        manager = self.manager
        if manager is None or not hasattr(manager, "request_show_kiosk"):
            self._send_message(chat_id, "Kiosk window cannot be shown because no UI manager is available.")
            return
        try:
            manager.request_show_kiosk()
            self._send_message(chat_id, "Kiosk window shown.")
        except Exception as exc:
            log_error(f"[Telegram] show app failed: {exc}")
            self._send_message(chat_id, f"Could not show the kiosk window: {exc}")

    def _restart_cups(self, chat_id: int | str | None) -> None:
        self._send_message(chat_id, "Restarting CUPS now.")
        ok, output = self._run_shell_command(config.CUPS_RESTART_COMMAND, cwd=config.APP_ROOT, timeout=60)
        self._send_message(chat_id, ("CUPS restarted." if ok else "CUPS restart failed.") + "\n\n" + self._tail(output))
        self._send_printer_status(chat_id)

    def _reopen_app(self, chat_id: int | str | None) -> None:
        ok, output = self._relaunch_updated_app()
        if not ok:
            self._send_message(chat_id, "App reopen failed.\n\n" + self._tail(output))
            return
        self._send_message(chat_id, "Restarting the kiosk app now.")
        self._close_current_app_soon()

    def _set_printer(self, chat_id: int | str | None, requested_name: str) -> None:
        try:
            if not requested_name:
                printers, _, code, message = list_configured_printers()
                available = ", ".join(printers) if printers else "(none)"
                extra = "" if code == "OK" else f"\nCUPS status: {message}"
                self._send_message(chat_id, f"Usage: /setprinter <name>\nAvailable printers: {available}{extra}")
                return

            printer_name = find_configured_printer(requested_name)
            if not printer_name:
                printers, _, code, message = list_configured_printers()
                available = ", ".join(printers) if printers else "(none)"
                if code != "OK" and message:
                    self._send_message(chat_id, f"Could not read CUPS printers: {message}")
                else:
                    self._send_message(chat_id, f"Printer '{requested_name}' was not found.\nAvailable printers: {available}")
                return

            ok, code, result = set_cups_default_printer(printer_name)
            if not ok:
                self._send_message(chat_id, f"Printer was not changed.\n{code}: {result}")
                return

            set_selected_printer(printer_name)
            self._send_message(
                chat_id,
                f"Printer changed successfully.\nApp printer: {printer_name}\nCUPS default: {printer_name}",
            )
        except Exception as exc:
            log_error(f"[Telegram] set printer failed: {exc}")
            self._send_message(chat_id, f"Printer was not changed: {exc}")

    def _use_cups_default(self, chat_id: int | str | None) -> None:
        clear_selected_printer()
        _, default_name, code, message = list_configured_printers()
        if default_name:
            self._send_message(
                chat_id,
                f"App printer override cleared. The app will now use CUPS default: {default_name}",
            )
        elif code != "OK":
            self._send_message(
                chat_id,
                f"App printer override cleared, but CUPS default could not be checked: {message}",
            )
        else:
            self._send_message(
                chat_id,
                "App printer override cleared, but CUPS has no default printer. Use /setprinter <name> first.",
            )

    def _start_background_command(self, name: str, chat_id: int | str | None, target) -> None:
        if not self._command_lock.acquire(blocking=False):
            active = self._active_command or "another command"
            self._send_message(chat_id, f"Busy running {active}. Try again when it finishes.")
            return

        self._active_command = name
        thread = threading.Thread(
            target=self._run_background_command,
            args=(name, chat_id, target),
            name=f"telegram-command-{name}",
            daemon=True,
        )
        thread.start()

    def _run_background_command(self, name: str, chat_id: int | str | None, target) -> None:
        try:
            target(chat_id)
        except Exception as exc:
            if name == "update":
                self._set_update_input_locked(False)
            log_error(f"[Telegram] {name} command failed: {exc}")
            self._send_message(chat_id, f"{name.capitalize()} failed: {exc}")
        finally:
            self._active_command = None
            self._command_lock.release()

    def _restart_pi(self, chat_id: int | str | None) -> None:
        self._send_message(chat_id, "Restart command received. Restarting the Raspberry Pi now.")
        ok, output = self._run_shell_command(
            config.TELEGRAM_REBOOT_COMMAND,
            cwd=config.APP_ROOT,
            timeout=60,
        )
        if not ok:
            self._send_message(
                chat_id,
                "Restart failed. Check that the app user can run the reboot command without a sudo password.\n\n"
                + self._tail(output),
            )

    def _update_project_then_relaunch(self, chat_id: int | str | None) -> None:
        self._set_update_input_locked(
            True,
            "Ažuriranje je u toku. Molimo ne dirajte ekran, tastaturu ili miš.",
        )
        self._send_message(chat_id, "Update command received. Inputs are locked while the project updates.")

        ok, output = self._run_update()
        if not ok:
            self._set_update_input_locked(False)
            self._send_message(chat_id, "Update failed. Inputs are unlocked and the old app is still running.\n\n" + self._tail(output))
            return

        if not config.TELEGRAM_RELAUNCH_AFTER_UPDATE:
            self._set_update_input_locked(False)
            self._send_message(
                chat_id,
                "Update completed successfully, but relaunch is disabled. Restart or reopen the app manually.\n\n"
                + self._tail(output),
            )
            return

        ok, relaunch_output = self._relaunch_updated_app()
        if not ok:
            self._set_update_input_locked(False)
            self._send_message(
                chat_id,
                "Update succeeded, but the new app version could not be opened. Inputs are unlocked.\n\n"
                + self._tail(relaunch_output),
            )
            return

        self._send_message(
            chat_id,
            "Update completed successfully. Opening the new app version now.\n\n" + self._tail(output),
        )
        self._close_current_app_soon()

    def _run_update(self) -> tuple[bool, str]:
        if config.TELEGRAM_UPDATE_COMMAND.strip():
            return self._run_shell_command(
                config.TELEGRAM_UPDATE_COMMAND,
                cwd=config.APP_ROOT,
                timeout=config.TELEGRAM_COMMAND_TIMEOUT,
            )

        repo_root = self._find_git_root(config.APP_ROOT) or self._find_git_root(Path.cwd())
        if repo_root is None:
            return (
                False,
                "No Git repository was found for the running app. "
                "Set POTVRDE_UPDATE_COMMAND in .env, for example: "
                "cd /home/pi/Raspberry-Pi-main && git pull --ff-only && ./install_uvjerenja_terminal.sh",
            )

        outputs: list[str] = []
        commands: list[list[str]] = [["git", "-C", str(repo_root), "pull", "--ff-only"]]
        requirements_file = repo_root / "requirements.txt"
        if requirements_file.exists():
            commands.append([sys.executable, "-m", "pip", "install", "-r", str(requirements_file)])

        for command in commands:
            ok, output = self._run_process(command, cwd=repo_root, timeout=config.TELEGRAM_COMMAND_TIMEOUT)
            outputs.append(f"$ {self._format_command(command)}\n{output}".strip())
            if not ok:
                return False, "\n\n".join(outputs)
        return True, "\n\n".join(outputs)

    def _set_update_input_locked(self, locked: bool, message: str | None = None) -> None:
        manager = self.manager
        if manager is None or not hasattr(manager, "set_input_locked"):
            return
        try:
            manager.set_input_locked(locked, message)
        except Exception as exc:
            log_error(f"[Telegram] Could not change kiosk input lock: {exc}")

    def _relaunch_updated_app(self) -> tuple[bool, str]:
        command = config.TELEGRAM_RELAUNCH_COMMAND.strip()
        if not command:
            return False, "POTVRDE_RELAUNCH_COMMAND is empty."

        try:
            process = subprocess.Popen(
                command,
                cwd=str(config.APP_ROOT),
                shell=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
        except Exception as exc:
            return False, f"Failed to start relaunch command: {exc}"

        try:
            return_code = process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            return True, f"Started relaunch command: {command}"

        return (
            False,
            "Relaunch command exited too quickly with code "
            f"{return_code}. Command: {command}. Check the launcher log in {config.ERROR_LOG_DIR}.",
        )

    def _close_current_app_soon(self) -> None:
        self._stop_event.set()

        def close_current_app() -> None:
            manager = self.manager
            if manager is not None and hasattr(manager, "request_shutdown"):
                try:
                    manager.request_shutdown()
                    return
                except Exception as exc:
                    log_error(f"[Telegram] Could not request app shutdown: {exc}")
            os._exit(0)

        threading.Timer(1.5, close_current_app).start()

    def _find_git_root(self, start: Path) -> Path | None:
        try:
            start = start.resolve()
        except Exception:
            pass

        for candidate in (start, *start.parents):
            if (candidate / ".git").exists():
                return candidate
        return None

    def _run_shell_command(self, command: str, cwd: Path, timeout: int) -> tuple[bool, str]:
        if not command.strip():
            return False, "Command is empty."
        return self._run_process(command, cwd=cwd, timeout=timeout, shell=True)

    def _run_process(
        self,
        command: list[str] | str,
        cwd: Path,
        timeout: int,
        *,
        shell: bool = False,
    ) -> tuple[bool, str]:
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd),
                shell=shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            return completed.returncode == 0, completed.stdout or f"Exit code: {completed.returncode}"
        except subprocess.TimeoutExpired as exc:
            output = exc.stdout or ""
            return False, f"Command timed out after {timeout} seconds.\n{output}"
        except FileNotFoundError as exc:
            return False, f"Command not found: {exc}"

    def _api_call(self, method: str, params: dict[str, str], timeout: int) -> dict[str, Any]:
        data = urllib.parse.urlencode(params).encode("utf-8")
        request = urllib.request.Request(f"{self.api_url}/{method}", data=data, method="POST")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not payload.get("ok"):
            raise RuntimeError(payload.get("description") or f"Telegram API call failed: {method}")
        return payload

    def _send_message(self, chat_id: int | str | None, text: str) -> None:
        if chat_id is None:
            return
        attempts = max(1, config.TELEGRAM_SEND_RETRY_ATTEMPTS)
        delay = max(0, config.TELEGRAM_SEND_RETRY_DELAY_SECONDS)
        for attempt in range(1, attempts + 1):
            try:
                self._api_call(
                    "sendMessage",
                    {
                        "chat_id": str(chat_id),
                        "text": self._tail(text, limit=3500),
                        "disable_web_page_preview": "true",
                    },
                    timeout=15,
                )
                return
            except (urllib.error.URLError, RuntimeError, TimeoutError) as exc:
                if attempt >= attempts:
                    log_error(f"[Telegram] Failed to send message after {attempts} attempt(s): {exc}")
                    return
                if delay > 0:
                    self._stop_event.wait(delay * attempt)

    def _tail(self, text: str, limit: int = 2500) -> str:
        text = text.strip()
        if len(text) <= limit:
            return text
        return "... output truncated ...\n" + text[-limit:]

    def _format_command(self, command: list[str] | str) -> str:
        if isinstance(command, str):
            return command
        return " ".join(shlex.quote(part) for part in command)


def start_telegram_control_bot(manager: Any | None = None) -> TelegramControlBot | None:
    token = config.TELEGRAM_BOT_TOKEN.strip()
    if not config.TELEGRAM_ENABLED:
        log_info("[Telegram] Control bot disabled.")
        return None
    if token in PLACEHOLDER_TOKENS or ":" not in token:
        log_info("[Telegram] Control bot not started because POTVRDE_TELEGRAM_BOT_TOKEN is not configured.")
        return None

    bot = TelegramControlBot(manager=manager)
    bot.start()
    return bot
