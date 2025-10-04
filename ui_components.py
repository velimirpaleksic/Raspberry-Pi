# ui_components.py
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

# Dialogs (error / user_error) -- they accept root so they don't rely on globals
def error_window(root, message=None):
    import tkinter as _tk
    win = _tk.Toplevel(root)
    win.title("Грешка програма")
    win.transient(root)
    win.resizable(False, False)

    if not message:
        message = ("Десила се критична грешка у коду програма.\n"
                   "Молимо вас да проблем пријавите секретару или надлежном.")

    label = _tk.Label(win, text=message, font=("Arial", 13, "bold"),
                      fg="red", justify="center", wraplength=700)
    label.pack(padx=20, pady=20)
    _tk.Button(win, text="OK", command=win.destroy, bg="lightgray", width=12).pack(pady=(0, 20))

    win.update_idletasks()
    width = min(win.winfo_reqwidth(), 900)
    height = min(win.winfo_reqheight(), 400)
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")

def user_error(root, message: str):
    import tkinter as _tk
    win = _tk.Toplevel(root)
    win.title("Грешка")
    win.transient(root)
    win.resizable(False, False)

    _tk.Label(win, text="⚠️ Погрешан унос", font=("Arial", 14, "bold"), fg="red").pack(pady=(10, 5))
    label = _tk.Label(win, text=message, wraplength=700, justify="center")
    label.pack(padx=20, pady=5)
    _tk.Button(win, text="OK", command=win.destroy, bg="lightgray", width=12).pack(pady=(0, 20))

    win.update_idletasks()
    width = min(win.winfo_reqwidth(), 900)
    height = min(win.winfo_reqheight(), 400)
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")

def info_box(root, message: str):
    import tkinter as _tk
    win = _tk.Toplevel(root)
    win.title("Успјешно")
    win.transient(root)
    win.resizable(False, False)

    label = _tk.Label(win, text=message, wraplength=700, justify="center")
    label.pack(padx=20, pady=5)
    _tk.Button(win, text="OK", command=win.destroy, bg="lightgray", width=12).pack(pady=(0, 20))

    win.update_idletasks()
    width = min(win.winfo_reqwidth(), 900)
    height = min(win.winfo_reqheight(), 400)
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")