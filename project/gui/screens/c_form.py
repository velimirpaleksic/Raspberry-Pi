# gui/screens/c_form.py
import datetime
import tkinter as tk
from tkinter import ttk

from project.core.config import MJESTO_PLACEHOLDER, OPSTINA_PLACEHOLDER, \
                        DEBUG_MODE, DEBUG_DATA, RAZREDI, STRUKE, RAZLOZI

from project.gui.ui_components import labeled_entry, user_error
from project.gui.virtual_keyboard import VirtualKeyboard

from project.utils.logging_utils import error_logging


class FormScreen(tk.Frame):
    def __init__(self, parent, manager=None, status_screen=None):
        try:
            super().__init__(parent)
            self.manager = manager
            self.status_screen = status_screen

            # --- Ensure PrintingStatusScreen is available ---
            try:
                if not hasattr(self, "status_screen") or self.status_screen is None:
                    if hasattr(self.manager, "frames") and "PrintingStatusScreen" in self.manager.frames:
                        self.status_screen = self.manager.frames["PrintingStatusScreen"]
                    else:
                        from project.gui.screens.d_printing_status import PrintingStatusScreen
                        self.status_screen = PrintingStatusScreen(parent=self.manager, manager=self.manager)
                        if hasattr(self.manager, "add_frame"):
                            self.manager.add_frame("PrintingStatusScreen", lambda p=self.manager, m=self.manager: self.status_screen)

            except Exception as e:
                error_logging(f"Failed to initialize 'PrintingStatusScreen': {e}")
                self.status_screen = None
                return

            # --- Build UI elements ---
            self._build_ui_()

        except Exception as e:
            error_logging(f"Failed to initialize 'PrintingStatusScreen': {e}")
            return

        # Debug Data
        if DEBUG_MODE:
            self.fill_debug_data()


    def _build_ui_(self):
        try:
            # --- Tkinter variables ---
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
        
            # --- Form creation ---
            main = tk.Frame(self, padx=20, pady=20)
            main.pack(fill="both", expand=True)
            main.columnconfigure(0, weight=1)
            main.columnconfigure(1, weight=1)
            main.columnconfigure(2, weight=1)

            # Row 0 - Name / Parent
            left_frame, self.ime_entry = labeled_entry(main, "Име и презиме ученика", placeholder=None)
            left_frame.grid(row=0, column=0, padx=10, pady=8, sticky="nsew")

            mid_frame, self.roditelj_entry = labeled_entry(main, "Име родитеља", placeholder=None)
            mid_frame.grid(row=0, column=1, padx=10, pady=8, sticky="nsew")

            tk.Frame(main).grid(row=0, column=2, padx=10, pady=8, sticky="nsew")

            # Row 1 - Date of Birth
            date_frame = tk.Frame(main)
            tk.Label(date_frame, text="Датум рођења").pack(anchor="w")
            date_inner = tk.Frame(date_frame)
            date_inner.pack(anchor="w", pady=2)

            self.godina_var = tk.StringVar()
            self.mjesec_var = tk.StringVar()
            self.dan_var = tk.StringVar()

            godine = list(range(2000, datetime.datetime.now().year + 1))
            self.godina_cb = ttk.Combobox(date_inner, textvariable=self.godina_var, values=godine, state="readonly", width=8)
            self.godina_cb.grid(row=0, column=0, padx=(0,6))
            self.mjesec_cb = ttk.Combobox(date_inner, textvariable=self.mjesec_var, values=list(range(1,13)), state="disabled", width=6)
            self.mjesec_cb.grid(row=0, column=1, padx=(0,6))
            self.dan_cb = ttk.Combobox(date_inner, textvariable=self.dan_var, values=list(range(1,32)), state="disabled", width=6)
            self.dan_cb.grid(row=0, column=2)

            self.godina_cb.bind("<<ComboboxSelected>>", lambda e: self.mjesec_cb.config(state="readonly"))
            self.mjesec_cb.bind("<<ComboboxSelected>>", lambda e: self.dan_cb.config(state="readonly"))

            date_frame.grid(row=1, column=0, padx=10, pady=8, sticky="nsew")

            # Row 1 - Place / Municipality
            mj_frame, self.mjesto_entry = labeled_entry(main, "Мјесто рођења", placeholder=MJESTO_PLACEHOLDER)
            mj_frame.grid(row=1, column=1, padx=10, pady=8, sticky="nsew")

            op_frame, self.opstina_entry = labeled_entry(main, "Општина", placeholder=OPSTINA_PLACEHOLDER)
            op_frame.grid(row=1, column=2, padx=10, pady=8, sticky="nsew")

            # Row 2 - Comboboxes
            self.razred_var = tk.StringVar()
            self.struka_var = tk.StringVar()
            self.razlog_var = tk.StringVar()

            f_r = tk.Frame(main)
            tk.Label(f_r, text="Разред").pack(anchor="w")
            razred_cb = ttk.Combobox(f_r, textvariable=self.razred_var, values=RAZREDI, state="readonly")
            razred_cb.pack(fill="x")
            f_r.grid(row=2, column=0, padx=10, pady=8, sticky="nsew")

            f_s = tk.Frame(main)
            tk.Label(f_s, text="Струка").pack(anchor="w")
            struka_cb = ttk.Combobox(f_s, textvariable=self.struka_var, values=STRUKE, state="readonly")
            struka_cb.pack(fill="x")
            f_s.grid(row=2, column=1, padx=10, pady=8, sticky="nsew")

            f_rz = tk.Frame(main)
            tk.Label(f_rz, text="Разлог").pack(anchor="w")
            razlog_cb = ttk.Combobox(f_rz, textvariable=self.razlog_var, values=RAZLOZI, state="readonly")
            razlog_cb.pack(fill="x")
            f_rz.grid(row=2, column=2, padx=10, pady=8, sticky="nsew")

            # Buttons
            btn_frame = tk.Frame(main)
            btn_frame.grid(row=3, column=0, columnspan=3, pady=12)
            tk.Button(btn_frame, text="Испринтај", command=self.submit, bg="lightblue", padx=12, pady=6).pack()

            # Virtual keyboard
            try:
                self.kbd = VirtualKeyboard(self, mjesto_entry=self.mjesto_entry, opstina_entry=self.opstina_entry,
                                    mjesto_placeholder=MJESTO_PLACEHOLDER, opstina_placeholder=OPSTINA_PLACEHOLDER)
                self.kbd.pack(side="bottom", fill="x")
                
            except Exception as e:
                # log error but continue
                from project.utils.logging_utils import error_logging
                error_logging(f"VirtualKeyboard init failed: {e}")
                self.kbd = None

        except Exception as e:
            error_logging(f"Failed to build 'Form' UI elements: {e}")
            return


    def fill_debug_data(self):
        try:
            for e in [self.mjesto_entry, self.opstina_entry]:
                e.delete(0, "end")
                e.config(fg="black")
            self.ime_entry.insert(0, DEBUG_DATA["IME"])
            self.roditelj_entry.insert(0, DEBUG_DATA["RODITELJ"])
            self.godina_var.set(DEBUG_DATA["GODINA"])
            self.mjesec_var.set(DEBUG_DATA["MJESEC"])
            self.dan_var.set(DEBUG_DATA["DAN"])
            self.mjesec_cb.config(state="readonly")
            self.dan_cb.config(state="readonly")
            self.mjesto_entry.insert(0, DEBUG_DATA["MJESTO"])
            self.opstina_entry.insert(0, DEBUG_DATA["OPSTINA"])
            self.razred_var.set(DEBUG_DATA["RAZRED"])
            self.struka_var.set(DEBUG_DATA["STRUKA"])
            self.razlog_var.set(DEBUG_DATA["RAZLOG"])

        except Exception as e:
            error_logging(f"Failed to fill debug data: {e}")
            return


    def submit(self):
        try:
            ime = self.ime_entry.get().strip()
            roditelj = self.roditelj_entry.get().strip()
            mjesto = self.mjesto_entry.get().strip()
            opstina = self.opstina_entry.get().strip()
            razred = self.razred_var.get()
            struka = self.struka_var.get()
            razlog = self.razlog_var.get()

            missing = []
            if not ime: missing.append("Име и презиме ученика")
            if not roditelj: missing.append("Име родитеља")
            if not self.godina_var.get() or not self.mjesec_var.get() or not self.dan_var.get():
                missing.append("Датум рођења")
            if not mjesto or mjesto == MJESTO_PLACEHOLDER: missing.append("Мјесто рођења")
            if not opstina or opstina == OPSTINA_PLACEHOLDER: missing.append("Општина")
            if not razred: missing.append("Разред")
            if not struka: missing.append("Струка")
            if not razlog: missing.append("Разлог")

            if missing:
                user_error(self, "Морате попунити поље/поља:\n- " + "\n- ".join(missing))
                return
            
            # Send variables to status screen for processing
            dan = self.dan_var.get()
            mjesec = self.mjesec_var.get()
            godina = self.godina_var.get()

            self.status_screen.process_data(
                ime=ime.title(),
                roditelj=roditelj.title(),
                mjesto=mjesto.title(),
                opstina=opstina.title(),
                razred=razred,
                struka=struka,
                razlog=razlog,
                dan=dan,
                mjesec=mjesec,
                godina=godina,
            )
            
            try:
                if self.manager:
                    self.manager.show_frame("PrintingStatusScreen")

            except Exception as e:
                error_logging(f"Failed to show 'PrintingStatusScreen' frame: {e}")
                return
        
        except Exception as e:
            error_logging(f"Failed to submit data to process screen: {e}")
            return