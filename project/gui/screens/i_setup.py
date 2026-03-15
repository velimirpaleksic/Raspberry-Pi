from __future__ import annotations

import tkinter as tk
from pathlib import Path

from project.gui import screen_ids
from project.gui.touch_input import ask_touch_text, bind_touch_text_entry
from project.services.admin_service import get_setup_checklist
from project.services.document_service import record_system_event
from project.services.device_service import get_idle_timeout_ms, get_terminal_location, get_terminal_name, save_idle_timeout_ms, save_terminal_identity
from project.services.network_service import format_network_snapshot, get_network_snapshot
from project.services.printer_service import (
    add_network_printer,
    discover_network_printers,
    get_active_printer,
    list_printers,
    send_test_page,
    set_active_printer,
)
from project.services.settings_service import (
    get_active_template_path,
    get_counter_current,
    get_manual_year,
    get_year_mode,
    is_setup_completed,
    set_counter_current,
    set_manual_year,
    set_setup_completed,
    set_year_mode,
    update_admin_pin,
)
from project.services.storage_service import (
    import_template_from_path,
    list_backup_bundles,
    list_docx_candidates,
    list_usb_mounts,
    restore_backup_bundle,
    use_default_template,
)
from project.services.template_validation_service import format_validation_report, validate_template_file
from project.utils.logging_utils import log_error
from project.gui.ui_components import polish_descendant_buttons


