import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
import time
import tkinter as tk
from typing import Callable


_TOUCH_DEBUG = os.getenv("POTVRDE_TOUCH_DEBUG", "").strip() in {"1", "true", "TRUE", "yes", "YES", "on", "ON"}
_KEYBOARD_LOGGER: logging.Logger | None = None


def _make_keyboard_log_handler() -> logging.Handler | None:
    directories: list[Path] = []
    try:
        from project.core import config

        directories.append(config.ERROR_LOG_DIR)
    except Exception:
        pass
    directories.extend([Path("/var/lib/uvjerenja-terminal/logs"), Path.cwd() / "var" / "logs"])
    for directory in directories:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                str(directory / "keyboard.log"),
                maxBytes=1_000_000,
                backupCount=3,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s", "%d.%m.%Y %H:%M:%S"))
            return handler
        except Exception:
            continue
    return None


def keyboard_logger() -> logging.Logger:
    global _KEYBOARD_LOGGER
    if _KEYBOARD_LOGGER is not None:
        return _KEYBOARD_LOGGER

    logger = logging.getLogger("uvjerenja_terminal.keyboard")
    logger.setLevel(logging.DEBUG if _TOUCH_DEBUG else logging.WARNING)
    logger.propagate = False
    if not logger.handlers:
        handler = _make_keyboard_log_handler()
        logger.addHandler(handler if handler is not None else logging.NullHandler())
    _KEYBOARD_LOGGER = logger
    return logger


def log_keyboard_warning(message: str) -> None:
    try:
        keyboard_logger().warning(message)
    except Exception:
        pass


def log_keyboard_exception(message: str) -> None:
    try:
        if _TOUCH_DEBUG:
            keyboard_logger().exception(message)
        else:
            keyboard_logger().error(message)
    except Exception:
        pass


