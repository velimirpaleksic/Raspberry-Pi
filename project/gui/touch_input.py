from __future__ import annotations

import tkinter as tk

from project.gui.ui_components import THEME, polish_descendant_buttons


class TouchTextInputDialog(tk.Toplevel):
    def __init__(self, parent, *, title: str, initial: str = '', secret: bool = False):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=THEME["root_bg"])
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.result: str | None = None
        self._secret = bool(secret)
        self._shift = False
        self.value_var = tk.StringVar(value=initial)
        self.display_var = tk.StringVar(value='')
        self._refresh_display()

        try:
            self.geometry(f"1000x620+{max(parent.winfo_rootx()+100, 40)}+{max(parent.winfo_rooty()+40, 40)}")
        except Exception:
            self.geometry('1000x620')

        tk.Label(self, text=title, font=("Arial", 22, "bold"), fg=THEME["text"], bg=THEME["root_bg"]).pack(anchor="w", padx=18, pady=(16, 8))
        tk.Label(self, textvariable=self.display_var, font=("Arial", 20, "bold"), fg=THEME["text"], bg=THEME["card"], anchor="w", justify="left", padx=14, pady=12).pack(fill="x", padx=18, pady=(0, 12))

        rows = [
            list('1234567890'),
            list('qwertyuiop'),
            list('asdfghjkl'),
            list('zxcvbnm'),
            ['.', '-', '_', '@', ':', '/', '?'],
        ]
        self.rows = rows
        self.keys_frame = tk.Frame(self, bg=THEME["root_bg"])
        self.keys_frame.pack(fill='both', expand=True, padx=18)
        self._build_keys()

        controls = tk.Frame(self, bg=THEME["root_bg"])
        controls.pack(fill='x', padx=18, pady=(12, 18))
        tk.Button(controls, text='Shift', command=self._toggle_shift, font=('Arial', 12, 'bold'), padx=12, pady=10).pack(side='left', padx=(0, 8))
        tk.Button(controls, text='Space', command=lambda: self._append(' '), font=('Arial', 12, 'bold'), padx=18, pady=10).pack(side='left', padx=8)
        tk.Button(controls, text='Backspace', command=self._backspace, font=('Arial', 12, 'bold'), padx=12, pady=10).pack(side='left', padx=8)
        tk.Button(controls, text='Clear', command=self._clear, font=('Arial', 12, 'bold'), padx=12, pady=10).pack(side='left', padx=8)
        tk.Button(controls, text='Otkaži', command=self._cancel, font=('Arial', 12, 'bold'), padx=14, pady=10).pack(side='right', padx=(8, 0))
        tk.Button(controls, text='Sačuvaj', command=self._save, font=('Arial', 12, 'bold'), padx=14, pady=10).pack(side='right')

        self.protocol('WM_DELETE_WINDOW', self._cancel)
        polish_descendant_buttons(self)

    def _refresh_display(self):
        value = self.value_var.get()
        self.display_var.set('•' * len(value) if self._secret and value else value)

    def _build_keys(self):
        for child in self.keys_frame.winfo_children():
            child.destroy()
        for row_keys in self.rows:
            row = tk.Frame(self.keys_frame, bg=THEME["root_bg"])
            row.pack(anchor='center', pady=4)
            for ch in row_keys:
                label = ch.upper() if self._shift and ch.isalpha() else ch
                width = 5 if len(label) == 1 else 7
                tk.Button(row, text=label, width=width, font=('Arial', 13, 'bold'), padx=6, pady=10, command=lambda c=label: self._append(c)).pack(side='left', padx=3)

    def _toggle_shift(self):
        self._shift = not self._shift
        self._build_keys()

    def _append(self, char: str):
        self.value_var.set(self.value_var.get() + char)
        self._refresh_display()
        if self._shift:
            self._shift = False
            self._build_keys()

    def _backspace(self):
        self.value_var.set(self.value_var.get()[:-1])
        self._refresh_display()

    def _clear(self):
        self.value_var.set('')
        self._refresh_display()

    def _cancel(self):
        self.result = None
        self.destroy()

    def _save(self):
        self.result = self.value_var.get()
        self.destroy()


def ask_touch_text(parent, *, title: str, initial: str = '', secret: bool = False) -> str | None:
    dialog = TouchTextInputDialog(parent, title=title, initial=initial, secret=secret)
    parent.wait_window(dialog)
    return dialog.result


def bind_touch_text_entry(entry: tk.Entry, parent, *, title: str, secret: bool = False):
    def _open_dialog(event=None):
        try:
            current = entry.get()
        except Exception:
            current = ""
        value = ask_touch_text(parent, title=title, initial=current, secret=secret)
        if value is not None:
            entry.delete(0, "end")
            entry.insert(0, value)
        return "break"

    entry.bind("<Button-1>", _open_dialog, add=True)
    return entry