class SetupScreen(tk.Frame):
    def __init__(self, parent, manager=None):
        super().__init__(parent, bg="#101010")
        self.manager = manager
        self.current_step = 0
        self.steps = ["PIN", "Brojač", "Printer", "Template", "Opšte", "Završetak"]
        self._pin = ""
        self._pin_confirm = ""
        self._tested_printer_name = ""
        self._printers: list[dict] = []
        self._usb_mounts: list[dict] = []
        self._docx_candidates: list[dict] = []
        self._backup_candidates: list[dict] = []
        self._network_candidates: list[dict] = []
        self._selected_usb_path = ""

        self.message_var = tk.StringVar(value="")
        self.step_var = tk.StringVar(value="")
        self.summary_var = tk.StringVar(value="")
        self.counter_var = tk.IntVar(value=get_counter_current())
        self.manual_year_var = tk.IntVar(value=get_manual_year())
        self.year_mode_var = tk.StringVar(value=get_year_mode())
        self.selected_printer_var = tk.StringVar(value=get_active_printer())
        self.network_queue_var = tk.StringVar(value="")
        self.network_uri_var = tk.StringVar(value="")
        self.active_template_var = tk.StringVar(value=get_active_template_path())
        self.terminal_name_var = tk.StringVar(value=get_terminal_name())
        self.terminal_location_var = tk.StringVar(value=get_terminal_location())
        self.idle_seconds_var = tk.IntVar(value=max(15, int(get_idle_timeout_ms() / 1000)))

        self._build_ui()
        polish_descendant_buttons(self)
        bind_touch_text_entry(self.network_queue_entry, self, title="Queue name", secret=False)
        bind_touch_text_entry(self.network_uri_entry, self, title="Printer URI", secret=False)
        self._show_step(0)

    def _build_ui(self):
        header = tk.Frame(self, bg="#101010")
        header.pack(fill="x", padx=24, pady=(18, 8))
        tk.Label(header, text="SETUP WIZARD", font=("Arial", 28, "bold"), fg="white", bg="#101010").pack(side="left")
        tk.Button(header, text="Nazad", command=self._go_back_home, font=("Arial", 14, "bold"), padx=16, pady=8).pack(side="right")
        tk.Button(header, text="Mreža / Wi‑Fi", command=self._open_network_setup, font=("Arial", 14, "bold"), padx=16, pady=8).pack(side="right", padx=(0, 10))

        tk.Label(self, textvariable=self.step_var, font=("Arial", 16, "bold"), fg="#7CFF8F", bg="#101010").pack(anchor="w", padx=24)
        tk.Label(self, textvariable=self.message_var, font=("Arial", 13, "bold"), fg="#ffcc66", bg="#101010").pack(anchor="w", padx=24, pady=(6, 10))

        self.content = tk.Frame(self, bg="#101010")
        self.content.pack(fill="both", expand=True, padx=24, pady=(0, 12))

        self.pin_frame = tk.Frame(self.content, bg="#101010")
        self.counter_frame = tk.Frame(self.content, bg="#101010")
        self.printer_frame = tk.Frame(self.content, bg="#101010")
        self.template_frame = tk.Frame(self.content, bg="#101010")
        self.general_frame = tk.Frame(self.content, bg="#101010")
        self.finish_frame = tk.Frame(self.content, bg="#101010")

        self._build_pin_step()
        self._build_counter_step()
        self._build_printer_step()
        self._build_template_step()
        self._build_general_step()
        self._build_finish_step()

        footer = tk.Frame(self, bg="#101010")
        footer.pack(fill="x", padx=24, pady=(0, 20))
        self.back_btn = tk.Button(footer, text="Nazad", command=self._prev_step, font=("Arial", 14, "bold"), padx=16, pady=8)
        self.back_btn.pack(side="left")
        self.next_btn = tk.Button(footer, text="Dalje", command=self._next_step, font=("Arial", 14, "bold"), padx=16, pady=8)
        self.next_btn.pack(side="right")

    def _build_pin_step(self):
        frame = self.pin_frame
        tk.Label(frame, text="1. Postavi admin PIN", font=("Arial", 24, "bold"), fg="white", bg="#101010").pack(pady=(20, 8))
        tk.Label(frame, text="Unesi novi PIN i potvrdi ga. Ovo će koristiti osoblje škole.", font=("Arial", 14), fg="#dddddd", bg="#101010").pack(pady=(0, 16))
        tk.Label(frame, text="Novi PIN", font=("Arial", 16), fg="white", bg="#101010").pack()
        self.pin_display = tk.Label(frame, text="○ ○ ○ ○", font=("Arial", 24, "bold"), fg="white", bg="#1c1c1c", width=18, pady=12)
        self.pin_display.pack(pady=(0, 12))
        tk.Label(frame, text="Potvrda PIN-a", font=("Arial", 16), fg="white", bg="#101010").pack()
        self.pin_confirm_display = tk.Label(frame, text="○ ○ ○ ○", font=("Arial", 24, "bold"), fg="white", bg="#1c1c1c", width=18, pady=12)
        self.pin_confirm_display.pack(pady=(0, 18))
        self.pin_hint_var = tk.StringVar(value="Prvo unesi novi PIN.")
        tk.Label(frame, textvariable=self.pin_hint_var, font=("Arial", 13, "bold"), fg="#ffcc66", bg="#101010").pack(pady=(0, 10))
        keypad = tk.Frame(frame, bg="#101010")
        keypad.pack()
        self._build_numeric_keypad(keypad)

    def _build_counter_step(self):
        frame = self.counter_frame
        tk.Label(frame, text="2. Brojač i godina", font=("Arial", 24, "bold"), fg="white", bg="#101010").pack(pady=(20, 8))
        tk.Label(frame, text="Podesi početni brojač i način obračuna godine.", font=("Arial", 14), fg="#dddddd", bg="#101010").pack(pady=(0, 18))

        card = tk.Frame(frame, bg="#1c1c1c", bd=1, relief="solid", padx=24, pady=18)
        card.pack(padx=10, pady=10)
        tk.Label(card, text="Trenutni brojač", font=("Arial", 18, "bold"), fg="white", bg="#1c1c1c").pack(anchor="w")
        tk.Label(card, textvariable=self.counter_var, font=("Arial", 38, "bold"), fg="#7CFF8F", bg="#1c1c1c").pack(anchor="w", pady=(8, 12))
        row = tk.Frame(card, bg="#1c1c1c")
        row.pack(anchor="w")
        for label, delta in (("-10", -10), ("-1", -1), ("+1", 1), ("+10", 10)):
            tk.Button(row, text=label, command=lambda d=delta: self.counter_var.set(max(0, int(self.counter_var.get()) + d)), width=6, font=("Arial", 13, "bold")).pack(side="left", padx=4)

        year_card = tk.Frame(frame, bg="#1c1c1c", bd=1, relief="solid", padx=24, pady=18)
        year_card.pack(padx=10, pady=10)
        tk.Label(year_card, text="Godina", font=("Arial", 18, "bold"), fg="white", bg="#1c1c1c").pack(anchor="w")
        tk.Button(year_card, text="Promijeni AUTO / MANUAL", command=self._toggle_year_mode, font=("Arial", 12, "bold"), padx=10, pady=6).pack(anchor="w", pady=(8, 10))
        self.year_mode_label = tk.Label(year_card, text="", font=("Arial", 16, "bold"), fg="#111111", bg="#7CFF8F", padx=12, pady=6)
        self.year_mode_label.pack(anchor="w", pady=(0, 10))
        self.manual_year_label = tk.Label(year_card, text="", font=("Arial", 18, "bold"), fg="white", bg="#1c1c1c")
        self.manual_year_label.pack(anchor="w", pady=(0, 10))
        year_row = tk.Frame(year_card, bg="#1c1c1c")
        year_row.pack(anchor="w")
        tk.Button(year_row, text="-1", command=lambda: self.manual_year_var.set(max(2000, int(self.manual_year_var.get()) - 1)), width=6, font=("Arial", 13, "bold")).pack(side="left", padx=4)
        tk.Button(year_row, text="+1", command=lambda: self.manual_year_var.set(min(2099, int(self.manual_year_var.get()) + 1)), width=6, font=("Arial", 13, "bold")).pack(side="left", padx=4)

    def _build_printer_step(self):
        frame = self.printer_frame
        top = tk.Frame(frame, bg="#101010")
        top.pack(fill="x", pady=(16, 8))
        tk.Label(top, text="3. Izbor printera", font=("Arial", 24, "bold"), fg="white", bg="#101010").pack(anchor="w")
        tk.Label(top, text="Testiraj printer prije selekcije. Ako mrežni printer nije već u CUPS-u, dodaj ga ispod iz otkrivenog URI-ja ili ručno.", font=("Arial", 14), fg="#dddddd", bg="#101010", wraplength=1400, justify="left").pack(anchor="w", pady=(6, 8))
        buttons = tk.Frame(top, bg="#101010")
        buttons.pack(anchor="w", pady=(0, 8))
        tk.Button(buttons, text="Osvježi listu", command=self._refresh_printers, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(buttons, text="Pronađi mrežne URI-jeve", command=self._refresh_network_candidates, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(buttons, text="Koristi aktivni printer", command=self._use_active_printer, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left")
        self.printer_status_var = tk.StringVar(value="")
        tk.Label(top, textvariable=self.printer_status_var, font=("Arial", 13, "bold"), fg="#ffcc66", bg="#101010").pack(anchor="w")

        body = tk.Frame(frame, bg="#101010")
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg="#101010")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right = tk.Frame(body, bg="#101010")
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        tk.Label(left, text="CUPS printeri", font=("Arial", 18, "bold"), fg="white", bg="#101010").pack(anchor="w", pady=(0, 8))
        self.printer_canvas = tk.Canvas(left, bg="#101010", highlightthickness=0)
        self.printer_scroll = tk.Scrollbar(left, orient="vertical", command=self.printer_canvas.yview)
        self.printer_inner = tk.Frame(self.printer_canvas, bg="#101010")
        self.printer_inner.bind("<Configure>", lambda e: self.printer_canvas.configure(scrollregion=self.printer_canvas.bbox("all")))
        self.printer_canvas.create_window((0, 0), window=self.printer_inner, anchor="nw")
        self.printer_canvas.configure(yscrollcommand=self.printer_scroll.set)
        self.printer_canvas.pack(side="left", fill="both", expand=True)
        self.printer_scroll.pack(side="right", fill="y")

        tk.Label(right, text="Dodaj mrežni printer", font=("Arial", 18, "bold"), fg="white", bg="#101010").pack(anchor="w", pady=(0, 8))
        manual = tk.Frame(right, bg="#1c1c1c", bd=1, relief="solid", padx=12, pady=12)
        manual.pack(fill="x", pady=(0, 10))
        tk.Label(manual, text="Queue name", font=("Arial", 12, "bold"), fg="white", bg="#1c1c1c").pack(anchor="w")
        tk.Entry(manual, textvariable=self.network_queue_var, font=("Arial", 12), bg="#101010", fg="white", insertbackground="white").pack(fill="x", pady=(4, 8))
        tk.Label(manual, text="URI (ipp://, ipps://, socket:// ...)", font=("Arial", 12, "bold"), fg="white", bg="#1c1c1c").pack(anchor="w")
        tk.Entry(manual, textvariable=self.network_uri_var, font=("Arial", 12), bg="#101010", fg="white", insertbackground="white").pack(fill="x", pady=(4, 8))
        tk.Button(manual, text="Dodaj ručno i postavi aktivni", command=self._add_network_printer_manual, font=("Arial", 12, "bold"), padx=12, pady=8).pack(anchor="w")

        tk.Label(right, text="Otkriveni mrežni URI-jevi", font=("Arial", 16, "bold"), fg="white", bg="#101010").pack(anchor="w", pady=(6, 8))
        self.network_canvas = tk.Canvas(right, bg="#101010", highlightthickness=0)
        self.network_scroll = tk.Scrollbar(right, orient="vertical", command=self.network_canvas.yview)
        self.network_inner = tk.Frame(self.network_canvas, bg="#101010")
        self.network_inner.bind("<Configure>", lambda e: self.network_canvas.configure(scrollregion=self.network_canvas.bbox("all")))
        self.network_canvas.create_window((0, 0), window=self.network_inner, anchor="nw")
        self.network_canvas.configure(yscrollcommand=self.network_scroll.set)
        self.network_canvas.pack(side="left", fill="both", expand=True)
        self.network_scroll.pack(side="right", fill="y")

    def _build_template_step(self):
        frame = self.template_frame
        header = tk.Frame(frame, bg="#101010")
        header.pack(fill="x", pady=(16, 8))
        tk.Label(header, text="4. Template setup", font=("Arial", 24, "bold"), fg="white", bg="#101010").pack(anchor="w")
        tk.Label(header, text="Možeš koristiti default template, uvesti novi .docx sa USB-a ili vratiti backup bundle sa postavkama i template-om.", font=("Arial", 14), fg="#dddddd", bg="#101010", wraplength=1400, justify="left").pack(anchor="w", pady=(6, 8))
        actions = tk.Frame(header, bg="#101010")
        actions.pack(anchor="w", pady=(0, 8))
        tk.Button(actions, text="Koristi default template", command=self._set_default_template, font=("Arial", 12, "bold"), padx=16, pady=10).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Provjeri aktivni template", command=self._validate_active_template, font=("Arial", 12, "bold"), padx=16, pady=10).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Osvježi USB", command=self._scan_usb_mounts, font=("Arial", 12, "bold"), padx=16, pady=10).pack(side="left")

        self.template_status_var = tk.StringVar(value="")
        tk.Label(header, textvariable=self.template_status_var, font=("Arial", 13, "bold"), fg="#ffcc66", bg="#101010").pack(anchor="w")
        tk.Label(header, textvariable=self.active_template_var, font=("Arial", 11), fg="#bbbbbb", bg="#101010", justify="left", wraplength=1400).pack(anchor="w", pady=(4, 0))

        body = tk.Frame(frame, bg="#101010")
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg="#101010")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right = tk.Frame(body, bg="#101010")
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        tk.Label(left, text="USB uređaji", font=("Arial", 18, "bold"), fg="white", bg="#101010").pack(anchor="w", pady=(0, 8))
        self.mounts_canvas = tk.Canvas(left, bg="#101010", highlightthickness=0)
        self.mounts_scroll = tk.Scrollbar(left, orient="vertical", command=self.mounts_canvas.yview)
        self.mounts_inner = tk.Frame(self.mounts_canvas, bg="#101010")
        self.mounts_inner.bind("<Configure>", lambda e: self.mounts_canvas.configure(scrollregion=self.mounts_canvas.bbox("all")))
        self.mounts_canvas.create_window((0, 0), window=self.mounts_inner, anchor="nw")
        self.mounts_canvas.configure(yscrollcommand=self.mounts_scroll.set)
        self.mounts_canvas.pack(side="left", fill="both", expand=True)
        self.mounts_scroll.pack(side="right", fill="y")

        tk.Label(right, text="DOCX fajlovi na odabranom USB-u", font=("Arial", 18, "bold"), fg="white", bg="#101010").pack(anchor="w", pady=(0, 8))
        self.docx_canvas = tk.Canvas(right, bg="#101010", highlightthickness=0)
        self.docx_scroll = tk.Scrollbar(right, orient="vertical", command=self.docx_canvas.yview)
        self.docx_inner = tk.Frame(self.docx_canvas, bg="#101010")
        self.docx_inner.bind("<Configure>", lambda e: self.docx_canvas.configure(scrollregion=self.docx_canvas.bbox("all")))
        self.docx_canvas.create_window((0, 0), window=self.docx_inner, anchor="nw")
        self.docx_canvas.configure(yscrollcommand=self.docx_scroll.set)
        self.docx_canvas.pack(side="left", fill="both", expand=True)
        self.docx_scroll.pack(side="right", fill="y")

    def _build_general_step(self):
        frame = self.general_frame
        tk.Label(frame, text="5. Opšte postavke terminala", font=("Arial", 24, "bold"), fg="white", bg="#101010").pack(pady=(24, 8))
        tk.Label(frame, text="Podesi naziv, lokaciju i idle timeout direktno tokom setupa. Ovo olakšava kasnije održavanje i identifikaciju terminala.", font=("Arial", 14), fg="#dddddd", bg="#101010", wraplength=1400, justify="left").pack(pady=(0, 16))

        card = tk.Frame(frame, bg="#1c1c1c", bd=1, relief="solid", padx=22, pady=18)
        card.pack(fill="x", padx=20, pady=10)
        tk.Label(card, text="Naziv terminala", font=("Arial", 16, "bold"), fg="white", bg="#1c1c1c").pack(anchor="w")
        tk.Label(card, textvariable=self.terminal_name_var, font=("Arial", 18), fg="#7CFF8F", bg="#1c1c1c").pack(anchor="w", pady=(6, 8))
        tk.Button(card, text="Promijeni naziv", command=self._edit_terminal_name, font=("Arial", 12, "bold"), padx=12, pady=8).pack(anchor="w")

        loc = tk.Frame(frame, bg="#1c1c1c", bd=1, relief="solid", padx=22, pady=18)
        loc.pack(fill="x", padx=20, pady=10)
        tk.Label(loc, text="Lokacija terminala", font=("Arial", 16, "bold"), fg="white", bg="#1c1c1c").pack(anchor="w")
        tk.Label(loc, textvariable=self.terminal_location_var, font=("Arial", 18), fg="#7CFF8F", bg="#1c1c1c", wraplength=1300, justify="left").pack(anchor="w", pady=(6, 8))
        tk.Button(loc, text="Promijeni lokaciju", command=self._edit_terminal_location, font=("Arial", 12, "bold"), padx=12, pady=8).pack(anchor="w")

        idle = tk.Frame(frame, bg="#1c1c1c", bd=1, relief="solid", padx=22, pady=18)
        idle.pack(fill="x", padx=20, pady=10)
        tk.Label(idle, text="Idle timeout", font=("Arial", 16, "bold"), fg="white", bg="#1c1c1c").pack(anchor="w")
        tk.Label(idle, textvariable=self.idle_seconds_var, font=("Arial", 34, "bold"), fg="#7CFF8F", bg="#1c1c1c").pack(anchor="w", pady=(6, 10))
        row = tk.Frame(idle, bg="#1c1c1c")
        row.pack(anchor="w")
        for label, delta in (("-30s", -30), ("-5s", -5), ("+5s", 5), ("+30s", 30)):
            tk.Button(row, text=label, command=lambda d=delta: self._adjust_idle_seconds(d), width=7, font=("Arial", 12, "bold")).pack(side="left", padx=4)
        tk.Label(idle, text="Savjet: 60–120 sekundi je dobar raspon za javni kiosk.", font=("Arial", 11), fg="#cccccc", bg="#1c1c1c").pack(anchor="w", pady=(10, 0))

    def _build_finish_step(self):
        frame = self.finish_frame
        tk.Label(frame, text="6. Završetak i spremnost", font=("Arial", 24, "bold"), fg="white", bg="#101010").pack(pady=(30, 12))
        tk.Label(frame, text="Provjeri sažetak i završi setup.", font=("Arial", 14), fg="#dddddd", bg="#101010").pack(pady=(0, 16))
        self.summary_label = tk.Label(frame, textvariable=self.summary_var, font=("Courier New", 14), fg="#f2f2f2", bg="#1c1c1c", justify="left", padx=20, pady=20)
        self.summary_label.pack(padx=20, pady=12, fill="x")
        actions = tk.Frame(frame, bg="#101010")
        actions.pack(pady=(4, 0))
        tk.Button(actions, text="Production readiness", command=self._open_readiness, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=6)
        tk.Button(actions, text="Opšte postavke", command=self._open_general_settings, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=6)

    def on_show(self):
        self.counter_var.set(get_counter_current())
        self.manual_year_var.set(get_manual_year())
        self.year_mode_var.set(get_year_mode())
        self.selected_printer_var.set(get_active_printer())
        self.active_template_var.set(get_active_template_path())
        self.terminal_name_var.set(get_terminal_name())
        self.terminal_location_var.set(get_terminal_location())
        self.idle_seconds_var.set(max(15, int(get_idle_timeout_ms() / 1000)))
        self._tested_printer_name = ""
        self._pin = ""
        self._pin_confirm = ""
        self._selected_usb_path = ""
        self._docx_candidates = []
        self._backup_candidates = []
        self._network_candidates = []
        self._usb_mounts = []
        self._update_pin_displays()
        self._refresh_year_labels()
        desired = None
        if self.manager:
            desired = self.manager.state.pop("setup_start_step", None)
        if isinstance(desired, int):
            self._show_step(desired)
        else:
            self._show_step(0)

    def _show_step(self, index: int):
        self.current_step = max(0, min(index, len(self.steps) - 1))
        self.step_var.set(f"Korak {self.current_step + 1} od {len(self.steps)} — {self.steps[self.current_step]}")
        for frame in (self.pin_frame, self.counter_frame, self.printer_frame, self.template_frame, self.general_frame, self.finish_frame):
            frame.pack_forget()
        target = (self.pin_frame, self.counter_frame, self.printer_frame, self.template_frame, self.general_frame, self.finish_frame)[self.current_step]
        target.pack(fill="both", expand=True)
        self.back_btn.config(state=("disabled" if self.current_step == 0 else "normal"))
        self.next_btn.config(text=("Završi" if self.current_step == len(self.steps) - 1 else "Dalje"))
        if self.current_step == 2:
            self._refresh_printers()
            self._refresh_network_candidates()
        elif self.current_step == 3:
            self._scan_usb_mounts()
        elif self.current_step == 4:
            self._refresh_general_labels()
        elif self.current_step == 5:
            self._refresh_summary()
        polish_descendant_buttons(self)

    def _next_step(self):
        try:
            if self.current_step == 0:
                if not self._validate_and_save_pin():
                    return
            elif self.current_step == 1:
                self._save_counter_step()
            elif self.current_step == 2:
                if not self._validate_printer_step():
                    return
            elif self.current_step == 3:
                if not self._validate_template_step():
                    return
            elif self.current_step == 4:
                self._save_general_step()
            elif self.current_step == 5:
                set_setup_completed(True)
                record_system_event("setup_completed", f"Setup wizard completed. printer={get_active_printer()} template={get_active_template_path()}")
                self.message_var.set("Setup završen.")
                if self.manager:
                    self.manager.state["readiness_return_screen"] = screen_ids.START
                    self.manager.show_frame(screen_ids.READINESS)
                return
            self._show_step(self.current_step + 1)
        except Exception as e:
            log_error(f"[SETUP] next step failed: {e}")
            self.message_var.set(f"Greška: {e}")

    def _prev_step(self):
        self._show_step(self.current_step - 1)

    def _open_network_setup(self):
        if self.manager:
            self.manager.state["network_return_screen"] = screen_ids.SETUP
            self.manager.show_frame(screen_ids.NETWORK)

    def _go_back_home(self):
        if self.manager:
            self.manager.show_frame(screen_ids.START)

    def _build_numeric_keypad(self, parent):
        rows = [("1", "2", "3"), ("4", "5", "6"), ("7", "8", "9")]
        for row_values in rows:
            row = tk.Frame(parent, bg="#101010")
            row.pack(pady=4)
            for value in row_values:
                tk.Button(row, text=value, width=6, height=2, font=("Arial", 18, "bold"), command=lambda v=value: self._append_pin_digit(v)).pack(side="left", padx=5)
        row = tk.Frame(parent, bg="#101010")
        row.pack(pady=4)
        tk.Button(row, text="C", width=6, height=2, font=("Arial", 18, "bold"), command=self._clear_pin).pack(side="left", padx=5)
        tk.Button(row, text="0", width=6, height=2, font=("Arial", 18, "bold"), command=lambda: self._append_pin_digit("0")).pack(side="left", padx=5)
        tk.Button(row, text="⌫", width=6, height=2, font=("Arial", 18, "bold"), command=self._backspace_pin).pack(side="left", padx=5)

    def _append_pin_digit(self, digit: str):
        target = "new" if len(self._pin) < 8 and len(self._pin_confirm) == 0 else "confirm"
        if target == "new":
            self._pin += digit
            if len(self._pin) >= 4:
                self.pin_hint_var.set("Sada potvrdi isti PIN.")
        else:
            if len(self._pin_confirm) < 8:
                self._pin_confirm += digit
        self._update_pin_displays()

    def _clear_pin(self):
        self._pin = ""
        self._pin_confirm = ""
        self.pin_hint_var.set("Prvo unesi novi PIN.")
        self._update_pin_displays()

    def _backspace_pin(self):
        if self._pin_confirm:
            self._pin_confirm = self._pin_confirm[:-1]
        elif self._pin:
            self._pin = self._pin[:-1]
        self._update_pin_displays()

    def _update_pin_displays(self):
        count1 = max(4, len(self._pin))
        count2 = max(4, len(self._pin_confirm))
        self.pin_display.config(text=" ".join("●" if i < len(self._pin) else "○" for i in range(count1)))
        self.pin_confirm_display.config(text=" ".join("●" if i < len(self._pin_confirm) else "○" for i in range(count2)))

    def _validate_and_save_pin(self) -> bool:
        if len(self._pin) < 4:
            self.message_var.set("PIN mora imati najmanje 4 cifre.")
            return False
        if self._pin != self._pin_confirm:
            self.message_var.set("PIN i potvrda se ne poklapaju.")
            return False
        update_admin_pin(self._pin)
        record_system_event("setup_pin_saved", "Admin PIN configured through setup wizard.")
        self.message_var.set("PIN je sačuvan.")
        return True

    def _toggle_year_mode(self):
        self.year_mode_var.set("manual" if self.year_mode_var.get() == "auto" else "auto")
        self._refresh_year_labels()

    def _refresh_year_labels(self):
        mode = self.year_mode_var.get().upper()
        self.year_mode_label.config(text=f"MOD: {mode}")
        self.manual_year_label.config(text=f"Manualna godina: {self.manual_year_var.get()}")

    def _save_counter_step(self):
        set_counter_current(int(self.counter_var.get()))
        set_manual_year(int(self.manual_year_var.get()))
        set_year_mode(self.year_mode_var.get())
        record_system_event("setup_counter_saved", f"Counter/year saved via setup wizard. counter={self.counter_var.get()} mode={self.year_mode_var.get()} year={self.manual_year_var.get()}")
        self.message_var.set("Brojač i godina su sačuvani.")

    def _refresh_printers(self):
        self._printers = list_printers()
        for child in self.printer_inner.winfo_children():
            child.destroy()
        if not self._printers:
            tk.Label(self.printer_inner, text="Nijedan printer nije pronađen preko CUPS-a.", font=("Arial", 14), fg="#ffcc66", bg="#101010").pack(anchor="w", pady=8)
        else:
            for row in self._printers:
                self._build_printer_card(self.printer_inner, row)
        self.printer_status_var.set(f"Pronađeno printera: {len(self._printers)} | aktivni: {get_active_printer()}")

    def _build_printer_card(self, parent, row: dict):
        box = tk.Frame(parent, bg="#1c1c1c", bd=1, relief="solid", padx=14, pady=12)
        box.pack(fill="x", pady=8, padx=6)
        name = row.get("name", "-")
        title = name
        badges = []
        if row.get("is_active"):
            badges.append("AKTIVNI")
        if self._tested_printer_name == name:
            badges.append("ZADNJI TEST")
        if badges:
            title += "   [" + ", ".join(badges) + "]"
        tk.Label(box, text=title, font=("Arial", 16, "bold"), fg="white", bg="#1c1c1c").pack(anchor="w")
        info = (
            f"Status: {row.get('status', '-') } | Ready: {'DA' if row.get('ready') else 'NE'} | Veza: {row.get('connection_type', '-') }\n"
            f"Kod: {row.get('code', '-') } | Poruka: {row.get('message', '') or '-'}\n"
            f"Savjet: {row.get('recovery_hint', '-') }"
        )
        if row.get("device_uri"):
            info += f"\nURI: {row.get('device_uri')}"
        tk.Label(box, text=info, font=("Arial", 12), fg="#dddddd", bg="#1c1c1c", justify="left").pack(anchor="w", pady=(6, 10))
        actions = tk.Frame(box, bg="#1c1c1c")
        actions.pack(anchor="w")
        tk.Button(actions, text="Test print", command=lambda n=name: self._test_printer(n), font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Odaberi ovaj printer", command=lambda n=name: self._select_printer(n), font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left")

    def _test_printer(self, printer_name: str):
        try:
            result = send_test_page(printer_name)
            self._tested_printer_name = printer_name if result.get("ok") else ""
            self.message_var.set(result.get("message") or "Test završen.")
            if result.get("ok"):
                self.printer_status_var.set(
                    f"Ako je baš printer '{printer_name}' ispisao test stranicu, klikni 'Odaberi ovaj printer'."
                )
            self._refresh_printers()
        except Exception as e:
            log_error(f"[SETUP] test printer failed: {e}")
            self.message_var.set(f"Test print nije uspio: {e}")

    def _select_printer(self, printer_name: str):
        if self._tested_printer_name != printer_name:
            self.message_var.set("Prvo uradi test print za ovaj printer, pa ga tek onda odaberi.")
            return
        try:
            set_active_printer(printer_name)
            self.selected_printer_var.set(printer_name)
            self.message_var.set(f"Aktivni printer postavljen: {printer_name}")
            self.printer_status_var.set(f"Odabran aktivni printer: {printer_name}")
            self._refresh_printers()
        except Exception as e:
            log_error(f"[SETUP] select printer failed: {e}")
            self.message_var.set(f"Printer nije postavljen: {e}")

    def _use_active_printer(self):
        active = get_active_printer()
        self.printer_status_var.set(f"Trenutni aktivni printer: {active}")
        self.message_var.set("Ako je to pravi uređaj, možeš nastaviti dalje.")

    def _refresh_network_candidates(self):
        self._network_candidates = discover_network_printers()
        for child in self.network_inner.winfo_children():
            child.destroy()
        if not self._network_candidates:
            tk.Label(self.network_inner, text="Nema otkrivenih mrežnih URI-jeva. Ručno unesi URI ako znaš IP/IPP adresu.", font=("Arial", 13), fg="#ffcc66", bg="#101010", wraplength=650, justify="left").pack(anchor="w", pady=8)
            return
        for row in self._network_candidates:
            self._build_network_candidate_card(self.network_inner, row)

    def _build_network_candidate_card(self, parent, row: dict):
        box = tk.Frame(parent, bg="#1c1c1c", bd=1, relief="solid", padx=12, pady=10)
        box.pack(fill="x", pady=6)
        tk.Label(box, text=row.get("suggested_queue_name", "net_printer"), font=("Arial", 14, "bold"), fg="white", bg="#1c1c1c").pack(anchor="w")
        info = f"Veza: {row.get('connection_type', '-')}\nURI: {row.get('uri', '-')}"
        tk.Label(box, text=info, font=("Arial", 11), fg="#dddddd", bg="#1c1c1c", justify="left", wraplength=650).pack(anchor="w", pady=(6, 8))
        actions = tk.Frame(box, bg="#1c1c1c")
        actions.pack(anchor="w")
        tk.Button(actions, text="Popuni formu", command=lambda r=row: self._prefill_network_candidate(r), font=("Arial", 11, "bold"), padx=10, pady=6).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Dodaj i postavi aktivni", command=lambda r=row: self._add_network_printer_from_candidate(r), font=("Arial", 11, "bold"), padx=10, pady=6).pack(side="left")

    def _prefill_network_candidate(self, row: dict):
        self.network_queue_var.set(str(row.get("suggested_queue_name") or ""))
        self.network_uri_var.set(str(row.get("uri") or ""))
        self.message_var.set("Mrežni printer popunjen u formu. Možeš ga dodati bez tipkanja.")

    def _add_network_printer_from_candidate(self, row: dict):
        self.network_queue_var.set(str(row.get("suggested_queue_name") or ""))
        self.network_uri_var.set(str(row.get("uri") or ""))
        self._add_network_printer_manual()

    def _add_network_printer_manual(self):
        try:
            result = add_network_printer(self.network_queue_var.get(), self.network_uri_var.get(), make_active=True)
            self.message_var.set(result.get("message") or "Dodavanje printera završeno.")
            hint = result.get("recovery_hint") or ""
            if hint:
                self.printer_status_var.set(f"{result.get('message', '')} Savjet: {hint}")
            else:
                self.printer_status_var.set(result.get("message", ""))
            if result.get("ok"):
                self._tested_printer_name = ""
                self.selected_printer_var.set(result.get("queue_name") or get_active_printer())
                self._refresh_printers()
        except Exception as e:
            log_error(f"[SETUP] add network printer failed: {e}")
            self.message_var.set(f"Dodavanje mrežnog printera nije uspjelo: {e}")

    def _validate_printer_step(self) -> bool:
        active = get_active_printer()
        if not active or active == "Printer_Name":
            self.message_var.set("Odaberi aktivni printer prije završetka setupa.")
            return False
        return True

    def _set_default_template(self):
        try:
            result = use_default_template()
            self.active_template_var.set(result['active_template_path'])
            self.template_status_var.set(result['message'])
            self.message_var.set(result['message'])
        except Exception as e:
            log_error(f"[SETUP] default template failed: {e}")
            self.message_var.set(f"Template nije postavljen: {e}")

    def _scan_usb_mounts(self):
        self._usb_mounts = list_usb_mounts()
        for child in self.mounts_inner.winfo_children():
            child.destroy()
        for child in self.docx_inner.winfo_children():
            child.destroy()
        self._docx_candidates = []
        self._backup_candidates = []
        if not self._usb_mounts:
            tk.Label(self.mounts_inner, text="Nijedan USB mount nije pronađen.", font=("Arial", 14), fg="#ffcc66", bg="#101010").pack(anchor="w", pady=8)
            self.template_status_var.set("Priključi USB sa template.docx fajlom ili backup bundle-om pa klikni Osvježi USB.")
            return
        for mount in self._usb_mounts:
            self._build_mount_card(self.mounts_inner, mount)
        self.template_status_var.set(f"Pronađeno USB mountova: {len(self._usb_mounts)}")
        if len(self._usb_mounts) == 1:
            self._select_mount(self._usb_mounts[0]['path'])

    def _build_mount_card(self, parent, mount: dict):
        box = tk.Frame(parent, bg="#1c1c1c", bd=1, relief="solid", padx=12, pady=10)
        box.pack(fill='x', pady=6)
        title = mount.get('label') or mount.get('path')
        if self._selected_usb_path == mount.get('path'):
            title += '   [ODABRAN]'
        tk.Label(box, text=title, font=("Arial", 15, "bold"), fg='white', bg="#1c1c1c").pack(anchor='w')
        free = mount.get('free_gb')
        info = f"Putanja: {mount.get('path')}"
        if free is not None:
            info += f"\nSlobodno: {free} GB"
        tk.Label(box, text=info, font=("Arial", 11), fg="#dddddd", bg="#1c1c1c", justify='left').pack(anchor='w', pady=(6, 8))
        tk.Button(box, text='Prikaži DOCX fajlove', command=lambda p=mount.get('path'): self._select_mount(p), font=("Arial", 12, "bold"), padx=12, pady=8).pack(anchor='w')

    def _select_mount(self, mount_path: str):
        self._selected_usb_path = mount_path
        self._docx_candidates = list_docx_candidates(mount_path)
        self._backup_candidates = list_backup_bundles(mount_path)
        for child in self.mounts_inner.winfo_children():
            child.destroy()
        for mount in self._usb_mounts:
            self._build_mount_card(self.mounts_inner, mount)
        for child in self.docx_inner.winfo_children():
            child.destroy()
        if self._docx_candidates:
            tk.Label(self.docx_inner, text='DOCX fajlovi', font=("Arial", 14, "bold"), fg="white", bg="#101010").pack(anchor='w', pady=(0, 6))
            for row in self._docx_candidates:
                self._build_docx_card(self.docx_inner, row)
        if self._backup_candidates:
            tk.Label(self.docx_inner, text='Backup bundle-ovi', font=("Arial", 14, "bold"), fg="white", bg="#101010").pack(anchor='w', pady=(14, 6))
            for row in self._backup_candidates:
                self._build_backup_card(self.docx_inner, row)
        if not self._docx_candidates and not self._backup_candidates:
            tk.Label(self.docx_inner, text='Na ovom USB-u nema .docx fajlova ni backup bundle-ova.', font=("Arial", 14), fg="#ffcc66", bg="#101010").pack(anchor='w', pady=8)
            return
        self.template_status_var.set(f"Na USB-u: {len(self._docx_candidates)} DOCX | {len(self._backup_candidates)} backup bundle-ova")

    def _build_docx_card(self, parent, row: dict):
        box = tk.Frame(parent, bg="#1c1c1c", bd=1, relief='solid', padx=12, pady=10)
        box.pack(fill='x', pady=6)
        tk.Label(box, text=row.get('name', '-'), font=("Arial", 14, "bold"), fg='white', bg="#1c1c1c").pack(anchor='w')
        info = f"{row.get('size_kb', 0)} KB | izmjena: {row.get('modified_at', '-') }\n{row.get('path', '-') }"
        tk.Label(box, text=info, font=("Arial", 11), fg="#dddddd", bg="#1c1c1c", justify='left', wraplength=950).pack(anchor='w', pady=(6, 8))
        actions = tk.Frame(box, bg="#1c1c1c")
        actions.pack(anchor='w')
        tk.Button(actions, text='Provjeri template', command=lambda p=row.get('path'): self._validate_template_candidate(p), font=("Arial", 12, "bold"), padx=12, pady=8).pack(side='left', padx=(0, 8))
        tk.Button(actions, text='Uvezi i postavi aktivni', command=lambda p=row.get('path'): self._import_template(p), font=("Arial", 12, "bold"), padx=12, pady=8).pack(side='left')

    def _build_backup_card(self, parent, row: dict):
        box = tk.Frame(parent, bg="#1c1c1c", bd=1, relief='solid', padx=12, pady=10)
        box.pack(fill='x', pady=6)
        tk.Label(box, text=row.get('name', '-'), font=("Arial", 14, "bold"), fg='white', bg="#1c1c1c").pack(anchor='w')
        info = (
            f"Kreirano: {row.get('created_at', '-')}\n"
            f"Template: {row.get('template_name', '-') or '-'} | settings: {row.get('settings_count', 0)} | baza: {'DA' if row.get('has_db') else 'NE'}\n"
            f"{row.get('bundle_path', '-')}"
        )
        tk.Label(box, text=info, font=("Arial", 11), fg="#dddddd", bg="#1c1c1c", justify='left', wraplength=950).pack(anchor='w', pady=(6, 8))
        actions = tk.Frame(box, bg="#1c1c1c")
        actions.pack(anchor='w')
        tk.Button(actions, text='Vrati samo postavke', command=lambda p=row.get('bundle_path'): self._restore_backup(p, mode='settings'), font=("Arial", 12, "bold"), padx=12, pady=8).pack(side='left', padx=(0, 8))
        tk.Button(actions, text='Vrati samo template', command=lambda p=row.get('bundle_path'): self._restore_backup(p, mode='template'), font=("Arial", 12, "bold"), padx=12, pady=8).pack(side='left', padx=(0, 8))
        tk.Button(actions, text='Vrati postavke + template', command=lambda p=row.get('bundle_path'): self._restore_backup(p, mode='both'), font=("Arial", 12, "bold"), padx=12, pady=8).pack(side='left')

    def _validate_template_candidate(self, source_path: str):
        try:
            report = validate_template_file(source_path, run_probe_render=True)
            summary = format_validation_report(report)
            self.template_status_var.set('Template je validan.' if report.get('ok') else 'Template validacija nije prošla.')
            self.message_var.set(self.template_status_var.get())
            self.summary_var.set(summary)
        except Exception as e:
            log_error(f"[SETUP] template validation failed: {e}")
            self.message_var.set(f"Template validacija nije uspjela: {e}")

    def _validate_active_template(self):
        self._validate_template_candidate(get_active_template_path())

    def _import_template(self, source_path: str):
        try:
            result = import_template_from_path(source_path)
            self.active_template_var.set(result['active_template_path'])
            self.template_status_var.set(result['message'])
            self.message_var.set(result['message'])
            if result.get('validation_report'):
                self.summary_var.set(result['validation_report'])
        except Exception as e:
            log_error(f"[SETUP] import template failed: {e}")
            self.message_var.set(f"Template import nije uspio: {e}")

    def _restore_backup(self, bundle_path: str, mode: str = 'both'):
        try:
            restore_settings = mode in {'settings', 'both'}
            restore_template = mode in {'template', 'both'}
            result = restore_backup_bundle(bundle_path, restore_settings=restore_settings, restore_template=restore_template)
            self.counter_var.set(get_counter_current())
            self.manual_year_var.set(get_manual_year())
            self.year_mode_var.set(get_year_mode())
            self.selected_printer_var.set(get_active_printer())
            self.active_template_var.set(get_active_template_path())
            self.terminal_name_var.set(get_terminal_name())
            self.terminal_location_var.set(get_terminal_location())
            self.idle_seconds_var.set(max(15, int(get_idle_timeout_ms() / 1000)))
            self._refresh_year_labels()
            self.message_var.set(result.get('message', 'Backup vraćen.'))
            self.template_status_var.set(
                f"Backup vraćen. Settings: {result.get('restored_settings_count', 0)} | Aktivni template: {get_active_template_path()}"
            )
        except Exception as e:
            log_error(f"[SETUP] restore backup failed: {e}")
            self.message_var.set(f"Restore backup-a nije uspio: {e}")

    def _validate_template_step(self) -> bool:
        path = Path(get_active_template_path())
        if not path.exists() or not path.is_file():
            self.message_var.set("Postavi validan template prije završetka setupa.")
            return False
        report = validate_template_file(str(path), run_probe_render=True)
        self.summary_var.set(format_validation_report(report))
        if not report.get('ok'):
            self.message_var.set("Aktivni template nije validan. Otvori validaciju i ispravi greške.")
            return False
        return True

    def _refresh_general_labels(self):
        self.terminal_name_var.set(self.terminal_name_var.get() or get_terminal_name())
        self.terminal_location_var.set(self.terminal_location_var.get() or get_terminal_location())
        self.idle_seconds_var.set(max(15, int(self.idle_seconds_var.get())))

    def _edit_terminal_name(self):
        value = ask_touch_text(self, title="Naziv terminala", initial=self.terminal_name_var.get(), secret=False)
        if value is not None:
            self.terminal_name_var.set(value.strip() or get_terminal_name())

    def _edit_terminal_location(self):
        value = ask_touch_text(self, title="Lokacija terminala", initial=self.terminal_location_var.get(), secret=False)
        if value is not None:
            self.terminal_location_var.set(value.strip())

    def _adjust_idle_seconds(self, delta: int):
        self.idle_seconds_var.set(max(15, min(900, int(self.idle_seconds_var.get()) + int(delta))))

    def _save_general_step(self):
        save_terminal_identity(name=self.terminal_name_var.get(), location=self.terminal_location_var.get())
        save_idle_timeout_ms(int(self.idle_seconds_var.get()) * 1000)
        if self.manager and hasattr(self.manager, "refresh_runtime_settings"):
            self.manager.refresh_runtime_settings()
        record_system_event("setup_general_saved", f"General settings saved via setup wizard. terminal={self.terminal_name_var.get()} location={self.terminal_location_var.get() or '-'} idle={self.idle_seconds_var.get()}s")
        self.message_var.set("Opšte postavke su sačuvane.")

    def _open_general_settings(self):
        if self.manager:
            self.manager.show_frame(screen_ids.SETTINGS)

    def _open_readiness(self):
        if self.manager:
            self.manager.state["readiness_return_screen"] = screen_ids.SETUP
            self.manager.show_frame(screen_ids.READINESS)

    def _refresh_summary(self):
        self._refresh_year_labels()
        completed = "DA" if is_setup_completed() else "NE"
        checklist = get_setup_checklist()
        checklist_lines = []
        for item in checklist.get('items', []):
            icon = 'OK' if item.get('ok') else 'TODO'
            checklist_lines.append(f"[{icon}] {item.get('label')}: {item.get('detail')}")
        network_snapshot = get_network_snapshot()
        self.summary_var.set(
            f"PIN: postavljen\n"
            f"Brojač: {self.counter_var.get()}\n"
            f"Godina mod: {self.year_mode_var.get()}\n"
            f"Manualna godina: {self.manual_year_var.get()}\n"
            f"Aktivni printer: {get_active_printer()}\n"
            f"Aktivni template: {get_active_template_path()}\n"
            f"Terminal: {self.terminal_name_var.get() or '-'}\n"
            f"Lokacija: {self.terminal_location_var.get() or '-'}\n"
            f"Idle timeout: {self.idle_seconds_var.get()} s\n"
            f"Mreža: {network_snapshot.get('message', '-')}\n"
            f"Setup completed prije završetka: {completed}\n\n"
            f"{checklist.get('summary', 'Setup checklist nedostupan')}\n"
            + "\n".join(checklist_lines)
            + "\n\n--- MREŽNI STATUS ---\n"
            + format_network_snapshot(network_snapshot)
        )
