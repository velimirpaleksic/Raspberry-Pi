import queue
import threading
import tkinter as tk

from project.core import config
from project.gui import screen_ids
from project.utils.logging_utils import log_error


class ScreenManager(tk.Tk):
    """Full-screen screen router with shared state."""

    def __init__(self):
        super().__init__()
        self.title("")
        try:
            self.wm_title("")
            self.iconname("")
        except Exception:
            pass
        # Match the dominant frame background to avoid visible flash during screen changes.
        self.configure(bg="#f5f5f5")

        self.screen_width = self.winfo_screenwidth()
        self.screen_height = self.winfo_screenheight()
        self.ui_scale = self._compute_ui_scale(self.screen_width, self.screen_height)

        # Hide the mouse cursor for touchscreen kiosk usage.
        try:
            self.option_add("*Cursor", "none")
            self.configure(cursor="none")
        except Exception:
            pass

        # Slight global Tk scaling so fonts and ttk controls become easier to tap.
        try:
            self.tk.call("tk", "scaling", max(1.15, min(1.6, self.ui_scale * 1.15)))
        except Exception:
            pass

        # Stable fullscreen setup for manual desktop launch.
        try:
            self.geometry(f"{self.screen_width}x{self.screen_height}+0+0")
        except Exception:
            pass

        try:
            self.attributes("-fullscreen", True)
        except Exception:
            try:
                w, h = self.winfo_screenwidth(), self.winfo_screenheight()
                self.geometry(f"{w}x{h}+0+0")
            except Exception:
                self.geometry("1280x720+0+0")

        try:
            self.attributes("-topmost", True)
        except Exception:
            pass

        # Remove the window-manager title bar on the touchscreen.
        # This prevents the visible "Uvjerenja Terminal" corner title if fullscreen is imperfect.
        try:
            self.overrideredirect(True)
        except Exception:
            pass

        self._is_closing = False
        self.bind("<Escape>", self._handle_escape, add=True)
        self.bind_all("<Escape>", self._handle_escape, add=True)
        self.bind_all("<KeyPress-Escape>", self._handle_escape, add=True)
        self.protocol("WM_DELETE_WINDOW", self.shutdown)

        self.frames = {}
        self.state = {}
        self.current_frame_name = None
        self.current_frame = None

        self._idle_after_id = None
        self._idle_suspended = False
        self._idle_timeout_ms = config.IDLE_TIMEOUT_MS
        self._ui_actions: queue.Queue = queue.Queue()
        self._ui_actions_after_id = None
        self._input_locked = False
        self._input_lock_overlay = None
        self._input_lock_message_var = tk.StringVar(value="")
        self._input_lock_idle_was_suspended = False
        self._kiosk_hidden = False

        self.bind_all("<Any-KeyPress>", self._on_activity, add=True)
        self.bind_all("<Button>", self._on_activity, add=True)
        self.bind_all("<Motion>", self._on_activity, add=True)
        self._schedule_ui_action_pump()
        self._reset_idle_timer()


    def _handle_escape(self, event=None):
        """Exit immediately from a physical keyboard ESC press.

        Useful during development and service work on the kiosk, while normal
        touchscreen users still see no close button.
        """
        self.shutdown()
        return "break"

    def add_frame(self, name: str, frame_class, **kwargs):
        frame = frame_class(self, **kwargs)
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.frames[name] = frame

    def show_frame(self, name: str, *, force: bool = False):
        if self._is_closing:
            return

        frame = self.frames.get(name)
        if not frame:
            log_error(f"[SM] Frame '{name}' does not exist.")
            return

        # Avoid repainting the same frame again unless the caller explicitly forces a refresh.
        if not force and self.current_frame_name == name:
            self._reset_idle_timer()
            return

        previous_frame = self.current_frame
        previous_name = self.current_frame_name
        if previous_frame is not None and previous_frame is not frame and hasattr(previous_frame, "on_hide"):
            try:
                previous_frame.on_hide()  # type: ignore[attr-defined]
            except Exception as e:
                log_error(f"[SM] on_hide failed for {previous_name}: {e}")

        try:
            frame.lift()
        except Exception as e:
            log_error(f"[SM] lift failed for {name}: {e}")
            return

        self.current_frame_name = name
        self.current_frame = frame

        if hasattr(frame, "on_show"):
            try:
                frame.on_show()  # type: ignore[attr-defined]
            except Exception as e:
                log_error(f"[SM] on_show failed for {name}: {e}")

        if self._input_locked and self._input_lock_overlay is not None:
            try:
                self._input_lock_overlay.lift()
            except Exception as e:
                log_error(f"[SM] input lock lift failed: {e}")

        self._reset_idle_timer()

    def set_input_locked(self, locked: bool, message: str | None = None) -> None:
        """Block or unblock touch, mouse and keyboard input inside the kiosk window."""

        self._run_on_ui_thread(lambda: self._set_input_locked_on_ui(locked, message))

    def request_shutdown(self) -> None:
        """Allow worker threads to close the Tk app safely."""

        self._run_on_ui_thread(self.shutdown)

    def request_hide_kiosk(self) -> None:
        """Hide the kiosk window while keeping the process and Telegram bot alive."""

        self._run_on_ui_thread(self.hide_kiosk_window)

    def request_show_kiosk(self) -> None:
        """Show the kiosk window again after it was hidden remotely."""

        self._run_on_ui_thread(self.show_kiosk_window)

    def is_kiosk_hidden(self) -> bool:
        return bool(self._kiosk_hidden)

    def hide_kiosk_window(self) -> None:
        if self._is_closing:
            return
        try:
            self.withdraw()
            self._kiosk_hidden = True
        except Exception as e:
            log_error(f"[SM] hide kiosk failed: {e}")

    def show_kiosk_window(self) -> None:
        if self._is_closing:
            return
        try:
            self.deiconify()
            self.geometry(f"{self.screen_width}x{self.screen_height}+0+0")
            try:
                self.attributes("-fullscreen", True)
            except Exception:
                pass
            try:
                self.attributes("-topmost", True)
            except Exception:
                pass
            try:
                self.overrideredirect(True)
            except Exception:
                pass
            self.lift()
            self.focus_force()
            if self.current_frame is not None:
                try:
                    self.current_frame.lift()
                except Exception:
                    pass
            if self._input_locked and self._input_lock_overlay is not None:
                self._input_lock_overlay.lift()
            self._kiosk_hidden = False
            self._reset_idle_timer()
        except Exception as e:
            log_error(f"[SM] show kiosk failed: {e}")

    def set_idle_suspended(self, suspended: bool) -> None:
        self._idle_suspended = suspended
        self._reset_idle_timer()

    def clear_state(self) -> None:
        self.state.clear()

    def shutdown(self) -> None:
        if self._is_closing:
            return
        self._is_closing = True
        try:
            if self._idle_after_id is not None:
                try:
                    self.after_cancel(self._idle_after_id)
                except Exception:
                    pass
                self._idle_after_id = None
            if self._ui_actions_after_id is not None:
                try:
                    self.after_cancel(self._ui_actions_after_id)
                except Exception:
                    pass
                self._ui_actions_after_id = None
        finally:
            try:
                self.destroy()
            except Exception:
                pass

    def _run_on_ui_thread(self, callback) -> None:
        if self._is_closing:
            return
        if threading.current_thread() is threading.main_thread():
            try:
                callback()
            except Exception as e:
                log_error(f"[SM] UI callback failed: {e}")
            return
        self._ui_actions.put(callback)

    def _schedule_ui_action_pump(self) -> None:
        if self._is_closing:
            return
        self._ui_actions_after_id = self.after(100, self._drain_ui_actions)

    def _drain_ui_actions(self) -> None:
        self._ui_actions_after_id = None
        if self._is_closing:
            return

        while True:
            try:
                callback = self._ui_actions.get_nowait()
            except queue.Empty:
                break
            try:
                callback()
            except Exception as e:
                log_error(f"[SM] UI action failed: {e}")

        self._schedule_ui_action_pump()

    def _set_input_locked_on_ui(self, locked: bool, message: str | None = None) -> None:
        if self._is_closing:
            return

        if locked:
            if not self._input_locked:
                self._input_lock_idle_was_suspended = self._idle_suspended
                self._idle_suspended = True
            self._input_locked = True
            self._input_lock_message_var.set(
                message or "Ažuriranje je u toku. Molimo sačekajte dok se aplikacija ponovo otvori."
            )
            overlay = self._ensure_input_lock_overlay()
            overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            overlay.lift()
            overlay.focus_force()
            try:
                overlay.grab_set()
            except Exception as e:
                log_error(f"[SM] input grab failed: {e}")
            self._reset_idle_timer()
            return

        if self._input_lock_overlay is not None:
            try:
                self._input_lock_overlay.grab_release()
            except Exception:
                pass
            self._input_lock_overlay.place_forget()
        if self._input_locked:
            self._idle_suspended = self._input_lock_idle_was_suspended
        self._input_locked = False
        self._reset_idle_timer()

    def _ensure_input_lock_overlay(self):
        if self._input_lock_overlay is not None:
            return self._input_lock_overlay

        overlay = tk.Frame(self, bg="#101820", cursor="none", bd=0, highlightthickness=0)
        card = tk.Frame(overlay, bg="#f8faf7", padx=44, pady=36, bd=0, highlightthickness=0)
        card.place(relx=0.5, rely=0.5, anchor="center")

        title = tk.Label(
            card,
            text="Aplikacija se ažurira",
            bg="#f8faf7",
            fg="#101820",
            font=("DejaVu Sans", 28, "bold"),
        )
        title.pack(pady=(0, 12))

        message = tk.Label(
            card,
            textvariable=self._input_lock_message_var,
            bg="#f8faf7",
            fg="#344054",
            font=("DejaVu Sans", 16),
            justify="center",
            wraplength=720,
        )
        message.pack()

        footer = tk.Label(
            card,
            text="Ekran, tastatura i miš su privremeno zaključani.",
            bg="#f8faf7",
            fg="#667085",
            font=("DejaVu Sans", 13),
        )
        footer.pack(pady=(18, 0))

        self._bind_input_blockers(overlay)
        self._input_lock_overlay = overlay
        return overlay

    def _bind_input_blockers(self, widget) -> None:
        for sequence in (
            "<Button>",
            "<ButtonRelease>",
            "<B1-Motion>",
            "<Motion>",
            "<MouseWheel>",
            "<KeyPress>",
            "<KeyRelease>",
        ):
            widget.bind(sequence, self._consume_locked_input)
        for child in widget.winfo_children():
            self._bind_input_blockers(child)

    def _consume_locked_input(self, event=None):
        return "break"


    def _compute_ui_scale(self, width: int, height: int) -> float:
        """Return a conservative touch-friendly scale factor based on screen size."""

        base_width = 1280
        base_height = 720
        if width <= 0 or height <= 0:
            return 1.0

        width_scale = width / base_width
        height_scale = height / base_height
        scale = min(width_scale, height_scale)
        return max(1.0, min(1.6, scale))

    def fit_aspect_ratio(self, aspect_w: float, aspect_h: float, *, fill: float = 1.0) -> tuple[int, int]:
        """Fit a target aspect ratio inside the current screen bounds."""

        if aspect_w <= 0 or aspect_h <= 0:
            return self.screen_width, self.screen_height

        fill = max(0.1, min(1.0, float(fill)))
        max_w = int(self.screen_width * fill)
        max_h = int(self.screen_height * fill)
        target_ratio = aspect_w / aspect_h

        width = max_w
        height = int(round(width / target_ratio))

        if height > max_h:
            height = max_h
            width = int(round(height * target_ratio))

        return max(1, width), max(1, height)

    def _on_activity(self, event=None):
        self._reset_idle_timer()

    def _reset_idle_timer(self):
        if self._is_closing:
            return

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
        if self._is_closing:
            return

        try:
            frame = self.current_frame
            if frame and hasattr(frame, "on_idle_timeout"):
                try:
                    frame.on_idle_timeout()  # type: ignore[attr-defined]
                except Exception as e:
                    log_error(f"[SM] on_idle_timeout failed for {self.current_frame_name}: {e}")
        finally:
            self._reset_idle_timer()
