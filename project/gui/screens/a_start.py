import tkinter as tk

from project.core import config
from project.gui import screen_ids
from project.gui.ui_components import TouchButton
from project.utils.logging_utils import log_error


class StartScreen(tk.Frame):
    def __init__(self, parent, manager=None):
        try:
            super().__init__(parent, bg="#000000")
            self.manager = manager
            self.message_var = tk.StringVar(value="")

            container = tk.Frame(self, bg="#000000", cursor="none")
            container.pack(expand=True, fill="both")
            container.bind("<ButtonPress-1>", self._start_from_anywhere, add=True)

            content = tk.Frame(container, bg="#000000", cursor="none")
            content.place(relx=0.5, rely=0.5, anchor="center")
            content.bind("<ButtonPress-1>", self._start_from_anywhere, add=True)

            start_btn = TouchButton(
                content,
                text="ЗАПОЧНИ",
                font=("Arial", 72, "bold"),
                fg="white",
                bg="#000000",
                activebackground="#111111",
                activeforeground="white",
                padx=90,
                pady=28,
                command=self.goto_form,
            )
            start_btn.pack(pady=(0, 24))

            disclaimer = tk.Label(
                content,
                text=f"Напомена: Терминал ради у периоду од {config.working_hours_window_text()},\nу радно вријеме секретаријата.",
                font=("Arial", 24, "bold"),
                fg="#f2f2f2",
                bg="#000000",
                justify="center",
                cursor="none",
            )
            disclaimer.pack()
            disclaimer.bind("<ButtonPress-1>", self._start_from_anywhere, add=True)

            self.closed_label = tk.Label(
                content,
                textvariable=self.message_var,
                font=("Arial", 22, "bold"),
                fg="#ffdddd",
                bg="#000000",
                justify="center",
                wraplength=900,
                cursor="none",
            )
            self.closed_label.pack(pady=(20, 0))
            self.closed_label.bind("<ButtonPress-1>", self._start_from_anywhere, add=True)
        except Exception as e:
            log_error(f"Failed to build 'StartScreen' UI elements: {e}")

    def _start_from_anywhere(self, event=None):
        self.goto_form()
        return "break"

    def on_show(self):
        if self.manager:
            self.manager.set_idle_suspended(True)
        self._refresh_working_hours_message()

    def _refresh_working_hours_message(self) -> None:
        try:
            if config.is_within_working_hours():
                self.message_var.set("")
            else:
                self.message_var.set(config.working_hours_unavailable_message())
        except Exception as e:
            log_error(f"Failed to refresh working-hours message: {e}")

    def goto_form(self):
        try:
            if not config.is_within_working_hours():
                self.message_var.set(config.working_hours_unavailable_message())
                return
            if self.manager:
                self.manager.clear_state()
                self.manager.show_frame(screen_ids.FORM)
        except Exception as e:
            log_error(f"Failed to initialize form screen: {e}")
