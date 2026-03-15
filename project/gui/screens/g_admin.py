from __future__ import annotations

import datetime
import threading
import tkinter as tk
from tkinter import ttk

from project.gui import screen_ids
from project.services.admin_service import get_admin_snapshot, get_recent_documents, get_setup_checklist
from project.services.document_service import record_system_event
from project.services.health_service import run_startup_checks
from project.services.history_service import (
    export_documents_csv,
    get_daily_summary,
    get_document_attempts,
    search_documents,
)
from project.services.analytics_service import get_analytics_snapshot, format_analytics_snapshot
from project.services.maintenance_service import run_cleanup, run_test_printer
from project.services.factory_mode_service import clear_bindings, clear_configuration, reset_setup_status_only
from project.services.support_bundle_service import export_support_bundle_to_mount
from project.services.network_service import format_network_snapshot, get_network_snapshot
from project.services.notification_service import send_test_notification
from project.services.telegram_remote_service import process_updates_once
from project.services.printer_service import get_printer_diagnostics
from project.gui.touch_input import bind_touch_text_entry
from project.gui.ui_components import apply_status_badge, polish_descendant_buttons
from project.services.storage_service import (
    export_backup_to_mount,
    import_template_from_path,
    list_backup_bundles,
    list_docx_candidates,
    list_usb_mounts,
    restore_backup_bundle,
    use_default_template,
)
from project.services.template_validation_service import format_validation_report, validate_template_file
from project.services.settings_service import (
    get_active_template_path,
    get_counter_current,
    get_counter_prefix,
    get_int_setting,
    get_manual_year,
    get_setting,
    get_year_mode,
    set_bool_setting,
    set_counter_current,
    set_manual_year,
    set_setting,
    set_year_mode,
    update_admin_pin,
    verify_admin_pin,
)
from project.utils.logging_utils import log_error


