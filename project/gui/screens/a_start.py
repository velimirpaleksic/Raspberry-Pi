import tkinter as tk

from project.gui import screen_ids
from project.gui.ui_components import TouchButton
from project.utils.logging_utils import log_error


class StartScreen(tk.Frame):
    def __init__(self, parent, manager=None):
        try:
            super().__init__(parent, bg="#000000")
            self.manager = manager

            container = tk.Frame(self, bg="#000000")
            container.pack(expand=True, fill="both")

            start_btn = TouchButton(
                container,
                text="ЗАПОЧНИ",
                font=("Arial", 72, "bold"),
                fg="white",
                bg="#000000",
                activebackground="#111111",
                activeforeground="white",
                padx=90,
                pady=34,
                command=self.goto_form,
            )
            start_btn.pack(expand=True)
        except Exception as e:
            log_error(f"Failed to build 'StartScreen' UI elements: {e}")

    def on_show(self):
        if self.manager:
            self.manager.set_idle_suspended(True)

    def goto_form(self):
        try:
            if self.manager:
                self.manager.clear_state()
                self.manager.show_frame(screen_ids.FORM)
        except Exception as e:
            log_error(f"Failed to initialize form screen: {e}")
