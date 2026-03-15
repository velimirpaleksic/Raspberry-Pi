from __future__ import annotations

import threading
import tkinter as tk

from project.gui import screen_ids
from project.services.health_service import run_startup_checks
from project.services.settings_service import is_setup_completed
from project.gui.ui_components import apply_status_badge, polish_descendant_buttons


class HealthScreen(tk.Frame):
    def __init__(self, parent, manager=None):
        super().__init__(parent, bg="#101010")
        self.manager = manager
        self._worker_started = False
        self._after_id = None

        tk.Label(self, text="Provjera sistema", font=("Arial", 30, "bold"), fg="white", bg="#101010").pack(pady=(40, 10))
        self.summary_var = tk.StringVar(value="Pokretanje provjera…")
        self.health_badge = tk.Label(self, font=("Arial", 14, "bold"))
        self.health_badge.pack(pady=(0, 8))
        tk.Label(self, textvariable=self.summary_var, font=("Arial", 16), fg="#dddddd", bg="#101010").pack(pady=(0, 14))

        self.text = tk.Text(self, height=18, font=("Courier New", 13), bg="#1b1b1b", fg="#f2f2f2", wrap="word")
        self.text.pack(fill="both", expand=True, padx=28, pady=(0, 18))
        self.text.config(state="disabled")

        self.actions = tk.Frame(self, bg="#101010")
        self.actions.pack(pady=(0, 24))
        self.retry_btn = tk.Button(self.actions, text="Ponovi provjeru", font=("Arial", 14, "bold"), padx=16, pady=8, command=self.on_show)
        self.continue_btn = tk.Button(self.actions, text="Nastavi", font=("Arial", 14, "bold"), padx=16, pady=8, command=self._go_start)
        self.admin_btn = tk.Button(self.actions, text="Admin", font=("Arial", 14, "bold"), padx=16, pady=8, command=self._go_admin)
        self.recovery_btn = tk.Button(self.actions, text="Recovery pomoć", font=("Arial", 14, "bold"), padx=16, pady=8, command=self._go_recovery)
        self.readiness_btn = tk.Button(self.actions, text="Spremnost", font=("Arial", 14, "bold"), padx=16, pady=8, command=self._go_readiness)
        polish_descendant_buttons(self)

    def on_show(self):
        self._worker_started = False
        self._set_text("Provjere u toku…")
        self.summary_var.set("Pokretanje provjera…")
        self._hide_buttons()
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self.after(100, self._start_checks)

    def _start_checks(self):
        if self._worker_started:
            return
        self._worker_started = True
        threading.Thread(target=self._run_checks, daemon=True).start()

    def _run_checks(self):
        result = run_startup_checks(notify_on_failure=True)
        self.after(0, lambda: self._render_result(result))

    def _render_result(self, result: dict):
        lines = []
        for row in result.get("checks", []):
            icon = "OK " if row.get("ok") else "ERR"
            lines.append(f"[{icon}] {row.get('name')}: {row.get('message')}")
        self._set_text("\n".join(lines) or "Nema rezultata provjere.")
        self.summary_var.set(result.get("summary", "Provjera završena."))

        apply_status_badge(self.health_badge, 'OK' if result.get('ok') else 'FAIL', text=('SYSTEM OK' if result.get('ok') else 'SYSTEM PROBLEM'))

        if result.get("ok"):
            self._after_id = self.after(1400, self._go_start)
        else:
            self._show_buttons()

    def _set_text(self, value: str):
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", value)
        self.text.config(state="disabled")

    def _hide_buttons(self):
        self.retry_btn.pack_forget()
        self.continue_btn.pack_forget()
        self.admin_btn.pack_forget()
        self.recovery_btn.pack_forget()
        self.readiness_btn.pack_forget()

    def _show_buttons(self):
        self.retry_btn.pack(side="left", padx=10)
        self.continue_btn.pack(side="left", padx=10)
        self.admin_btn.pack(side="left", padx=10)
        self.recovery_btn.pack(side="left", padx=10)
        self.readiness_btn.pack(side="left", padx=10)

    def _go_start(self):
        if self.manager:
            target = screen_ids.START if is_setup_completed() else screen_ids.SETUP
            self.manager.show_frame(target)

    def _go_admin(self):
        if self.manager:
            self.manager.show_frame(screen_ids.ADMIN)


    def _go_recovery(self):
        if self.manager:
            self.manager.state["recovery_return_screen"] = screen_ids.HEALTH
            self.manager.show_frame(screen_ids.RECOVERY)


    def _go_readiness(self):
        if self.manager:
            self.manager.state["readiness_return_screen"] = screen_ids.HEALTH
            self.manager.show_frame(screen_ids.READINESS)
