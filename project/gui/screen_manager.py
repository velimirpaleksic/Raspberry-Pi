import tkinter as tk

from project.core import config
from project.gui import screen_ids
from project.utils.logging_utils import log_error


class ScreenManager(tk.Tk):
    """Full-screen screen router with shared state.

    Features:
      - Deterministic screen IDs (via project.gui.screen_ids)
      - Shared state dict for passing data between screens
      - on_show() hook called when a frame becomes active
      - Inactivity auto-reset to Start screen
    """

    def __init__(self):
        super().__init__()
        self.title(config.APP_TITLE)

        # Appliance-style UI
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        # Escape = emergency exit (disable later if you want)
        self.bind("<Escape>", lambda e: self.destroy())

        try:
            w, h = self.winfo_screenwidth(), self.winfo_screenheight()
            self.geometry(f"{w}x{h}")
        except Exception:
            self.geometry("1920x1080")

        self.frames = {}
        self.state = {}

        # Inactivity timer
        self._idle_after_id = None
        self._idle_suspended = False
        self._idle_timeout_ms = config.IDLE_TIMEOUT_MS

        # Reset idle on any user activity
        self.bind_all("<Any-KeyPress>", self._on_activity, add=True)
        self.bind_all("<Button>", self._on_activity, add=True)
        self.bind_all("<Motion>", self._on_activity, add=True)
        self._reset_idle_timer()

    def add_frame(self, name: str, frame_class, **kwargs):
        frame = frame_class(self, **kwargs)
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.frames[name] = frame

    def show_frame(self, name: str):
        frame = self.frames.get(name)
        if not frame:
            log_error(f"[SM] Frame '{name}' does not exist.")
            return

        for f in self.frames.values():
            f.lower()
        frame.lift()

        # Hook
        if hasattr(frame, "on_show"):
            try:
                frame.on_show()  # type: ignore[attr-defined]
            except Exception as e:
                log_error(f"[SM] on_show failed for {name}: {e}")

        self._reset_idle_timer()

    def set_idle_suspended(self, suspended: bool) -> None:
        self._idle_suspended = suspended
        self._reset_idle_timer()

    def clear_state(self) -> None:
        self.state.clear()

    # -----------------
    # Idle handling
    # -----------------
    def _on_activity(self, event=None):
        self._reset_idle_timer()

    def _reset_idle_timer(self):
        if self._idle_after_id is not None:
            try:
                self.after_cancel(self._idle_after_id)
            except Exception:
                pass
            self._idle_after_id = None

        if self._idle_suspended:
            return

        self._idle_after_id = self.after(self._idle_timeout_ms, self._idle_timeout)

    def _idle_timeout(self):
        # Reset to Start screen and clear transient state
        try:
            self.clear_state()
            self.show_frame(screen_ids.START)
        finally:
            self._reset_idle_timer()
