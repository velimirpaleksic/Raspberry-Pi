# gui/screen_manager.py
import tkinter as tk
from project.utils.logging_utils import error_logging


class ScreenManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Window")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.bind("<Escape>", lambda e: self.destroy())

        try:
            w, h = self.winfo_screenwidth(), self.winfo_screenheight()
            self.geometry(f"{w}x{h}")
        except:
            self.geometry("1920x1080")

        self.frames = {}

    def add_frame(self, name, frame_class, **kwargs):
        frame = frame_class(self, **kwargs)
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.frames[name] = frame

    def show_frame(self, name):
        frame = self.frames.get(name)
        if frame:
            for f in self.frames.values():
                f.lower()
            frame.lift()
        else:
            error_logging(f"[SM] Frame '{name}' does not exist.")