import tkinter as tk

from project.gui import screen_ids
from project.gui.ui_components import TouchButton
from project.utils.logging_utils import log_error


class StartScreen(tk.Frame):
    def __init__(self, parent, manager=None):
        try:
            super().__init__(parent, bg="#000000")
            self.manager = manager

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
                text="Напомена: Терминал ради у периоду од 08:00 до 15:00,\nу радно вријеме секретаријата.",
                font=("Arial", 24, "bold"),
                fg="#f2f2f2",
                bg="#000000",
                justify="center",
                cursor="none",
            )
            disclaimer.pack()
            disclaimer.bind("<ButtonPress-1>", self._start_from_anywhere, add=True)
        except Exception as e:
            log_error(f"Failed to build 'StartScreen' UI elements: {e}")

    def _start_from_anywhere(self, event=None):
        self.goto_form()
        return "break"

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
