# gui/screens/a_start.py
import tkinter as tk

from project.utils.logging_utils import error_logging


class StartScreen(tk.Frame):
    def __init__(self, parent, manager=None):
        try:
            super().__init__(parent, bg="black")
            self.manager = manager

            # Full-screen big button, borderless and centered
            btn = tk.Button(
                self,
                text="ЗАПОЧНИ",
                font=("Arial", 64, "bold"),
                fg="white",
                bg="black",
                activebackground="gray20",
                activeforeground="white",
                bd=0,                  # remove border
                highlightthickness=0,  # remove focus highlight
                relief="flat",         # flat style
                command=self.goto_tutorial
            )
            btn.pack(expand=True, fill="both")

        except Exception as e:
            error_logging(f"Failed to build 'StartScreen' UI elements: {e}")
            return

    def goto_tutorial(self):
        try:
            if self.manager:
                # MARK
                #self.manager.show_frame("TutorialScreen")
                self.manager.show_frame("FormScreen")
        
        except Exception as e:
            error_logging(f"Failed to initialize 'TutorialScreen': {e}")
            return