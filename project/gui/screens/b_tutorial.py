# gui/screens/b_tutorial.py
import tkinter as tk
from tkinter import ttk

from project.gui import screen_ids


class TutorialScreen(tk.Frame):
    def __init__(self, parent, manager):
        super().__init__(parent)
        self.manager = manager

        tk.Label(self, text="Туторијал.").pack(pady=5)

        ttk.Button(self, text="Next", command=lambda: manager.show_frame(screen_ids.FORM)).pack(pady=20)