class AdminScreen(tk.Frame):
    def __init__(self, parent, manager=None):
        super().__init__(parent, bg="#111111")
        self.manager = manager
        self._pin_buffer = ""
        self._new_pin_buffer = ""
        self._confirm_pin_buffer = ""
        self._pin_change_stage = "new"
        self._authenticated = False
        self._history_rows: list[dict] = []
        self._usb_mounts: list[dict] = []
        self._docx_candidates: list[dict] = []
        self._backup_candidates: list[dict] = []
        self._selected_usb_path = ""

        self.counter_var = tk.IntVar(value=get_counter_current())
        self.prefix_var = tk.StringVar(value=get_counter_prefix())
        self.prefix_label_var = tk.StringVar(value=f"Prefiks: {get_counter_prefix()}")
        self.manual_year_var = tk.IntVar(value=get_manual_year())
        self.year_mode_var = tk.StringVar(value=get_year_mode())
        self.message_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="")
        self.stats_var = tk.StringVar(value="")
        self.preview_var = tk.StringVar(value="")
        self.history_status_var = tk.StringVar(value="all")
        self.history_query_var = tk.StringVar(value="")
        self.history_from_var = tk.StringVar(value="")
        self.history_to_var = tk.StringVar(value="")
        self.analytics_days_var = tk.IntVar(value=30)

        self.telegram_enabled_var = tk.BooleanVar(value=False)
        self.discord_enabled_var = tk.BooleanVar(value=False)
        self.cleanup_keep_days_var = tk.IntVar(value=14)
        self.cleanup_keep_last_var = tk.IntVar(value=200)
        self.low_disk_threshold_var = tk.IntVar(value=512)
        self.template_status_var = tk.StringVar(value="")
        self.active_template_var = tk.StringVar(value=get_active_template_path())
        self.checklist_summary_var = tk.StringVar(value="")
        self.factory_status_var = tk.StringVar(value="")
        self.telegram_remote_var = tk.StringVar(value="")

        self._build_ui()
        self._show_login_view()

    def _build_ui(self):
        header = tk.Frame(self, bg="#111111")
        header.pack(fill="x", padx=24, pady=(18, 8))

        tk.Label(header, text="ADMIN PANEL", font=("Arial", 28, "bold"), fg="white", bg="#111111").pack(side="left")
        self.nav_wrap = tk.Frame(header, bg="#111111")
        self.nav_wrap.pack(side="left", padx=24)
        self.dashboard_nav_btn = tk.Button(self.nav_wrap, text="Dashboard", command=self._show_dashboard_view, font=("Arial", 13, "bold"), padx=12, pady=6)
        self.history_nav_btn = tk.Button(self.nav_wrap, text="Historija / Export", command=self._show_history_view, font=("Arial", 13, "bold"), padx=12, pady=6)
        self.template_nav_btn = tk.Button(self.nav_wrap, text="Template / USB", command=self._show_template_view, font=("Arial", 13, "bold"), padx=12, pady=6)
        self.diagnostics_nav_btn = tk.Button(self.nav_wrap, text="Printer dijagnostika", command=self._show_diagnostics_view, font=("Arial", 13, "bold"), padx=12, pady=6)
        self.analytics_nav_btn = tk.Button(self.nav_wrap, text="Analytics", command=self._show_analytics_view, font=("Arial", 13, "bold"), padx=12, pady=6)
        self.pin_nav_btn = tk.Button(self.nav_wrap, text="PIN", command=self._show_pin_change_view, font=("Arial", 13, "bold"), padx=12, pady=6)

        tk.Button(header, text="Nazad", command=self._go_home, font=("Arial", 14, "bold"), padx=18, pady=8).pack(side="right")

        self.message_label = tk.Label(self, textvariable=self.message_var, font=("Arial", 13, "bold"), fg="#ffcc66", bg="#111111")
        self.message_label.pack(fill="x", padx=24, pady=(0, 8))

        self.content = tk.Frame(self, bg="#111111")
        self.content.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        self.login_frame = tk.Frame(self.content, bg="#111111")
        self.dashboard_frame = tk.Frame(self.content, bg="#111111")
        self.history_frame = tk.Frame(self.content, bg="#111111")
        self.template_frame = tk.Frame(self.content, bg="#111111")
        self.diagnostics_frame = tk.Frame(self.content, bg="#111111")
        self.analytics_frame = tk.Frame(self.content, bg="#111111")
        self.pin_change_frame = tk.Frame(self.content, bg="#111111")

        self._build_login_frame()
        self._build_dashboard_frame()
        self._build_history_frame()
        self._build_template_frame()
        self._build_diagnostics_frame()
        self._build_analytics_frame()
        self._build_pin_change_frame()
        self._set_nav_visible(False)
        polish_descendant_buttons(self)

    def _set_nav_visible(self, visible: bool):
        for btn in (self.dashboard_nav_btn, self.history_nav_btn, self.template_nav_btn, self.diagnostics_nav_btn, self.analytics_nav_btn, self.pin_nav_btn):
            if visible:
                btn.pack(side="left", padx=4)
            else:
                btn.pack_forget()

    def _build_login_frame(self):
        frame = self.login_frame
        tk.Label(frame, text="Unesite admin PIN", font=("Arial", 24, "bold"), fg="white", bg="#111111").pack(pady=(30, 12))
        self.pin_display = tk.Label(frame, text="○ ○ ○ ○", font=("Arial", 26, "bold"), fg="white", bg="#1c1c1c", width=18, pady=16)
        self.pin_display.pack(pady=(0, 20))
        keypad = tk.Frame(frame, bg="#111111")
        keypad.pack()
        self._build_numeric_keypad(keypad, self._append_pin_digit, self._pin_backspace, self._pin_clear, self._submit_pin)

    def _build_pin_change_frame(self):
        frame = self.pin_change_frame
        tk.Label(frame, text="Promjena admin PIN-a", font=("Arial", 24, "bold"), fg="white", bg="#111111").pack(pady=(24, 8))
        tk.Label(frame, text="Novi PIN", font=("Arial", 16), fg="white", bg="#111111").pack()
        self.new_pin_display = tk.Label(frame, text="○ ○ ○ ○", font=("Arial", 24, "bold"), fg="white", bg="#1c1c1c", width=18, pady=12)
        self.new_pin_display.pack(pady=(0, 12))
        tk.Label(frame, text="Potvrdi novi PIN", font=("Arial", 16), fg="white", bg="#111111").pack()
        self.confirm_pin_display = tk.Label(frame, text="○ ○ ○ ○", font=("Arial", 24, "bold"), fg="white", bg="#1c1c1c", width=18, pady=12)
        self.confirm_pin_display.pack(pady=(0, 20))
        keypad = tk.Frame(frame, bg="#111111")
        keypad.pack()
        self._build_numeric_keypad(keypad, self._append_new_pin_digit, self._new_pin_backspace, self._new_pin_clear, self._save_new_pin)
        self.pin_change_hint = tk.Label(frame, text="", font=("Arial", 13, "bold"), fg="#ffcc66", bg="#111111")
        self.pin_change_hint.pack(pady=(12, 4))
        tk.Button(frame, text="Nazad na dashboard", command=self._show_dashboard_view, font=("Arial", 14, "bold"), padx=16, pady=8).pack(pady=16)

    def _build_dashboard_frame(self):
        frame = self.dashboard_frame
        top = tk.Frame(frame, bg="#111111")
        top.pack(fill="x", pady=(8, 16))
        tk.Label(top, textvariable=self.status_var, font=("Arial", 16, "bold"), fg="white", bg="#111111", justify="left").pack(anchor="w")
        tk.Label(top, textvariable=self.stats_var, font=("Arial", 14), fg="#dddddd", bg="#111111", justify="left").pack(anchor="w", pady=(8, 0))
        tk.Label(top, textvariable=self.preview_var, font=("Arial", 16, "bold"), fg="#7CFF8F", bg="#111111").pack(anchor="w", pady=(12, 0))
        tk.Label(top, textvariable=self.prefix_label_var, font=("Arial", 12), fg="#bbbbbb", bg="#111111").pack(anchor="w", pady=(6, 0))

        controls = tk.Frame(frame, bg="#111111")
        controls.pack(fill="x")
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)
        self._build_counter_card(controls).grid(row=0, column=0, padx=(0, 12), sticky="nsew")
        self._build_year_card(controls).grid(row=0, column=1, padx=(12, 0), sticky="nsew")

        actions = tk.Frame(frame, bg="#111111")
        actions.pack(fill="x", pady=(16, 14))
        tk.Button(actions, text="Sačuvaj postavke", command=self._save_settings, font=("Arial", 14, "bold"), padx=18, pady=10).pack(side="left", padx=(0, 10))
        tk.Button(actions, text="Historija / Export", command=self._show_history_view, font=("Arial", 14, "bold"), padx=18, pady=10).pack(side="left", padx=10)
        tk.Button(actions, text="Template / USB", command=self._show_template_view, font=("Arial", 14, "bold"), padx=18, pady=10).pack(side="left", padx=10)
        tk.Button(actions, text="Printer dijagnostika", command=self._show_diagnostics_view, font=("Arial", 14, "bold"), padx=18, pady=10).pack(side="left", padx=10)
        tk.Button(actions, text="Analytics", command=self._show_analytics_view, font=("Arial", 14, "bold"), padx=18, pady=10).pack(side="left", padx=10)
        tk.Button(actions, text="Setup printera", command=self._open_setup_printer_step, font=("Arial", 14, "bold"), padx=18, pady=10).pack(side="left", padx=10)
        tk.Button(actions, text="Mreža / Wi‑Fi", command=self._open_network_screen, font=("Arial", 14, "bold"), padx=18, pady=10).pack(side="left", padx=10)
        tk.Button(actions, text="Opšte postavke", command=self._open_general_settings, font=("Arial", 14, "bold"), padx=18, pady=10).pack(side="left", padx=10)
        tk.Button(actions, text="Recovery pomoć", command=self._open_recovery_screen, font=("Arial", 14, "bold"), padx=18, pady=10).pack(side="left", padx=10)
        tk.Button(actions, text="Production readiness", command=self._open_readiness_screen, font=("Arial", 14, "bold"), padx=18, pady=10).pack(side="left", padx=10)
        tk.Button(actions, text="Setup wizard", command=lambda: self.manager.show_frame(screen_ids.SETUP) if self.manager else None, font=("Arial", 14, "bold"), padx=18, pady=10).pack(side="left", padx=10)
        tk.Button(actions, text="Osvježi", command=self._refresh_dashboard, font=("Arial", 14, "bold"), padx=18, pady=10).pack(side="right")

        tools = tk.Frame(frame, bg="#111111")
        tools.pack(fill="x", pady=(0, 14))
        tools.columnconfigure(0, weight=1)
        tools.columnconfigure(1, weight=1)
        self._build_maintenance_card(tools).grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self._build_notifications_card(tools).grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        lower = tk.Frame(frame, bg="#111111")
        lower.pack(fill="both", expand=True)
        lower.columnconfigure(0, weight=1)
        lower.columnconfigure(1, weight=1)
        lower.rowconfigure(0, weight=1)
        lower.rowconfigure(1, weight=1)
        lower.rowconfigure(2, weight=1)

        recent_docs_box = self._card(lower, "Zadnji dokumenti")
        recent_docs_box.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
        self.recent_docs_text = self._card_text(recent_docs_box, height=8)

        events_box = self._card(lower, "Sistemski događaji")
        events_box.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=(0, 10))
        self.events_text = self._card_text(events_box, height=8)

        summary_box = self._card(lower, "Sažetak po danima (7 dana)")
        summary_box.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        self.summary_text = self._card_text(summary_box, height=8)

        tool_box = self._card(lower, "Rezultat alata / health check")
        tool_box.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        self.tool_output_text = self._card_text(tool_box, height=8)

        checklist_box = self._card(lower, "Setup checklist")
        checklist_box.grid(row=2, column=0, sticky="nsew", padx=(0, 10), pady=(10, 0))
        self.checklist_text = self._card_text(checklist_box, height=8)

        diag_box = self._card(lower, "Printer dijagnostika (preview)")
        diag_box.grid(row=2, column=1, sticky="nsew", padx=(10, 0), pady=(10, 0))
        self.diagnostics_preview_text = self._card_text(diag_box, height=8)

    def _build_history_frame(self):
        frame = self.history_frame
        toolbar = tk.Frame(frame, bg="#111111")
        toolbar.pack(fill="x", pady=(6, 12))
        self.history_query_entry = self._toolbar_entry(toolbar, self.history_query_var, width=24)
        self.history_query_entry.pack(side="left", padx=(0, 8))
        self.history_query_entry.insert(0, "")

        tk.Label(toolbar, text="Status", font=("Arial", 12), fg="white", bg="#111111").pack(side="left", padx=(6, 4))
        ttk.Combobox(toolbar, textvariable=self.history_status_var, values=["all", "created", "rendering", "printing", "printed", "failed", "interrupted"], state="readonly", width=12).pack(side="left", padx=(0, 8))
        tk.Label(toolbar, text="Od", font=("Arial", 12), fg="white", bg="#111111").pack(side="left", padx=(6, 4))
        self.history_from_entry = self._toolbar_entry(toolbar, self.history_from_var, width=12)
        self.history_from_entry.pack(side="left", padx=(0, 8))
        tk.Label(toolbar, text="Do", font=("Arial", 12), fg="white", bg="#111111").pack(side="left", padx=(6, 4))
        self.history_to_entry = self._toolbar_entry(toolbar, self.history_to_var, width=12)
        self.history_to_entry.pack(side="left", padx=(0, 12))
        tk.Button(toolbar, text="Traži", command=self._history_search, font=("Arial", 12, "bold"), padx=10, pady=6).pack(side="left", padx=(0, 8))
        tk.Button(toolbar, text="Export CSV", command=self._history_export, font=("Arial", 12, "bold"), padx=10, pady=6).pack(side="left")

        presets = tk.Frame(frame, bg="#111111")
        presets.pack(fill="x", pady=(0, 12))
        tk.Label(presets, text="Preset filteri:", font=("Arial", 12, "bold"), fg="#dddddd", bg="#111111").pack(side="left", padx=(0, 8))
        tk.Button(presets, text="Danas", command=lambda: self._apply_preset("today"), font=("Arial", 11, "bold"), padx=10, pady=6).pack(side="left", padx=4)
        tk.Button(presets, text="Zadnjih 7 dana", command=lambda: self._apply_preset("week"), font=("Arial", 11, "bold"), padx=10, pady=6).pack(side="left", padx=4)
        tk.Button(presets, text="Samo fail", command=lambda: self._apply_preset("failed"), font=("Arial", 11, "bold"), padx=10, pady=6).pack(side="left", padx=4)
        tk.Button(presets, text="Sve očisti", command=self._clear_history_filters, font=("Arial", 11, "bold"), padx=10, pady=6).pack(side="left", padx=4)
        tk.Button(presets, text="Nazad na dashboard", command=self._show_dashboard_view, font=("Arial", 11, "bold"), padx=10, pady=6).pack(side="right")

        top = tk.Frame(frame, bg="#111111")
        top.pack(fill="both", expand=True)
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)
        top.rowconfigure(0, weight=1)
        top.rowconfigure(1, weight=1)

        results_box = self._card(top, "Rezultati pretrage")
        results_box.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
        self.results_list = tk.Listbox(results_box, font=("Courier New", 11), bg="#101010", fg="#f2f2f2", selectbackground="#2d5cff", activestyle="none")
        self.results_list.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.results_list.bind("<<ListboxSelect>>", self._on_history_select)

        details_box = self._card(top, "Detalji + pokušaji")
        details_box.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=(0, 10))
        self.history_details_text = self._card_text(details_box, height=12)

        history_summary_box = self._card(top, "Dnevna statistika")
        history_summary_box.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        self.history_summary_text = self._card_text(history_summary_box, height=8)

        exports_box = self._card(top, "Napomene")
        exports_box.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        self.history_help_text = self._card_text(exports_box, height=8)
        self._replace_text(
            self.history_help_text,
            "Pretraga podržava ime, broj dokumenta i job_id.\n"
            "Datumi su u formatu YYYY-MM-DD.\n"
            "CSV export poštuje aktivne filtere i sprema fajl u VAR_DIR/exports/.\n"
            "Klik na rezultat otvara detalje i sve attemptove za taj dokument.",
        )

    def _build_template_frame(self):
        frame = self.template_frame
        top = tk.Frame(frame, bg="#111111")
        top.pack(fill="x", pady=(8, 12))
        tk.Label(top, text="Template i USB alati", font=("Arial", 24, "bold"), fg="white", bg="#111111").pack(anchor="w")
        tk.Label(top, text="Uvezi novi .docx template sa USB-a, izvezi backup ili vrati postavke/template iz postojećeg backup bundle-a.", font=("Arial", 13), fg="#dddddd", bg="#111111").pack(anchor="w", pady=(6, 8))
        actions = tk.Frame(top, bg="#111111")
        actions.pack(anchor="w")
        tk.Button(actions, text="Koristi default template", command=self._template_use_default, font=("Arial", 12, "bold"), padx=14, pady=10).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Provjeri aktivni template", command=self._validate_active_template, font=("Arial", 12, "bold"), padx=14, pady=10).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Osvježi USB", command=self._template_refresh_usb, font=("Arial", 12, "bold"), padx=14, pady=10).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Otvori setup na template koraku", command=self._open_setup_template_step, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Otvori setup na printer koraku", command=self._open_setup_printer_step, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left")
        tk.Label(top, textvariable=self.template_status_var, font=("Arial", 13, "bold"), fg="#ffcc66", bg="#111111").pack(anchor="w", pady=(10, 0))
        tk.Label(top, textvariable=self.active_template_var, font=("Arial", 11), fg="#bbbbbb", bg="#111111", wraplength=1500, justify="left").pack(anchor="w", pady=(4, 0))

        body = tk.Frame(frame, bg="#111111")
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        left_card = self._card(body, "USB mountovi")
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right_card = self._card(body, "DOCX template fajlovi / Backup restore")
        right_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        self.template_mounts_canvas = tk.Canvas(left_card, bg="#1c1c1c", highlightthickness=0)
        self.template_mounts_scroll = tk.Scrollbar(left_card, orient="vertical", command=self.template_mounts_canvas.yview)
        self.template_mounts_inner = tk.Frame(self.template_mounts_canvas, bg="#1c1c1c")
        self.template_mounts_inner.bind("<Configure>", lambda e: self.template_mounts_canvas.configure(scrollregion=self.template_mounts_canvas.bbox("all")))
        self.template_mounts_canvas.create_window((0, 0), window=self.template_mounts_inner, anchor="nw")
        self.template_mounts_canvas.configure(yscrollcommand=self.template_mounts_scroll.set)
        self.template_mounts_canvas.pack(side="left", fill="both", expand=True, padx=12, pady=(0, 12))
        self.template_mounts_scroll.pack(side="right", fill="y", pady=(0, 12))

        self.template_files_canvas = tk.Canvas(right_card, bg="#1c1c1c", highlightthickness=0)
        self.template_files_scroll = tk.Scrollbar(right_card, orient="vertical", command=self.template_files_canvas.yview)
        self.template_files_inner = tk.Frame(self.template_files_canvas, bg="#1c1c1c")
        self.template_files_inner.bind("<Configure>", lambda e: self.template_files_canvas.configure(scrollregion=self.template_files_canvas.bbox("all")))
        self.template_files_canvas.create_window((0, 0), window=self.template_files_inner, anchor="nw")
        self.template_files_canvas.configure(yscrollcommand=self.template_files_scroll.set)
        self.template_files_canvas.pack(side="left", fill="both", expand=True, padx=12, pady=(0, 12))
        self.template_files_scroll.pack(side="right", fill="y", pady=(0, 12))

    def _build_analytics_frame(self):
        frame = self.analytics_frame
        top = tk.Frame(frame, bg="#111111")
        top.pack(fill="x", pady=(6, 12))
        tk.Label(top, text="Printer / Job analytics", font=("Arial", 22, "bold"), fg="white", bg="#111111").pack(side="left")
        controls = tk.Frame(top, bg="#111111")
        controls.pack(side="right")
        tk.Label(controls, text="Period", font=("Arial", 12, "bold"), fg="#dddddd", bg="#111111").pack(side="left", padx=(0, 6))
        ttk.Combobox(controls, textvariable=self.analytics_days_var, values=[7, 14, 30, 60, 90], state="readonly", width=6).pack(side="left", padx=(0, 8))
        tk.Button(controls, text="Osvježi", command=self._refresh_analytics, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(controls, text="Nazad na dashboard", command=self._show_dashboard_view, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left")

        kpis = tk.Frame(frame, bg="#111111")
        kpis.pack(fill="x", pady=(0, 12))
        self.analytics_badge_docs = tk.Label(kpis, font=("Arial", 13, "bold"))
        self.analytics_badge_success = tk.Label(kpis, font=("Arial", 13, "bold"))
        self.analytics_badge_retry = tk.Label(kpis, font=("Arial", 13, "bold"))
        self.analytics_badge_speed = tk.Label(kpis, font=("Arial", 13, "bold"))
        for badge in (self.analytics_badge_docs, self.analytics_badge_success, self.analytics_badge_retry, self.analytics_badge_speed):
            badge.pack(side="left", padx=(0, 10))

        body = tk.Frame(frame, bg="#111111")
        body.pack(fill="both", expand=True)
        for c in range(2):
            body.columnconfigure(c, weight=1)
        for r in range(2):
            body.rowconfigure(r, weight=1)

        analytics_summary = self._card(body, "Sažetak")
        analytics_summary.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
        self.analytics_summary_text = self._card_text(analytics_summary, height=10)

        analytics_daily = self._card(body, "Trend po danima")
        analytics_daily.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=(0, 10))
        self.analytics_daily_text = self._card_text(analytics_daily, height=10)

        analytics_errors = self._card(body, "Najčešće greške")
        analytics_errors.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        self.analytics_errors_text = self._card_text(analytics_errors, height=10)

        analytics_retries = self._card(body, "Retry distribucija / preporuke")
        analytics_retries.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        self.analytics_retry_text = self._card_text(analytics_retries, height=10)

    def _build_diagnostics_frame(self):
        frame = self.diagnostics_frame
        top = tk.Frame(frame, bg="#111111")
        top.pack(fill="x", pady=(8, 12))
        tk.Label(top, text="Printer dijagnostika", font=("Arial", 24, "bold"), fg="white", bg="#111111").pack(anchor="w")
        tk.Label(top, text="Dublji pregled CUPS stanja, lpstat izlaza i recovery hintova za aktivni printer.", font=("Arial", 13), fg="#dddddd", bg="#111111").pack(anchor="w", pady=(6, 8))
        actions = tk.Frame(top, bg="#111111")
        actions.pack(anchor="w")
        tk.Button(actions, text="Osvježi dijagnostiku", command=self._refresh_diagnostics, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Test printera", command=self._run_test_printer, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Otvori setup printera", command=self._open_setup_printer_step, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Nazad na dashboard", command=self._show_dashboard_view, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left")

        self.diagnostics_status_var = tk.StringVar(value="")
        tk.Label(top, textvariable=self.diagnostics_status_var, font=("Arial", 13, "bold"), fg="#ffcc66", bg="#111111", wraplength=1500, justify="left").pack(anchor="w", pady=(10, 0))

        body = tk.Frame(frame, bg="#111111")
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = self._card(body, "Sažetak i hintovi")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.diagnostics_summary_text = self._card_text(left, height=22)

        right = self._card(body, "lpstat izlazi")
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        self.diagnostics_raw_text = self._card_text(right, height=22)

    def _toolbar_entry(self, parent, variable: tk.StringVar, width: int = 16) -> tk.Entry:
        entry = tk.Entry(parent, textvariable=variable, width=width, font=("Arial", 12), bg="#101010", fg="white", insertbackground="white")
        bind_touch_text_entry(entry, self, title='Unos teksta', secret=False)
        return entry

    def _card(self, parent, title: str) -> tk.Frame:
        box = tk.Frame(parent, bg="#162238", bd=1, relief="solid", highlightbackground="#31415f", highlightthickness=1)
        header = tk.Frame(box, bg="#1D2A42", height=42)
        header.pack(fill="x")
        tk.Label(header, text=title, font=("Arial", 16, "bold"), fg="white", bg="#1D2A42").pack(anchor="w", padx=14, pady=(10, 8))
        return box

    def _card_text(self, parent, *, height: int = 8) -> tk.Text:
        text = tk.Text(parent, height=height, font=("Courier New", 11), bg="#0E1524", fg="#F3F7FF", wrap="word", relief="flat", bd=0)
        text.pack(fill="both", expand=True, padx=14, pady=(10, 14))
        text.config(state="disabled")
        return text

    def _build_numeric_keypad(self, parent, digit_command, backspace_command, clear_command, submit_command):
        rows = [("1", "2", "3"), ("4", "5", "6"), ("7", "8", "9")]
        for row_values in rows:
            row = tk.Frame(parent, bg="#111111")
            row.pack(pady=4)
            for value in row_values:
                tk.Button(row, text=value, width=6, height=2, font=("Arial", 18, "bold"), command=lambda v=value: digit_command(v)).pack(side="left", padx=5)
        row = tk.Frame(parent, bg="#111111")
        row.pack(pady=4)
        tk.Button(row, text="C", width=6, height=2, font=("Arial", 18, "bold"), command=clear_command).pack(side="left", padx=5)
        tk.Button(row, text="0", width=6, height=2, font=("Arial", 18, "bold"), command=lambda: digit_command("0")).pack(side="left", padx=5)
        tk.Button(row, text="⌫", width=6, height=2, font=("Arial", 18, "bold"), command=backspace_command).pack(side="left", padx=5)
        tk.Button(parent, text="Potvrdi", width=22, height=2, font=("Arial", 16, "bold"), command=submit_command).pack(pady=(10, 0))

    def _build_counter_card(self, parent):
        card = tk.Frame(parent, bg="#1c1c1c", bd=1, relief="solid", padx=18, pady=16)
        tk.Label(card, text="Brojač", font=("Arial", 18, "bold"), fg="white", bg="#1c1c1c").pack(anchor="w")
        tk.Label(card, textvariable=self.prefix_label_var, font=("Arial", 12), fg="#cccccc", bg="#1c1c1c").pack(anchor="w", pady=(6, 4))
        tk.Label(card, textvariable=self.counter_var, font=("Arial", 34, "bold"), fg="#7CFF8F", bg="#1c1c1c").pack(anchor="w", pady=(4, 12))
        row = tk.Frame(card, bg="#1c1c1c")
        row.pack(anchor="w")
        for label, delta in (("-10", -10), ("-1", -1), ("+1", 1), ("+10", 10)):
            tk.Button(row, text=label, command=lambda d=delta: self._adjust_counter(d), width=6, font=("Arial", 13, "bold")).pack(side="left", padx=4)
        return card

    def _build_year_card(self, parent):
        card = tk.Frame(parent, bg="#1c1c1c", bd=1, relief="solid", padx=18, pady=16)
        tk.Label(card, text="Godina", font=("Arial", 18, "bold"), fg="white", bg="#1c1c1c").pack(anchor="w")
        mode_wrap = tk.Frame(card, bg="#1c1c1c")
        mode_wrap.pack(anchor="w", pady=(8, 10))
        tk.Label(mode_wrap, text="Mod:", font=("Arial", 12), fg="#dddddd", bg="#1c1c1c").pack(side="left")
        self.year_mode_badge = tk.Label(mode_wrap, text="AUTO", font=("Arial", 12, "bold"), fg="#111111", bg="#7CFF8F", padx=12, pady=4)
        self.year_mode_badge.pack(side="left", padx=8)
        tk.Button(mode_wrap, text="Promijeni", command=self._toggle_year_mode, font=("Arial", 12, "bold"), padx=10, pady=4).pack(side="left")
        self.manual_year_label = tk.Label(card, text=f"Manual: {self.manual_year_var.get()}", font=("Arial", 16, "bold"), fg="white", bg="#1c1c1c")
        self.manual_year_label.pack(anchor="w", pady=(6, 12))
        row = tk.Frame(card, bg="#1c1c1c")
        row.pack(anchor="w")
        tk.Button(row, text="-1", command=lambda: self._adjust_manual_year(-1), width=6, font=("Arial", 13, "bold")).pack(side="left", padx=4)
        tk.Button(row, text="+1", command=lambda: self._adjust_manual_year(1), width=6, font=("Arial", 13, "bold")).pack(side="left", padx=4)
        tk.Label(card, text="Manualna godina se koristi samo u manual modu.", font=("Arial", 11), fg="#cccccc", bg="#1c1c1c").pack(anchor="w", pady=(10, 0))
        return card

    def _build_maintenance_card(self, parent):
        card = tk.Frame(parent, bg="#1c1c1c", bd=1, relief="solid", padx=18, pady=16)
        tk.Label(card, text="Maintenance + Factory mode", font=("Arial", 18, "bold"), fg="white", bg="#1c1c1c").pack(anchor="w")
        row1 = tk.Frame(card, bg="#1c1c1c")
        row1.pack(anchor="w", pady=(12, 8))
        tk.Button(row1, text="Startup check", command=self._run_health_checks, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(row1, text="Cleanup", command=self._run_cleanup, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(row1, text="Test printera", command=self._run_test_printer, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left")
        row2 = tk.Frame(card, bg="#1c1c1c")
        row2.pack(anchor="w", pady=(0, 8))
        tk.Button(row2, text="Test notifikacija", command=self._run_test_notification, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(row2, text="Telegram poll once", command=self._run_telegram_remote_poll, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left")
        tk.Label(card, text="Factory mode služi za servis/redeploy. Koristi ga pažljivo.", font=("Arial", 11, "bold"), fg="#ffcc66", bg="#1c1c1c").pack(anchor="w", pady=(8, 6))
        row3 = tk.Frame(card, bg="#1c1c1c")
        row3.pack(anchor="w", pady=(0, 8))
        tk.Button(row3, text="Reset setup status", command=self._factory_reset_setup_status, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(row3, text="Očisti Wi‑Fi/printer", command=self._factory_clear_bindings, font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(0, 8))
        row4 = tk.Frame(card, bg="#1c1c1c")
        row4.pack(anchor="w", pady=(0, 10))
        tk.Button(row4, text="Očisti konfiguraciju", command=lambda: self._factory_clear_configuration(True), font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(row4, text="Factory reset + obriši evidenciju", command=lambda: self._factory_clear_configuration(False), font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left")
        tk.Label(card, textvariable=self.factory_status_var, font=("Arial", 11), fg="#dddddd", bg="#1c1c1c", wraplength=700, justify="left").pack(anchor="w", pady=(0, 8))
        limits = tk.Frame(card, bg="#1c1c1c")
        limits.pack(anchor="w", pady=(8, 0))
        self._spin_group(limits, "Keep days", self.cleanup_keep_days_var, -1, +1).pack(side="left", padx=(0, 18))
        self._spin_group(limits, "Keep last", self.cleanup_keep_last_var, -10, +10).pack(side="left", padx=(0, 18))
        self._spin_group(limits, "Low disk MB", self.low_disk_threshold_var, -64, +64).pack(side="left")
        return card

    def _build_notifications_card(self, parent):
        card = tk.Frame(parent, bg="#1c1c1c", bd=1, relief="solid", padx=18, pady=16)
        tk.Label(card, text="Notifikacije + Telegram remote", font=("Arial", 18, "bold"), fg="white", bg="#1c1c1c").pack(anchor="w")
        toggles = tk.Frame(card, bg="#1c1c1c")
        toggles.pack(fill="x", pady=(10, 8))
        tk.Checkbutton(toggles, text="Telegram", variable=self.telegram_enabled_var, bg="#1c1c1c", fg="white", selectcolor="#333333", activebackground="#1c1c1c", activeforeground="white").pack(side="left", padx=(0, 18))
        tk.Checkbutton(toggles, text="Discord fallback", variable=self.discord_enabled_var, bg="#1c1c1c", fg="white", selectcolor="#333333", activebackground="#1c1c1c", activeforeground="white").pack(side="left")
        self.telegram_token_entry = self._labeled_entry(card, "Telegram bot token")
        self.telegram_chat_id_entry = self._labeled_entry(card, "Telegram chat id")
        self.discord_webhook_entry = self._labeled_entry(card, "Discord webhook fallback")
        tk.Label(card, text="Remote komande: /status /health /readiness /printer /network /analytics /help", font=("Arial", 11), fg="#cccccc", bg="#1c1c1c", wraplength=700, justify="left").pack(anchor="w", pady=(8, 4))
        tk.Label(card, textvariable=self.telegram_remote_var, font=("Arial", 11, "bold"), fg="#ffcc66", bg="#1c1c1c", wraplength=700, justify="left").pack(anchor="w", pady=(0, 4))
        return card

    def _labeled_entry(self, parent, label: str) -> tk.Entry:
        wrap = tk.Frame(parent, bg="#1c1c1c")
        wrap.pack(fill="x", pady=4)
        tk.Label(wrap, text=label, font=("Arial", 12), fg="#e6e6e6", bg="#1c1c1c").pack(anchor="w")
        entry = tk.Entry(wrap, font=("Arial", 12), bg="#101010", fg="white", insertbackground="white")
        entry.pack(fill="x", pady=(4, 0))
        bind_touch_text_entry(entry, self, title=label, secret=('PIN' in label.lower() or 'token' in label.lower()))
        return entry

    def _spin_group(self, parent, label: str, variable: tk.IntVar, minus_delta: int, plus_delta: int):
        wrap = tk.Frame(parent, bg="#1c1c1c")
        tk.Label(wrap, text=label, font=("Arial", 12), fg="#e6e6e6", bg="#1c1c1c").pack(anchor="w")
        row = tk.Frame(wrap, bg="#1c1c1c")
        row.pack(anchor="w", pady=(4, 0))
        tk.Button(row, text="-", width=3, command=lambda: variable.set(max(0, int(variable.get()) + minus_delta))).pack(side="left", padx=(0, 4))
        tk.Label(row, textvariable=variable, width=6, font=("Arial", 13, "bold"), fg="#7CFF8F", bg="#1c1c1c").pack(side="left", padx=4)
        tk.Button(row, text="+", width=3, command=lambda: variable.set(max(0, int(variable.get()) + plus_delta))).pack(side="left", padx=(4, 0))
        return wrap

    def on_show(self):
        if self.manager and self.manager.state.get("admin_authenticated"):
            self._authenticated = True
            self._show_dashboard_view()
            return
        self._show_login_view()

    def _show_login_view(self):
        self._authenticated = False
        self._set_nav_visible(False)
        self._hide_all_views()
        self._pin_buffer = ""
        self._update_pin_display()
        self.login_frame.pack(fill="both", expand=True)
        self.message_var.set("")
        polish_descendant_buttons(self)

    def _show_dashboard_view(self):
        if not self._authenticated:
            return self._show_login_view()
        self._set_nav_visible(True)
        self._hide_all_views()
        self.dashboard_frame.pack(fill="both", expand=True)
        self._refresh_dashboard()
        polish_descendant_buttons(self)

    def _show_history_view(self):
        if not self._authenticated:
            return self._show_login_view()
        self._set_nav_visible(True)
        self._hide_all_views()
        self.history_frame.pack(fill="both", expand=True)
        self._history_search()
        polish_descendant_buttons(self)

    def _show_template_view(self):
        if not self._authenticated:
            return self._show_login_view()
        self._set_nav_visible(True)
        self._hide_all_views()
        self.template_frame.pack(fill="both", expand=True)
        self._refresh_template_tools()
        polish_descendant_buttons(self)

    def _show_diagnostics_view(self):
        if not self._authenticated:
            return self._show_login_view()
        self._set_nav_visible(True)
        self._hide_all_views()
        self.diagnostics_frame.pack(fill="both", expand=True)
        self._refresh_diagnostics()
        polish_descendant_buttons(self)

    def _show_analytics_view(self):
        if not self._authenticated:
            return self._show_login_view()
        self._set_nav_visible(True)
        self._hide_all_views()
        self.analytics_frame.pack(fill="both", expand=True)
        self._refresh_analytics()
        polish_descendant_buttons(self)

    def _show_pin_change_view(self):
        if not self._authenticated:
            return self._show_login_view()
        self._set_nav_visible(True)
        self._hide_all_views()
        self.pin_change_frame.pack(fill="both", expand=True)
        self._new_pin_buffer = ""
        self._confirm_pin_buffer = ""
        self._pin_change_stage = "new"
        self._update_new_pin_displays()
        self._update_pin_change_hint()
        self.message_var.set("")
        polish_descendant_buttons(self)

    def _hide_all_views(self):
        for frame in (self.login_frame, self.dashboard_frame, self.history_frame, self.template_frame, self.diagnostics_frame, self.analytics_frame, self.pin_change_frame):
            frame.pack_forget()

    def _append_pin_digit(self, digit: str):
        if len(self._pin_buffer) < 8:
            self._pin_buffer += digit
            self._update_pin_display()

    def _pin_backspace(self):
        self._pin_buffer = self._pin_buffer[:-1]
        self._update_pin_display()

    def _pin_clear(self):
        self._pin_buffer = ""
        self._update_pin_display()

    def _update_pin_display(self):
        count = max(4, len(self._pin_buffer))
        self.pin_display.config(text=" ".join("●" if i < len(self._pin_buffer) else "○" for i in range(count)))

    def _submit_pin(self):
        try:
            if verify_admin_pin(self._pin_buffer):
                self._authenticated = True
                if self.manager:
                    self.manager.state["admin_authenticated"] = True
                record_system_event("admin_login", "Admin login uspješan.")
                self.message_var.set("")
                if self.manager:
                    target = self.manager.state.pop("admin_post_auth_target", None)
                    if target and target in self.manager.frames:
                        self.manager.show_frame(target)
                        return
                self._show_dashboard_view()
                return
            record_system_event("admin_login_failed", "Neuspješan admin login.", level="warning")
            self.message_var.set("Pogrešan PIN.")
            self._pin_clear()
        except Exception as e:
            log_error(f"[ADMIN] PIN verification failed: {e}")
            self.message_var.set("Greška pri provjeri PIN-a.")
            self._pin_clear()

    def _append_new_pin_digit(self, digit: str):
        if self._pin_change_stage == "new":
            if len(self._new_pin_buffer) < 8:
                self._new_pin_buffer += digit
        else:
            if len(self._confirm_pin_buffer) < 8:
                self._confirm_pin_buffer += digit
        self._update_new_pin_displays()

    def _new_pin_backspace(self):
        if self._pin_change_stage == "confirm":
            self._confirm_pin_buffer = self._confirm_pin_buffer[:-1]
        else:
            self._new_pin_buffer = self._new_pin_buffer[:-1]
        self._update_new_pin_displays()

    def _new_pin_clear(self):
        if self._pin_change_stage == "confirm":
            self._confirm_pin_buffer = ""
        else:
            self._new_pin_buffer = ""
        self._update_new_pin_displays()

    def _update_new_pin_displays(self):
        def mask(value: str) -> str:
            count = max(4, len(value))
            return " ".join("●" if i < len(value) else "○" for i in range(count))
        self.new_pin_display.config(text=mask(self._new_pin_buffer))
        self.confirm_pin_display.config(text=mask(self._confirm_pin_buffer))
        self._update_pin_change_hint()

    def _save_new_pin(self):
        try:
            if self._pin_change_stage == "new":
                if len(self._new_pin_buffer) < 4:
                    self.message_var.set("Novi PIN mora imati najmanje 4 cifre.")
                    return
                self._pin_change_stage = "confirm"
                self._confirm_pin_buffer = ""
                self._update_new_pin_displays()
                self.message_var.set("Ponovi isti PIN za potvrdu.")
                return
            if self._new_pin_buffer != self._confirm_pin_buffer:
                self.message_var.set("PIN potvrda se ne poklapa.")
                self._confirm_pin_buffer = ""
                self._update_new_pin_displays()
                return
            update_admin_pin(self._new_pin_buffer)
            record_system_event("admin_pin_changed", "Admin PIN promijenjen.")
            self.message_var.set("PIN uspješno promijenjen.")
            self._show_dashboard_view()
        except Exception as e:
            log_error(f"[ADMIN] Failed to update PIN: {e}")
            self.message_var.set("PIN nije sačuvan.")

    def _update_pin_change_hint(self):
        if self._pin_change_stage == "new":
            self.pin_change_hint.config(text="Korak 1/2: Unesi novi PIN pa klikni Potvrdi.")
        else:
            self.pin_change_hint.config(text="Korak 2/2: Ponovi novi PIN pa klikni Potvrdi.")

    def _adjust_counter(self, delta: int):
        self.counter_var.set(max(0, int(self.counter_var.get()) + int(delta)))
        self._update_preview()

    def _adjust_manual_year(self, delta: int):
        self.manual_year_var.set(max(2000, min(2099, int(self.manual_year_var.get()) + int(delta))))
        self._update_preview()
        self._update_year_card()

    def _toggle_year_mode(self):
        self.year_mode_var.set("manual" if self.year_mode_var.get() == "auto" else "auto")
        self._update_preview()
        self._update_year_card()

    def _update_year_card(self):
        mode = self.year_mode_var.get()
        self.year_mode_badge.config(text=mode.upper(), bg="#7CFF8F" if mode == "auto" else "#FFD166")
        self.manual_year_label.config(text=f"Manual: {self.manual_year_var.get()}")

    def _update_preview(self):
        year = self.manual_year_var.get() if self.year_mode_var.get() == "manual" else datetime.datetime.now().year
        self.preview_var.set(f"Sljedeći broj: {self.prefix_var.get()}-{int(self.counter_var.get()) + 1}/{int(year) % 100:02d}")

    def _refresh_dashboard(self):
        try:
            snapshot = get_admin_snapshot()
            network_snapshot = get_network_snapshot()
            self.prefix_var.set(str(snapshot["counter_prefix"]))
            self.prefix_label_var.set(f"Prefiks: {snapshot['counter_prefix']}")
            self.counter_var.set(int(snapshot["counter_current"]))
            self.manual_year_var.set(int(snapshot["manual_year"]))
            self.year_mode_var.set(str(snapshot["year_mode"]))
            self._update_year_card()
            self.preview_var.set(f"Sljedeći broj: {snapshot['next_document_number']}")
            self.telegram_enabled_var.set(str(get_setting("telegram_enabled", "0")) == "1")
            self.discord_enabled_var.set(str(get_setting("discord_enabled", "0")) == "1")
            self._set_entry(self.telegram_token_entry, get_setting("telegram_bot_token", "") or "")
            self._set_entry(self.telegram_chat_id_entry, get_setting("telegram_chat_id", "") or "")
            self._set_entry(self.discord_webhook_entry, get_setting("discord_webhook_url", "") or "")
            self.cleanup_keep_days_var.set(get_int_setting("cleanup_keep_days", 14))
            self.cleanup_keep_last_var.set(get_int_setting("cleanup_keep_last", 200))
            self.low_disk_threshold_var.set(get_int_setting("low_disk_threshold_mb", 512))
            last_tg_cmd = (get_setting("telegram_last_command", "") or "").strip()
            last_tg_at = (get_setting("telegram_last_command_at", "") or "").strip()
            last_tg_status = (get_setting("telegram_last_command_status", "") or "").strip()
            self.telegram_remote_var.set(f"Zadnja remote komanda: {last_tg_cmd or '-'} | {last_tg_at or 'nikad'} | status: {last_tg_status or '-'}")
            self.factory_status_var.set("Factory mode: reset setup status, binding ili konfiguraciju. Support bundle izvoz radi sa odabranog USB mounta.")
            printer_text = "Printer: spreman" if snapshot["printer_ready"] else f"Printer: problem ({snapshot['printer_code']})"
            apply_status_badge(self.printer_badge, 'OK' if snapshot['printer_ready'] else 'FAIL', text=('PRINTER OK' if snapshot['printer_ready'] else 'PRINTER PROBLEM'))
            if snapshot["printer_message"]:
                printer_text += f"\n{snapshot['printer_message']}"
            self.status_var.set(
                f"Aktivni printer: {snapshot.get('active_printer', '-')}\n"
                f"{printer_text}\n"
                f"Mreža: {network_snapshot.get('message', '-')}\n"
                f"Disk: {snapshot['disk_free_gb']} GB slobodno • {snapshot['disk_used_percent']}% zauzeto\n"
                f"Template: {snapshot.get('template_path', '-')}\n"
                f"VAR_DIR: {snapshot.get('var_dir', '-')}"
            )
            self.stats_var.set(
                f"Danas pokušaja: {snapshot['today_attempts']}\n"
                f"Danas uspješno: {snapshot['today_printed']}\n"
                f"Danas neuspješno: {snapshot['today_failed']}\n"
                f"Osvježeno: {snapshot.get('generated_at', '-')}"
            )
            self._replace_text(self.recent_docs_text, self._format_recent_documents(get_recent_documents()))
            self._replace_text(self.events_text, self._format_events(snapshot["recent_events"]))
            self._replace_text(self.summary_text, self._format_daily_summary(snapshot.get("daily_summary") or get_daily_summary(7)))
            checklist = get_setup_checklist()
            self.checklist_summary_var.set(checklist.get("summary", ""))
            self._replace_text(self.checklist_text, self._format_setup_checklist(checklist))
            self._replace_text(self.diagnostics_preview_text, self._format_printer_diagnostics(checklist.get("printer_diagnostics_preview") or {}))
            if not self.message_var.get():
                self.message_var.set(checklist.get("summary", ""))
            current_tool = self.tool_output_text.get("1.0", "end").strip()
            if not current_tool:
                self._replace_text(self.tool_output_text, format_network_snapshot(network_snapshot))
        except Exception as e:
            log_error(f"[ADMIN] Dashboard refresh failed: {e}")
            self.message_var.set("Admin dashboard nije moguće osvježiti.")

    def _set_entry(self, entry: tk.Entry, value: str):
        entry.delete(0, "end")
        entry.insert(0, value)

    def _save_settings(self):
        try:
            new_counter = set_counter_current(int(self.counter_var.get()))
            new_year_mode = set_year_mode(self.year_mode_var.get())
            new_manual_year = set_manual_year(int(self.manual_year_var.get()))
            set_bool_setting("telegram_enabled", bool(self.telegram_enabled_var.get()))
            set_bool_setting("discord_enabled", bool(self.discord_enabled_var.get()))
            set_setting("telegram_bot_token", self.telegram_token_entry.get().strip())
            set_setting("telegram_chat_id", self.telegram_chat_id_entry.get().strip())
            set_setting("discord_webhook_url", self.discord_webhook_entry.get().strip())
            set_setting("cleanup_keep_days", str(max(0, int(self.cleanup_keep_days_var.get()))))
            set_setting("cleanup_keep_last", str(max(0, int(self.cleanup_keep_last_var.get()))))
            set_setting("low_disk_threshold_mb", str(max(64, int(self.low_disk_threshold_var.get()))))
            record_system_event(
                "admin_settings_changed",
                f"Admin settings saved: counter={new_counter}, year_mode={new_year_mode}, manual_year={new_manual_year}, telegram={int(bool(self.telegram_enabled_var.get()))}, discord={int(bool(self.discord_enabled_var.get()))}",
            )
            self.message_var.set("Postavke uspješno sačuvane.")
            self._refresh_dashboard()
        except Exception as e:
            log_error(f"[ADMIN] Failed to save settings: {e}")
            self.message_var.set("Postavke nisu sačuvane.")

    def _run_in_background(self, worker, start_message: str):
        self.message_var.set(start_message)
        threading.Thread(target=worker, daemon=True).start()

    def _run_health_checks(self):
        def worker():
            try:
                result = run_startup_checks(notify_on_failure=False)
                text = self._format_health_result(result)
                self.after(0, lambda: self._replace_text(self.tool_output_text, text))
                self.after(0, lambda: self.message_var.set(result.get("summary", "Health check završen.")))
                self.after(0, self._refresh_dashboard)
            except Exception as e:
                self.after(0, lambda: self.message_var.set(f"Health check greška: {e}"))
        self._run_in_background(worker, "Pokrećem startup health check…")

    def _run_cleanup(self):
        def worker():
            try:
                result = run_cleanup()
                text = (
                    f"Cleanup završen.\n"
                    f"keep_days={result['keep_days']}\n"
                    f"keep_last={result['keep_last']}\n"
                    f"deleted_jobs={result['jobs_deleted']}\n"
                    f"free_mb={result['free_mb']}\n"
                )
                if result.get("errors"):
                    text += "Greške:\n- " + "\n- ".join(result["errors"])
                self.after(0, lambda: self._replace_text(self.tool_output_text, text))
                self.after(0, lambda: self.message_var.set("Cleanup uspješno završen."))
                self.after(0, self._refresh_dashboard)
            except Exception as e:
                self.after(0, lambda: self.message_var.set(f"Cleanup greška: {e}"))
        self._run_in_background(worker, "Pokrećem cleanup…")

    def _run_test_printer(self):
        def worker():
            result = run_test_printer()
            text = (
                f"Printer test: {'OK' if result['ok'] else 'FAIL'}\n"
                f"printer={result['printer_name']}\n"
                f"code={result['code']}\n"
                f"message={result['message']}\n"
                f"savjet={result.get('recovery_hint', '-') }\n"
            )
            if result.get('test_file'):
                text += f"test_file={result['test_file']}\n"
            self.after(0, lambda: self._replace_text(self.tool_output_text, text))
            self.after(0, lambda: self.message_var.set(result['message']))
            self.after(0, self._refresh_dashboard)
        self._run_in_background(worker, "Pokrećem test printera…")

    def _run_test_notification(self):
        def worker():
            ok, msg = send_test_notification(source="admin_panel")
            text = f"Notifikacija: {'OK' if ok else 'FAIL'}\n{msg}"
            self.after(0, lambda: self._replace_text(self.tool_output_text, text))
            self.after(0, lambda: self.message_var.set(msg))
            self.after(0, self._refresh_dashboard)
        self._run_in_background(worker, "Šaljem test notifikaciju…")

    def _run_telegram_remote_poll(self):
        def worker():
            try:
                result = process_updates_once(timeout_seconds=1)
                text = (
                    f"Telegram remote poll: {'OK' if result.get('ok') else 'FAIL'}\n"
                    f"message={result.get('message', '-')}\n"
                    f"processed={result.get('processed', 0)}\n"
                    f"replied={result.get('replied', 0)}\n"
                    f"last_update_id={result.get('last_update_id', '-')}\n"
                    "Komande: /status /health /readiness /printer /network /analytics /help"
                )
                self.after(0, lambda: self._replace_text(self.tool_output_text, text))
                self.after(0, lambda: self.message_var.set(result.get('message', 'Telegram poll završen.')))
                self.after(0, self._refresh_dashboard)
            except Exception as e:
                self.after(0, lambda: self.message_var.set(f"Telegram poll greška: {e}"))
        self._run_in_background(worker, "Provjeravam Telegram remote komande…")

    def _factory_reset_setup_status(self):
        def worker():
            try:
                result = reset_setup_status_only()
                self.after(0, lambda: self._replace_text(self.tool_output_text, result.get('message', 'Setup status resetovan.')))
                self.after(0, lambda: self.factory_status_var.set(result.get('message', 'Setup status resetovan.')))
                self.after(0, lambda: self.message_var.set(result.get('message', 'Setup status resetovan.')))
                self.after(0, self._refresh_dashboard)
            except Exception as e:
                self.after(0, lambda: self.message_var.set(f"Factory reset setup greška: {e}"))
        self._run_in_background(worker, "Resetujem setup status…")

    def _factory_clear_bindings(self):
        def worker():
            try:
                result = clear_bindings(clear_wifi=True, clear_printer=True)
                forgotten = sum(1 for r in result.get('wifi_results', []) if r.get('ok'))
                text = f"{result.get('message', 'Binding čišćenje završeno.')}\nObrisanih Wi‑Fi konekcija: {forgotten}\nAktivni printer resetovan na: {result.get('active_printer', '-')}"
                self.after(0, lambda: self._replace_text(self.tool_output_text, text))
                self.after(0, lambda: self.factory_status_var.set(result.get('message', 'Binding očišćen.')))
                self.after(0, lambda: self.message_var.set(result.get('message', 'Binding očišćen.')))
                self.after(0, self._refresh_dashboard)
            except Exception as e:
                self.after(0, lambda: self.message_var.set(f"Factory clear bindings greška: {e}"))
        self._run_in_background(worker, "Čistim Wi‑Fi/printer binding…")

    def _factory_clear_configuration(self, preserve_database: bool):
        def worker():
            try:
                result = clear_configuration(preserve_database=preserve_database)
                text = (
                    f"{result.get('message', 'Factory čišćenje završeno.')}\n"
                    f"preserve_database={int(bool(result.get('preserve_database', True)))}\n"
                    f"deleted_rows={result.get('deleted_rows', 0)}"
                )
                self.after(0, lambda: self._replace_text(self.tool_output_text, text))
                self.after(0, lambda: self.factory_status_var.set(result.get('message', 'Konfiguracija očišćena.')))
                self.after(0, lambda: self.message_var.set(result.get('message', 'Konfiguracija očišćena.')))
                self.after(0, self._refresh_dashboard)
            except Exception as e:
                self.after(0, lambda: self.message_var.set(f"Factory clear configuration greška: {e}"))
        label = "Očisti konfiguraciju + zadrži bazu" if preserve_database else "Očisti konfiguraciju + obriši evidenciju"
        self._run_in_background(worker, f"{label}…")

    def _export_support_bundle(self, mount_path: str):
        def worker():
            try:
                result = export_support_bundle_to_mount(mount_path, analytics_days=int(self.analytics_days_var.get() or 30))
                text = "\n".join([
                    result.get('message', 'Support bundle izvezen.'),
                    f"Bundle: {result.get('bundle_path', '-')}",
                    f"Log files: {len(result.get('copied_logs', []))}",
                    "Fajlovi:",
                    *[f"- {name}" for name in result.get('files', [])],
                ])
                self.after(0, lambda: self._replace_text(self.tool_output_text, text))
                self.after(0, lambda: self.template_status_var.set(result.get('message', 'Support bundle izvezen.')))
                self.after(0, lambda: self.message_var.set(result.get('message', 'Support bundle izvezen.')))
                self.after(0, self._refresh_dashboard)
            except Exception as e:
                self.after(0, lambda: self.message_var.set(f"Support bundle greška: {e}"))
        self._run_in_background(worker, "Pravim support bundle na USB…")

    def _history_search(self):
        try:
            self._history_rows = search_documents(
                query=self.history_query_var.get(),
                status=self.history_status_var.get(),
                date_from=self.history_from_var.get(),
                date_to=self.history_to_var.get(),
                limit=200,
            )
            self.results_list.delete(0, "end")
            for row in self._history_rows:
                line = (
                    f"{(row.get('created_at') or '-')[:16]} | {str(row.get('status') or '-'):11} | "
                    f"{row.get('document_number') or '-'} | {row.get('ime') or '-'}"
                )
                self.results_list.insert("end", line)
            self._replace_text(self.history_summary_text, self._format_daily_summary(get_daily_summary(14)))
            if self._history_rows:
                self.results_list.selection_clear(0, "end")
                self.results_list.selection_set(0)
                self.results_list.event_generate("<<ListboxSelect>>")
            else:
                self._replace_text(self.history_details_text, "Nema rezultata za aktivne filtere.")
            self.message_var.set(f"Pronađeno: {len(self._history_rows)} zapisa.")
        except Exception as e:
            log_error(f"[ADMIN] History search failed: {e}")
            self.message_var.set(f"Historija nije dostupna: {e}")

    def _history_export(self):
        try:
            out_path = export_documents_csv(
                query=self.history_query_var.get(),
                status=self.history_status_var.get(),
                date_from=self.history_from_var.get(),
                date_to=self.history_to_var.get(),
                limit=2000,
            )
            self.message_var.set(f"CSV export spremljen: {out_path}")
            record_system_event("admin_export", f"CSV export created: {out_path}")
        except Exception as e:
            log_error(f"[ADMIN] CSV export failed: {e}")
            self.message_var.set(f"CSV export nije uspio: {e}")

    def _on_history_select(self, event=None):
        try:
            selection = self.results_list.curselection()
            if not selection:
                return
            row = self._history_rows[int(selection[0])]
            attempts = get_document_attempts(str(row.get("job_id") or ""))
            self._replace_text(self.history_details_text, self._format_history_details(row, attempts))
        except Exception as e:
            log_error(f"[ADMIN] History detail failed: {e}")
            self._replace_text(self.history_details_text, f"Detalji nisu dostupni: {e}")

    def _apply_preset(self, preset: str):
        today = datetime.date.today()
        if preset == "today":
            day = today.strftime("%Y-%m-%d")
            self.history_from_var.set(day)
            self.history_to_var.set(day)
            self.history_status_var.set("all")
        elif preset == "week":
            start = (today - datetime.timedelta(days=6)).strftime("%Y-%m-%d")
            self.history_from_var.set(start)
            self.history_to_var.set(today.strftime("%Y-%m-%d"))
            self.history_status_var.set("all")
        elif preset == "failed":
            self.history_status_var.set("failed")
            self.history_from_var.set("")
            self.history_to_var.set("")
        self._history_search()

    def _clear_history_filters(self):
        self.history_query_var.set("")
        self.history_status_var.set("all")
        self.history_from_var.set("")
        self.history_to_var.set("")
        self._history_search()

    def _replace_text(self, widget: tk.Text, value: str):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.config(state="disabled")

    def _format_health_result(self, result: dict) -> str:
        rows = result.get("checks", [])
        if not rows:
            return "Nema rezultata."
        return "\n\n".join(
            f"[{'OK ' if row.get('ok') else 'ERR'}] {row.get('name')}: {row.get('code')}\n  {row.get('message')}"
            for row in rows
        )

    def _format_recent_documents(self, rows: list[dict]) -> str:
        if not rows:
            return "Nema dokumenata."
        return "\n\n".join(
            f"{str(row.get('created_at', '-'))[:16]} | {str(row.get('status', '-')):10} | {row.get('document_number', '-')}\n  {row.get('ime', '-')}"
            for row in rows
        )

    def _format_events(self, rows: list[dict]) -> str:
        if not rows:
            return "Nema događaja."
        return "\n\n".join(
            f"{str(row.get('created_at', '-'))[:16]} | {str(row.get('level', '-')):7} | {row.get('event_type', '-')}\n  {row.get('message', '-')}"
            for row in rows
        )

    def _format_daily_summary(self, rows: list[dict]) -> str:
        if not rows:
            return "Nema podataka."
        lines = []
        for row in rows:
            lines.append(
                f"{row.get('day', '-')}: docs={int(row.get('total_documents') or 0)} | "
                f"printed={int(row.get('printed_documents') or 0)} | failed={int(row.get('failed_documents') or 0)} | "
                f"attempts={int(row.get('total_attempts') or 0)}"
            )
        return "\n".join(lines)

    def _format_history_details(self, row: dict, attempts: list[dict]) -> str:
        lines = [
            f"Broj: {row.get('document_number', '-')}",
            f"Job ID: {row.get('job_id', '-')}",
            f"Status: {row.get('status', '-')}",
            f"Učenik: {row.get('ime', '-')}",
            f"Roditelj: {row.get('roditelj', '-')}",
            f"Razred: {row.get('razred', '-')}",
            f"Struka: {row.get('struka', '-')}",
            f"Razlog: {row.get('razlog', '-')}",
            f"Kreirano: {row.get('created_at', '-')}",
            f"Štampano: {row.get('printed_at', '-')}",
            f"Greška: {row.get('last_error_code', '-') or '-'} / {row.get('last_error_message', '-') or '-'}",
            "",
            "Pokušaji:",
        ]
        if not attempts:
            lines.append("- nema attemptova")
        else:
            for att in attempts:
                lines.append(
                    f"- #{att.get('attempt_no', '-')} | {att.get('status', '-')} | {str(att.get('started_at', '-'))[:19]} -> {str(att.get('finished_at', '-'))[:19]}"
                )
                if att.get("error_code") or att.get("error_message"):
                    lines.append(f"    error={att.get('error_code', '-')}: {att.get('error_message', '-')}")
                if att.get("pdf_path"):
                    lines.append(f"    pdf={att.get('pdf_path')}")
        return "\n".join(lines)

    def _format_setup_checklist(self, payload: dict) -> str:
        lines = [payload.get("summary", "Setup checklist nije dostupan."), ""]
        for item in payload.get("items", []):
            icon = "OK" if item.get("ok") else "TODO"
            lines.append(f"[{icon}] {item.get('label', '-')} — {item.get('detail', '-')}")
        if payload.get("missing"):
            lines.append("")
            lines.append("Nedostaje: " + ", ".join(payload.get("missing") or []))
        return "\n".join(lines)

    def _format_printer_diagnostics(self, payload: dict) -> str:
        if not payload:
            return "Printer dijagnostika nije dostupna."
        lines = [
            f"Printer: {payload.get('printer_name', '-')}",
            f"Aktivni queue: {payload.get('active_printer', '-')}",
            f"Stanje: {'SPREMAN' if payload.get('ready') else 'PROBLEM'} | kod={payload.get('code', '-')}",
            f"Poruka: {payload.get('message', '-') or '-'}",
            f"Zadnji test: {payload.get('last_tested_at', '-') or '-'} | printer: {payload.get('last_tested_printer', '-') or '-'}",
            "",
            "Recovery hintovi:",
        ]
        for hint in payload.get('hints', []) or []:
            lines.append(f"- {hint}")
        return "\n".join(lines)

    def _refresh_analytics(self):
        try:
            snapshot = get_analytics_snapshot(int(self.analytics_days_var.get() or 30))
            summary = snapshot.get("summary") or {}
            apply_status_badge(self.analytics_badge_docs, "OK", text=f"DOCS {summary.get('total_documents', 0)}")
            success_role = "OK" if snapshot.get("success_rate", 0) >= 90 else ("WARN" if snapshot.get("success_rate", 0) >= 70 else "FAIL")
            retry_role = "OK" if snapshot.get("retry_rate", 0) <= 10 else ("WARN" if snapshot.get("retry_rate", 0) <= 25 else "FAIL")
            speed_role = "OK" if summary.get("avg_seconds_to_print", 0) <= 45 else ("WARN" if summary.get("avg_seconds_to_print", 0) <= 90 else "FAIL")
            apply_status_badge(self.analytics_badge_success, success_role, text=f"SUCCESS {snapshot.get('success_rate', 0)}%")
            apply_status_badge(self.analytics_badge_retry, retry_role, text=f"RETRY {snapshot.get('retry_rate', 0)}%")
            apply_status_badge(self.analytics_badge_speed, speed_role, text=f"AVG {summary.get('avg_seconds_to_print', 0)}s")
            self._replace_text(self.analytics_summary_text, format_analytics_snapshot(snapshot))
            self._replace_text(self.analytics_daily_text, self._format_analytics_daily(snapshot.get("daily") or []))
            self._replace_text(self.analytics_errors_text, self._format_top_errors(snapshot.get("top_errors") or []))
            self._replace_text(self.analytics_retry_text, self._format_retry_distribution(snapshot))
            self.message_var.set(f"Analytics osvježen za zadnjih {snapshot.get('days', '-') } dana.")
        except Exception as e:
            log_error(f"[ADMIN] Analytics refresh failed: {e}")
            self.message_var.set("Analytics nije moguće osvježiti.")

    def _format_analytics_daily(self, rows: list[dict]) -> str:
        if not rows:
            return "Nema dnevnih podataka za izabrani period."
        lines = []
        for row in rows:
            lines.append(
                f"{row.get('day', '-')} | docs={row.get('documents', 0)} | ok={row.get('printed', 0)} | fail={row.get('failed', 0)} | retry_docs={row.get('retry_documents', 0)} | avg={row.get('avg_seconds_to_print', 0) or 0}s"
            )
        return "\n".join(lines)

    def _format_top_errors(self, rows: list[dict]) -> str:
        if not rows:
            return "Nema zabilježenih grešaka u izabranom periodu."
        lines = []
        for row in rows:
            msg = str(row.get('error_message', '-') or '-').strip().replace('\n', ' ')
            if len(msg) > 120:
                msg = msg[:117] + '...'
            lines.append(f"[{row.get('hits', 0)}x] {row.get('error_code', 'UNKNOWN')} — {msg}")
        return "\n".join(lines)

    def _format_retry_distribution(self, snapshot: dict) -> str:
        buckets = snapshot.get("retry_buckets") or {}
        lines = [
            f"1 attempt: {buckets.get('one_attempt', 0) or 0}",
            f"2 attempta: {buckets.get('two_attempts', 0) or 0}",
            f"3+ attempta: {buckets.get('three_plus_attempts', 0) or 0}",
            "",
            "Preporuke:",
        ]
        recs = snapshot.get("recommendations") or []
        lines.extend(f"- {item}" for item in recs)
        return "\n".join(lines)

    def _refresh_template_tools(self):
        self.active_template_var.set(get_active_template_path())
        self._template_refresh_usb()

    def _open_network_screen(self):
        if self.manager:
            self.manager.state["network_return_screen"] = screen_ids.ADMIN
            self.manager.show_frame(screen_ids.NETWORK)

    def _open_general_settings(self):
        if self.manager:
            self.manager.show_frame(screen_ids.SETTINGS)

    def _open_readiness_screen(self):
        if self.manager:
            self.manager.state["readiness_return_screen"] = screen_ids.ADMIN
            self.manager.show_frame(screen_ids.READINESS)

    def _open_recovery_screen(self):
        if self.manager:
            self.manager.state["recovery_return_screen"] = screen_ids.ADMIN
            self.manager.show_frame(screen_ids.RECOVERY)

    def _open_setup_template_step(self):
        if self.manager:
            self.manager.state["setup_start_step"] = 3
            self.manager.show_frame(screen_ids.SETUP)

    def _open_setup_printer_step(self):
        if self.manager:
            self.manager.state["setup_start_step"] = 2
            self.manager.show_frame(screen_ids.SETUP)

    def _template_use_default(self):
        try:
            result = use_default_template()
            self.active_template_var.set(result.get("active_template_path", get_active_template_path()))
            self.template_status_var.set(result.get("message", "Default template aktiviran."))
            self.message_var.set(self.template_status_var.get())
        except Exception as e:
            self.template_status_var.set(f"Greška: {e}")
            self.message_var.set(self.template_status_var.get())

    def _template_refresh_usb(self):
        self._usb_mounts = list_usb_mounts()
        self._docx_candidates = []
        self._backup_candidates = []
        self._selected_usb_path = ""
        for child in self.template_mounts_inner.winfo_children():
            child.destroy()
        for child in self.template_files_inner.winfo_children():
            child.destroy()
        if not self._usb_mounts:
            tk.Label(self.template_mounts_inner, text="Nijedan USB mount nije pronađen.", font=("Arial", 13), fg="#ffcc66", bg="#1c1c1c").pack(anchor="w", pady=8)
            self.template_status_var.set("Priključi USB pa klikni Osvježi USB.")
            return
        for mount in self._usb_mounts:
            self._build_usb_mount_card(self.template_mounts_inner, mount)
        self.template_status_var.set(f"Pronađeno USB mountova: {len(self._usb_mounts)}")
        if len(self._usb_mounts) == 1:
            self._template_select_mount(self._usb_mounts[0]["path"])

    def _build_usb_mount_card(self, parent, mount: dict):
        box = tk.Frame(parent, bg="#101010", bd=1, relief="solid", padx=10, pady=10)
        box.pack(fill="x", pady=6)
        title = mount.get("label") or mount.get("path")
        if self._selected_usb_path == mount.get("path"):
            title += "   [ODABRAN]"
        tk.Label(box, text=title, font=("Arial", 14, "bold"), fg="white", bg="#101010").pack(anchor="w")
        info = f"{mount.get('path')}"
        if mount.get("free_gb") is not None:
            info += f"\nSlobodno: {mount.get('free_gb')} GB"
        tk.Label(box, text=info, font=("Arial", 11), fg="#dddddd", bg="#101010", justify="left", wraplength=400).pack(anchor="w", pady=(6, 8))
        actions = tk.Frame(box, bg="#101010")
        actions.pack(anchor="w")
        tk.Button(actions, text="DOCX fajlovi", command=lambda p=mount.get("path"): self._template_select_mount(p), font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Backup na ovaj USB", command=lambda p=mount.get("path"): self._backup_to_usb(p), font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Support bundle", command=lambda p=mount.get("path"): self._export_support_bundle(p), font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left")

    def _template_select_mount(self, mount_path: str):
        self._selected_usb_path = mount_path
        self._docx_candidates = list_docx_candidates(mount_path)
        self._backup_candidates = list_backup_bundles(mount_path)
        for child in self.template_mounts_inner.winfo_children():
            child.destroy()
        for mount in self._usb_mounts:
            self._build_usb_mount_card(self.template_mounts_inner, mount)
        for child in self.template_files_inner.winfo_children():
            child.destroy()

        if self._docx_candidates:
            tk.Label(self.template_files_inner, text="DOCX template fajlovi", font=("Arial", 14, "bold"), fg="white", bg="#1c1c1c").pack(anchor="w", pady=(4, 6), padx=4)
            for row in self._docx_candidates:
                self._build_docx_template_card(self.template_files_inner, row)

        if self._backup_candidates:
            tk.Label(self.template_files_inner, text="Backup bundle-ovi", font=("Arial", 14, "bold"), fg="white", bg="#1c1c1c").pack(anchor="w", pady=(14, 6), padx=4)
            for row in self._backup_candidates:
                self._build_backup_bundle_card(self.template_files_inner, row)

        if not self._docx_candidates and not self._backup_candidates:
            tk.Label(self.template_files_inner, text="Na odabranom USB-u nema .docx fajlova ni backup bundle-ova.", font=("Arial", 13), fg="#ffcc66", bg="#1c1c1c").pack(anchor="w", pady=8)
            self.template_status_var.set("Na USB-u nema template-a ni backup bundle-a za restore.")
            return

        self.template_status_var.set(
            f"USB sadrži {len(self._docx_candidates)} DOCX fajlova i {len(self._backup_candidates)} backup bundle-ova."
        )

    def _build_docx_template_card(self, parent, row: dict):
        box = tk.Frame(parent, bg="#101010", bd=1, relief="solid", padx=10, pady=10)
        box.pack(fill="x", pady=6)
        tk.Label(box, text=row.get("name", "-"), font=("Arial", 14, "bold"), fg="white", bg="#101010").pack(anchor="w")
        info = f"{row.get('size_kb', 0)} KB | {row.get('modified_at', '-')}\n{row.get('path', '-')}"
        tk.Label(box, text=info, font=("Arial", 11), fg="#dddddd", bg="#101010", justify="left", wraplength=800).pack(anchor="w", pady=(6, 8))
        actions = tk.Frame(box, bg="#101010")
        actions.pack(anchor="w")
        tk.Button(actions, text="Provjeri template", command=lambda p=row.get("path"): self._validate_template_candidate(p), font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Uvezi i postavi aktivni", command=lambda p=row.get("path"): self._import_template_from_usb(p), font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left")

    def _build_backup_bundle_card(self, parent, row: dict):
        box = tk.Frame(parent, bg="#101010", bd=1, relief="solid", padx=10, pady=10)
        box.pack(fill="x", pady=6)
        tk.Label(box, text=row.get("name", "backup"), font=("Arial", 14, "bold"), fg="white", bg="#101010").pack(anchor="w")
        info = (
            f"Kreirano: {row.get('created_at', '-')}\n"
            f"Template: {row.get('template_name', '-') or '-'} | settings: {row.get('settings_count', 0)} | baza: {'DA' if row.get('has_db') else 'NE'}\n"
            f"{row.get('bundle_path', '-')}"
        )
        tk.Label(box, text=info, font=("Arial", 11), fg="#dddddd", bg="#101010", justify="left", wraplength=800).pack(anchor="w", pady=(6, 8))
        actions = tk.Frame(box, bg="#101010")
        actions.pack(anchor="w")
        tk.Button(actions, text="Vrati samo postavke", command=lambda p=row.get("bundle_path"): self._restore_backup_bundle(p, mode="settings"), font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Vrati samo template", command=lambda p=row.get("bundle_path"): self._restore_backup_bundle(p, mode="template"), font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Vrati postavke + template", command=lambda p=row.get("bundle_path"): self._restore_backup_bundle(p, mode="both"), font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left")

    def _validate_template_candidate(self, source_path: str):
        try:
            report = validate_template_file(source_path, run_probe_render=True)
            self.template_status_var.set('Template je validan.' if report.get('ok') else 'Template validacija nije prošla.')
            self.message_var.set(self.template_status_var.get())
            self._replace_text(self.tool_output_text, format_validation_report(report))
        except Exception as e:
            self.template_status_var.set(f"Template validacija nije uspjela: {e}")
            self.message_var.set(self.template_status_var.get())

    def _validate_active_template(self):
        self._validate_template_candidate(get_active_template_path())

    def _import_template_from_usb(self, source_path: str):
        try:
            result = import_template_from_path(source_path)
            self.active_template_var.set(result.get("active_template_path", get_active_template_path()))
            self.template_status_var.set(result.get("message", "Template uvezen."))
            self.message_var.set(self.template_status_var.get())
            if result.get('validation_report'):
                self._replace_text(self.tool_output_text, result.get('validation_report'))
        except Exception as e:
            self.template_status_var.set(f"Import nije uspio: {e}")
            self.message_var.set(self.template_status_var.get())

    def _backup_to_usb(self, mount_path: str):
        try:
            result = export_backup_to_mount(mount_path)
            self.template_status_var.set(result.get("message", "Backup izvezen."))
            self.message_var.set(self.template_status_var.get())
            self._replace_text(self.tool_output_text, "\n".join([result.get("message", "")] + [f"- {name}" for name in result.get("copied_files", [])]))
        except Exception as e:
            self.template_status_var.set(f"Backup nije uspio: {e}")
            self.message_var.set(self.template_status_var.get())

    def _restore_backup_bundle(self, bundle_path: str, mode: str = "both"):
        try:
            restore_settings = mode in {"settings", "both"}
            restore_template = mode in {"template", "both"}
            result = restore_backup_bundle(bundle_path, restore_settings=restore_settings, restore_template=restore_template)
            template_info = result.get("template_result") or {}
            self.active_template_var.set(get_active_template_path())
            self.template_status_var.set(result.get("message", "Backup vraćen."))
            details = [
                result.get("message", ""),
                f"Restored settings: {result.get('restored_settings_count', 0)}",
            ]
            if template_info.get("active_template_path"):
                details.append(f"Template: {template_info.get('active_template_path')}")
            self.message_var.set(self.template_status_var.get())
            self._replace_text(self.tool_output_text, "\n".join(details))
            self._refresh_dashboard()
            self._template_refresh_usb()
        except Exception as e:
            self.template_status_var.set(f"Restore nije uspio: {e}")
            self.message_var.set(self.template_status_var.get())

    def _go_home(self):
        if self.manager:
            self._authenticated = False
            self.manager.state.pop("admin_authenticated", None)
            self.manager.clear_state()
            self.manager.show_frame(screen_ids.START)
