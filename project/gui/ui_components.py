# gui/ui_components.py
import tkinter as tk


def add_placeholder(entry: tk.Entry, placeholder: str):
    """Add placeholder text to an Entry (gray), clears on focus, restores on focusout."""
    entry.delete(0, "end")
    entry.insert(0, placeholder)
    entry.config(fg="#7a7a7a")

    previous_focus_in = getattr(entry, "_placeholder_focus_in_id", None)
    previous_focus_out = getattr(entry, "_placeholder_focus_out_id", None)
    if previous_focus_in:
        try:
            entry.unbind("<FocusIn>", previous_focus_in)
        except Exception:
            pass
    if previous_focus_out:
        try:
            entry.unbind("<FocusOut>", previous_focus_out)
        except Exception:
            pass

    def on_focus_in(event):
        if entry.get() == placeholder:
            entry.delete(0, "end")
            entry.config(fg="#111111")

    def on_focus_out(event):
        if not entry.get():
            entry.insert(0, placeholder)
            entry.config(fg="#7a7a7a")

    entry._placeholder_focus_in_id = entry.bind("<FocusIn>", on_focus_in)
    entry._placeholder_focus_out_id = entry.bind("<FocusOut>", on_focus_out)


class TouchButton(tk.Label):
    """Press-event button for resistive touchscreens.

    Normal tk.Button calls its command on ButtonRelease. On older resistive
    touch panels a release can land outside the widget, so the UI visibly
    presses but the command never runs. This label-based button triggers on
    <ButtonPress-1> and uses the whole rectangular widget as the hitbox.
    """

    def __init__(
        self,
        parent,
        *,
        text: str,
        command=None,
        bg: str = "#111111",
        fg: str = "white",
        activebackground: str | None = None,
        activeforeground: str | None = None,
        **kwargs,
    ):
        self.command = command
        self.normal_bg = bg
        self.normal_fg = fg
        self.active_bg = activebackground or bg
        self.active_fg = activeforeground or fg
        self._touch_enabled = True
        super().__init__(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            bd=0,
            relief="flat",
            cursor="none",
            takefocus=0,
            **kwargs,
        )
        self.bind("<ButtonPress-1>", self._on_press, add=False)
        self.bind("<ButtonRelease-1>", self._on_release, add=False)
        self.bind("<Leave>", self._on_release, add=False)

    def _on_press(self, event=None):
        if not self._touch_enabled:
            return "break"
        try:
            super().config(bg=self.active_bg, fg=self.active_fg)
        except Exception:
            pass
        try:
            self.after(90, self._restore)
        except Exception:
            pass
        if callable(self.command):
            self.command()
        return "break"

    def _on_release(self, event=None):
        self._restore()
        return "break"

    def _restore(self):
        try:
            super().config(bg=self.normal_bg, fg=self.normal_fg)
        except Exception:
            pass

    def configure(self, cnf=None, **kwargs):
        state = kwargs.pop("state", None)
        if state is not None:
            self._touch_enabled = str(state) != "disabled"
        if cnf:
            return super().configure(cnf, **kwargs)
        return super().configure(**kwargs)

    config = configure


def labeled_entry(parent, label_text, placeholder=None, *, font=("Arial", 16), label_font=("Arial", 16, "bold"), entry_height=1):
    """Return (frame, entry) where label is above entry."""
    f = tk.Frame(parent, bg="white")
    lbl = tk.Label(f, text=label_text, font=label_font, bg="white", fg="#111111")
    lbl.pack(anchor="w")
    ent = tk.Entry(
        f,
        font=font,
        relief="solid",
        bd=1,
        highlightthickness=1,
        highlightbackground="#d8d8d8",
        highlightcolor="#111111",
        bg="white",
        fg="#111111",
        insertbackground="#111111",
    )
    ent.pack(fill="x", expand=True, pady=(3, 0), ipady=max(4, entry_height * 3))
    if placeholder:
        add_placeholder(ent, placeholder)
    return f, ent


# === Helper for consistent top-level window setup ===
def create_dialog(title: str, content_builder, *, root=None, max_ratio=0.8, topmost=True):
    win = tk.Toplevel(root) if root is not None else tk.Toplevel()
    win.title(title)
    if topmost:
        win.attributes("-topmost", True)
    win.resizable(False, False)
    if root is not None:
        try:
            win.transient(root.winfo_toplevel())
        except Exception:
            pass

    content_builder(win, tk)

    win.update_idletasks()
    req_w, req_h = win.winfo_reqwidth(), win.winfo_reqheight()
    screen_w, screen_h = win.winfo_screenwidth(), win.winfo_screenheight()

    width = min(req_w, int(screen_w * max_ratio))
    height = min(req_h, int(screen_h * max_ratio))

    x = (screen_w - width) // 2
    y = (screen_h - height) // 2
    win.geometry(f"{width}x{height}+{x}+{y}")

    win.focus_force()
    win.lift()

    return win


def critical_error_window(root=None, message=None):
    if message is None:
        message = "Десила се критична грешка..."

    def build(win, tk):
        tk.Label(win, text=message, fg="red", wraplength=700, font=("Arial", 16)).pack(padx=24, pady=20)
        TouchButton(win, text="OK", command=win.destroy, font=("Arial", 15, "bold"), padx=16, pady=8, bg="#dddddd", fg="#111111", activebackground="#e7e7e7", activeforeground="#111111").pack(pady=(0, 20))

    return create_dialog("Грешка", build, root=root)


def user_error(root=None, message="Десила се грешка."):
    def build(win, tk):
        tk.Label(win, text="Погрешан унос", font=("Arial", 18, "bold"), fg="red").pack(pady=(14, 8))
        tk.Label(win, text=message, wraplength=760, justify="center", font=("Arial", 15)).pack(padx=24, pady=8)
        TouchButton(win, text="OK", command=win.destroy, bg="#dddddd", fg="#111111", activebackground="#e7e7e7", activeforeground="#111111", width=12, font=("Arial", 14, "bold")).pack(pady=(0, 20), ipady=6)

    return create_dialog("Грешка при уносу", build, root=root)