class VirtualKeyboard(tk.Frame):
    """Touch-first on-screen keyboard for old resistive screens.

    Key actions run on <ButtonPress-1>. The keyboard never depends on normal
    Button release commands, and it keeps an explicit active_entry so tapping a
    key cannot steal the target input field.
    """

    ALPHA_ROWS = [
        list("љњертзуиопш"),
        list("асдфгхјклчћ"),
        ["џ", "ц", "в", "б", "н", "м", "ђ", "ж", "backspace"],
        ["space"],
    ]
    NUMERIC_ROWS = [
        ["1", "2", "3"],
        ["4", "5", "6"],
        ["7", "8", "9"],
        ["0", "backspace"],
    ]
    NUMERIC_FIELD_KEYS = {"godina", "mjesec", "dan"}

    KEY_BG = "#5b5d63"
    KEY_ACTIVE_BG = "#737780"
    KEY_DISABLED_BG = "#d4d4d4"
    KEY_FG = "#ffffff"
    KEY_DISABLED_FG = "#777777"
    DOCK_BG = "#f5f5f5"

    def __init__(
        self,
        parent,
        *,
        ui_scale: float = 1.0,
        target_width: int | None = None,
        target_height: int | None = None,
        bg: str = DOCK_BG,
        **kwargs,
    ):
        super().__init__(parent, relief="flat", bd=0, padx=0, pady=0, bg=bg, cursor="none", takefocus=0, **kwargs)
        self.ui_scale = max(1.0, float(ui_scale or 1.0))
        self.target_width = int(target_width or 1000)
        self.target_height = int(target_height or 260)
        self.active_entry: tk.Entry | None = None
        self._last_active_entry: tk.Entry | None = None
        self.mode = "alpha"
        self.force_uppercase = True
        self._keys: list[tk.Widget] = []
        self._entry_callbacks: dict[tk.Entry, Callable[[tk.Entry], None]] = {}
        self._last_press: tuple[str, float] | None = None
        self._logger = keyboard_logger()
        self._touch_debug = _TOUCH_DEBUG
        self._warned_missing_field_keys: set[str] = set()

        self.configure(height=self.target_height)
        self.pack_propagate(False)
        self._build_shell(bg)
        self.set_mode("alpha", uppercase=True)

    def _build_shell(self, bg: str) -> None:
        # Deliberately no dark keyboard slab/background. Only the keys are grey.
        self.shell = tk.Frame(
            self,
            bg=bg,
            bd=0,
            highlightthickness=0,
            padx=max(4, int(round(5 * self.ui_scale))),
            pady=max(3, int(round(4 * self.ui_scale))),
            cursor="none",
            takefocus=0,
        )
        self.shell.pack(fill="both", expand=True, padx=0, pady=0)

    def bind_entry(
        self,
        entry: tk.Entry,
        *,
        mode: str = "alpha",
        uppercase_first: bool = False,
        one_word: bool = False,
        max_words: int | None = None,
        on_change: Callable[[tk.Entry], None] | None = None,
        placeholder: str | None = None,
    ) -> None:
        requested_mode = mode if mode in {"alpha", "numeric"} else "alpha"
        field_key = getattr(entry, "field_key", "")
        if requested_mode == "numeric" and field_key not in self.NUMERIC_FIELD_KEYS:
            self._log_warning(
                f"[VK] Ignoring numeric keyboard mode for non-date field {field_key or entry!s}; using alpha instead"
            )
            requested_mode = "alpha"
        entry._vk_mode = requested_mode
        entry._vk_placeholder = placeholder
        entry._vk_uppercase_first = bool(uppercase_first)
        entry._vk_one_word = bool(one_word)
        entry._vk_max_words = int(max_words) if max_words else None
        if on_change is not None:
            self._entry_callbacks[entry] = on_change
        entry.bind("<FocusIn>", self._handle_focus_in, add=True)
        entry.bind("<ButtonPress-1>", self._handle_focus_in, add=True)
        entry.bind("<KeyRelease>", self._handle_entry_changed, add=True)
        entry.bind("<ButtonRelease-1>", self._handle_entry_changed, add=True)
        entry.bind("<<VKChanged>>", self._handle_entry_changed, add=True)

    def set_active_entry(self, entry: tk.Entry | None) -> None:
        try:
            if self._entry_is_usable(entry):
                self.active_entry = entry
                self._last_active_entry = entry
                self._sync_mode_for_entry(entry)
            else:
                self.active_entry = None
        except Exception:
            self.active_entry = None
            self._log_exception("[VK] Failed to set active entry")

    def clear_active_entry(self) -> None:
        self.active_entry = None
        self._last_active_entry = None
        self._refresh_key_labels()

    def set_mode(self, mode: str, *, uppercase: bool | None = None) -> None:
        mode = mode if mode in {"alpha", "numeric"} else "alpha"
        if uppercase is not None:
            self.force_uppercase = bool(uppercase)
        rebuild = self.mode != mode or not self.shell.winfo_children()
        self.mode = mode
        if rebuild:
            self._clear_shell()
            if self.mode == "numeric":
                self._build_numeric_keyboard()
            else:
                self._build_alpha_keyboard()
        self._refresh_key_labels()

    def _handle_focus_in(self, event=None):
        entry = getattr(event, "widget", None)
        if isinstance(entry, tk.Entry):
            self.set_active_entry(entry)

    def _handle_entry_changed(self, event=None):
        entry = getattr(event, "widget", None)
        if isinstance(entry, tk.Entry):
            self.set_active_entry(entry)

    def _entry_is_usable(self, entry) -> bool:
        if not isinstance(entry, tk.Entry):
            return False
        try:
            return bool(entry.winfo_exists())
        except Exception:
            return False

    def _clear_shell(self) -> None:
        for child in self.shell.winfo_children():
            child.destroy()
        self._keys.clear()

    def _sync_mode_for_entry(self, entry: tk.Entry | None) -> None:
        if not self._entry_is_usable(entry):
            return
        try:
            mode = getattr(entry, "_vk_mode", "alpha")
            field_key = self._field_key_for_entry(entry)
            if mode == "numeric" and field_key not in self.NUMERIC_FIELD_KEYS:
                self._log_warning(
                    f"[VK] Refusing numeric keyboard for non-date field {field_key or self._entry_description(entry)}; using alpha"
                )
                mode = "alpha"
                try:
                    entry._vk_mode = "alpha"
                except Exception:
                    pass
            uppercase = False
            if mode == "alpha" and bool(getattr(entry, "_vk_uppercase_first", False)):
                uppercase = self._should_use_uppercase(entry)
            self.set_mode(mode, uppercase=uppercase)
        except Exception:
            self._log_exception(f"[VK] Failed to sync mode for {self._entry_description(entry)}")

    def _should_use_uppercase(self, entry: tk.Entry) -> bool:
        text = self._entry_effective_text(entry)
        try:
            cursor = entry.index(tk.INSERT)
        except Exception:
            cursor = len(text)
        cursor = max(0, min(cursor, len(text)))
        prefix = text[:cursor]
        if not prefix:
            return True
        if bool(getattr(entry, "_vk_one_word", False)):
            return False
        return prefix[-1].isspace()

    def _entry_effective_text(self, entry: tk.Entry) -> str:
        try:
            text = entry.get()
        except Exception:
            self._log_exception(f"[VK] Could not read entry text for {self._entry_description(entry)}")
            return ""
        placeholder = getattr(entry, "_vk_placeholder", None)
        return "" if placeholder and text == placeholder else text

    def _build_alpha_keyboard(self) -> None:
        self._build_keyboard(self.ALPHA_ROWS, alpha=True)

    def _build_numeric_keyboard(self) -> None:
        self._build_keyboard(self.NUMERIC_ROWS, alpha=False)

    def _build_keyboard(self, rows: list[list[str]], *, alpha: bool) -> None:
        keyboard = tk.Frame(self.shell, bg=self.DOCK_BG, cursor="none", takefocus=0)
        keyboard.pack(fill="both", expand=True)

        available_w = max(320, self.target_width - 18)
        available_h = max(160, self.target_height - 12)
        row_count = len(rows)
        gap = max(6, int(round(7 * self.ui_scale)))

        key_h = int((available_h - gap * (row_count - 1)) / row_count)
        if alpha:
            key_h = max(50, min(int(round(66 * self.ui_scale)), key_h))
            max_keys = 11
            key_w = int((available_w - gap * (max_keys - 1)) / max_keys)
            key_w = max(58, min(int(round(92 * self.ui_scale)), key_w))
            space_w = min(available_w, key_w * 5 + gap * 4)
        else:
            gap = max(8, min(12, int(round(10 * self.ui_scale))))
            key_h = int((available_h - gap * (row_count - 1)) / row_count)
            key_h = max(50, min(int(round(60 * self.ui_scale)), key_h))
            group_w = min(
                available_w,
                max(
                    int(round(360 * self.ui_scale)),
                    min(int(round(430 * self.ui_scale)), int(available_w * 0.52)),
                ),
            )
            key_w = int((group_w - gap * 2) / 3)
            key_w = max(int(round(105 * self.ui_scale)), min(int(round(135 * self.ui_scale)), key_w))
            if key_w * 3 + gap * 2 > available_w:
                key_w = max(90, int((available_w - gap * 2) / 3))
            space_w = key_w

        for row_index, row_tokens in enumerate(rows):
            row = tk.Frame(keyboard, bg=self.DOCK_BG, height=key_h, cursor="none", takefocus=0)
            row.pack(anchor="center", pady=(0, 0 if row_index == row_count - 1 else gap))
            for index, token in enumerate(row_tokens):
                width = space_w if token == "space" else key_w
                self._make_key(row, token, width=width, height=key_h)
                if index != len(row_tokens) - 1:
                    tk.Frame(row, width=gap, bg=self.DOCK_BG, takefocus=0).pack(side="left")

    def _make_key(self, parent, token: str, *, width: int, height: int) -> tk.Frame:
        is_action = token in {"backspace", "space"}
        key_font = ("Arial", max(18, int(round(20 * self.ui_scale))), "bold")
        action_font = ("Arial", max(16, int(round(18 * self.ui_scale))), "bold")

        key = tk.Frame(
            parent,
            width=width,
            height=height,
            bg=self.KEY_BG,
            bd=0,
            highlightthickness=0,
            cursor="none",
            takefocus=0,
        )
        key.pack(side="left")
        key.pack_propagate(False)
        key._vk_token = token
        key._normal_bg = self.KEY_BG
        key._active_bg = self.KEY_ACTIVE_BG
        key._disabled_bg = self.KEY_DISABLED_BG
        key._vk_disabled = False

        label = tk.Label(
            key,
            text=self._display_label(token),
            font=action_font if is_action else key_font,
            bg=key._normal_bg,
            fg=self.KEY_FG,
            bd=0,
            relief="flat",
            cursor="none",
            takefocus=0,
        )
        label.pack(fill="both", expand=True)
        label._vk_key_frame = key

        for widget in (key, label):
            widget.bind("<ButtonPress-1>", lambda event, t=token, k=key: self._touch_key_press(t, k), add=False)
            widget.bind("<ButtonRelease-1>", lambda event, k=key: self._touch_key_release(k), add=False)
            widget.bind("<Leave>", lambda event, k=key: self._touch_key_release(k), add=False)

        self._keys.append(key)
        return key

    def _display_label(self, token: str) -> str:
        if token == "backspace":
            return "⌫"
        if token == "space":
            return "Размак"
        if self.mode == "alpha" and self.force_uppercase:
            return token.upper()
        return token.lower()

    def _refresh_key_labels(self) -> None:
        for key in self._keys:
            token = getattr(key, "_vk_token", "")
            key._vk_disabled = self._token_disabled(token)
            for child in key.winfo_children():
                if isinstance(child, tk.Label):
                    try:
                        child.config(
                            text=self._display_label(token),
                            fg=self.KEY_DISABLED_FG if key._vk_disabled else self.KEY_FG,
                        )
                    except Exception:
                        pass
            self._set_key_bg(key, active=False)

    def _token_disabled(self, token: str) -> bool:
        if token != "space":
            return False
        entry = self.active_entry if self._entry_is_usable(self.active_entry) else None
        if entry is None and self._entry_is_usable(self._last_active_entry):
            entry = self._last_active_entry
        return bool(entry is not None and getattr(entry, "_vk_one_word", False))

    def _log_debug(self, message: str) -> None:
        if not self._touch_debug:
            return
        try:
            self._logger.debug(message)
        except Exception:
            pass

    def _log_warning(self, message: str) -> None:
        try:
            self._logger.warning(message)
        except Exception:
            pass

    def _log_exception(self, message: str) -> None:
        try:
            if self._touch_debug:
                self._logger.exception(message)
            else:
                self._logger.error(message)
        except Exception:
            pass

    def _entry_description(self, entry: tk.Entry | None) -> str:
        if not self._entry_is_usable(entry):
            return "none"
        field_key = getattr(entry, "field_key", "")
        field_label = getattr(entry, "field_label", "") or str(entry)
        return f"{field_key or '<missing>'}/{field_label}"

    def _safe_entry_value(self, entry: tk.Entry | None) -> str:
        if not self._entry_is_usable(entry):
            return ""
        try:
            return entry.get()
        except Exception:
            return "<unavailable>"

    def _focused_widget_description(self) -> str:
        try:
            focused = self.winfo_toplevel().focus_get()
        except Exception:
            focused = None
        if focused is None:
            return "none"
        if isinstance(focused, tk.Entry):
            return self._entry_description(focused)
        return str(focused)

    def _field_key_for_entry(self, entry: tk.Entry) -> str:
        field_key = getattr(entry, "field_key", "")
        if not field_key:
            entry_id = str(entry)
            if entry_id not in self._warned_missing_field_keys:
                self._warned_missing_field_keys.add(entry_id)
                self._log_warning(f"[VK] Active entry has no field_key: {entry_id}")
        return field_key

    def _log_touch_result(
        self,
        *,
        token: str,
        entry_before: tk.Entry | None,
        value_before: str,
        value_after: str,
        accepted: bool,
        reason: str,
    ) -> None:
        if self._touch_debug:
            state = "accepted" if accepted else f"blocked:{reason or 'unknown'}"
            self._log_debug(
                "[VK] key=%r mode=%s field=%s focused=%s before=%r after=%r active_after=%s %s"
                % (
                    token,
                    self.mode,
                    self._entry_description(entry_before),
                    self._focused_widget_description(),
                    value_before,
                    value_after,
                    self._entry_description(self.active_entry),
                    state,
                )
            )
        elif reason in {"no active field", "active field unavailable"}:
            self._log_warning(f"[VK] Key {token!r} ignored: {reason}")

    def _touch_key_press(self, token: str, key: tk.Frame):
        if self._token_disabled(token):
            key._vk_disabled = True
            self._set_key_bg(key, active=False)
            self._log_touch_result(
                token=token,
                entry_before=self.active_entry,
                value_before=self._safe_entry_value(self.active_entry),
                value_after=self._safe_entry_value(self.active_entry),
                accepted=False,
                reason="space disabled for one-word field",
            )
            return "break"

        # Tiny duplicate guard only for the same widget/token in the same event burst.
        # It does not block normal repeated taps.
        now = time.monotonic()
        last = self._last_press
        self._last_press = (token, now)
        if last and last[0] == token and now - last[1] < 0.025:
            self._log_touch_result(
                token=token,
                entry_before=self.active_entry,
                value_before=self._safe_entry_value(self.active_entry),
                value_after=self._safe_entry_value(self.active_entry),
                accepted=False,
                reason="debounced duplicate press",
            )
            return "break"

        entry_before = self._focused_entry()
        if not self._entry_is_usable(entry_before):
            self._log_touch_result(
                token=token,
                entry_before=entry_before,
                value_before="",
                value_after="",
                accepted=False,
                reason="no active field",
            )
            return "break"

        self._set_key_bg(key, active=True)
        try:
            key.after(80, lambda k=key: self._set_key_bg(k, active=False))
        except Exception:
            pass

        value_before = self._safe_entry_value(entry_before)
        accepted = False
        reason = ""
        try:
            accepted, reason = self._on_token(token)
        except Exception:
            reason = "exception"
            self._log_exception(f"[VK] Key action failed for token={token!r} field={self._entry_description(entry_before)}")
        value_after = self._safe_entry_value(entry_before)
        self._log_touch_result(
            token=token,
            entry_before=entry_before,
            value_before=value_before,
            value_after=value_after,
            accepted=accepted,
            reason=reason,
        )
        return "break"

    def _touch_key_release(self, key: tk.Frame):
        self._set_key_bg(key, active=False)
        return "break"

    def _set_key_bg(self, key: tk.Frame, *, active: bool) -> None:
        disabled = bool(getattr(key, "_vk_disabled", False))
        if disabled:
            color = getattr(key, "_disabled_bg", self.KEY_DISABLED_BG)
        else:
            color = getattr(key, "_active_bg" if active else "_normal_bg", self.KEY_BG)
        try:
            key.config(bg=color)
            for child in key.winfo_children():
                child.config(bg=color)
                if isinstance(child, tk.Label):
                    child.config(fg=self.KEY_DISABLED_FG if disabled else self.KEY_FG)
        except Exception:
            pass

    def _on_token(self, token: str) -> tuple[bool, str]:
        if token == "backspace":
            return self.backspace_pressed()
        if token == "space":
            if self._token_disabled(token):
                return False, "space disabled for one-word field"
            return self.insert_char(" ")
        return self.insert_char(token)

    def _focused_entry(self) -> tk.Entry | None:
        if self._entry_is_usable(self.active_entry):
            return self.active_entry
        if self.active_entry is not None:
            self._log_warning(f"[VK] Stored active entry is unavailable: {self.active_entry}")
            self.active_entry = None
        try:
            focused = self.winfo_toplevel().focus_get()
        except Exception:
            focused = None
        if isinstance(focused, tk.Entry):
            self.active_entry = focused
            self._last_active_entry = focused
            return focused
        if self._entry_is_usable(self._last_active_entry):
            self.active_entry = self._last_active_entry
            self._sync_mode_for_entry(self.active_entry)
            return self.active_entry
        return None

    def insert_char(self, ch: str) -> tuple[bool, str]:
        entry = self._focused_entry()
        if not self._entry_is_usable(entry):
            return False, "no active field"

        field_key = self._field_key_for_entry(entry)
        if self.mode == "numeric" and field_key not in self.NUMERIC_FIELD_KEYS:
            self._log_warning(
                f"[VK] Numeric key {ch!r} blocked for non-date field {field_key or self._entry_description(entry)}"
            )
            self._sync_mode_for_entry(entry)
            return False, "numeric keyboard blocked for non-date field"
        one_word = bool(getattr(entry, "_vk_one_word", False))
        max_words = getattr(entry, "_vk_max_words", None)

        if field_key == "godina":
            if not ch.isdigit():
                return False, "non-digit blocked"
            try:
                digits = "".join(c for c in entry.get() if c.isdigit())
            except Exception:
                self._log_exception(f"[VK] Could not read year field before inserting {ch!r}")
                return False, "active field unavailable"
            suffix = digits[2:] if digits.startswith("20") else digits[-2:]
            suffix = suffix[:2]
            if len(suffix) >= 2:
                self._after_edit(entry)
                return False, "max digits reached"
            if not self._replace_entry(entry, "20" + suffix + ch):
                return False, "active field unavailable"
            self._after_edit(entry)
            return True, ""

        if field_key in {"mjesec", "dan"}:
            if not ch.isdigit():
                return False, "non-digit blocked"
            try:
                digits = "".join(c for c in entry.get() if c.isdigit())
            except Exception:
                self._log_exception(f"[VK] Could not read numeric field before inserting {ch!r}")
                return False, "active field unavailable"
            if len(digits) >= 2:
                self._after_edit(entry)
                return False, "max digits reached"

        placeholder = getattr(entry, "_vk_placeholder", None)
        if placeholder and self._safe_entry_value(entry) == placeholder:
            try:
                entry.delete(0, "end")
                entry.config(fg="#111111")
            except Exception:
                self._log_exception(f"[VK] Could not clear placeholder for {self._entry_description(entry)}")
                return False, "active field unavailable"

        if one_word and ch.isspace():
            # A stray space on a one-word field should be invisible and harmless.
            # Do not lock the field, because that makes later letter taps look broken.
            try:
                entry._vk_word_limit_block = False
            except Exception:
                pass
            self._after_edit(entry)
            return False, "one-word field blocks spaces"

        if max_words and ch.isspace():
            text = self._entry_effective_text(entry)
            parts = [p for p in text.strip().split() if p]
            if not text.strip() or text.endswith(" ") or len(parts) >= int(max_words):
                entry._vk_word_limit_block = len(parts) >= int(max_words)
                self._after_edit(entry)
                return False, "word limit reached"
            entry._vk_word_limit_block = False

        if max_words and not ch.isspace():
            if bool(getattr(entry, "_vk_word_limit_block", False)):
                self._after_edit(entry)
                return False, "word limit blocked"

        if self.mode == "alpha":
            ch = ch.upper() if self._should_use_uppercase(entry) else ch.lower()

        try:
            pos = entry.index(tk.INSERT)
            entry.insert(pos, ch)
        except Exception:
            try:
                entry.insert("end", ch)
            except Exception:
                self._log_exception(f"[VK] Could not insert {ch!r} into {self._entry_description(entry)}")
                return False, "active field unavailable"
        self._after_edit(entry)
        return True, ""

    def backspace_pressed(self) -> tuple[bool, str]:
        entry = self._focused_entry()
        if not self._entry_is_usable(entry):
            return False, "no active field"
        try:
            entry._vk_word_limit_block = False
        except Exception:
            pass

        if self._field_key_for_entry(entry) == "godina":
            try:
                digits = "".join(c for c in entry.get() if c.isdigit())
            except Exception:
                self._log_exception("[VK] Could not read year field before backspace")
                return False, "active field unavailable"
            suffix = digits[2:] if digits.startswith("20") else digits[-2:]
            if not suffix:
                self._after_edit(entry)
                return False, "locked year prefix"
            suffix = suffix[:-1]
            if not self._replace_entry(entry, "20" + suffix):
                return False, "active field unavailable"
            self._after_edit(entry)
            return True, ""

        try:
            sel_first = entry.index("sel.first")
            sel_last = entry.index("sel.last")
            entry.delete(sel_first, sel_last)
            changed = True
        except Exception:
            try:
                idx = entry.index(tk.INSERT)
            except Exception:
                idx = len(self._safe_entry_value(entry))
            changed = idx > 0
            if idx > 0:
                try:
                    entry.delete(idx - 1)
                except Exception:
                    self._log_exception(f"[VK] Could not backspace {self._entry_description(entry)}")
                    return False, "active field unavailable"
        self._after_edit(entry)
        return changed, "" if changed else "empty field"

    def _replace_entry(self, entry: tk.Entry, value: str) -> bool:
        try:
            entry.delete(0, "end")
            entry.insert(0, value)
            entry.icursor("end")
            return True
        except Exception:
            self._log_exception(f"[VK] Could not replace {self._entry_description(entry)} with {value!r}")
            return False

    def _after_edit(self, entry: tk.Entry) -> None:
        self.active_entry = entry
        self._last_active_entry = entry
        # Do not call focus_set() here. On old resistive touchscreens/X11,
        # delayed FocusIn events from this call can override a later auto-advance
        # target such as year -> month. The stored active_entry is the source of
        # truth for virtual keyboard input.
        try:
            entry.icursor("end")
        except Exception:
            pass
        try:
            entry.event_generate("<<VKChanged>>")
        except Exception:
            self._log_exception(f"[VK] Could not generate VKChanged for {self._entry_description(entry)}")
        callback = self._entry_callbacks.get(entry)
        if callback is not None:
            try:
                callback(entry)
            except Exception:
                self._log_exception(f"[VK] on_change callback failed for {self._entry_description(entry)}")
        # Make the typed character visible immediately on slow Raspberry Pi/X11 setups.
        try:
            entry.update_idletasks()
        except Exception:
            pass
        if self._entry_is_usable(self.active_entry):
            self._sync_mode_for_entry(self.active_entry)
        else:
            self._sync_mode_for_entry(entry)
