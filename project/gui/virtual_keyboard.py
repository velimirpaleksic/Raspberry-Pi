# gui/virtual_keyboard.py
import tkinter as tk


class VirtualKeyboard(tk.Frame):
    def __init__(self, parent, mjesto_entry=None, opstina_entry=None,
                 mjesto_placeholder=None, opstina_placeholder=None, *args, **kwargs):
        super().__init__(parent, relief="raised", bd=2, padx=6, pady=6, *args, **kwargs)
        self.mjesto_entry = mjesto_entry
        self.opstina_entry = opstina_entry
        self.mjesto_placeholder = mjesto_placeholder
        self.opstina_placeholder = opstina_placeholder

        kbd_rows = [
            list("љњертзуиопшђ"),
            list("асдфгхјклчћж"),
            list("џцвбнм"),
        ]

        for row_keys in kbd_rows:
            rowf = tk.Frame(self)
            rowf.pack(side="top", pady=2)
            for ch in row_keys:
                b = tk.Button(rowf, text=ch, width=4, height=2,
                              command=lambda c=ch: self.insert_char(c))
                b.pack(side="left", padx=1)

        # control row
        ctrl_row = tk.Frame(self)
        ctrl_row.pack(side="top", pady=6)
        tk.Button(ctrl_row, text="Backspace", width=10, command=self.backspace_pressed).pack(side="left", padx=4)
        tk.Button(ctrl_row, text="Space", width=10, command=lambda: self.insert_char(" ")).pack(side="left", padx=4)
        tk.Button(ctrl_row, text="Clear", width=8, command=self.clear_pressed).pack(side="left", padx=4)


    def insert_char(self, ch):
        w = self.master.focus_get()
        if not w:
            return
        if isinstance(w, tk.Entry):
            cur_val = w.get()
            if cur_val in (self.mjesto_placeholder, self.opstina_placeholder):
                w.delete(0, "end")
                w.config(fg="black")
            pos = w.index(tk.INSERT)
            w.insert(pos, ch)
            w.focus_set()


    def backspace_pressed(self):
        w = self.master.focus_get()
        if not w:
            return
        if isinstance(w, tk.Entry):
            try:
                sel_first = w.index("sel.first")
                sel_last = w.index("sel.last")
                w.delete(sel_first, sel_last)
            except Exception:
                idx = w.index(tk.INSERT)
                if idx > 0:
                    w.delete(idx-1)
            w.focus_set()


    def clear_pressed(self):
        w = self.master.focus_get()
        if not w:
            return
        if isinstance(w, tk.Entry):
            w.delete(0, "end")
            # restore placeholder if this is mjesto or opstina
            from project.gui.ui_components import add_placeholder

            if w is self.mjesto_entry and self.mjesto_placeholder:
                add_placeholder(w, self.mjesto_placeholder)
            elif w is self.opstina_entry and self.opstina_placeholder:
                add_placeholder(w, self.opstina_placeholder)
            w.focus_set()