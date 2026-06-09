import tkinter as tk

from project.gui import screen_ids
from project.gui.ui_components import TouchButton


class DoneScreen(tk.Frame):
    def __init__(self, parent, manager=None):
        super().__init__(parent, bg="#f5f5f5")
        self.manager = manager
        self._countdown_after_id = None
        self._seconds_left = 10

        container = tk.Frame(self, bg="#f5f5f5")
        container.pack(expand=True)

        tk.Label(container, text="ГОТОВО", font=("Arial", 34, "bold"), fg="#1b7d38", bg="#f5f5f5").pack(pady=(0, 10))
        tk.Label(container, text="Документ је послат на штампу.", font=("Arial", 20), bg="#f5f5f5", fg="#111111").pack()

        self.count_label = tk.Label(container, text="", font=("Arial", 18), bg="#f5f5f5", fg="#444444")
        self.count_label.pack(pady=(14, 4))

        TouchButton(
            container,
            text="КРЕНИ ИСПОЧЕТКА",
            font=("Arial", 18, "bold"),
            padx=28,
            pady=14,
            command=self._go_home,
            bg="#111111",
            fg="white",
            activebackground="#202020",
            activeforeground="white",
        ).pack(pady=20)

    def on_show(self):
        if self.manager:
            self.manager.set_idle_suspended(False)
        self._seconds_left = 10
        self._update_countdown()

    def on_idle_timeout(self):
        self._go_home()

    def _update_countdown(self):
        if self._countdown_after_id is not None:
            try:
                self.after_cancel(self._countdown_after_id)
            except Exception:
                pass
            self._countdown_after_id = None

        if not self.winfo_exists():
            return

        self.count_label.config(text=f"Повратак на почетак за {self._seconds_left} с")
        if self._seconds_left <= 0:
            self._go_home()
            return

        self._seconds_left -= 1
        self._countdown_after_id = self.after(1000, self._update_countdown)

    def _go_home(self):
        if self._countdown_after_id is not None:
            try:
                self.after_cancel(self._countdown_after_id)
            except Exception:
                pass
            self._countdown_after_id = None
        if self.manager:
            self.manager.clear_state()
            self.manager.set_idle_suspended(True)
            self.manager.show_frame(screen_ids.START)
