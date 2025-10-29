# gui/ui_components.py
import tkinter as tk


def add_placeholder(entry: tk.Entry, placeholder: str):
    """Add placeholder text to an Entry (gray), clears on focus, restores on focusout."""
    entry.delete(0, "end")
    entry.insert(0, placeholder)
    entry.config(fg="grey")

    def on_focus_in(event):
        if entry.get() == placeholder:
            entry.delete(0, "end")
            entry.config(fg="black")

    def on_focus_out(event):
        if not entry.get():
            entry.insert(0, placeholder)
            entry.config(fg="grey")

    entry.bind("<FocusIn>", on_focus_in)
    entry.bind("<FocusOut>", on_focus_out)


def labeled_entry(parent, label_text, placeholder=None):
    """Return (frame, entry) where label is above entry."""
    f = tk.Frame(parent)
    lbl = tk.Label(f, text=label_text)
    lbl.pack(anchor="w")
    ent = tk.Entry(f)
    ent.pack(fill="x", expand=True)
    if placeholder:
        add_placeholder(ent, placeholder)
    return f, ent


# === Helper for consistent top-level window setup ===
def create_dialog(title: str, content_builder, *, root=None, max_ratio=0.8, topmost=True):
    """
    Creates a top-level dialog window that auto-sizes and centers responsively.
    
    Args:
        title: Window title text
        content_builder: A function that takes (win, tk) and builds the content inside the window
        root: Optional root (ignored for toplevel independence)
        max_ratio: Max size ratio of the screen (0.8 = 80%)
        topmost: Whether to keep dialog on top
    """
    # Always independent top-level window
    win = tk.Toplevel()
    win.title(title)
    if topmost:
        win.attributes("-topmost", True)
    win.resizable(False, False)

    # Let caller populate the content
    content_builder(win, tk)

    # Update layout and compute responsive geometry
    win.update_idletasks()
    req_w, req_h = win.winfo_reqwidth(), win.winfo_reqheight()
    screen_w, screen_h = win.winfo_screenwidth(), win.winfo_screenheight()

    # Limit window to certain screen ratio (responsive)
    width = min(req_w, int(screen_w * max_ratio))
    height = min(req_h, int(screen_h * max_ratio))

    # Center the dialog
    x = (screen_w - width) // 2
    y = (screen_h - height) // 2
    win.geometry(f"{width}x{height}+{x}+{y}")

    # Bring to front and focus
    win.focus_force()
    win.lift()

    return win


# === Dialog 1: Critical error ===
def critical_error_window(root=None, message=None):
    if message is None:
        message = "Десила се критична грешка..."

    def build(win, tk):
        tk.Label(win, text=message, fg="red", wraplength=700).pack(padx=20, pady=20)
        tk.Button(win, text="OK", command=win.destroy).pack(pady=(0, 20))

    return create_dialog("Грешка", build, root=root)


# === Dialog 2: User error ===
def user_error(root=None, message="Десила се грешка."):
    def build(win, tk):
        tk.Label(win, text="⚠️ Погрешан унос", font=("Arial", 14, "bold"), fg="red").pack(pady=(10, 5))
        tk.Label(win, text=message, wraplength=700, justify="center").pack(padx=20, pady=5)
        tk.Button(win, text="OK", command=win.destroy, bg="lightgray", width=12).pack(pady=(0, 20))

    return create_dialog("Грешка при уносу", build, root=root)