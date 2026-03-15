from __future__ import annotations

import tkinter as tk

from project.gui import screen_ids
from project.services.maintenance_service import run_test_printer
from project.services.recovery_service import build_recovery_snapshot
from project.gui.ui_components import polish_descendant_buttons


class RecoveryScreen(tk.Frame):
    def __init__(self, parent, manager=None):
        super().__init__(parent, bg="#101010")
        self.manager = manager
        self.status_var = tk.StringVar(value="")
        self.startup_var = tk.StringVar(value="")
        self.printer_var = tk.StringVar(value="")
        self.network_var = tk.StringVar(value="")
        self._build_ui()
        polish_descendant_buttons(self)

    def _build_ui(self):
        header = tk.Frame(self, bg="#101010")
        header.pack(fill="x", padx=24, pady=(18, 8))
        tk.Label(header, text="GUIDED RECOVERY", font=("Arial", 28, "bold"), fg="white", bg="#101010").pack(side="left")
        tk.Button(header, text="Nazad", command=self._go_back, font=("Arial", 14, "bold"), padx=16, pady=8).pack(side="right")
        tk.Label(self, textvariable=self.status_var, font=("Arial", 13, "bold"), fg="#ffcc66", bg="#101010").pack(anchor="w", padx=24, pady=(0, 8))

        actions = tk.Frame(self, bg="#101010")
        actions.pack(fill="x", padx=24, pady=(0, 10))
        tk.Button(actions, text="Osvježi recovery", command=self._refresh, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left")
        tk.Button(actions, text="Test printera", command=self._test_printer, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=8)
        tk.Button(actions, text="Setup printera", command=self._open_printer_setup, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=8)
        tk.Button(actions, text="Mreža / Wi‑Fi", command=self._open_network, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=8)
        tk.Button(actions, text="Admin", command=lambda: self.manager.show_frame(screen_ids.ADMIN), font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="right")

        content = tk.Frame(self, bg="#101010")
        content.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)

        startup = self._card(content, "Šta prvo provjeriti")
        startup.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
        tk.Label(startup, textvariable=self.startup_var, font=("Arial", 13), fg="#f2f2f2", bg="#111111", justify="left", wraplength=760).pack(fill="both", expand=True, padx=14, pady=(0, 14))

        printer = self._card(content, "Printer recovery")
        printer.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=(0, 10))
        tk.Label(printer, textvariable=self.printer_var, font=("Arial", 13), fg="#f2f2f2", bg="#111111", justify="left", wraplength=760).pack(fill="both", expand=True, padx=14, pady=(0, 14))

        network = self._card(content, "Network recovery")
        network.grid(row=1, column=0, columnspan=2, sticky="nsew")
        tk.Label(network, textvariable=self.network_var, font=("Arial", 13), fg="#f2f2f2", bg="#111111", justify="left", wraplength=1540).pack(fill="both", expand=True, padx=14, pady=(0, 14))

    def _card(self, parent, title: str):
        box = tk.Frame(parent, bg="#111111", bd=1, relief="solid")
        tk.Label(box, text=title, font=("Arial", 17, "bold"), fg="white", bg="#111111").pack(anchor="w", padx=14, pady=(12, 8))
        return box

    def on_show(self):
        self._refresh()

    def _format_plan(self, plan: dict) -> str:
        lines = [f"Sažetak: {plan.get('summary', '-')}", ""]
        steps = plan.get("steps") or []
        if not steps:
            lines.append("Nema predloženih koraka.")
        else:
            for idx, step in enumerate(steps, 1):
                lines.append(f"{idx}. {step}")
        return "\n".join(lines)

    def _refresh(self):
        snapshot = build_recovery_snapshot()
        self.startup_var.set(self._format_plan(snapshot.get("startup_plan", {})))
        self.printer_var.set(self._format_plan(snapshot.get("printer_plan", {})))
        self.network_var.set(self._format_plan(snapshot.get("network_plan", {})))
        self.status_var.set(
            f"Startup: {snapshot.get('health', {}).get('summary', '-')} | "
            f"Printer: {snapshot.get('printer', {}).get('message', '-')} | "
            f"Mreža: {snapshot.get('network', {}).get('message', '-') }"
        )

    def _test_printer(self):
        result = run_test_printer()
        self.status_var.set(result.get("message", "Test printera završen."))
        self._refresh()

    def _open_printer_setup(self):
        if self.manager:
            self.manager.state["setup_start_step"] = 2
            self.manager.show_frame(screen_ids.SETUP)

    def _open_network(self):
        if self.manager:
            self.manager.state["network_return_screen"] = screen_ids.RECOVERY
            self.manager.show_frame(screen_ids.NETWORK)

    def _go_back(self):
        if not self.manager:
            return
        target = self.manager.state.get("recovery_return_screen") or screen_ids.ADMIN
        self.manager.show_frame(target)
