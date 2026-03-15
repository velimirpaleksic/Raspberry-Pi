import datetime
import tkinter as tk
from tkinter import ttk

from project.core import config
from project.gui import screen_ids
from project.gui.ui_components import labeled_entry, user_error
from project.gui.virtual_keyboard import VirtualKeyboard
from project.utils.logging_utils import log_error


class FormScreen(tk.Frame):
    """Step 1/3: Collect data."""

    def __init__(self, parent, manager=None):
        super().__init__(parent)
        self.manager = manager

        self._build_ui()

        if config.DEBUG_MODE:
            self.fill_debug_data()

    def _build_ui(self):
        # Tkinter variables
        self.ime_var = tk.StringVar()
        self.roditelj_var = tk.StringVar()
        self.mjesto_var = tk.StringVar()
        self.opstina_var = tk.StringVar()
        self.razred_var = tk.StringVar()
        self.struka_var = tk.StringVar()
        self.razlog_var = tk.StringVar()
        self.dan_var = tk.StringVar()
        self.mjesec_var = tk.StringVar()
        self.godina_var = tk.StringVar()

        main = tk.Frame(self, padx=20, pady=20)
        main.pack(fill="both", expand=True)
        for i in range(3):
            main.columnconfigure(i, weight=1)

        # Row 0
        left_frame, self.ime_entry = labeled_entry(main, "Име и презиме ученика")
        left_frame.grid(row=0, column=0, padx=10, pady=8, sticky="nsew")
        mid_frame, self.roditelj_entry = labeled_entry(main, "Име родитеља")
        mid_frame.grid(row=0, column=1, padx=10, pady=8, sticky="nsew")
        tk.Frame(main).grid(row=0, column=2, padx=10, pady=8, sticky="nsew")

        # Row 1 - date of birth
        date_frame = tk.Frame(main)
        tk.Label(date_frame, text="Датум рођења").pack(anchor="w")
        date_inner = tk.Frame(date_frame)
        date_inner.pack(anchor="w", pady=2)

        godine = list(range(1950, datetime.datetime.now().year + 1))
        self.godina_cb = ttk.Combobox(date_inner, textvariable=self.godina_var, values=godine, state="readonly", width=8)
        self.godina_cb.grid(row=0, column=0, padx=(0, 6))
        self.mjesec_cb = ttk.Combobox(date_inner, textvariable=self.mjesec_var, values=list(range(1, 13)), state="disabled", width=6)
        self.mjesec_cb.grid(row=0, column=1, padx=(0, 6))
        self.dan_cb = ttk.Combobox(date_inner, textvariable=self.dan_var, values=list(range(1, 32)), state="disabled", width=6)
        self.dan_cb.grid(row=0, column=2)

        self.godina_cb.bind("<<ComboboxSelected>>", lambda e: self.mjesec_cb.config(state="readonly"))
        self.mjesec_cb.bind("<<ComboboxSelected>>", lambda e: self.dan_cb.config(state="readonly"))

        date_frame.grid(row=1, column=0, padx=10, pady=8, sticky="nsew")

        # Row 1 - place/municipality
        mj_frame, self.mjesto_entry = labeled_entry(main, "Мјесто рођења", placeholder=config.MJESTO_PLACEHOLDER)
        mj_frame.grid(row=1, column=1, padx=10, pady=8, sticky="nsew")
        op_frame, self.opstina_entry = labeled_entry(main, "Општина", placeholder=config.OPSTINA_PLACEHOLDER)
        op_frame.grid(row=1, column=2, padx=10, pady=8, sticky="nsew")

        # Row 2 - comboboxes
        f_r = tk.Frame(main)
        tk.Label(f_r, text="Разред").pack(anchor="w")
        ttk.Combobox(f_r, textvariable=self.razred_var, values=config.RAZREDI, state="readonly").pack(fill="x")
        f_r.grid(row=2, column=0, padx=10, pady=8, sticky="nsew")

        f_s = tk.Frame(main)
        tk.Label(f_s, text="Струка").pack(anchor="w")
        ttk.Combobox(f_s, textvariable=self.struka_var, values=config.STRUKE, state="readonly").pack(fill="x")
        f_s.grid(row=2, column=1, padx=10, pady=8, sticky="nsew")

        f_rz = tk.Frame(main)
        tk.Label(f_rz, text="Разлог").pack(anchor="w")
        ttk.Combobox(f_rz, textvariable=self.razlog_var, values=config.RAZLOZI, state="readonly").pack(fill="x")
        f_rz.grid(row=2, column=2, padx=10, pady=8, sticky="nsew")

        # Buttons
        btn_frame = tk.Frame(main)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=14)
        tk.Button(btn_frame, text="Назад", command=self._go_back, padx=18, pady=8).pack(side="left", padx=8)
        tk.Button(btn_frame, text="ДАЛЈЕ", command=self.submit, bg="lightblue", padx=18, pady=8).pack(side="left", padx=8)

        # Virtual keyboard (best-effort)
        try:
            self.kbd = VirtualKeyboard(
                self,
                mjesto_entry=self.mjesto_entry,
                opstina_entry=self.opstina_entry,
                mjesto_placeholder=config.MJESTO_PLACEHOLDER,
                opstina_placeholder=config.OPSTINA_PLACEHOLDER,
            )
            self.kbd.pack(side="bottom", fill="x")
        except Exception as e:
            log_error(f"[UI] VirtualKeyboard init failed: {e}")
            self.kbd = None

    def _go_back(self):
        if self.manager:
            self.manager.clear_state()
            self.manager.show_frame(screen_ids.START)

    def fill_debug_data(self):
        try:
            for e in [self.mjesto_entry, self.opstina_entry]:
                e.delete(0, "end")
                e.config(fg="black")
            self.ime_entry.insert(0, config.DEBUG_DATA["IME"])
            self.roditelj_entry.insert(0, config.DEBUG_DATA["RODITELJ"])
            self.godina_var.set(config.DEBUG_DATA["GODINA"])
            self.mjesec_var.set(config.DEBUG_DATA["MJESEC"])
            self.dan_var.set(config.DEBUG_DATA["DAN"])
            self.mjesec_cb.config(state="readonly")
            self.dan_cb.config(state="readonly")
            self.mjesto_entry.insert(0, config.DEBUG_DATA["MJESTO"])
            self.opstina_entry.insert(0, config.DEBUG_DATA["OPSTINA"])
            self.razred_var.set(config.DEBUG_DATA["RAZRED"])
            self.struka_var.set(config.DEBUG_DATA["STRUKA"])
            self.razlog_var.set(config.DEBUG_DATA["RAZLOG"])
        except Exception as e:
            log_error(f"[UI] Failed to fill debug data: {e}")

    def submit(self):
        ime = self.ime_entry.get().strip()
        roditelj = self.roditelj_entry.get().strip()
        mjesto = self.mjesto_entry.get().strip()
        opstina = self.opstina_entry.get().strip()
        razred = self.razred_var.get()
        struka = self.struka_var.get()
        razlog = self.razlog_var.get()

        missing = []
        if not ime:
            missing.append("Име и презиме ученика")
        if not roditelj:
            missing.append("Име родитеља")
        if not self.godina_var.get() or not self.mjesec_var.get() or not self.dan_var.get():
            missing.append("Датум рођења")
        if not mjesto or mjesto == config.MJESTO_PLACEHOLDER:
            missing.append("Мјесто рођења")
        if not opstina or opstina == config.OPSTINA_PLACEHOLDER:
            missing.append("Општина")
        if not razred:
            missing.append("Разред")
        if not struka:
            missing.append("Струка")
        if not razlog:
            missing.append("Разлог")

        if missing:
            user_error(self, "Морате попунити поље/поља:\n- " + "\n- ".join(missing))
            return

        form_data = {
            "ime": ime.title(),
            "roditelj": roditelj.title(),
            "mjesto": mjesto.title(),
            "opstina": opstina.title(),
            "razred": razred,
            "struka": struka,
            "razlog": razlog,
            "dan": self.dan_var.get(),
            "mjesec": self.mjesec_var.get(),
            "godina": self.godina_var.get(),
        }

        if self.manager:
            self.manager.state["form_data"] = form_data
            self.manager.show_frame(screen_ids.REVIEW)
