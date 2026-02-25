import tkinter as tk

from project.gui import screen_ids


class DoneScreen(tk.Frame):
    def __init__(self, parent, manager=None):
        super().__init__(parent)
        self.manager = manager

        tk.Label(self, text="Успјешно одштампано ✅", font=("Arial", 28, "bold"), fg="green").pack(pady=(60, 10))
        tk.Label(self, text="Узмите документ са printera.", font=("Arial", 18)).pack(pady=10)

        self.countdown_label = tk.Label(self, text="", font=("Arial", 16))
        self.countdown_label.pack(pady=30)

        tk.Button(self, text="ГОТОВО", padx=22, pady=10, command=self._go_home).pack(pady=10)

        self._after_id = None

    def on_show(self):
        self._start_countdown(10)

    def _start_countdown(self, seconds: int):
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

        self._tick(seconds)

    def _tick(self, remaining: int):
        if remaining >= 0:
            self.countdown_label.config(text=f"Враћање на почетну страну за {remaining}…")
            self._after_id = self.after(1000, lambda: self._tick(remaining - 1))
        else:
            self._go_home()

    def _go_home(self):
        if self.manager:
            self.manager.clear_state()
            self.manager.show_frame(screen_ids.START)
