from __future__ import annotations

import tkinter as tk

from project.gui import screen_ids
from project.gui.touch_input import ask_touch_text
from project.services.network_service import (
    connect_wifi_network,
    forget_wifi_connection,
    format_network_snapshot,
    get_network_snapshot,
    get_saved_wifi_connections,
    scan_wifi_networks,
)
from project.utils.logging_utils import log_error
from project.gui.ui_components import polish_descendant_buttons


class NetworkScreen(tk.Frame):
    def __init__(self, parent, manager=None):
        super().__init__(parent, bg='#101010')
        self.manager = manager
        self.ssid_var = tk.StringVar(value='')
        self.password_var = tk.StringVar(value='')
        self.hidden_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value='')
        self.summary_var = tk.StringVar(value='')
        self._wifi_rows: list[dict] = []
        self._saved_rows: list[dict] = []

        self._build_ui()
        polish_descendant_buttons(self)

    def _build_ui(self):
        header = tk.Frame(self, bg='#101010')
        header.pack(fill='x', padx=24, pady=(18, 8))
        tk.Label(header, text='MREŽA / WI‑FI', font=('Arial', 28, 'bold'), fg='white', bg='#101010').pack(side='left')
        tk.Button(header, text='Nazad', command=self._go_back, font=('Arial', 14, 'bold'), padx=16, pady=8).pack(side='right')

        tk.Label(self, textvariable=self.status_var, font=('Arial', 13, 'bold'), fg='#ffcc66', bg='#101010').pack(anchor='w', padx=24)
        tk.Label(self, textvariable=self.summary_var, font=('Arial', 14), fg='#dddddd', bg='#101010', justify='left').pack(anchor='w', padx=24, pady=(6, 10))

        actions = tk.Frame(self, bg='#101010')
        actions.pack(fill='x', padx=24, pady=(0, 10))
        tk.Button(actions, text='Osvježi status', command=self._refresh_all, font=('Arial', 12, 'bold'), padx=12, pady=8).pack(side='left', padx=(0, 8))
        tk.Button(actions, text='Skeniraj Wi‑Fi', command=self._scan_wifi, font=('Arial', 12, 'bold'), padx=12, pady=8).pack(side='left', padx=(0, 8))

        content = tk.Frame(self, bg='#101010')
        content.pack(fill='both', expand=True, padx=24, pady=(0, 18))
        content.columnconfigure(0, weight=2)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)

        left_top = self._card(content, 'Status i dijagnostika')
        left_top.grid(row=0, column=0, sticky='nsew', padx=(0, 10), pady=(0, 10))
        self.snapshot_text = self._card_text(left_top, height=14)

        right_top = self._card(content, 'Pronađene Wi‑Fi mreže')
        right_top.grid(row=0, column=1, sticky='nsew', padx=(10, 0), pady=(0, 10))
        self.wifi_canvas = tk.Canvas(right_top, bg='#111111', highlightthickness=0)
        self.wifi_scroll = tk.Scrollbar(right_top, orient='vertical', command=self.wifi_canvas.yview)
        self.wifi_inner = tk.Frame(self.wifi_canvas, bg='#111111')
        self.wifi_inner.bind('<Configure>', lambda e: self.wifi_canvas.configure(scrollregion=self.wifi_canvas.bbox('all')))
        self.wifi_canvas.create_window((0, 0), window=self.wifi_inner, anchor='nw')
        self.wifi_canvas.configure(yscrollcommand=self.wifi_scroll.set)
        self.wifi_canvas.pack(side='left', fill='both', expand=True)
        self.wifi_scroll.pack(side='right', fill='y')

        left_bottom = self._card(content, 'Poveži se na Wi‑Fi')
        left_bottom.grid(row=1, column=0, sticky='nsew', padx=(0, 10))
        self._build_connect_card(left_bottom)

        right_bottom = self._card(content, 'Sačuvane Wi‑Fi konekcije')
        right_bottom.grid(row=1, column=1, sticky='nsew', padx=(10, 0))
        self.saved_canvas = tk.Canvas(right_bottom, bg='#111111', highlightthickness=0)
        self.saved_scroll = tk.Scrollbar(right_bottom, orient='vertical', command=self.saved_canvas.yview)
        self.saved_inner = tk.Frame(self.saved_canvas, bg='#111111')
        self.saved_inner.bind('<Configure>', lambda e: self.saved_canvas.configure(scrollregion=self.saved_canvas.bbox('all')))
        self.saved_canvas.create_window((0, 0), window=self.saved_inner, anchor='nw')
        self.saved_canvas.configure(yscrollcommand=self.saved_scroll.set)
        self.saved_canvas.pack(side='left', fill='both', expand=True)
        self.saved_scroll.pack(side='right', fill='y')

    def _card(self, parent, title: str):
        box = tk.Frame(parent, bg='#111111', bd=1, relief='solid')
        tk.Label(box, text=title, font=('Arial', 16, 'bold'), fg='white', bg='#111111').pack(anchor='w', padx=14, pady=(12, 8))
        return box

    def _card_text(self, parent, height: int = 10):
        text = tk.Text(parent, height=height, font=('Courier New', 11), bg='#101010', fg='#f2f2f2', wrap='word')
        text.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        text.configure(state='disabled')
        return text

    def _replace_text(self, widget, value: str):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', value)
        widget.configure(state='disabled')

    def _build_connect_card(self, parent):
        body = tk.Frame(parent, bg='#111111')
        body.pack(fill='both', expand=True, padx=12, pady=(0, 12))

        tk.Label(body, text='SSID', font=('Arial', 14, 'bold'), fg='white', bg='#111111').grid(row=0, column=0, sticky='w', pady=(0, 6))
        self.ssid_display = tk.Label(body, textvariable=self.ssid_var, font=('Arial', 14), fg='white', bg='#1c1c1c', anchor='w', justify='left', padx=10, pady=10)
        self.ssid_display.grid(row=1, column=0, sticky='ew', padx=(0, 8))
        tk.Button(body, text='Unesi SSID', command=self._edit_ssid, font=('Arial', 12, 'bold'), padx=12, pady=8).grid(row=1, column=1, sticky='ew')

        tk.Label(body, text='Lozinka', font=('Arial', 14, 'bold'), fg='white', bg='#111111').grid(row=2, column=0, sticky='w', pady=(14, 6))
        self.password_display_var = tk.StringVar(value='')
        self.password_display = tk.Label(body, textvariable=self.password_display_var, font=('Arial', 14), fg='white', bg='#1c1c1c', anchor='w', justify='left', padx=10, pady=10)
        self.password_display.grid(row=3, column=0, sticky='ew', padx=(0, 8))
        tk.Button(body, text='Unesi lozinku', command=self._edit_password, font=('Arial', 12, 'bold'), padx=12, pady=8).grid(row=3, column=1, sticky='ew')
        tk.Checkbutton(body, text='Skrivena mreža', variable=self.hidden_var, font=('Arial', 12, 'bold'), fg='white', bg='#111111', selectcolor='#111111', activebackground='#111111', activeforeground='white').grid(row=4, column=0, sticky='w', pady=(14, 10))
        actions = tk.Frame(body, bg='#111111')
        actions.grid(row=5, column=0, columnspan=2, sticky='ew', pady=(4, 0))
        tk.Button(actions, text='Poveži', command=self._connect_wifi, font=('Arial', 12, 'bold'), padx=14, pady=8).pack(side='left')
        tk.Button(actions, text='Očisti', command=self._clear_form, font=('Arial', 12, 'bold'), padx=14, pady=8).pack(side='left', padx=8)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=0)
        self._refresh_password_display()

    def _refresh_password_display(self):
        pwd = self.password_var.get()
        self.password_display_var.set('•' * len(pwd) if pwd else '')

    def _go_back(self):
        if not self.manager:
            return
        target = self.manager.state.get('network_return_screen') or screen_ids.ADMIN
        self.manager.show_frame(target)

    def on_show(self):
        self._refresh_all()

    def _edit_ssid(self):
        value = ask_touch_text(self, title='Unesi SSID', initial=self.ssid_var.get(), secret=False)
        if value is not None:
            self.ssid_var.set(value)

    def _edit_password(self):
        value = ask_touch_text(self, title='Unesi Wi‑Fi lozinku', initial=self.password_var.get(), secret=True)
        if value is not None:
            self.password_var.set(value)
            self._refresh_password_display()

    def _clear_form(self):
        self.ssid_var.set('')
        self.password_var.set('')
        self.hidden_var.set(False)
        self._refresh_password_display()

    def _refresh_all(self):
        self._render_snapshot()
        self._scan_wifi()
        self._render_saved_connections()

    def _render_snapshot(self):
        snapshot = get_network_snapshot()
        self.summary_var.set(snapshot.get('message', 'Mrežni status nije dostupan.'))
        self._replace_text(self.snapshot_text, format_network_snapshot(snapshot))
        self.status_var.set('Mrežni status osvježen.' if snapshot.get('ok') else snapshot.get('message', 'Mrežni status nije dostupan.'))

    def _scan_wifi(self):
        result = scan_wifi_networks()
        self._wifi_rows = result.get('networks', []) or []
        for child in self.wifi_inner.winfo_children():
            child.destroy()
        if not self._wifi_rows:
            tk.Label(self.wifi_inner, text=result.get('message', 'Nema pronađenih Wi‑Fi mreža.'), font=('Arial', 13), fg='#ffcc66', bg='#111111', justify='left', wraplength=700).pack(anchor='w', padx=8, pady=8)
        for row in self._wifi_rows:
            self._build_wifi_card(row)
        self.status_var.set(result.get('message', 'Wi‑Fi scan završen.'))

    def _build_wifi_card(self, row: dict):
        box = tk.Frame(self.wifi_inner, bg='#1c1c1c', bd=1, relief='solid', padx=10, pady=10)
        box.pack(fill='x', padx=8, pady=6)
        title = str(row.get('ssid') or '-')
        if row.get('active'):
            title += '   [AKTIVNA]'
        tk.Label(box, text=title, font=('Arial', 14, 'bold'), fg='white', bg='#1c1c1c').pack(anchor='w')
        info = f"Signal: {row.get('signal', 0)} | Security: {row.get('security', '-')} | Bars: {row.get('bars', '-')}"
        tk.Label(box, text=info, font=('Arial', 11), fg='#dddddd', bg='#1c1c1c').pack(anchor='w', pady=(6, 8))
        actions = tk.Frame(box, bg='#1c1c1c')
        actions.pack(anchor='w')
        tk.Button(actions, text='Koristi SSID', command=lambda s=row.get('ssid', ''): self.ssid_var.set(s), font=('Arial', 11, 'bold'), padx=10, pady=6).pack(side='left')
        tk.Button(actions, text='Poveži odmah', command=lambda s=row.get('ssid', ''): self._connect_wifi(ssid_override=s), font=('Arial', 11, 'bold'), padx=10, pady=6).pack(side='left', padx=8)

    def _render_saved_connections(self):
        self._saved_rows = get_saved_wifi_connections()
        for child in self.saved_inner.winfo_children():
            child.destroy()
        if not self._saved_rows:
            tk.Label(self.saved_inner, text='Nema sačuvanih Wi‑Fi konekcija ili nmcli nije dostupan.', font=('Arial', 13), fg='#ffcc66', bg='#111111', justify='left', wraplength=700).pack(anchor='w', padx=8, pady=8)
            return
        for row in self._saved_rows:
            box = tk.Frame(self.saved_inner, bg='#1c1c1c', bd=1, relief='solid', padx=10, pady=10)
            box.pack(fill='x', padx=8, pady=6)
            tk.Label(box, text=row.get('name', '-'), font=('Arial', 14, 'bold'), fg='white', bg='#1c1c1c').pack(anchor='w')
            tk.Label(box, text=f"Device: {row.get('device') or '-'}", font=('Arial', 11), fg='#dddddd', bg='#1c1c1c').pack(anchor='w', pady=(6, 8))
            actions = tk.Frame(box, bg='#1c1c1c')
            actions.pack(anchor='w')
            tk.Button(actions, text='Koristi kao SSID', command=lambda n=row.get('name', ''): self.ssid_var.set(n), font=('Arial', 11, 'bold'), padx=10, pady=6).pack(side='left')
            tk.Button(actions, text='Obriši', command=lambda n=row.get('name', ''): self._forget_saved(n), font=('Arial', 11, 'bold'), padx=10, pady=6).pack(side='left', padx=8)

    def _forget_saved(self, name: str):
        try:
            result = forget_wifi_connection(name)
            self.status_var.set(result.get('message', 'Konekcija obrisana.'))
            self._render_saved_connections()
            self._render_snapshot()
        except Exception as e:
            log_error(f'[NETWORK_SCREEN] forget failed: {e}')
            self.status_var.set(f'Brisanje konekcije nije uspjelo: {e}')

    def _connect_wifi(self, ssid_override: str | None = None):
        ssid = (ssid_override or self.ssid_var.get()).strip()
        password = self.password_var.get()
        try:
            result = connect_wifi_network(ssid, password, hidden=bool(self.hidden_var.get()))
            self.status_var.set(result.get('message', 'Wi‑Fi konekcija obrađena.'))
            if result.get('ok') and ssid:
                self.ssid_var.set(ssid)
                self.password_var.set('')
                self._refresh_password_display()
            self._render_snapshot()
            self._render_saved_connections()
        except Exception as e:
            log_error(f'[NETWORK_SCREEN] connect failed: {e}')
            self.status_var.set(f'Wi‑Fi konekcija nije uspjela: {e}')
