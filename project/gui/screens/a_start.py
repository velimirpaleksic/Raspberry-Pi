# gui/screens/a_start.py
import tkinter as tk

from project.gui import screen_ids
from project.services.admin_service import get_setup_checklist
from project.gui.ui_components import apply_status_badge, polish_descendant_buttons
from project.utils.logging_utils import log_error


class StartScreen(tk.Frame):
    def __init__(self, parent, manager=None):
        try:
            super().__init__(parent, bg="black")
            self.manager = manager

            container = tk.Frame(self, bg="black")
            container.pack(fill="both", expand=True)

            top_bar = tk.Frame(container, bg="black")
            top_bar.pack(fill="x", padx=24, pady=24)

            tk.Button(
                top_bar,
                text="ADMIN",
                font=("Arial", 16, "bold"),
                fg="white",
                bg="#222222",
                activebackground="#444444",
                activeforeground="white",
                bd=0,
                highlightthickness=0,
                relief="flat",
                padx=18,
                pady=10,
                command=self.goto_admin,
            ).pack(side="right")

            tk.Button(
                top_bar,
                text="SETUP",
                font=("Arial", 16, "bold"),
                fg="white",
                bg="#333333",
                activebackground="#555555",
                activeforeground="white",
                bd=0,
                highlightthickness=0,
                relief="flat",
                padx=18,
                pady=10,
                command=self.goto_setup,
            ).pack(side="right", padx=(0, 10))

            tk.Button(
                top_bar,
                text="SPREMNOST",
                font=("Arial", 16, "bold"),
                fg="white",
                bg="#2a3f2b",
                activebackground="#406642",
                activeforeground="white",
                bd=0,
                highlightthickness=0,
                relief="flat",
                padx=18,
                pady=10,
                command=self.goto_readiness,
            ).pack(side="right", padx=(0, 10))

            center = tk.Frame(container, bg="black")
            center.pack(fill="both", expand=True)

            btn = tk.Button(
                center,
                text="ЗАПОЧНИ",
                font=("Arial", 64, "bold"),
                fg="white",
                bg="black",
                activebackground="gray20",
                activeforeground="white",
                bd=0,
                highlightthickness=0,
                relief="flat",
                command=self.goto_tutorial,
            )
            btn.pack(expand=True, fill="both")

            self.setup_status_var = tk.StringVar(value="")
            self.setup_missing_var = tk.StringVar(value="")
            footer = tk.Frame(container, bg="#050505")
            footer.pack(fill="x", padx=24, pady=(0, 24))
            self.setup_badge = tk.Label(footer, font=("Arial", 13, "bold"))
            self.setup_badge.pack(anchor='w', pady=(10, 6))
            tk.Label(
                footer,
                textvariable=self.setup_status_var,
                font=("Arial", 15, "bold"),
                fg="#7CFF8F",
                bg="#050505",
                anchor="w",
                justify="left",
            ).pack(fill="x", pady=(0, 4))
            tk.Label(
                footer,
                textvariable=self.setup_missing_var,
                font=("Arial", 12),
                fg="#dddddd",
                bg="#050505",
                anchor="w",
                justify="left",
                wraplength=1500,
            ).pack(fill="x", pady=(0, 10))

            polish_descendant_buttons(self)
        except Exception as e:
            log_error(f"Failed to build 'StartScreen' UI elements: {e}")
            return

    def goto_tutorial(self):
        try:
            if self.manager:
                self.manager.clear_state()
                self.manager.show_frame(screen_ids.FORM)
        except Exception as e:
            log_error(f"Failed to initialize next screen: {e}")
            return

    def goto_setup(self):
        try:
            if self.manager:
                self.manager.clear_state()
                self.manager.show_frame(screen_ids.SETUP)
        except Exception as e:
            log_error(f"Failed to open setup screen: {e}")
            return

    def goto_readiness(self):
        try:
            if self.manager:
                self.manager.state["readiness_return_screen"] = screen_ids.START
                self.manager.show_frame(screen_ids.READINESS)
        except Exception as e:
            log_error(f"Failed to open readiness screen: {e}")
            return

    def goto_admin(self):
        try:
            if self.manager:
                self.manager.clear_state()
                self.manager.show_frame(screen_ids.ADMIN)
        except Exception as e:
            log_error(f"Failed to open admin screen: {e}")
            return


    def on_show(self):
        try:
            checklist = get_setup_checklist()
            apply_status_badge(self.setup_badge, 'OK' if checklist.get('score_percent', 0) >= 100 else ('WARN' if checklist.get('score_percent', 0) >= 70 else 'FAIL'), text=f"SETUP {checklist.get('score_percent', 0)}%")
            self.setup_status_var.set(f"{checklist.get('summary', 'Setup status nedostupan')} ")
            missing = checklist.get('missing') or []
            if missing:
                self.setup_missing_var.set("Nedostaje: " + ", ".join(missing))
            else:
                self.setup_missing_var.set("Sve ključne setup stavke su zatvorene.")
        except Exception as e:
            self.setup_status_var.set("Setup status nije dostupan.")
            self.setup_missing_var.set(str(e))
