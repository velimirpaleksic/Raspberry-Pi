from __future__ import annotations

import tkinter as tk

from project.gui import screen_ids
from project.gui.touch_input import ask_touch_text
from project.gui.ui_components import polish_descendant_buttons
from project.services.device_service import (
    apply_display_settings,
    format_terminal_settings_snapshot,
    get_display_brightness_percent,
    get_idle_timeout_ms,
    get_terminal_location,
    get_terminal_name,
    get_terminal_settings_snapshot,
    is_screensaver_enabled,
    save_idle_timeout_ms,
    save_terminal_identity,
)


class SettingsScreen(tk.Frame):
    def __init__(self, parent, manager=None):
        super().__init__(parent, bg="#101010")
        self.manager = manager
        self.name_var = tk.StringVar(value=get_terminal_name())
        self.location_var = tk.StringVar(value=get_terminal_location())
        self.idle_seconds_var = tk.IntVar(value=int(get_idle_timeout_ms() / 1000))
        self.brightness_var = tk.IntVar(value=get_display_brightness_percent())
        self.screensaver_var = tk.BooleanVar(value=is_screensaver_enabled())
        self.status_var = tk.StringVar(value="")
        self.clock_var = tk.StringVar(value="")
        self._after_id = None
        self._build_ui()
        polish_descendant_buttons(self)

    def _build_ui(self):
        header = tk.Frame(self, bg="#101010")
        header.pack(fill="x", padx=24, pady=(18, 8))
        tk.Label(header, text="OPŠTE POSTAVKE", font=("Arial", 28, "bold"), fg="white", bg="#101010").pack(side="left")
        tk.Button(header, text="Recovery", command=self._open_recovery, font=("Arial", 14, "bold"), padx=16, pady=8).pack(side="right", padx=(8, 0))
        tk.Button(header, text="Nazad", command=self._go_back, font=("Arial", 14, "bold"), padx=16, pady=8).pack(side="right")

        tk.Label(self, textvariable=self.status_var, font=("Arial", 13, "bold"), fg="#ffcc66", bg="#101010").pack(anchor="w", padx=24)
        tk.Label(self, textvariable=self.clock_var, font=("Arial", 12), fg="#bbbbbb", bg="#101010").pack(anchor="w", padx=24, pady=(4, 10))

        content = tk.Frame(self, bg="#101010")
        content.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)

        identity = self._card(content, "Naziv terminala / lokacija")
        identity.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
        self._build_identity_card(identity)

        kiosk = self._card(content, "Idle timeout i kiosk info")
        kiosk.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=(0, 10))
        self._build_idle_card(kiosk)

        display = self._card(content, "Display / screensaver")
        display.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        self._build_display_card(display)

        snapshot = self._card(content, "Status postavki")
        snapshot.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        self.snapshot_text = tk.Text(snapshot, height=14, font=("Courier New", 12), bg="#101010", fg="#f2f2f2", wrap="word")
        self.snapshot_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.snapshot_text.configure(state="disabled")

    def _card(self, parent, title: str):
        box = tk.Frame(parent, bg="#111111", bd=1, relief="solid")
        tk.Label(box, text=title, font=("Arial", 17, "bold"), fg="white", bg="#111111").pack(anchor="w", padx=14, pady=(12, 8))
        return box

    def _build_identity_card(self, parent):
        body = tk.Frame(parent, bg="#111111")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        tk.Label(body, text="Naziv terminala", font=("Arial", 13, "bold"), fg="white", bg="#111111").pack(anchor="w")
        row1 = tk.Frame(body, bg="#111111")
        row1.pack(fill="x", pady=(4, 12))
        tk.Label(row1, textvariable=self.name_var, font=("Arial", 16), fg="#f2f2f2", bg="#1a1a1a", anchor="w", justify="left", padx=10, pady=10).pack(side="left", fill="x", expand=True)
        tk.Button(row1, text="Uredi", command=self._edit_name, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(8, 0))
        tk.Label(body, text="Lokacija", font=("Arial", 13, "bold"), fg="white", bg="#111111").pack(anchor="w")
        row2 = tk.Frame(body, bg="#111111")
        row2.pack(fill="x", pady=(4, 12))
        tk.Label(row2, textvariable=self.location_var, font=("Arial", 16), fg="#f2f2f2", bg="#1a1a1a", anchor="w", justify="left", padx=10, pady=10).pack(side="left", fill="x", expand=True)
        tk.Button(row2, text="Uredi", command=self._edit_location, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(8, 0))
        tk.Button(body, text="Sačuvaj naziv i lokaciju", command=self._save_identity, font=("Arial", 12, "bold"), padx=14, pady=10).pack(anchor="w")

    def _build_idle_card(self, parent):
        body = tk.Frame(parent, bg="#111111")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        tk.Label(body, text="Idle timeout", font=("Arial", 13, "bold"), fg="white", bg="#111111").pack(anchor="w")
        tk.Label(body, textvariable=self.idle_seconds_var, font=("Arial", 28, "bold"), fg="#7CFF8F", bg="#111111").pack(anchor="w", pady=(6, 8))
        buttons = tk.Frame(body, bg="#111111")
        buttons.pack(anchor="w", pady=(0, 12))
        for label, delta in (("-60s", -60), ("-15s", -15), ("+15s", 15), ("+60s", 60)):
            tk.Button(buttons, text=label, command=lambda d=delta: self._adjust_idle(d), font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(0, 8))
        presets = tk.Frame(body, bg="#111111")
        presets.pack(anchor="w", pady=(0, 12))
        for seconds in (30, 60, 120, 300):
            tk.Button(presets, text=f"{seconds}s", command=lambda s=seconds: self.idle_seconds_var.set(s), font=("Arial", 11, "bold"), padx=10, pady=6).pack(side="left", padx=(0, 8))
        tk.Button(body, text="Sačuvaj idle timeout", command=self._save_idle_timeout, font=("Arial", 12, "bold"), padx=14, pady=10).pack(anchor="w", pady=(0, 12))
        tk.Label(body, text="Kiosk mode info: production mod drži fullscreen/topmost. Escape izlaz je dostupan samo u DEBUG modu.", font=("Arial", 12), fg="#dddddd", bg="#111111", justify="left", wraplength=720).pack(anchor="w")

    def _build_display_card(self, parent):
        body = tk.Frame(parent, bg="#111111")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        tk.Label(body, text="Svjetlina", font=("Arial", 13, "bold"), fg="white", bg="#111111").pack(anchor="w")
        tk.Label(body, textvariable=self.brightness_var, font=("Arial", 28, "bold"), fg="#7CFF8F", bg="#111111").pack(anchor="w", pady=(6, 8))
        controls = tk.Frame(body, bg="#111111")
        controls.pack(anchor="w", pady=(0, 12))
        for label, delta in (("-10%", -10), ("-5%", -5), ("+5%", 5), ("+10%", 10)):
            tk.Button(controls, text=label, command=lambda d=delta: self._adjust_brightness(d), font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Checkbutton(body, text="Dozvoli screensaver / gašenje ekrana", variable=self.screensaver_var, font=("Arial", 12, "bold"), fg="white", bg="#111111", selectcolor="#111111", activebackground="#111111", activeforeground="white").pack(anchor="w", pady=(4, 12))
        actions = tk.Frame(body, bg="#111111")
        actions.pack(anchor="w")
        tk.Button(actions, text="Primijeni display postavke", command=self._apply_display, font=("Arial", 12, "bold"), padx=14, pady=10).pack(side="left")
        tk.Button(actions, text="Mreža / Wi‑Fi", command=self._open_network, font=("Arial", 12, "bold"), padx=14, pady=10).pack(side="left", padx=8)

    def on_show(self):
        if not self.manager or not self.manager.state.get("admin_authenticated"):
            if self.manager:
                self.manager.state["admin_post_auth_target"] = screen_ids.SETTINGS
                self.manager.show_frame(screen_ids.ADMIN)
            return
        self._load_values()
        self._tick_clock()
        self._refresh_snapshot()

    def _load_values(self):
        self.name_var.set(get_terminal_name())
        self.location_var.set(get_terminal_location())
        self.idle_seconds_var.set(int(get_idle_timeout_ms() / 1000))
        self.brightness_var.set(get_display_brightness_percent())
        self.screensaver_var.set(is_screensaver_enabled())
        self.status_var.set("")

    def _tick_clock(self):
        snapshot = get_terminal_settings_snapshot()
        self.clock_var.set(f"Vrijeme / status: {snapshot.get('timestamp')} | {snapshot.get('message')}")
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = self.after(1000, self._tick_clock)

    def _refresh_snapshot(self):
        self._replace_text(self.snapshot_text, format_terminal_settings_snapshot(get_terminal_settings_snapshot()))

    def _replace_text(self, widget, value: str):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def _edit_name(self):
        value = ask_touch_text(self, title="Naziv terminala", initial=self.name_var.get(), secret=False)
        if value is not None:
            self.name_var.set(value)

    def _edit_location(self):
        value = ask_touch_text(self, title="Lokacija terminala", initial=self.location_var.get(), secret=False)
        if value is not None:
            self.location_var.set(value)

    def _adjust_idle(self, delta: int):
        self.idle_seconds_var.set(max(15, min(900, int(self.idle_seconds_var.get()) + int(delta))))

    def _adjust_brightness(self, delta: int):
        self.brightness_var.set(max(30, min(100, int(self.brightness_var.get()) + int(delta))))

    def _save_identity(self):
        result = save_terminal_identity(name=self.name_var.get(), location=self.location_var.get())
        if self.manager and hasattr(self.manager, "refresh_runtime_settings"):
            self.manager.refresh_runtime_settings()
        self.status_var.set(result.get("message", "Postavke sačuvane."))
        self._refresh_snapshot()

    def _save_idle_timeout(self):
        result = save_idle_timeout_ms(int(self.idle_seconds_var.get()) * 1000)
        if self.manager and hasattr(self.manager, "refresh_runtime_settings"):
            self.manager.refresh_runtime_settings()
        self.idle_seconds_var.set(int(result.get("idle_timeout_ms", get_idle_timeout_ms()) / 1000))
        self.status_var.set(result.get("message", "Idle timeout sačuvan."))
        self._refresh_snapshot()

    def _apply_display(self):
        result = apply_display_settings(brightness_percent=int(self.brightness_var.get()), screensaver_enabled=bool(self.screensaver_var.get()))
        self.brightness_var.set(int(result.get("brightness_percent", self.brightness_var.get())))
        self.status_var.set(result.get("message", "Display postavke obrađene."))
        self._refresh_snapshot()

    def _open_network(self):
        if self.manager:
            self.manager.state["network_return_screen"] = screen_ids.SETTINGS
            self.manager.show_frame(screen_ids.NETWORK)

    def _open_recovery(self):
        if self.manager:
            self.manager.state["recovery_return_screen"] = screen_ids.SETTINGS
            self.manager.show_frame(screen_ids.RECOVERY)

    def _go_back(self):
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self.manager:
            self.manager.show_frame(screen_ids.ADMIN)
