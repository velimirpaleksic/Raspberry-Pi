from __future__ import annotations

import tkinter as tk


THEME = {
    "root_bg": "#0B1220",
    "surface": "#10192B",
    "surface_alt": "#0E1524",
    "card": "#162238",
    "card_alt": "#1D2A42",
    "border": "#2D3B57",
    "text": "#F3F7FF",
    "muted": "#B8C3D9",
    "accent": "#5B8CFF",
    "accent_alt": "#7FA4FF",
    "success": "#34D399",
    "warning": "#FBBF24",
    "danger": "#F87171",
    "input_bg": "#0D1524",
    "input_fg": "#F3F7FF",
}

KNOWN_DARK_BACKGROUNDS = {
    "black", "#000000", "#050505", "#101010", "#111111", "#1b1b1b", "#1c1c1c", "#222222", "#333333"
}
KNOWN_LIGHT_TEXT = {"white", "#ffffff", "#f2f2f2", "#dddddd", "#cccccc", "#bbbbbb", "#7cff8f", "#ffcc66"}


def _safe_cget(widget: tk.Misc, option: str, default: str = "") -> str:
    try:
        return str(widget.cget(option))
    except Exception:
        return default


def _is_themeable_bg(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized in KNOWN_DARK_BACKGROUNDS


def _style_label(widget: tk.Label) -> None:
    bg = _safe_cget(widget, "bg")
    fg = _safe_cget(widget, "fg")
    if _is_themeable_bg(bg):
        widget.configure(bg=THEME["root_bg"] if bg.lower() in {"black", "#000000", "#050505"} else THEME["surface"])
    if fg.lower() in KNOWN_LIGHT_TEXT:
        widget.configure(fg=THEME["text"] if "bold" in str(_safe_cget(widget, "font")).lower() or fg.lower() in {"white", "#ffffff"} else THEME["muted"])


def _style_container(widget: tk.Misc) -> None:
    bg = _safe_cget(widget, "bg")
    relief = _safe_cget(widget, "relief")
    if not _is_themeable_bg(bg):
        return
    target_bg = THEME["card"] if relief in {"solid", "groove", "ridge"} else THEME["root_bg"]
    try:
        if isinstance(widget, tk.Canvas):
            target_bg = THEME["surface_alt"]
        widget.configure(bg=target_bg)
    except Exception:
        return
    try:
        if relief in {"solid", "groove", "ridge"}:
            widget.configure(highlightbackground=THEME["border"], highlightcolor=THEME["border"])
    except Exception:
        pass


def _style_text(widget: tk.Text) -> None:
    if _is_themeable_bg(_safe_cget(widget, "bg")):
        widget.configure(
            bg=THEME["surface_alt"],
            fg=THEME["text"],
            insertbackground=THEME["text"],
            selectbackground=THEME["accent"],
            selectforeground=THEME["text"],
            highlightbackground=THEME["border"],
            highlightcolor=THEME["accent_alt"],
        )


def _style_entry(widget: tk.Entry) -> None:
    if _is_themeable_bg(_safe_cget(widget, "bg")):
        widget.configure(
            bg=THEME["input_bg"],
            fg=THEME["input_fg"],
            insertbackground=THEME["text"],
            disabledbackground=THEME["surface_alt"],
            disabledforeground=THEME["muted"],
            highlightbackground=THEME["border"],
            highlightcolor=THEME["accent_alt"],
            relief="flat",
            bd=0,
        )


def add_placeholder(entry: tk.Entry, placeholder: str):
    """Add placeholder text to an Entry (gray), clears on focus, restores on focusout."""
    entry.delete(0, "end")
    entry.insert(0, placeholder)
    entry.config(fg="grey")

    def on_focus_in(event):
        if entry.get() == placeholder:
            entry.delete(0, "end")
            entry.config(fg=THEME["input_fg"])

    def on_focus_out(event):
        if not entry.get():
            entry.insert(0, placeholder)
            entry.config(fg="grey")

    entry.bind("<FocusIn>", on_focus_in)
    entry.bind("<FocusOut>", on_focus_out)


def labeled_entry(parent, label_text, placeholder=None):
    """Return (frame, entry) where label is above entry."""
    f = tk.Frame(parent, bg=THEME["root_bg"])
    lbl = tk.Label(f, text=label_text, bg=THEME["root_bg"], fg=THEME["text"])
    lbl.pack(anchor="w")
    ent = tk.Entry(f)
    ent.pack(fill="x", expand=True)
    _style_entry(ent)
    if placeholder:
        add_placeholder(ent, placeholder)
    return f, ent


# === Helper for consistent top-level window setup ===
def create_dialog(title: str, content_builder, *, root=None, max_ratio=0.8, topmost=True):
    """
    Creates a top-level dialog window that auto-sizes and centers responsively.
    """
    win = tk.Toplevel()
    win.title(title)
    win.configure(bg=THEME["root_bg"])
    if topmost:
        win.attributes("-topmost", True)
    win.resizable(False, False)
    content_builder(win, tk)
    polish_descendant_buttons(win)
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


# === Dialog 1: Critical error ===
def critical_error_window(root=None, message=None):
    if message is None:
        message = "Десила се критична грешка..."

    def build(win, tk):
        tk.Label(win, text=message, fg=THEME["danger"], bg=THEME["root_bg"], wraplength=700).pack(padx=20, pady=20)
        tk.Button(win, text="OK", command=win.destroy).pack(pady=(0, 20))

    return create_dialog("Грешка", build, root=root)


# === Dialog 2: User error ===
def user_error(root=None, message="Десила се грешка."):
    def build(win, tk):
        tk.Label(win, text="⚠️ Погрешан унос", font=("Arial", 14, "bold"), fg=THEME["danger"], bg=THEME["root_bg"]).pack(pady=(10, 5))
        tk.Label(win, text=message, bg=THEME["root_bg"], fg=THEME["text"], wraplength=700, justify="center").pack(padx=20, pady=5)
        tk.Button(win, text="OK", command=win.destroy, width=12).pack(pady=(0, 20))

    return create_dialog("Грешка при уносу", build, root=root)


TOUCH_BUTTON_PALETTES = {
    "primary": {"bg": THEME["accent"], "fg": "white", "activebackground": THEME["accent_alt"], "activeforeground": "white"},
    "secondary": {"bg": THEME["card_alt"], "fg": "white", "activebackground": "#304566", "activeforeground": "white"},
    "success": {"bg": "#12805C", "fg": "white", "activebackground": "#17A271", "activeforeground": "white"},
    "warning": {"bg": "#A66D00", "fg": "white", "activebackground": "#C88911", "activeforeground": "white"},
    "danger": {"bg": "#B63F4A", "fg": "white", "activebackground": "#D95561", "activeforeground": "white"},
}


def status_palette(state: str):
    normalized = str(state or "").upper()
    if normalized in {"READY", "OK", "PASS", "SUCCESS"}:
        return {"bg": "#0F7B5A", "fg": "white"}
    if normalized in {"READY_WITH_WARNINGS", "WARN", "WARNING"}:
        return {"bg": "#A66D00", "fg": "white"}
    return {"bg": "#B63F4A", "fg": "white"}


def apply_status_badge(label: tk.Label, state: str, text: str | None = None):
    palette = status_palette(state)
    label.config(text=text or state, bg=palette["bg"], fg=palette["fg"], padx=14, pady=6, bd=0, relief="flat")


def apply_touch_button(button: tk.Button, *, role: str = "secondary", compact: bool = False) -> tk.Button:
    palette = TOUCH_BUTTON_PALETTES.get(role, TOUCH_BUTTON_PALETTES["secondary"])
    button.configure(
        bg=palette["bg"],
        fg=palette["fg"],
        activebackground=palette["activebackground"],
        activeforeground=palette["activeforeground"],
        relief="flat",
        bd=0,
        highlightthickness=0,
        cursor="hand2",
        padx=10 if compact else 16,
        pady=7 if compact else 10,
    )
    return button


def polish_descendant_buttons(root: tk.Misc) -> None:
    important = {
        "sačuvaj": "primary",
        "save": "primary",
        "traži": "primary",
        "search": "primary",
        "wizard": "primary",
        "spremnost": "success",
        "readiness": "success",
        "export": "success",
        "backup": "success",
        "analytics": "primary",
        "import": "primary",
        "restore": "warning",
        "test": "warning",
        "recovery": "warning",
        "cleanup": "warning",
        "factory": "danger",
        "reset": "danger",
        "nazad": "secondary",
        "back": "secondary",
        "delete": "danger",
        "obriši": "danger",
        "otkaži": "danger",
    }

    def walk(node: tk.Misc):
        for child in node.winfo_children():
            try:
                if isinstance(child, tk.Button):
                    text = str(child.cget("text") or "").lower()
                    role = "secondary"
                    compact = False
                    for needle, candidate in important.items():
                        if needle in text:
                            role = candidate
                            break
                    if len(text) <= 12:
                        compact = True
                    apply_touch_button(child, role=role, compact=compact)
                elif isinstance(child, (tk.Frame, tk.LabelFrame, tk.Canvas)):
                    _style_container(child)
                elif isinstance(child, tk.Label):
                    _style_label(child)
                elif isinstance(child, tk.Text):
                    _style_text(child)
                elif isinstance(child, tk.Entry):
                    _style_entry(child)
                elif isinstance(child, (tk.Checkbutton, tk.Radiobutton)):
                    if _is_themeable_bg(_safe_cget(child, "bg")):
                        child.configure(
                            bg=THEME["root_bg"],
                            fg=THEME["text"],
                            activebackground=THEME["root_bg"],
                            activeforeground=THEME["text"],
                            selectcolor=THEME["surface_alt"],
                            highlightthickness=0,
                        )
                elif isinstance(child, tk.Listbox):
                    if _is_themeable_bg(_safe_cget(child, "bg")):
                        child.configure(
                            bg=THEME["surface_alt"],
                            fg=THEME["text"],
                            selectbackground=THEME["accent"],
                            selectforeground=THEME["text"],
                            highlightthickness=0,
                        )
            except Exception:
                pass
            walk(child)

    try:
        _style_container(root)
    except Exception:
        pass
    walk(root)
