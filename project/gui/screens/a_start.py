import tkinter as tk

from project.core import config
from project.gui import screen_ids
from project.gui.ui_components import TouchButton
from project.utils.logging_utils import log_error


def start_availability_state() -> tuple[bool, str, str]:
    window = config.working_hours_window_text()
    restriction_enabled = config.working_hours_enabled()
    blocked = restriction_enabled and not config.is_within_working_hours()
    disclaimer = f"Радно вријеме терминала: {window}."
    if not restriction_enabled:
        disclaimer += "\nАдминистратор је привремено омогућио рад ван тог периода."
    message = (
        f"ТЕРМИНАЛ ТРЕНУТНО НЕ РАДИ\nДоступан је од {window}, у радно вријеме секретаријата."
        if blocked
        else ""
    )
    return blocked, disclaimer, message


class StartScreen(tk.Frame):
    def __init__(self, parent, manager=None):
        try:
            super().__init__(parent, bg="#000000")
            self.manager = manager
            self.message_var = tk.StringVar(value="")
            self.disclaimer_var = tk.StringVar(value="")
            self._refresh_after_id = None

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
                textvariable=self.disclaimer_var,
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

            admin_btn = TouchButton(
                container,
                text="ADMIN",
                command=self.goto_admin,
                font=("Arial", 16, "bold"),
                fg="white",
                bg="#183b5b",
                activebackground="#24577f",
                activeforeground="white",
                padx=22,
                pady=12,
            )
            admin_btn.place(relx=0.97, rely=0.95, anchor="se")
        except Exception as e:
            log_error(f"Failed to build 'StartScreen' UI elements: {e}")

    def _start_from_anywhere(self, event=None):
        self.goto_form()
        return "break"

    def on_show(self):
        if self.manager:
            self.manager.set_idle_suspended(True)
        self._refresh_working_hours_message()

    def on_hide(self):
        if self._refresh_after_id is not None:
            try:
                self.after_cancel(self._refresh_after_id)
            except Exception:
                pass
            self._refresh_after_id = None

    def _refresh_working_hours_message(self) -> None:
        try:
            blocked, disclaimer, message = start_availability_state()
            self.disclaimer_var.set(disclaimer)
            self.message_var.set(message)
            self.config(highlightthickness=10 if blocked else 0, highlightbackground="#d71920")
            if self._refresh_after_id is not None:
                try:
                    self.after_cancel(self._refresh_after_id)
                except Exception:
                    pass
            self._refresh_after_id = self.after(30_000, self._refresh_working_hours_message)
        except Exception as e:
            log_error(f"Failed to refresh working-hours message: {e}")

    def goto_form(self):
        try:
            if not config.is_within_working_hours():
                self._refresh_working_hours_message()
                return
            if self.manager:
                self.manager.clear_state()
                self.manager.show_frame(screen_ids.FORM)
        except Exception as e:
            log_error(f"Failed to initialize form screen: {e}")

    def goto_admin(self):
        if self.manager:
            self.manager.state["admin_return_screen"] = screen_ids.START
            self.manager.show_frame(screen_ids.ADMIN)
