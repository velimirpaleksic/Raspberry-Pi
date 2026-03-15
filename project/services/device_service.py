from __future__ import annotations

import datetime as dt
import shutil
import subprocess
from typing import Any, Dict, List

from project.core import config
from project.services.document_service import record_system_event
from project.services.settings_service import get_bool_setting, get_int_setting, get_setting, set_bool_setting, set_setting

MIN_BRIGHTNESS_PERCENT = 30
MAX_BRIGHTNESS_PERCENT = 100


def _run(args: List[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout or config.SUBPROCESS_TIMEOUT,
        check=False,
    )


def _command_exists(name: str) -> bool:
    return bool(shutil.which(name))


def _pick_xrandr_output() -> str:
    if not _command_exists("xrandr"):
        return ""
    try:
        proc = _run(["xrandr", "--query"], timeout=10)
        if proc.returncode != 0:
            return ""
        for line in (proc.stdout or "").splitlines():
            if " connected" in line:
                return line.split()[0].strip()
    except Exception:
        return ""
    return ""


def clamp_brightness(value: int) -> int:
    try:
        return max(MIN_BRIGHTNESS_PERCENT, min(MAX_BRIGHTNESS_PERCENT, int(value)))
    except Exception:
        return 100


def get_terminal_name() -> str:
    return (get_setting("terminal_name", config.APP_TITLE) or config.APP_TITLE).strip()


def get_terminal_location() -> str:
    return (get_setting("terminal_location", "") or "").strip()


def get_idle_timeout_ms() -> int:
    return get_int_setting("idle_timeout_ms", config.IDLE_TIMEOUT_MS)


def get_display_brightness_percent() -> int:
    return clamp_brightness(get_int_setting("display_brightness_percent", 100))


def is_screensaver_enabled() -> bool:
    return get_bool_setting("screensaver_enabled", False)


def save_terminal_identity(*, name: str, location: str) -> Dict[str, Any]:
    terminal_name = (name or "").strip() or config.APP_TITLE
    terminal_location = (location or "").strip()
    set_setting("terminal_name", terminal_name)
    set_setting("terminal_location", terminal_location)
    record_system_event("terminal_identity_updated", f"Terminal identity updated: name={terminal_name} location={terminal_location or '-'}")
    return {"ok": True, "terminal_name": terminal_name, "terminal_location": terminal_location, "message": "Naziv terminala i lokacija su sačuvani."}


def save_idle_timeout_ms(value_ms: int) -> Dict[str, Any]:
    safe_value = max(15_000, min(15 * 60_000, int(value_ms)))
    set_setting("idle_timeout_ms", str(safe_value))
    record_system_event("idle_timeout_updated", f"Idle timeout updated to {safe_value} ms")
    return {"ok": True, "idle_timeout_ms": safe_value, "message": "Idle timeout sačuvan."}


def apply_display_settings(*, brightness_percent: int, screensaver_enabled: bool) -> Dict[str, Any]:
    brightness = clamp_brightness(brightness_percent)
    commands: List[Dict[str, Any]] = []
    ok = True

    set_setting("display_brightness_percent", str(brightness))
    set_bool_setting("screensaver_enabled", bool(screensaver_enabled))

    xrandr_output = _pick_xrandr_output()
    if xrandr_output:
        proc = _run(["xrandr", "--output", xrandr_output, "--brightness", f"{brightness / 100:.2f}"], timeout=10)
        row = {"command": f"xrandr --output {xrandr_output} --brightness {brightness / 100:.2f}", "ok": proc.returncode == 0, "stdout": (proc.stdout or "").strip(), "stderr": (proc.stderr or "").strip()}
        ok = ok and row["ok"]
        commands.append(row)
    elif _command_exists("brightnessctl"):
        proc = _run(["brightnessctl", "set", f"{brightness}%"], timeout=10)
        row = {"command": f"brightnessctl set {brightness}%", "ok": proc.returncode == 0, "stdout": (proc.stdout or "").strip(), "stderr": (proc.stderr or "").strip()}
        ok = ok and row["ok"]
        commands.append(row)
    else:
        commands.append({"command": "brightness", "ok": False, "stdout": "", "stderr": "xrandr/brightnessctl nisu dostupni; postavka je sačuvana, ali svjetlina nije promijenjena."})

    if _command_exists("xset"):
        sequence = [["xset", "s", "on"], ["xset", "+dpms"], ["xset", "s", "300", "300"]] if screensaver_enabled else [["xset", "s", "off"], ["xset", "-dpms"], ["xset", "s", "noblank"]]
        for cmd in sequence:
            proc = _run(cmd, timeout=10)
            row = {"command": " ".join(cmd), "ok": proc.returncode == 0, "stdout": (proc.stdout or "").strip(), "stderr": (proc.stderr or "").strip()}
            ok = ok and row["ok"]
            commands.append(row)
    else:
        commands.append({"command": "xset", "ok": False, "stdout": "", "stderr": "xset nije dostupan; screensaver postavka je sačuvana, ali X11 nije ažuriran."})

    set_setting("display_last_applied_at", dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    record_system_event("display_settings_applied", f"Display settings applied: brightness={brightness} screensaver={'on' if screensaver_enabled else 'off'} ok={ok}")
    return {"ok": ok, "brightness_percent": brightness, "screensaver_enabled": bool(screensaver_enabled), "commands": commands, "message": "Display postavke primijenjene." if ok else "Display postavke su sačuvane, ali neke sistemske komande nisu prošle."}


def get_terminal_settings_snapshot() -> Dict[str, Any]:
    idle_ms = get_idle_timeout_ms()
    snapshot = {
        "terminal_name": get_terminal_name(),
        "terminal_location": get_terminal_location(),
        "idle_timeout_ms": idle_ms,
        "idle_timeout_seconds": int(idle_ms / 1000),
        "brightness_percent": get_display_brightness_percent(),
        "screensaver_enabled": is_screensaver_enabled(),
        "display_last_applied_at": (get_setting("display_last_applied_at", "") or "").strip(),
        "app_title": config.APP_TITLE,
        "debug_mode": bool(config.DEBUG_MODE),
        "allow_escape_exit": bool(config.ALLOW_ESCAPE_EXIT),
        "timestamp": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    snapshot["message"] = f"{snapshot['terminal_name']} | {snapshot['terminal_location'] or 'Lokacija nije postavljena'} | idle {snapshot['idle_timeout_seconds']} s"
    return snapshot


def format_terminal_settings_snapshot(snapshot: Dict[str, Any]) -> str:
    return "\n".join([
        f"Naziv terminala: {snapshot.get('terminal_name') or '-'}",
        f"Lokacija: {snapshot.get('terminal_location') or '-'}",
        f"Vrijeme: {snapshot.get('timestamp') or '-'}",
        f"Idle timeout: {snapshot.get('idle_timeout_seconds', 0)} s",
        f"Svjetlina: {snapshot.get('brightness_percent', 100)}%",
        f"Screensaver: {'UKLJUČEN' if snapshot.get('screensaver_enabled') else 'ISKLJUČEN'}",
        f"Zadnja primjena display postavki: {snapshot.get('display_last_applied_at') or 'nikad'}",
        f"Kiosk mode: {'DEBUG' if snapshot.get('debug_mode') else 'PRODUCTION'} | Escape exit: {'da' if snapshot.get('allow_escape_exit') else 'ne'}",
    ])
