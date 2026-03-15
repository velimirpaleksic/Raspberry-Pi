from __future__ import annotations

import tkinter as tk

from project.gui import screen_ids
from project.services.readiness_service import build_readiness_snapshot, format_readiness_snapshot
from project.gui.ui_components import apply_status_badge, polish_descendant_buttons


class ReadinessScreen(tk.Frame):
    def __init__(self, parent, manager=None):
        super().__init__(parent, bg="#101010")
        self.manager = manager
        self.status_var = tk.StringVar(value="")
        self.summary_var = tk.StringVar(value="")
        self._build_ui()

    def _build_ui(self):
        header = tk.Frame(self, bg="#101010")
        header.pack(fill="x", padx=24, pady=(18, 8))
        tk.Label(header, text="PRODUCTION READINESS", font=("Arial", 28, "bold"), fg="white", bg="#101010").pack(side="left")
        tk.Button(header, text="Nazad", command=self._go_back, font=("Arial", 14, "bold"), padx=16, pady=8).pack(side="right")
        self.state_badge = tk.Label(self, font=("Arial", 15, "bold"))
        self.state_badge.pack(anchor="w", padx=24, pady=(0, 6))
        tk.Label(self, textvariable=self.status_var, font=("Arial", 18, "bold"), fg="#7CFF8F", bg="#101010").pack(anchor="w", padx=24)
        tk.Label(self, textvariable=self.summary_var, font=("Arial", 13, "bold"), fg="#dddddd", bg="#101010", justify="left", wraplength=1550).pack(anchor="w", padx=24, pady=(6, 10))

        actions = tk.Frame(self, bg="#101010")
        actions.pack(fill="x", padx=24, pady=(0, 10))
        tk.Button(actions, text="Osvježi", command=self._refresh, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left")
        tk.Button(actions, text="Setup wizard", command=self._open_setup, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=8)
        tk.Button(actions, text="Opšte postavke", command=self._open_settings, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=8)
        tk.Button(actions, text="Mreža / Wi‑Fi", command=self._open_network, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=8)
        tk.Button(actions, text="Recovery pomoć", command=self._open_recovery, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=8)
        tk.Button(actions, text="Admin", command=self._open_admin, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="right")

        content = tk.Frame(self, bg="#101010")
        content.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        for c in range(2):
            content.columnconfigure(c, weight=1)
        for r in range(2):
            content.rowconfigure(r, weight=1)

        self.summary_text = self._card_text(content, "Sažetak", row=0, column=0)
        self.blockers_text = self._card_text(content, "Blockers", row=0, column=1)
        self.warnings_text = self._card_text(content, "Warnings / preporuke", row=1, column=0)
        self.acceptance_text = self._card_text(content, "Acceptance / teren check", row=1, column=1)
        polish_descendant_buttons(self)

    def _card_text(self, parent, title: str, *, row: int, column: int):
        card = tk.Frame(parent, bg="#1c1c1c", bd=1, relief="solid")
        card.grid(row=row, column=column, sticky="nsew", padx=10, pady=10)
        tk.Label(card, text=title, font=("Arial", 16, "bold"), fg="white", bg="#1c1c1c").pack(anchor="w", padx=12, pady=(10, 6))
        text = tk.Text(card, font=("Courier New", 11), bg="#101010", fg="#f2f2f2", wrap="word")
        text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        text.config(state="disabled")
        return text

    def _set_text(self, widget: tk.Text, value: str):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.config(state="disabled")

    def on_show(self):
        self._refresh()

    def _refresh(self):
        snapshot = build_readiness_snapshot()
        state = snapshot.get("state", "UNKNOWN")
        score = snapshot.get("readiness_score", 0)
        apply_status_badge(self.state_badge, state, text=state.replace('_', ' '))
        self.status_var.set(f"{state} • {score}%")
        # label color may be configured each refresh
        # rely on widget lookup via variable label not trivial, so keep summary in text too
        self.summary_var.set(
            "Terminal readiness je zbir startup health provjera i setup checkliste. "
            "Ako postoje BLOCKER stavke, uređaj još nije spreman za produkcijski rad bez nadzora."
        )
        self._set_text(self.summary_text, format_readiness_snapshot(snapshot))
        blockers = snapshot.get("blockers") or []
        self._set_text(self.blockers_text, "\n".join(f"- {row}" for row in blockers) or "Nema kritičnih blokada.")
        warnings = list(snapshot.get("warnings") or []) + [""] + [f"PREPORUKA: {r}" for r in (snapshot.get("recommendations") or [])]
        self._set_text(self.warnings_text, "\n".join(row for row in warnings if row) or "Nema dodatnih upozorenja.")
        acceptance = snapshot.get("acceptance_steps") or []
        self._set_text(self.acceptance_text, "\n".join(f"{idx}. {step}" for idx, step in enumerate(acceptance, 1)))

    def _go_back(self):
        if not self.manager:
            return
        target = self.manager.state.get("readiness_return_screen") or screen_ids.START
        self.manager.show_frame(target)

    def _open_setup(self):
        if self.manager:
            self.manager.show_frame(screen_ids.SETUP)

    def _open_admin(self):
        if self.manager:
            self.manager.show_frame(screen_ids.ADMIN)

    def _open_settings(self):
        if self.manager:
            self.manager.show_frame(screen_ids.SETTINGS)

    def _open_network(self):
        if self.manager:
            self.manager.state["network_return_screen"] = screen_ids.READINESS
            self.manager.show_frame(screen_ids.NETWORK)

    def _open_recovery(self):
        if self.manager:
            self.manager.state["recovery_return_screen"] = screen_ids.READINESS
            self.manager.show_frame(screen_ids.RECOVERY)
