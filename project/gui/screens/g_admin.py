from __future__ import annotations

import threading
import tkinter as tk

from project.core.admin_auth import AdminLoginGuard, toggled_secret_mask
from project.core.school_year import current_school_year
from project.gui import screen_ids
from project.gui.ui_components import TouchButton, paginate_values
from project.gui.virtual_keyboard import VirtualKeyboard
from project.services.app_control import launch_replacement_app
from project.services.self_test import format_self_test_report, run_self_test
from project.services.telegram_notify import notify_telegram_async
from project.services.storage_cleanup import collect_storage_report, format_bytes
from project.core.runtime_settings import clear_selected_printer, get_selected_printer, set_selected_printer
from project.utils.network_status import collect_network_diagnostics, connect_wifi, scan_wifi_networks
from project.utils.printing.printer_status import collect_printer_diagnostics, list_configured_printers, set_cups_default_printer


def notify_admin_self_test_failure(report) -> bool:
    if report.ok:
        return False
    notify_telegram_async(format_self_test_report(report), kind="error")
    return True


class AdminScreen(tk.Frame):
    LOCKOUT_AFTER = 5
    LOCKOUT_SECONDS = 60

    def __init__(self, parent, manager=None):
        super().__init__(parent, bg="#0b1f33")
        self.manager = manager
        self.password_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self._authenticated = False
        self._login_guard = AdminLoginGuard(self.LOCKOUT_AFTER, self.LOCKOUT_SECONDS)
        self._busy = False
        self._view: tk.Widget | None = None
        self._show_login()

    def _clear(self):
        if self._view is not None:
            self._view.destroy()
        self._view = tk.Frame(self, bg="#0b1f33")
        self._view.pack(fill="both", expand=True)
        return self._view

    def _button(self, parent, text, command, *, danger=False, width=20):
        return TouchButton(
            parent, text=text, command=command, width=width, padx=12, pady=10,
            font=("Arial", 16, "bold"), bg="#a51d2d" if danger else "#183b5b",
            fg="white", activebackground="#bd2b3d" if danger else "#24577f",
            activeforeground="white",
        )

    def on_show(self):
        if self.manager:
            self.manager.set_idle_suspended(False)
        self._authenticated = False
        self.password_var.set("")
        self.status_var.set("")
        self._show_login()

    def on_idle_timeout(self):
        self._go_back()

    def on_hide(self):
        self._authenticated = False
        self.password_var.set("")

    def _show_login(self):
        root = self._clear()
        card = tk.Frame(root, bg="#f4f6f8", padx=34, pady=22, highlightthickness=2, highlightbackground="#94a3b8")
        card.pack(fill="both", expand=True, padx=45, pady=30)
        tk.Label(card, text="АДМИНИСТРАТОРСКИ ПРИСТУП", font=("Arial", 26, "bold"), bg="#f4f6f8", fg="#0b1f33").pack(pady=(0, 8))
        tk.Label(card, text="Овлашћено особље", font=("Arial", 15), bg="#f4f6f8", fg="#526273").pack()
        entry = tk.Entry(card, textvariable=self.password_var, show="●", font=("Arial", 22), justify="center", bd=2, relief="solid")
        entry.field_key = "admin_password"
        entry.pack(fill="x", padx=150, pady=(16, 8), ipady=8)
        controls = tk.Frame(card, bg="#f4f6f8")
        controls.pack()

        def toggle():
            entry.config(show=toggled_secret_mask(str(entry.cget("show"))))
            show_btn.config(text="ПРИКАЖИ/САКРИЈ")

        show_btn = self._button(controls, "ПРИКАЖИ/САКРИЈ", toggle, width=18)
        show_btn.pack(side="left", padx=5)
        self._button(controls, "УЛАЗ", self._login, width=12).pack(side="left", padx=5)
        self._button(controls, "ОДУСТАНИ", self._go_back, danger=True, width=12).pack(side="left", padx=5)
        tk.Label(card, textvariable=self.status_var, font=("Arial", 14, "bold"), bg="#f4f6f8", fg="#a51d2d").pack(pady=6)
        keyboard = VirtualKeyboard(card, bg="#f4f6f8", ui_scale=getattr(self.manager, "ui_scale", 1), target_height=255, alphabet="latin")
        keyboard.pack(fill="both", expand=True)
        keyboard.bind_entry(entry, mode="alpha", uppercase_first=False, one_word=True)
        keyboard.set_active_entry(entry)
        entry.focus_set()

    def _login(self):
        result = self._login_guard.attempt(self.password_var.get())
        self.password_var.set("")
        if result.lock_seconds:
            self.status_var.set(f"Приступ је закључан. Покушајте поново за {result.lock_seconds} секунди.")
            return
        if result.authenticated:
            self._authenticated = True
            self._show_dashboard()
            return
        self.status_var.set(f"Погрешна лозинка. Преостало покушаја: {result.remaining_attempts}.")

    def _show_dashboard(self):
        if not self._authenticated:
            self._show_login()
            return
        root = self._clear()
        header = tk.Frame(root, bg="#0b1f33")
        header.pack(fill="x", padx=30, pady=(20, 10))
        tk.Label(header, text="АДМИНИСТРАЦИЈА ТЕРМИНАЛА", font=("Arial", 26, "bold"), bg="#0b1f33", fg="white").pack(side="left")
        self._button(header, "ИЗЛАЗ ИЗ АДМИНА", self._go_back, danger=True, width=18).pack(side="right")
        self.status_var.set("Изаберите административну функцију.")
        tk.Label(root, textvariable=self.status_var, font=("Arial", 14), bg="#0b1f33", fg="#dbeafe", wraplength=1050, justify="center").pack(pady=6)
        grid = tk.Frame(root, bg="#0b1f33")
        grid.pack(expand=True)
        actions = [
            ("СТАТУС СИСТЕМА", self._load_status, False),
            ("WI-FI МРЕЖА", self._show_wifi, False),
            ("SELF-TEST БЕЗ ШТАМПЕ", self._run_self_test, False),
            ("ИЗБОР ШТАМПАЧА", self._show_printers, False),
            ("ПОНОВО ПОКРЕНИ АПЛИКАЦИЈУ", self._confirm_restart, False),
            ("САКРИЈ КИОСК", self._hide_kiosk, False),
            ("ПОТПУНО УГАСИ АПЛИКАЦИЈУ", self._confirm_shutdown, True),
        ]
        for index, (label, command, danger) in enumerate(actions):
            self._button(grid, label, command, danger=danger, width=30).grid(row=index // 2, column=index % 2, padx=12, pady=10, sticky="nsew")

    def _worker(self, name, target, done):
        if self._busy:
            self.status_var.set("Сачекајте да се тренутна операција заврши.")
            return
        self._busy = True
        self.status_var.set(f"{name} — у току…")

        def run():
            try:
                result = target()
            except Exception as exc:
                result = exc
            self.manager.post_ui_action(lambda: self._finish_worker(result, done))

        threading.Thread(target=run, name=f"admin-{name}", daemon=True).start()

    def _finish_worker(self, result, done):
        self._busy = False
        if isinstance(result, Exception):
            self.status_var.set(f"Операција није успјела: {result}")
            notify_telegram_async(f"Admin operation failed: {result}", kind="error")
            return
        done(result)

    def _load_status(self):
        def collect():
            return (
                collect_network_diagnostics(),
                collect_printer_diagnostics(get_selected_printer()),
                collect_storage_report(),
                current_school_year(),
            )
        def done(result):
            self._render_status(result)
        self._worker("Провјера статуса", collect, done)

    def _render_status(self, result):
        network, printer, storage, year = result
        root = self._clear()
        tk.Label(root, text="СТАТУС СИСТЕМА", font=("Arial", 26, "bold"), bg="#0b1f33", fg="white").pack(pady=(18, 10))
        cards = tk.Frame(root, bg="#0b1f33")
        cards.pack(fill="both", expand=True, padx=45)
        app_disk = storage.get("app_data")
        free_space = "непознато"
        if app_disk is not None and not app_disk.error:
            free_space = format_bytes(app_disk.free)
        rows = [
            ("WI-FI", str(network.get("ssid") or "није повезан"), bool(network.get("ssid"))),
            ("СИГНАЛ", f"{network.get('signal', 0)}%" if network.get("signal") is not None else "непознат", bool(network.get("signal"))),
            ("ИНТЕРНЕТ", "ДОСТУПАН" if network.get("internet") else "НИЈЕ ДОСТУПАН", bool(network.get("internet"))),
            ("IP АДРЕСА", str(network.get("ip") or "нема"), bool(network.get("ip"))),
            ("ШТАМПАЧ", str(printer.get("resolved") or "није изабран"), bool(printer.get("ready"))),
            ("СЛОБОДАН ПРОСТОР", free_space, app_disk is not None and not app_disk.error),
            ("ШКОЛСКА ГОДИНА", year, True),
        ]
        for index, (label, value, ok) in enumerate(rows):
            card = tk.Frame(cards, bg="white", padx=18, pady=14, highlightthickness=2, highlightbackground="#22a06b" if ok else "#d14343")
            card.grid(row=index // 2, column=index % 2, padx=8, pady=8, sticky="nsew")
            tk.Label(card, text=label, font=("Arial", 13, "bold"), bg="white", fg="#526273").pack(anchor="w")
            tk.Label(card, text=value, font=("Arial", 18, "bold"), bg="white", fg="#16845b" if ok else "#b42318", wraplength=420).pack(anchor="w")
        cards.grid_columnconfigure(0, weight=1)
        cards.grid_columnconfigure(1, weight=1)
        controls = tk.Frame(root, bg="#0b1f33")
        controls.pack(pady=14)
        self._button(controls, "ОСВЈЕЖИ", self._load_status, width=16).pack(side="left", padx=7)
        self._button(controls, "НАЗАД", self._show_dashboard, danger=True, width=16).pack(side="left", padx=7)

    def _run_self_test(self):
        def done(report):
            self.status_var.set("Self-test је успјешан; папир није штампан." if report.ok else "Self-test је пронашао грешку; извјештај је послан на Telegram.")
            notify_admin_self_test_failure(report)
        self._worker("Self-test", run_self_test, done)

    def _show_wifi(self):
        self._worker("Претрага Wi-Fi мрежа", scan_wifi_networks, self._render_wifi)

    def _render_wifi(self, result, page=0):
        items, error = result
        root = self._clear()
        tk.Label(root, text="WI-FI МРЕЖА", font=("Arial", 26, "bold"), bg="#0b1f33", fg="white").pack(pady=(18, 8))
        self.status_var.set(error or "Изаберите мрежу или унесите скривени SSID.")
        tk.Label(root, textvariable=self.status_var, font=("Arial", 14), bg="#0b1f33", fg="#dbeafe").pack()
        form = tk.Frame(root, bg="#f4f6f8", padx=25, pady=14)
        form.pack(fill="both", expand=True, padx=35, pady=12)
        ssid_var, wifi_password = tk.StringVar(), tk.StringVar()
        networks = tk.Frame(form, bg="#f4f6f8")
        networks.pack(fill="x")
        visible, page, page_count = paginate_values(items, page, 6)
        for index, item in enumerate(visible):
            security = "отворена" if not item["security"] or item["security"] == "--" else "заштићена"
            label = f"{'● ' if item['active'] else ''}{item['ssid']}  ({item['signal']}%, {security})"
            self._button(networks, label, lambda value=item["ssid"]: ssid_var.set(value), width=24).grid(
                row=index // 2, column=index % 2, padx=4, pady=4, sticky="ew"
            )
        networks.grid_columnconfigure(0, weight=1)
        networks.grid_columnconfigure(1, weight=1)
        if page_count > 1:
            page_controls = tk.Frame(form, bg="#f4f6f8")
            page_controls.pack(fill="x", pady=(2, 5))
            self._button(page_controls, "ПРЕТХОДНО", lambda: self._render_wifi((items, error), page - 1), width=15).pack(side="left")
            tk.Label(page_controls, text=f"Страница {page + 1}/{page_count}", bg="#f4f6f8", font=("Arial", 13, "bold")).pack(side="left", expand=True)
            self._button(page_controls, "СЉЕДЕЋЕ", lambda: self._render_wifi((items, error), page + 1), width=15).pack(side="right")
        tk.Label(form, text="Назив мреже (SSID)", bg="#f4f6f8", font=("Arial", 13, "bold")).pack()
        ssid_entry = tk.Entry(form, textvariable=ssid_var, font=("Arial", 18), justify="center")
        ssid_entry.field_key = "wifi_ssid"
        ssid_entry.pack(fill="x", padx=140, ipady=5)
        tk.Label(form, text="Лозинка мреже", bg="#f4f6f8", font=("Arial", 13, "bold")).pack(pady=(7, 0))
        pass_entry = tk.Entry(form, textvariable=wifi_password, show="●", font=("Arial", 18), justify="center")
        pass_entry.field_key = "wifi_password"
        pass_entry.pack(fill="x", padx=140, ipady=5)
        controls = tk.Frame(form, bg="#f4f6f8")
        controls.pack(pady=7)
        self._button(controls, "ПРИКАЖИ/САКРИЈ", lambda: pass_entry.config(show="" if pass_entry.cget("show") else "●"), width=17).pack(side="left", padx=4)
        connect_button = self._button(controls, "ПОВЕЖИ", lambda: self._connect_wifi(ssid_var.get(), wifi_password.get()), width=12)
        connect_button.pack(side="left", padx=4)
        if error and "nmcli" in error.lower():
            connect_button.config(state="disabled", bg="#7b8794", fg="#d0d5dd")
        self._button(controls, "НАЗАД", self._show_dashboard, danger=True, width=12).pack(side="left", padx=4)
        keyboard = VirtualKeyboard(form, bg="#f4f6f8", ui_scale=getattr(self.manager, "ui_scale", 1), target_height=210, alphabet="latin")
        keyboard.pack(fill="both", expand=True)
        for entry in (ssid_entry, pass_entry):
            keyboard.bind_entry(entry, mode="alpha", uppercase_first=False, allow_numeric=True)
        keyboard.set_active_entry(ssid_entry)

        def toggle_keyboard_mode():
            active = keyboard.active_entry if keyboard.active_entry in (ssid_entry, pass_entry) else pass_entry
            new_mode = "numeric" if keyboard.mode == "alpha" else "alpha"
            active._vk_mode = new_mode
            keyboard.set_active_entry(active)
            mode_button.config(text="СЛОВА" if new_mode == "numeric" else "БРОЈЕВИ")

        mode_button = self._button(controls, "БРОЈЕВИ", toggle_keyboard_mode, width=12)
        mode_button.pack(side="left", padx=4)

    def _connect_wifi(self, ssid, password):
        self._worker("Повезивање на Wi-Fi", lambda: connect_wifi(ssid, password), lambda result: self.status_var.set("Wi-Fi је повезан." if result[0] else f"Wi-Fi није повезан: {result[1]}"))

    def _show_printers(self):
        self._worker("Учитавање штампача", list_configured_printers, self._render_printers)

    def _render_printers(self, result):
        printers, default, code, message = result
        root = self._clear()
        tk.Label(root, text="ИЗБОР ШТАМПАЧА", font=("Arial", 26, "bold"), bg="#0b1f33", fg="white").pack(pady=25)
        tk.Label(root, text=f"Тренутни: {get_selected_printer() or default or 'CUPS подразумјевани'}", font=("Arial", 16), bg="#0b1f33", fg="#dbeafe").pack()
        if code != "OK":
            tk.Label(root, text=message, font=("Arial", 15), bg="#0b1f33", fg="#fecaca").pack(pady=10)
        for printer in printers:
            self._button(root, printer, lambda value=printer: self._select_printer(value), width=34).pack(pady=7)
        self._button(root, "КОРИСТИ CUPS ПОДРАЗУМЈЕВАНИ", self._use_default_printer, width=34).pack(pady=7)
        self._button(root, "НАЗАД", self._show_dashboard, danger=True, width=18).pack(pady=15)

    def _select_printer(self, name):
        def choose():
            ok, code, detail = set_cups_default_printer(name)
            if ok:
                set_selected_printer(name)
            return ok, code, detail
        self._worker("Промјена штампача", choose, lambda result: self.status_var.set("Штампач је изабран." if result[0] else f"{result[1]}: {result[2]}"))

    def _use_default_printer(self):
        clear_selected_printer()
        self.status_var.set("Апликација сада користи CUPS подразумјевани штампач.")

    def _restart_app(self):
        def done(result):
            ok, message = result
            self.status_var.set(message)
            if ok:
                self.after(800, self.manager.shutdown)
        self._worker("Поновно покретање", launch_replacement_app, done)

    def _confirm_restart(self):
        self._show_confirmation(
            "ПОТВРДА ПОНОВНОГ ПОКРЕТАЊА",
            "Нова инстанца ће бити провјерена прије гашења тренутне апликације.",
            "ПОНОВО ПОКРЕНИ",
            self._restart_app,
        )

    def _hide_kiosk(self):
        self.manager.hide_kiosk_window()

    def _shutdown(self):
        self.manager.shutdown()

    def _confirm_shutdown(self):
        self._show_confirmation(
            "ПОТВРДА ГАШЕЊА",
            "Апликација и Telegram контрола ће бити потпуно угашени.\nПоновно покретање ће бити потребно на уређају.",
            "УГАСИ",
            self._shutdown,
        )

    def _show_confirmation(self, title, message, confirm_text, action):
        root = self._clear()
        card = tk.Frame(root, bg="#f4f6f8", padx=45, pady=38)
        card.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(card, text=title, font=("Arial", 28, "bold"), bg="#f4f6f8", fg="#a51d2d").pack(pady=(0, 14))
        tk.Label(card, text=message, font=("Arial", 17), bg="#f4f6f8", fg="#0b1f33", justify="center").pack(pady=(0, 24))
        controls = tk.Frame(card, bg="#f4f6f8")
        controls.pack()
        self._button(controls, "ОТКАЖИ", self._show_dashboard, width=16).pack(side="left", padx=8)
        self._button(controls, confirm_text, action, danger=True, width=20).pack(side="left", padx=8)

    def _go_back(self):
        target = self.manager.state.pop("admin_return_screen", screen_ids.START) if self.manager else screen_ids.START
        self._authenticated = False
        self.password_var.set("")
        if self.manager:
            self.manager.show_frame(target)
