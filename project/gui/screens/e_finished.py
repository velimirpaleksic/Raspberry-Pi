# gui/screens/e_finished.py
import tkinter as tk


class FinishedPrintingScreen(tk.Frame):
    def __init__(self, parent, manager=None):
        super().__init__(parent)
        self.manager = manager

        tk.Label(self, text="Принтање успјешно!", font=("Arial", 24), fg="green").pack(pady=50)
        tk.Label(self, text="Отиђите у уред секретара по потврду и печат.", font=("Arial", 16)).pack(pady=10)

        # Countdown label
        self.countdown_label = tk.Label(self, text="", font=("Arial", 16)).pack(pady=20)

    def start(self):
        """Call this when the frame is shown."""
        self.countdown(5)

    def countdown(self, remaining):
        if remaining >= 0:
            self.countdown_label.config(text=f"Враћање на почетну страну за {remaining}...")
            remaining -= 1
            self.after(1000, self.countdown, remaining)
        else:
            if self.manager:
                self.manager.show_frame("BlackScreen")