import calendar
import datetime
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
import unicodedata

from project.core import config
from project.gui import screen_ids
from project.gui.ui_components import add_placeholder
from project.gui.virtual_keyboard import VirtualKeyboard, log_keyboard_exception, log_keyboard_warning
from project.utils.logging_utils import log_error


class FormScreen(tk.Frame):
    """Certificate data entry screen rebuilt for a 4:3 touchscreen kiosk."""

    STUDENT_NAME_FIELD = "ime"
    STUDENT_NAME_MAX_WORDS = 3
    SINGLE_WORD_FIELDS = {"roditelj"}
    DATE_FIELDS = {"godina", "mjesec", "dan"}

    ENTRY_NORMAL_BORDER = "#b8b8b8"
    ENTRY_ACTIVE_BORDER = "#000000"
    ENTRY_INVALID_BORDER = "#a11f1f"
    ENTRY_ACTIVE_BG = "#fffdf2"

    def __init__(self, parent, manager=None):
        super().__init__(parent, bg="#f5f5f5")
        self.manager = manager
        self.active_entry: tk.Entry | None = None
        self.kbd: VirtualKeyboard | None = None
        self._suppress_field_events = False
        self._date_trace_busy = False
        self._last_text_entry: tk.Entry | None = None
        self._combo_list_font: tkfont.Font | None = None
        self._build_ui()
        if config.DEBUG_MODE:
            self.fill_debug_data()

    def _build_ui(self) -> None:
        self.ime_var = tk.StringVar()
        self.roditelj_var = tk.StringVar()
        self.mjesto_var = tk.StringVar()
        self.opstina_var = tk.StringVar()
        self.razred_var = tk.StringVar()
        self.struka_var = tk.StringVar()
        self.razlog_var = tk.StringVar()
        self.dan_var = tk.StringVar()
        self.mjesec_var = tk.StringVar()
        self.godina_var = tk.StringVar(value="20")

        ui_scale = getattr(self.manager, "ui_scale", 1.0) if self.manager else 1.0
        self.ui_scale = max(1.0, float(ui_scale or 1.0))
        target_w, target_h = (self.manager.fit_aspect_ratio(31, 23, fill=0.995) if self.manager else (1024, 760))

        # 4:3 kiosk split. The action button has its own compact row, so the form
        # can breathe without taking space from the touch keyboard.
        header_h = self._clamp(int(target_h * 0.060), 42, 50)
        validation_h = self._clamp(int(target_h * 0.030), 20, 24)
        action_h = self._clamp(int(target_h * 0.070), 48, 56)
        keyboard_h = self._clamp(int(target_h * 0.350), 258, 282)

        base_font = ("Arial", max(15, int(round(15 * self.ui_scale))))
        label_font = ("Arial", max(14, int(round(14 * self.ui_scale))), "bold")
        small_label_font = ("Arial", max(11, int(round(11 * self.ui_scale))), "bold")
        title_font = ("Arial", max(23, int(round(24 * self.ui_scale))), "bold")
        button_font = ("Arial", max(16, int(round(17 * self.ui_scale))), "bold")

        # Larger dropdown field and popup text for the Toshiba touchscreen.
        combo_font = ("Arial", max(18, int(round(18 * self.ui_scale))), "bold")
        combo_list_font = ("Arial", max(22, int(round(22 * self.ui_scale))))
        validation_font = ("Arial", max(12, int(round(12 * self.ui_scale))), "bold")

        self._configure_combobox_style(combo_font, combo_list_font)

        outer = tk.Frame(self, bg="#f5f5f5")
        outer.pack(fill="both", expand=True)

        content = tk.Frame(outer, bg="#f5f5f5", width=target_w, height=target_h)
        content.place(relx=0.5, rely=0.5, anchor="center")
        content.grid_propagate(False)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, minsize=header_h)
        content.grid_rowconfigure(1, weight=1)
        content.grid_rowconfigure(2, minsize=validation_h)
        content.grid_rowconfigure(3, minsize=action_h)
        content.grid_rowconfigure(4, minsize=keyboard_h)

        header = tk.Frame(content, bg="#f5f5f5", height=header_h)
        header.grid(row=0, column=0, sticky="nsew")
        header.grid_propagate(False)
        tk.Label(
            header,
            text="УНЕСИТЕ ПОДАТКЕ",
            font=title_font,
            bg="#f5f5f5",
            fg="#111111",
        ).place(relx=0.5, rely=0.53, anchor="center")

        form_shell = tk.Frame(content, bg="#f5f5f5")
        form_shell.grid(row=1, column=0, sticky="nsew", padx=7, pady=(0, 0))
        form_shell.grid_rowconfigure(0, weight=1)
        form_shell.grid_columnconfigure(0, weight=1)

        card = tk.Frame(
            form_shell,
            bg="white",
            bd=1,
            relief="solid",
            padx=max(10, int(round(10 * self.ui_scale))),
            pady=max(8, int(round(8 * self.ui_scale))),
        )
        card.grid(row=0, column=0, sticky="nsew")
        for column in range(2):
            card.grid_columnconfigure(column, weight=1, uniform="formcols")
        for row in range(4):
            card.grid_rowconfigure(row, weight=1, uniform="formrows")

        # Top row: the two name fields belong together and are reached first.
        self.ime_entry = self._make_entry_field(
            card,
            "Име и презиме ученика",
            self.ime_var,
            self.STUDENT_NAME_FIELD,
            base_font,
            label_font,
        )
        self.ime_entry.master.grid(row=0, column=0, padx=7, pady=4, sticky="nsew")

        self.roditelj_entry = self._make_entry_field(card, "Име родитеља", self.roditelj_var, "roditelj", base_font, label_font)
        self.roditelj_entry.master.grid(row=0, column=1, padx=7, pady=4, sticky="nsew")

        self.mjesto_entry = self._make_entry_field(card, "Мјесто рођења", self.mjesto_var, "mjesto", base_font, label_font)
        self.mjesto_entry.master.grid(row=1, column=0, padx=7, pady=4, sticky="nsew")
        add_placeholder(self.mjesto_entry, config.MJESTO_PLACEHOLDER)

        self._build_date_field(card, base_font, label_font, small_label_font).grid(row=1, column=1, padx=7, pady=4, sticky="nsew")

        self.opstina_entry = self._make_entry_field(card, "Општина рођења", self.opstina_var, "opstina", base_font, label_font)
        self.opstina_entry.master.grid(row=2, column=0, padx=7, pady=4, sticky="nsew")
        add_placeholder(self.opstina_entry, config.OPSTINA_PLACEHOLDER)

        self.razred_cb = self._make_combo_field(card, "Разред", self.razred_var, config.RAZREDI, label_font)
        self.razred_cb.master.grid(row=2, column=1, padx=7, pady=4, sticky="nsew")

        self.struka_cb = self._make_combo_field(card, "Струка", self.struka_var, config.STRUKE, label_font)
        self.struka_cb.master.grid(row=3, column=0, padx=7, pady=4, sticky="nsew")

        self.razlog_cb = self._make_combo_field(card, "Разлог", self.razlog_var, config.RAZLOZI, label_font, popup_rows=6)
        self.razlog_cb.master.grid(row=3, column=1, padx=7, pady=4, sticky="nsew")

        validation_frame = tk.Frame(content, bg="#f5f5f5", height=validation_h)
        validation_frame.grid(row=2, column=0, sticky="nsew")
        validation_frame.grid_propagate(False)
        self.validation_label = tk.Label(
            validation_frame,
            text="",
            font=validation_font,
            bg="#f5f5f5",
            fg="#a11f1f",
            wraplength=max(500, target_w - 50),
            justify="center",
        )
        self.validation_label.pack(fill="both", expand=True)

        action_frame = tk.Frame(content, bg="#f5f5f5", height=action_h)
        action_frame.grid(row=3, column=0, sticky="nsew")
        action_frame.grid_propagate(False)
        self.back_to_start_button = tk.Label(
            action_frame,
            text="ПОЧЕТАК",
            font=button_font,
            fg="white",
            bg="#8B1D1D",
            bd=0,
            cursor="none",
            takefocus=0,
        )
        self.back_to_start_button.place(
            x=max(18, int(target_w * 0.035)),
            rely=0.5,
            anchor="w",
            width=max(145, int(target_w * 0.18)),
            height=max(38, action_h - 12),
        )
        self.back_to_start_button.bind("<ButtonPress-1>", self._go_back_to_start_from_touch, add=False)
        self.back_to_start_button.bind("<ButtonRelease-1>", lambda e: self.back_to_start_button.config(bg="#8B1D1D"), add=False)
        self.back_to_start_button.bind("<Leave>", lambda e: self.back_to_start_button.config(bg="#8B1D1D"), add=False)

        self.next_button = tk.Label(
            action_frame,
            text="ДАЉЕ",
            font=button_font,
            fg="white",
            bg="#000000",
            bd=0,
            cursor="none",
            takefocus=0,
        )
        self.next_button.place(
            relx=0.5,
            rely=0.5,
            anchor="center",
            width=max(250, int(target_w * 0.30)),
            height=max(40, action_h - 10),
        )
        self.next_button.bind("<ButtonPress-1>", self._submit_from_touch, add=False)
        self.next_button.bind("<ButtonRelease-1>", lambda e: self.next_button.config(bg="#000000"), add=False)
        self.next_button.bind("<Leave>", lambda e: self.next_button.config(bg="#000000"), add=False)

        keyboard_frame = tk.Frame(content, bg="#f5f5f5", height=keyboard_h)
        keyboard_frame.grid(row=4, column=0, sticky="nsew")
        keyboard_frame.grid_propagate(False)
        keyboard_frame.grid_columnconfigure(0, weight=1)
        keyboard_frame.grid_rowconfigure(0, weight=1)

        self.kbd = VirtualKeyboard(
            keyboard_frame,
            bg="#f5f5f5",
            ui_scale=self.ui_scale,
            target_width=target_w,
            target_height=keyboard_h,
        )
        self.kbd.grid(row=0, column=0, sticky="nsew")

        self._text_entries = [
            self.ime_entry,
            self.roditelj_entry,
            self.godina_entry,
            self.mjesec_entry,
            self.dan_entry,
            self.mjesto_entry,
            self.opstina_entry,
        ]

        self._required_order = [
            ("Име и презиме ученика", self.ime_entry),
            ("Име родитеља", self.roditelj_entry),
            ("Година рођења", self.godina_entry),
            ("Мјесец рођења", self.mjesec_entry),
            ("Дан рођења", self.dan_entry),
            ("Мјесто рођења", self.mjesto_entry),
            ("Општина рођења", self.opstina_entry),
            ("Разред", self.razred_cb),
            ("Струка", self.struka_cb),
            ("Разлог", self.razlog_cb),
        ]

        self._bind_entries_to_keyboard()
        self._bind_field_validation()

    def _clamp(self, value: int, low: int, high: int) -> int:
        return max(low, min(high, value))

    def _configure_combobox_style(self, combo_font, combo_list_font) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        self._combo_list_font = tkfont.Font(
            self,
            family=combo_list_font[0],
            size=combo_list_font[1],
            weight="normal",
        )
        self.option_add("*TCombobox*Listbox.font", self._combo_list_font)
        self.option_add("*TCombobox*Listbox.selectBorderWidth", 2)
        self.option_add("*TCombobox*Listbox.activestyle", "dotbox")

        arrow_size = max(28, int(round(28 * self.ui_scale)))
        padding = (10, 9, 10, 9)
        style.configure(
            "Touch.TCombobox",
            font=combo_font,
            padding=padding,
            arrowsize=arrow_size,
            fieldbackground="white",
            background="white",
            foreground="#111111",
        )
        style.map(
            "Touch.TCombobox",
            fieldbackground=[("readonly", "white")],
            foreground=[("readonly", "#111111")],
        )
        style.configure(
            "Invalid.Touch.TCombobox",
            font=combo_font,
            padding=padding,
            arrowsize=arrow_size,
            fieldbackground="#fff1f1",
            background="#fff1f1",
            foreground="#111111",
        )

    def _make_entry_field(self, parent, label: str, variable: tk.StringVar, field_key: str, entry_font, label_font) -> tk.Entry:
        frame = tk.Frame(parent, bg="white")
        frame.grid_columnconfigure(0, weight=1)
        tk.Label(frame, text=label, bg="white", fg="#111111", font=label_font).grid(row=0, column=0, sticky="w")
        entry = tk.Entry(
            frame,
            textvariable=variable,
            font=entry_font,
            relief="solid",
            bd=1,
            highlightthickness=2,
            highlightbackground=self.ENTRY_NORMAL_BORDER,
            highlightcolor=self.ENTRY_ACTIVE_BORDER,
            bg="white",
            fg="#111111",
            insertbackground="#111111",
            insertwidth=max(2, int(round(3 * self.ui_scale))),
            takefocus=1,
        )
        entry.grid(row=1, column=0, sticky="ew", pady=(3, 0), ipady=max(5, int(round(5 * self.ui_scale))))
        entry.field_key = field_key
        entry.field_label = label
        entry.bind("<FocusIn>", self._remember_active_entry, add=True)
        entry.bind("<ButtonPress-1>", self._remember_active_entry, add=True)
        entry.bind("<Return>", self._focus_next_required, add=True)
        return entry

    def _build_date_field(self, parent, entry_font, label_font, small_label_font) -> tk.Frame:
        frame = tk.Frame(parent, bg="white")
        frame.grid_columnconfigure(0, weight=1)
        tk.Label(frame, text="Датум рођења", bg="white", fg="#111111", font=label_font).grid(row=0, column=0, sticky="w")

        inner = tk.Frame(frame, bg="white")
        inner.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        for column in range(3):
            inner.grid_columnconfigure(column, weight=1, uniform="date")

        tk.Label(inner, text="Година", bg="white", fg="#555555", font=small_label_font).grid(row=0, column=0, padx=(0, 6), sticky="w")
        tk.Label(inner, text="Мјесец", bg="white", fg="#555555", font=small_label_font).grid(row=0, column=1, padx=(0, 6), sticky="w")
        tk.Label(inner, text="Дан", bg="white", fg="#555555", font=small_label_font).grid(row=0, column=2, sticky="w")

        self.godina_entry = self._make_date_entry(inner, self.godina_var, "godina", entry_font)
        self.godina_entry.grid(row=1, column=0, padx=(0, 6), sticky="ew", ipady=max(5, int(round(5 * self.ui_scale))))
        self.mjesec_entry = self._make_date_entry(inner, self.mjesec_var, "mjesec", entry_font)
        self.mjesec_entry.grid(row=1, column=1, padx=(0, 6), sticky="ew", ipady=max(5, int(round(5 * self.ui_scale))))
        self.dan_entry = self._make_date_entry(inner, self.dan_var, "dan", entry_font)
        self.dan_entry.grid(row=1, column=2, sticky="ew", ipady=max(5, int(round(5 * self.ui_scale))))
        return frame

    def _make_date_entry(self, parent, variable: tk.StringVar, field_key: str, entry_font) -> tk.Entry:
        entry = tk.Entry(
            parent,
            textvariable=variable,
            font=entry_font,
            justify="center",
            relief="solid",
            bd=1,
            highlightthickness=2,
            highlightbackground=self.ENTRY_NORMAL_BORDER,
            highlightcolor=self.ENTRY_ACTIVE_BORDER,
            bg="white",
            fg="#111111",
            insertbackground="#111111",
            insertwidth=max(2, int(round(3 * self.ui_scale))),
            takefocus=1,
        )
        entry.field_key = field_key
        entry.field_label = {"godina": "Година", "mjesec": "Мјесец", "dan": "Дан"}.get(field_key, field_key)
        entry.bind("<FocusIn>", self._remember_active_entry, add=True)
        entry.bind("<ButtonPress-1>", self._remember_active_entry, add=True)
        return entry

    def _make_combo_field(self, parent, label: str, variable: tk.StringVar, values, label_font, *, popup_rows: int | None = None) -> ttk.Combobox:
        frame = tk.Frame(parent, bg="white")
        frame.grid_columnconfigure(0, weight=1)
        tk.Label(frame, text=label, bg="white", fg="#111111", font=label_font).grid(row=0, column=0, sticky="w")
        combo = ttk.Combobox(
            frame,
            textvariable=variable,
            values=list(values),
            state="readonly",
            style="Touch.TCombobox",
            height=popup_rows or min(6, max(4, len(values))),
            takefocus=1,
        )
        combo.grid(row=1, column=0, sticky="ew", pady=(3, 0))
        combo.bind("<FocusIn>", self._keep_keyboard_for_combo, add=True)
        combo.bind("<ButtonPress-1>", self._keep_keyboard_for_combo, add=True)
        combo.bind("<ButtonRelease-1>", lambda e, c=combo: self.after(25, lambda: self._enlarge_combo_popup(c)), add=True)
        combo.bind("<<ComboboxSelected>>", self._on_combo_selected, add=True)
        return combo

    def _keep_keyboard_for_combo(self, event=None):
        """Combobox focus must not undock or reset the virtual keyboard."""
        target = self.active_entry if self._entry_is_available(self.active_entry) else self._last_text_entry
        if self._entry_is_available(target):
            self.active_entry = target
            self._last_text_entry = target
            self._show_active_entry(target)
            if self.kbd:
                self.kbd.set_active_entry(target)
        else:
            self.active_entry = None
            self._last_text_entry = None
            self._show_active_entry(None)
            if self.kbd:
                self.kbd.clear_active_entry()

    def _on_combo_selected(self, event=None):
        self._keep_keyboard_for_combo(event)
        return self._focus_next_required(event)

    def _focus_combo(self, combo: ttk.Combobox) -> None:
        try:
            combo.focus_set()
        except Exception:
            pass
        self._keep_keyboard_for_combo(type("Event", (), {"widget": combo})())

    def _enlarge_combo_popup(self, combo: ttk.Combobox) -> None:
        """Keep the popup list text large on Tk themes that ignore option_add."""
        if not self._combo_list_font:
            return
        try:
            popdown = combo.tk.call("ttk::combobox::PopdownWindow", combo)
            listbox = f"{popdown}.f.l"
            combo.tk.call(listbox, "configure", "-font", self._combo_list_font.name)
        except Exception:
            pass

    def _make_next_button_field(self, parent, button_font) -> tk.Frame:
        frame = tk.Frame(parent, bg="white")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)
        tk.Label(frame, text="", bg="white", fg="#111111", font=("Arial", max(14, int(round(14 * self.ui_scale))), "bold")).grid(
            row=0, column=0, sticky="w"
        )
        self.next_button = tk.Label(
            frame,
            text="ДАЉЕ",
            font=button_font,
            fg="white",
            bg="#000000",
            bd=0,
            cursor="none",
            takefocus=0,
        )
        self.next_button.grid(row=1, column=0, sticky="nsew", pady=(3, 0), ipady=max(9, int(round(9 * self.ui_scale))))
        self.next_button.bind("<ButtonPress-1>", self._submit_from_touch, add=False)
        self.next_button.bind("<ButtonRelease-1>", lambda e: self.next_button.config(bg="#000000"), add=False)
        self.next_button.bind("<Leave>", lambda e: self.next_button.config(bg="#000000"), add=False)
        return frame

    def _bind_entries_to_keyboard(self) -> None:
        if not self.kbd:
            return
        self.kbd.bind_entry(
            self.ime_entry,
            mode="alpha",
            uppercase_first=True,
            one_word=False,
            max_words=self.STUDENT_NAME_MAX_WORDS,
            on_change=self._on_virtual_keyboard_change,
        )
        self.kbd.bind_entry(self.roditelj_entry, mode="alpha", uppercase_first=True, one_word=True, on_change=self._on_virtual_keyboard_change)
        self.kbd.bind_entry(self.mjesto_entry, mode="alpha", uppercase_first=True, one_word=False, on_change=self._on_virtual_keyboard_change, placeholder=config.MJESTO_PLACEHOLDER)
        self.kbd.bind_entry(self.opstina_entry, mode="alpha", uppercase_first=True, one_word=False, on_change=self._on_virtual_keyboard_change, placeholder=config.OPSTINA_PLACEHOLDER)
        self.kbd.bind_entry(self.godina_entry, mode="numeric", uppercase_first=False, on_change=self._on_virtual_keyboard_change)
        self.kbd.bind_entry(self.mjesec_entry, mode="numeric", uppercase_first=False, on_change=self._on_virtual_keyboard_change)
        self.kbd.bind_entry(self.dan_entry, mode="numeric", uppercase_first=False, on_change=self._on_virtual_keyboard_change)

    def _bind_field_validation(self) -> None:
        self.ime_entry.bind("<KeyRelease>", self._schedule_student_name_sanitize, add=True)
        self.ime_entry.bind("<<Paste>>", self._schedule_student_name_sanitize, add=True)
        self.ime_entry.bind("<FocusOut>", self._student_name_focus_out, add=True)
        self.ime_entry.bind("<<VKChanged>>", self._schedule_student_name_sanitize, add=True)

        self.roditelj_entry.bind("<KeyRelease>", self._schedule_single_word_sanitize, add=True)
        self.roditelj_entry.bind("<<Paste>>", self._schedule_single_word_sanitize, add=True)
        self.roditelj_entry.bind("<FocusOut>", self._single_word_focus_out, add=True)
        self.roditelj_entry.bind("<<VKChanged>>", self._schedule_single_word_sanitize, add=True)

        for entry in (self.mjesto_entry, self.opstina_entry):
            entry.bind("<FocusOut>", self._titlecase_entry, add=True)
            entry.bind("<KeyRelease>", self._refresh_keyboard_case, add=True)
            entry.bind("<<VKChanged>>", self._refresh_keyboard_case, add=True)

        self.godina_entry.bind("<FocusIn>", self._on_year_focus_in, add=True)
        self.godina_entry.bind("<KeyPress>", self._guard_year_keypress, add=True)
        self.godina_entry.bind("<KeyRelease>", self._on_year_input, add=True)
        self.godina_entry.bind("<<Paste>>", lambda e: self.after_idle(lambda: self._on_year_input(e)), add=True)
        self.godina_entry.bind("<<VKChanged>>", self._on_year_input, add=True)
        self.godina_var.trace_add("write", lambda *_: self._sanitize_date_var("godina"))

        self.mjesec_entry.bind("<KeyPress>", self._guard_two_digit_keypress, add=True)
        self.mjesec_entry.bind("<KeyRelease>", self._on_month_input, add=True)
        self.mjesec_entry.bind("<<Paste>>", lambda e: self.after_idle(lambda: self._on_month_input(e)), add=True)
        self.mjesec_entry.bind("<<VKChanged>>", self._on_month_input, add=True)
        self.mjesec_var.trace_add("write", lambda *_: self._sanitize_date_var("mjesec"))

        self.dan_entry.bind("<KeyPress>", self._guard_two_digit_keypress, add=True)
        self.dan_entry.bind("<KeyRelease>", self._on_day_input, add=True)
        self.dan_entry.bind("<<Paste>>", lambda e: self.after_idle(lambda: self._on_day_input(e)), add=True)
        self.dan_entry.bind("<<VKChanged>>", self._on_day_input, add=True)
        self.dan_var.trace_add("write", lambda *_: self._sanitize_date_var("dan"))

    def _remember_active_entry(self, event=None):
        entry = getattr(event, "widget", None)
        if isinstance(entry, tk.Entry):
            self.active_entry = entry
            self._last_text_entry = entry
            self._show_active_entry(entry)
            if self.kbd:
                self.kbd.set_active_entry(entry)

    def _clear_keyboard_active(self, event=None):
        self.active_entry = None
        self._last_text_entry = None
        self._show_active_entry(None)
        if self.kbd:
            self.kbd.clear_active_entry()

    def _entry_is_available(self, entry) -> bool:
        if not isinstance(entry, tk.Entry):
            return False
        try:
            return bool(entry.winfo_exists())
        except Exception:
            return False

    def _focus_date_target(self, attr_name: str) -> bool:
        entry = getattr(self, attr_name, None)
        if self._entry_is_available(entry):
            self._focus_entry(entry)
            return True
        log_keyboard_warning(f"[VK] Date auto-focus target is missing: {attr_name}")
        return False

    def _focus_entry(self, entry: tk.Entry) -> None:
        if not self._entry_is_available(entry):
            log_keyboard_warning(f"[VK] Cannot focus missing entry: {entry!r}")
            return
        try:
            entry.focus_set()
        except Exception:
            pass
        try:
            entry.icursor("end")
        except Exception:
            pass
        self.active_entry = entry
        self._last_text_entry = entry
        self._show_active_entry(entry)
        if self.kbd:
            self.kbd.set_active_entry(entry)

    def _focus_widget(self, widget) -> None:
        if isinstance(widget, ttk.Combobox):
            self._focus_combo(widget)
            return
        if isinstance(widget, tk.Entry):
            self._focus_entry(widget)
            return
        try:
            widget.focus_set()
        except Exception:
            pass
        self._clear_keyboard_active()

    def _show_active_entry(self, active: tk.Entry | None) -> None:
        """Give the current typing target a clear kiosk-visible state.

        On the Toshiba resistive panel the virtual keyboard may keep logical
        focus internally, so a normal Tk caret is not always enough feedback.
        The active field gets a darker border, warmer background, and wider
        insert cursor; inactive fields return to a quiet neutral border.
        """
        for entry in getattr(self, "_text_entries", []):
            if not isinstance(entry, tk.Entry):
                continue
            try:
                if active is entry:
                    entry.config(
                        highlightthickness=2,
                        highlightbackground=self.ENTRY_ACTIVE_BORDER,
                        highlightcolor=self.ENTRY_ACTIVE_BORDER,
                        bg="white",
                        insertbackground=self.ENTRY_ACTIVE_BORDER,
                        insertwidth=max(2, int(round(3 * self.ui_scale))),
                    )
                else:
                    entry.config(
                        highlightthickness=2,
                        highlightbackground=self.ENTRY_NORMAL_BORDER,
                        highlightcolor=self.ENTRY_ACTIVE_BORDER,
                        bg="white",
                        insertbackground=self.ENTRY_ACTIVE_BORDER,
                        insertwidth=max(2, int(round(3 * self.ui_scale))),
                    )
            except tk.TclError:
                pass

    def _on_virtual_keyboard_change(self, entry: tk.Entry) -> None:
        try:
            field_key = getattr(entry, "field_key", "")
            if not field_key:
                log_keyboard_warning(f"[VK] Keyboard callback received entry without field_key: {entry!r}")
            if field_key == self.STUDENT_NAME_FIELD:
                self._sanitize_student_name_now(entry)
            elif field_key in self.SINGLE_WORD_FIELDS:
                self._sanitize_single_word_now(entry)
            elif field_key == "godina":
                self._on_year_input()
            elif field_key == "mjesec":
                self._on_month_input()
            elif field_key == "dan":
                self._on_day_input()
            self._clear_validation()
        except Exception:
            log_keyboard_exception(f"[VK] Keyboard on_change failed for {getattr(entry, 'field_key', '<missing>')}")

    def _refresh_keyboard_case(self, event=None):
        if self.kbd and isinstance(self.active_entry, tk.Entry):
            self.kbd.set_active_entry(self.active_entry)

    def on_show(self) -> None:
        data = (self.manager.state.get("form_data") if self.manager else None) or None
        if data:
            self._apply_form_data(data)
        else:
            self._reset_form()
            if config.DEBUG_MODE:
                self.fill_debug_data()
        self._clear_validation()
        self._focus_entry(self.ime_entry)

    def _is_letter_for_name(self, ch: str) -> bool:
        if not ch or not ch.isalpha():
            return False
        try:
            name = unicodedata.name(ch)
        except ValueError:
            return False
        return name.startswith("CYRILLIC") or name.startswith("LATIN")

    def _normalize_title(self, text: str) -> str:
        parts = [p for p in str(text or "").strip().split() if p]
        return " ".join(part[:1].upper() + part[1:].lower() for part in parts)

    def _normalize_single_word(self, text: str) -> str:
        cleaned = "".join(ch for ch in str(text or "").strip() if self._is_letter_for_name(ch))
        if not cleaned:
            return ""
        return cleaned[:1].upper() + cleaned[1:].lower()

    def _normalize_student_name(self, text: str) -> str:
        raw = self._clean_student_name_raw(text).strip()
        parts = [p for p in raw.split() if p][: self.STUDENT_NAME_MAX_WORDS]
        return " ".join(part[:1].upper() + part[1:].lower() for part in parts)

    def _split_student_name(self, text: str) -> tuple[str, str]:
        normalized = self._normalize_student_name(text)
        parts = normalized.split()
        if not 2 <= len(parts) <= self.STUDENT_NAME_MAX_WORDS:
            return "", ""
        return parts[0], " ".join(parts[1:])

    def _clean_single_word_raw(self, text: str) -> str:
        return "".join(ch for ch in str(text or "") if self._is_letter_for_name(ch))

    def _clean_student_name_raw(self, text: str) -> str:
        result: list[str] = []
        for ch in str(text or ""):
            if self._is_letter_for_name(ch):
                result.append(ch)
            elif ch.isspace():
                if result and result[-1] != " ":
                    result.append(" ")
        cleaned = "".join(result)
        trailing_space = cleaned.endswith(" ")
        parts = [p for p in cleaned.strip().split() if p]
        if not parts:
            return ""
        if len(parts) < self.STUDENT_NAME_MAX_WORDS and trailing_space:
            return " ".join(parts) + " "
        return " ".join(parts[: self.STUDENT_NAME_MAX_WORDS])

    def _schedule_student_name_sanitize(self, event=None):
        entry = getattr(event, "widget", None)
        if isinstance(entry, tk.Entry):
            self.after_idle(lambda e=entry: self._sanitize_student_name_now(e))

    def _sanitize_student_name_now(self, entry: tk.Entry) -> None:
        if self._suppress_field_events or getattr(entry, "field_key", "") != self.STUDENT_NAME_FIELD:
            return
        current = entry.get()
        cleaned = self._clean_student_name_raw(current)
        if current == cleaned:
            if self.kbd and self.active_entry is entry:
                self.kbd.set_active_entry(entry)
            return
        try:
            cursor = entry.index(tk.INSERT)
        except Exception:
            cursor = len(cleaned)
        cleaned_before_cursor = self._clean_student_name_raw(current[:cursor])
        self._suppress_field_events = True
        try:
            entry.delete(0, "end")
            entry.insert(0, cleaned)
            entry.icursor(min(len(cleaned), len(cleaned_before_cursor)))
        finally:
            self._suppress_field_events = False
        if self.kbd and self.active_entry is entry:
            self.kbd.set_active_entry(entry)

    def _student_name_focus_out(self, event=None):
        entry = getattr(event, "widget", None)
        if isinstance(entry, tk.Entry):
            normalized = self._normalize_student_name(entry.get())
            self._set_entry_text(entry, normalized)

    def _schedule_single_word_sanitize(self, event=None):
        entry = getattr(event, "widget", None)
        if isinstance(entry, tk.Entry):
            self.after_idle(lambda e=entry: self._sanitize_single_word_now(e))

    def _sanitize_single_word_now(self, entry: tk.Entry) -> None:
        if self._suppress_field_events or getattr(entry, "field_key", "") not in self.SINGLE_WORD_FIELDS:
            return
        current = entry.get()
        cleaned = self._clean_single_word_raw(current)
        if current == cleaned:
            if self.kbd and self.active_entry is entry:
                self.kbd.set_active_entry(entry)
            return
        try:
            cursor = entry.index(tk.INSERT)
        except Exception:
            cursor = len(cleaned)
        cleaned_before_cursor = self._clean_single_word_raw(current[:cursor])
        self._suppress_field_events = True
        try:
            entry.delete(0, "end")
            entry.insert(0, cleaned)
            entry.icursor(min(len(cleaned), len(cleaned_before_cursor)))
        finally:
            self._suppress_field_events = False
        if self.kbd and self.active_entry is entry:
            self.kbd.set_active_entry(entry)

    def _single_word_focus_out(self, event=None):
        entry = getattr(event, "widget", None)
        if isinstance(entry, tk.Entry):
            normalized = self._normalize_single_word(entry.get())
            self._set_entry_text(entry, normalized)

    def _titlecase_entry(self, event=None):
        entry = getattr(event, "widget", None)
        if not isinstance(entry, tk.Entry):
            return
        text = entry.get()
        if text in (config.MJESTO_PLACEHOLDER, config.OPSTINA_PLACEHOLDER):
            return
        normalized = self._normalize_title(text)
        if normalized != text:
            self._set_entry_text(entry, normalized)

    def _sanitize_date_var(self, field_key: str) -> None:
        if self._date_trace_busy:
            return
        var = {
            "godina": self.godina_var,
            "mjesec": self.mjesec_var,
            "dan": self.dan_var,
        }.get(field_key)
        if var is None:
            return

        raw = str(var.get() or "")
        digits = "".join(ch for ch in raw if ch.isdigit())
        if field_key == "godina":
            suffix = digits[2:] if digits.startswith("20") else (digits[-2:] if len(digits) > 2 else digits)
            cleaned = "20" + suffix[:2]
        else:
            cleaned = digits[:2]

        if raw == cleaned:
            return
        self._date_trace_busy = True
        try:
            var.set(cleaned)
        finally:
            self._date_trace_busy = False

    def _guard_year_keypress(self, event=None):
        if event is None:
            return None
        if getattr(event, "state", 0) & 0x4:
            return None
        keysym = getattr(event, "keysym", "")
        char = getattr(event, "char", "")
        if keysym in {"Left", "Right", "Home", "End", "Tab", "Delete"}:
            return None
        if keysym == "BackSpace":
            try:
                if self.godina_entry.index(tk.INSERT) <= 2:
                    return "break"
            except Exception:
                pass
            return None
        if char and not char.isdigit():
            return "break"
        if char and char.isdigit():
            digits = "".join(c for c in self.godina_entry.get() if c.isdigit())
            suffix = digits[2:] if digits.startswith("20") else digits[-2:]
            has_selection = self._entry_has_selection(self.godina_entry)
            if len(suffix) >= 2 and not has_selection:
                return "break"
        return None

    def _guard_two_digit_keypress(self, event=None):
        if event is None:
            return None
        if getattr(event, "state", 0) & 0x4:
            return None
        keysym = getattr(event, "keysym", "")
        char = getattr(event, "char", "")
        if keysym in {"BackSpace", "Left", "Right", "Home", "End", "Tab", "Delete"}:
            return None
        if char and not char.isdigit():
            return "break"
        widget = getattr(event, "widget", None)
        if isinstance(widget, tk.Entry) and char and len("".join(c for c in widget.get() if c.isdigit())) >= 2 and not self._entry_has_selection(widget):
            return "break"
        return None

    def _entry_has_selection(self, entry: tk.Entry) -> bool:
        try:
            entry.index("sel.first")
            entry.index("sel.last")
            return True
        except Exception:
            return False

    def _on_year_focus_in(self, event=None):
        current = "".join(ch for ch in self.godina_var.get() if ch.isdigit())
        if not current.startswith("20"):
            current = "20" + current[-2:]
        self.godina_var.set(current[:4] or "20")
        self._focus_entry(self.godina_entry)

    def _on_year_input(self, event=None):
        try:
            digits = "".join(ch for ch in self.godina_var.get() if ch.isdigit())
            if digits.startswith("20"):
                suffix = digits[2:]
            else:
                suffix = digits[-2:] if len(digits) > 2 else digits
            suffix = suffix[:2]
            current = "20" + suffix
            if current != self.godina_var.get():
                self.godina_var.set(current)
            try:
                self.godina_entry.icursor("end")
            except Exception:
                pass
            if len(suffix) == 2 and self.active_entry is self.godina_entry:
                self._focus_date_target("mjesec_entry")
            elif self.kbd and self.active_entry is self.godina_entry:
                self.kbd.set_active_entry(self.godina_entry)
        except Exception:
            log_keyboard_exception("[VK] Year input handler failed")

    def _on_month_input(self, event=None):
        try:
            current = "".join(ch for ch in self.mjesec_var.get() if ch.isdigit())[:2]
            if current != self.mjesec_var.get():
                self.mjesec_var.set(current)
            try:
                self.mjesec_entry.icursor("end")
            except Exception:
                pass
            should_advance = len(current) == 2 or (len(current) == 1 and current in {"2", "3", "4", "5", "6", "7", "8", "9"})
            if should_advance and self.active_entry is self.mjesec_entry:
                self._focus_date_target("dan_entry")
            elif self.kbd and self.active_entry is self.mjesec_entry:
                self.kbd.set_active_entry(self.mjesec_entry)
        except Exception:
            log_keyboard_exception("[VK] Month input handler failed")

    def _on_day_input(self, event=None):
        try:
            current = "".join(ch for ch in self.dan_var.get() if ch.isdigit())[:2]
            if current != self.dan_var.get():
                self.dan_var.set(current)
            try:
                self.dan_entry.icursor("end")
            except Exception:
                pass
            if self.kbd and self.active_entry is self.dan_entry:
                self.kbd.set_active_entry(self.dan_entry)
        except Exception:
            log_keyboard_exception("[VK] Day input handler failed")

    def _student_birth_years(self) -> list[str]:
        current_year = datetime.date.today().year
        youngest_age = 13
        oldest_age = 21
        newest_year = current_year - youngest_age
        oldest_year = current_year - oldest_age
        return [str(year) for year in range(newest_year, oldest_year - 1, -1)]

    def _is_empty_widget(self, widget) -> bool:
        if widget is self.ime_entry:
            ime, prezime = self._split_student_name(widget.get())
            return not ime or not prezime
        if widget is self.roditelj_entry:
            return not self._normalize_single_word(widget.get())
        if widget is self.mjesto_entry:
            value = self._normalize_title(widget.get())
            return not value or value == config.MJESTO_PLACEHOLDER
        if widget is self.opstina_entry:
            value = self._normalize_title(widget.get())
            return not value or value == config.OPSTINA_PLACEHOLDER
        if widget is self.godina_entry:
            return len(self.godina_var.get().strip()) != 4
        if widget is self.mjesec_entry:
            return len(self.mjesec_var.get().strip()) == 0
        if widget is self.dan_entry:
            return len(self.dan_var.get().strip()) == 0
        if widget is self.razred_cb:
            return not self.razred_var.get().strip()
        if widget is self.struka_cb:
            return not self.struka_var.get().strip()
        if widget is self.razlog_cb:
            return not self.razlog_var.get().strip()
        return False

    def _focus_next_required(self, event=None):
        for _label, widget in getattr(self, "_required_order", []):
            if self._is_empty_widget(widget):
                self._focus_widget(widget)
                return "break"
        return None

    def _clear_validation(self) -> None:
        if hasattr(self, "validation_label"):
            self.validation_label.config(text="")
        for _label, target in getattr(self, "_required_order", []):
            if isinstance(target, tk.Entry):
                self._safe_config(
                    target,
                    highlightthickness=2,
                    highlightbackground=self.ENTRY_NORMAL_BORDER,
                    highlightcolor=self.ENTRY_ACTIVE_BORDER,
                    bg="white",
                    insertbackground=self.ENTRY_ACTIVE_BORDER,
                )
            elif isinstance(target, ttk.Combobox):
                self._safe_config(target, style="Touch.TCombobox")
        if isinstance(getattr(self, "active_entry", None), tk.Entry):
            self._show_active_entry(self.active_entry)

    def _mark_invalid(self, widgets) -> None:
        for widget in widgets:
            if isinstance(widget, tk.Entry):
                self._safe_config(
                    widget,
                    highlightthickness=2,
                    highlightbackground=self.ENTRY_INVALID_BORDER,
                    highlightcolor=self.ENTRY_INVALID_BORDER,
                    bg="#fff1f1",
                    insertbackground=self.ENTRY_INVALID_BORDER,
                )
            elif isinstance(widget, ttk.Combobox):
                self._safe_config(widget, style="Invalid.Touch.TCombobox")

    def _safe_config(self, widget, **options) -> None:
        try:
            widget.config(**options)
            return
        except tk.TclError:
            pass
        for key, value in options.items():
            try:
                widget.config(**{key: value})
            except tk.TclError:
                pass

    def _set_entry_text(self, entry: tk.Entry, value: str, *, placeholder: str | None = None) -> None:
        self._suppress_field_events = True
        try:
            entry.delete(0, "end")
            if value:
                entry.insert(0, value)
                self._safe_config(entry, fg="#111111")
            elif placeholder:
                add_placeholder(entry, placeholder)
            else:
                self._safe_config(entry, fg="#111111")
        finally:
            self._suppress_field_events = False

    def _reset_form(self) -> None:
        self._clear_validation()
        for var in (
            self.ime_var,
            self.roditelj_var,
            self.mjesto_var,
            self.opstina_var,
            self.razred_var,
            self.struka_var,
            self.razlog_var,
            self.dan_var,
            self.mjesec_var,
        ):
            var.set("")
        self.godina_var.set("20")
        self._set_entry_text(self.ime_entry, "")
        self._set_entry_text(self.roditelj_entry, "")
        self._set_entry_text(self.godina_entry, "20")
        self._set_entry_text(self.mjesec_entry, "")
        self._set_entry_text(self.dan_entry, "")
        self._set_entry_text(self.mjesto_entry, "", placeholder=config.MJESTO_PLACEHOLDER)
        self._set_entry_text(self.opstina_entry, "", placeholder=config.OPSTINA_PLACEHOLDER)
        if self.kbd:
            self.kbd.set_active_entry(self.ime_entry)

    def _apply_form_data(self, data: dict) -> None:
        ime_ucenika = str(data.get("ime_ucenika") or "").strip()
        prezime = str(data.get("prezime") or "").strip()
        if not ime_ucenika and not prezime:
            parts = str(data.get("ime") or "").strip().split()
            if parts:
                ime_ucenika = parts[0]
                prezime = " ".join(parts[1 : self.STUDENT_NAME_MAX_WORDS])
        self._set_entry_text(self.ime_entry, self._normalize_student_name(f"{ime_ucenika} {prezime}".strip()))
        self._set_entry_text(self.roditelj_entry, self._normalize_single_word(str(data.get("roditelj", ""))))
        godina = "".join(ch for ch in str(data.get("godina", "")) if ch.isdigit())
        if len(godina) >= 4:
            godina = godina[:4]
        elif len(godina) <= 2:
            godina = "20" + godina[-2:]
        self._set_entry_text(self.godina_entry, godina or "20")
        self._set_entry_text(self.mjesec_entry, "".join(ch for ch in str(data.get("mjesec", "")) if ch.isdigit())[:2])
        self._set_entry_text(self.dan_entry, "".join(ch for ch in str(data.get("dan", "")) if ch.isdigit())[:2])
        self._set_entry_text(self.mjesto_entry, self._normalize_title(str(data.get("mjesto", ""))), placeholder=config.MJESTO_PLACEHOLDER)
        self._set_entry_text(self.opstina_entry, self._normalize_title(str(data.get("opstina", ""))), placeholder=config.OPSTINA_PLACEHOLDER)
        self.razred_var.set(data.get("razred", ""))
        self.struka_var.set(data.get("struka", ""))
        self.razlog_var.set(data.get("razlog", ""))

    def _parse_birth_date(self) -> tuple[datetime.date | None, str]:
        year_raw = self.godina_var.get().strip()
        month_raw = self.mjesec_var.get().strip()
        day_raw = self.dan_var.get().strip()
        if len(year_raw) != 4 or not year_raw.startswith("20"):
            return None, "Година рођења мора бити у формату 20xx."
        if len(month_raw) not in {1, 2} or len(day_raw) not in {1, 2}:
            return None, "Унесите исправан датум рођења."
        try:
            year = int(year_raw)
            month = int(month_raw)
            day = int(day_raw)
        except (TypeError, ValueError):
            return None, "Датум рођења није исправан."
        if not 2000 <= year <= 2099:
            return None, "Година рођења мора бити од 2000 до 2099."
        if year_raw not in self._student_birth_years():
            return None, "Година рођења није у дозвољеном распону за ученике."
        if not 1 <= month <= 12:
            return None, "Мјесец мора бити од 1 до 12."
        max_day = calendar.monthrange(year, month)[1]
        if not 1 <= day <= max_day:
            return None, "Датум рођења није исправан. Провјерите дан, мјесец и годину."
        return datetime.date(year, month, day), ""

    def fill_debug_data(self) -> None:
        try:
            combined_name = f"{config.DEBUG_DATA.get('IME', '')} {config.DEBUG_DATA.get('PREZIME', '')}".strip()
            self._set_entry_text(self.ime_entry, self._normalize_student_name(combined_name))
            self._set_entry_text(self.roditelj_entry, self._normalize_single_word(config.DEBUG_DATA["RODITELJ"]))
            self._set_entry_text(self.godina_entry, str(config.DEBUG_DATA["GODINA"]))
            self._set_entry_text(self.mjesec_entry, str(config.DEBUG_DATA["MJESEC"]))
            self._set_entry_text(self.dan_entry, str(config.DEBUG_DATA["DAN"]))
            self._set_entry_text(self.mjesto_entry, self._normalize_title(config.DEBUG_DATA["MJESTO"]))
            self._set_entry_text(self.opstina_entry, self._normalize_title(config.DEBUG_DATA["OPSTINA"]))
            self.razred_var.set(config.DEBUG_DATA["RAZRED"])
            self.struka_var.set(config.DEBUG_DATA["STRUKA"])
            self.razlog_var.set(config.DEBUG_DATA["RAZLOG"])
        except Exception as e:
            log_error(f"[UI] Failed to fill debug data: {e}")


    def _go_back_to_start_from_touch(self, event=None):
        """Return to the start screen and wipe any partially entered form data."""
        try:
            if hasattr(self, "back_to_start_button"):
                self.back_to_start_button.config(bg="#8B1D1D")
            self._reset_form()
            self._clear_keyboard_active()
            if self.manager:
                self.manager.clear_state()
                self.manager.show_frame(screen_ids.START, force=True)
        except Exception as e:
            log_error(f"[UI] Failed to return to start screen: {e}")
            self.validation_label.config(text="Није могуће вратити се на почетак. Рестартујте апликацију.")
        return "break"

    def _submit_from_touch(self, event=None):
        self.next_button.config(bg="#000000")
        self.submit()
        return "break"

    def submit(self):
        try:
            return self._submit_impl()
        except Exception as e:
            log_error(f"[UI] Form submit failed: {e}")
            self.validation_label.config(text="Није могуће наставити. Провјерите податке или рестартујте апликацију.")
            return None

    def _submit_impl(self):
        self._clear_validation()
        self._sanitize_student_name_now(self.ime_entry)
        self._sanitize_single_word_now(self.roditelj_entry)
        self._student_name_focus_out(type("Event", (), {"widget": self.ime_entry})())
        self._single_word_focus_out(type("Event", (), {"widget": self.roditelj_entry})())
        for entry in (self.mjesto_entry, self.opstina_entry):
            self._titlecase_entry(type("Event", (), {"widget": entry})())
        self._on_year_input()
        self._on_month_input()
        self._on_day_input()

        ime_ucenika, prezime = self._split_student_name(self.ime_entry.get())
        ime = f"{ime_ucenika} {prezime}".strip()
        roditelj = self._normalize_single_word(self.roditelj_entry.get())
        mjesto = self._normalize_title(self.mjesto_entry.get())
        opstina = self._normalize_title(self.opstina_entry.get())
        razred = self.razred_var.get().strip()
        struka = self.struka_var.get().strip()
        razlog = self.razlog_var.get().strip()

        missing = []
        invalid_widgets = []
        if not ime_ucenika or not prezime:
            missing.append("Име и презиме ученика (2 до 3 ријечи)")
            invalid_widgets.append(self.ime_entry)
        if not roditelj:
            missing.append("Име родитеља")
            invalid_widgets.append(self.roditelj_entry)
        if len(self.godina_var.get().strip()) != 4 or not self.mjesec_var.get() or not self.dan_var.get():
            missing.append("Датум рођења")
            if len(self.godina_var.get().strip()) != 4:
                invalid_widgets.append(self.godina_entry)
            if not self.mjesec_var.get():
                invalid_widgets.append(self.mjesec_entry)
            if not self.dan_var.get():
                invalid_widgets.append(self.dan_entry)
        if not mjesto or mjesto == config.MJESTO_PLACEHOLDER:
            missing.append("Мјесто рођења")
            invalid_widgets.append(self.mjesto_entry)
        if not opstina or opstina == config.OPSTINA_PLACEHOLDER:
            missing.append("Општина рођења")
            invalid_widgets.append(self.opstina_entry)
        if not razred:
            missing.append("Разред")
            invalid_widgets.append(self.razred_cb)
        if not struka:
            missing.append("Струка")
            invalid_widgets.append(self.struka_cb)
        if not razlog:
            missing.append("Разлог")
            invalid_widgets.append(self.razlog_cb)

        if missing:
            self._mark_invalid(invalid_widgets)
            self.validation_label.config(text="Попуните означена поља: " + ", ".join(missing))
            if invalid_widgets:
                self._focus_widget(invalid_widgets[0])
            return None

        birth_date, date_error = self._parse_birth_date()
        if date_error or birth_date is None:
            self._mark_invalid([self.godina_entry, self.mjesec_entry, self.dan_entry])
            self.validation_label.config(text=date_error)
            self._focus_entry(self.godina_entry)
            return None

        day = f"{birth_date.day:02d}"
        month = f"{birth_date.month:02d}"
        year = str(birth_date.year)

        form_data = {
            "ime": ime,
            "ime_ucenika": ime_ucenika,
            "prezime": prezime,
            "roditelj": roditelj,
            "mjesto": mjesto,
            "opstina": opstina,
            "razred": razred,
            "struka": struka,
            "razlog": razlog,
            "dan": day,
            "mjesec": month,
            "godina": year,
        }

        self._set_entry_text(self.ime_entry, ime)
        self._set_entry_text(self.roditelj_entry, roditelj)
        self._set_entry_text(self.godina_entry, year)
        self._set_entry_text(self.mjesec_entry, month)
        self._set_entry_text(self.dan_entry, day)
        self._set_entry_text(self.mjesto_entry, mjesto, placeholder=config.MJESTO_PLACEHOLDER)
        self._set_entry_text(self.opstina_entry, opstina, placeholder=config.OPSTINA_PLACEHOLDER)

        if self.manager:
            self.manager.state["form_data"] = form_data
            self.manager.show_frame(screen_ids.REVIEW)
            if self.manager.current_frame_name != screen_ids.REVIEW:
                raise RuntimeError("Review screen did not open.")
        return None
