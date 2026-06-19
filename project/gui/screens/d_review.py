import tkinter as tk

from project.gui import screen_ids
from project.gui.ui_components import TouchButton


class ReviewScreen(tk.Frame):
    """Review entered data before printing."""

    CONFIRM_WAIT_SECONDS = 10

    def __init__(self, parent, manager=None):
        super().__init__(parent, bg="#f5f5f5")
        self.manager = manager
        self._confirm_ready = False
        self._countdown_after_id = None
        self._countdown_remaining = self.CONFIRM_WAIT_SECONDS

        ui_scale = getattr(self.manager, "ui_scale", 1.0) if self.manager else 1.0
        title_font = ("Arial", max(28, int(round(28 * ui_scale))), "bold")
        row_font = ("Arial", max(20, int(round(20 * ui_scale))))
        button_font = ("Arial", max(18, int(round(18 * ui_scale))), "bold")

        outer = tk.Frame(self, bg="#f5f5f5")
        outer.pack(fill="both", expand=True)

        content = tk.Frame(outer, bg="#f5f5f5")
        content.place(relx=0.5, rely=0.5, anchor="center")
        if self.manager:
            w, h = self.manager.fit_aspect_ratio(31, 23, fill=0.96)
        else:
            w, h = 1100, 820
        content.configure(width=w, height=h)
        content.pack_propagate(False)

        tk.Label(content, text="ПРОВЈЕРИТЕ ПОДАТКЕ", font=title_font, bg="#f5f5f5", fg="#111111").pack(pady=(10, 18))

        self.box = tk.Frame(content, padx=28, pady=22, relief="solid", bd=1, bg="white")
        self.box.pack(padx=20, pady=6, fill="x", expand=False)

        self.lines = []
        for _ in range(8):
            row = tk.Label(self.box, text="", font=row_font, anchor="w", justify="left", bg="white", fg="#111111")
            row.pack(fill="x", pady=7)
            self.lines.append(row)

        btns = tk.Frame(content, bg="#f5f5f5")
        btns.pack(pady=22)
        TouchButton(
            btns,
            text="НАЗАД",
            font=button_font,
            padx=28,
            pady=14,
            command=self._back,
            bg="#dddddd",
            fg="#111111",
            activebackground="#e7e7e7",
            activeforeground="#111111",
        ).pack(side="left", padx=10)
        self.print_button = TouchButton(
            btns,
            text="ПОТВРДИ И ШТАМПАЈ",
            font=button_font,
            padx=28,
            pady=14,
            bg="#111111",
            fg="white",
            activebackground="#202020",
            activeforeground="white",
            command=self._print,
        )
        self.print_button.pack(side="left", padx=10)

    def _capitalize_words(self, value: str, *, single_word: bool = False) -> str:
        value = str(value or "").strip()
        if not value:
            return ""
        parts = [p for p in value.split() if p]
        if single_word and parts:
            parts = parts[:1]
        return " ".join(part[:1].upper() + part[1:].lower() for part in parts)

    def on_show(self):
        data = (self.manager.state.get("form_data") if self.manager else None) or {}
        if not data:
            self._back()
            return

        ime_ucenika = self._capitalize_words(data.get("ime_ucenika"), single_word=True)
        prezime = self._capitalize_words(data.get("prezime"))
        if not ime_ucenika and not prezime:
            parts = str(data.get("ime") or "").strip().split()
            if parts:
                ime_ucenika = self._capitalize_words(parts[0], single_word=True)
                prezime = self._capitalize_words(" ".join(parts[1:3]))

        dan = str(data.get('dan', '')).zfill(2) if str(data.get('dan', '')).strip() else ''
        mjesec = str(data.get('mjesec', '')).zfill(2) if str(data.get('mjesec', '')).strip() else ''
        datum = f"{dan}.{mjesec}.{data.get('godina','')}"
        full_name = " ".join(part for part in (ime_ucenika, prezime) if part).strip()
        if not full_name:
            full_name = self._capitalize_words(data.get("ime", ""))

        rows = [
            f"Име и презиме ученика: {full_name}",
            f"Име родитеља: {self._capitalize_words(data.get('roditelj', ''), single_word=True)}",
            f"Датум рођења: {datum}",
            f"Мјесто рођења: {self._capitalize_words(data.get('mjesto', ''))}",
            f"Општина рођења: {self._capitalize_words(data.get('opstina', ''))}",
            f"Разред: {data.get('razred', '')}",
            f"Струка: {data.get('struka', '')}",
            f"Разлог: {data.get('razlog', '')}",
        ]
        for lbl, text in zip(self.lines, rows):
            lbl.config(text=text)
        self._start_confirm_countdown()

    def on_hide(self):
        self._cancel_confirm_countdown()

    def _start_confirm_countdown(self):
        self._cancel_confirm_countdown()
        self._confirm_ready = False
        self._countdown_remaining = self.CONFIRM_WAIT_SECONDS
        self._update_confirm_countdown()

    def _cancel_confirm_countdown(self):
        self._confirm_ready = False
        if self._countdown_after_id is not None:
            try:
                self.after_cancel(self._countdown_after_id)
            except Exception:
                pass
            self._countdown_after_id = None

    def _update_confirm_countdown(self):
        self._countdown_after_id = None
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        if self.manager and getattr(self.manager, "current_frame_name", None) != screen_ids.REVIEW:
            return

        if self._countdown_remaining <= 0:
            self._confirm_ready = True
            try:
                self.print_button.config(state="normal", text="ШТАМПАЈ")
            except Exception:
                pass
            return

        try:
            self.print_button.config(state="disabled", text=f"САЧЕКАЈТЕ {self._countdown_remaining}")
        except Exception:
            return
        self._countdown_remaining -= 1
        try:
            self._countdown_after_id = self.after(1000, self._update_confirm_countdown)
        except Exception:
            self._countdown_after_id = None

    def _back(self):
        self._cancel_confirm_countdown()
        if self.manager:
            self.manager.show_frame(screen_ids.FORM)

    def _print(self):
        if self.manager and getattr(self.manager, "current_frame_name", None) != screen_ids.REVIEW:
            return
        if not self._confirm_ready:
            return
        self._cancel_confirm_countdown()
        if self.manager:
            self.manager.show_frame(screen_ids.PRINTING)
