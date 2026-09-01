# gui/ui_components.py
import tkinter as tk


def paginate_values(values, page: int, page_size: int) -> tuple[list, int, int]:
    """Return (visible values, clamped page, page count)."""

    items = list(values)
    size = max(1, int(page_size))
    page_count = max(1, (len(items) + size - 1) // size)
    current_page = max(0, min(int(page), page_count - 1))
    start = current_page * size
    return items[start : start + size], current_page, page_count


def add_placeholder(entry: tk.Entry, placeholder: str):
    """Add placeholder text to an Entry (gray), clears on focus, restores on focusout."""
    entry.delete(0, "end")
    entry.insert(0, placeholder)
    entry.config(fg="#7a7a7a")

    previous_focus_in = getattr(entry, "_placeholder_focus_in_id", None)
    previous_focus_out = getattr(entry, "_placeholder_focus_out_id", None)
    if previous_focus_in:
        try:
            entry.unbind("<FocusIn>", previous_focus_in)
        except Exception:
            pass
    if previous_focus_out:
        try:
            entry.unbind("<FocusOut>", previous_focus_out)
        except Exception:
            pass

    def on_focus_in(event):
        if entry.get() == placeholder:
            entry.delete(0, "end")
            entry.config(fg="#111111")

    def on_focus_out(event):
        if not entry.get():
            entry.insert(0, placeholder)
            entry.config(fg="#7a7a7a")

    entry._placeholder_focus_in_id = entry.bind("<FocusIn>", on_focus_in, add=True)
    entry._placeholder_focus_out_id = entry.bind("<FocusOut>", on_focus_out, add=True)


class TouchButton(tk.Label):
    """Press-event button for resistive touchscreens.

    Normal tk.Button calls its command on ButtonRelease. On older resistive
    touch panels a release can land outside the widget, so the UI visibly
    presses but the command never runs. This label-based button triggers on
    <ButtonPress-1> and uses the whole rectangular widget as the hitbox.
    """

    def __init__(
        self,
        parent,
        *,
        text: str,
        command=None,
        bg: str = "#111111",
        fg: str = "white",
        activebackground: str | None = None,
        activeforeground: str | None = None,
        **kwargs,
    ):
        self.command = command
        self.normal_bg = bg
        self.normal_fg = fg
        self.active_bg = activebackground or bg
        self.active_fg = activeforeground or fg
        self._touch_enabled = True
        super().__init__(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            bd=0,
            relief="flat",
            cursor="none",
            takefocus=0,
            **kwargs,
        )
        self.bind("<ButtonPress-1>", self._on_press, add=False)
        self.bind("<ButtonRelease-1>", self._on_release, add=False)
        self.bind("<Leave>", self._on_release, add=False)

    def _on_press(self, event=None):
        if not self._touch_enabled:
            return "break"
        try:
            super().config(bg=self.active_bg, fg=self.active_fg)
        except Exception:
            pass
        try:
            self.after(90, self._restore)
        except Exception:
            pass
        if callable(self.command):
            self.command()
        return "break"

    def _on_release(self, event=None):
        self._restore()
        return "break"

    def _restore(self):
        try:
            super().config(bg=self.normal_bg, fg=self.normal_fg)
        except Exception:
            pass

    def configure(self, cnf=None, **kwargs):
        state = kwargs.pop("state", None)
        if state is not None:
            self._touch_enabled = str(state) != "disabled"
        if cnf:
            return super().configure(cnf, **kwargs)
        return super().configure(**kwargs)

    config = configure


class TouchListPicker(tk.Label):
    """Large paged selector that does not depend on drag or multitouch."""

    NORMAL_BORDER = "#b8b8b8"
    INVALID_BORDER = "#a11f1f"

    def __init__(
        self,
        parent,
        *,
        textvariable: tk.StringVar,
        values,
        overlay_parent=None,
        page_size: int = 5,
        on_selected=None,
        placeholder: str = "Изаберите разлог",
        ui_scale: float = 1.0,
        **kwargs,
    ):
        self.variable = textvariable
        self.values = list(values)
        self.overlay_parent = overlay_parent or parent.winfo_toplevel()
        self.page_size = max(1, int(page_size))
        self.on_selected = on_selected
        self.placeholder = placeholder
        self.ui_scale = max(1.0, float(ui_scale or 1.0))
        self._page = 0
        self._overlay = None
        self._rows_frame = None
        self._page_label = None
        self._display_var = tk.StringVar(value="")
        self._trace_id = self.variable.trace_add("write", self._sync_display)
        self._sync_display()

        super().__init__(
            parent,
            textvariable=self._display_var,
            anchor="w",
            justify="left",
            bg="white",
            fg="#111111",
            relief="solid",
            bd=1,
            highlightthickness=2,
            highlightbackground=self.NORMAL_BORDER,
            highlightcolor="#111111",
            cursor="none",
            takefocus=1,
            **kwargs,
        )
        self.bind("<ButtonPress-1>", self._open_from_event, add=False)
        self.bind("<Return>", self._open_from_event, add=False)
        self.bind("<space>", self._open_from_event, add=False)

    def _sync_display(self, *_args) -> None:
        selected = str(self.variable.get() or "").strip()
        self._display_var.set(f"{selected or self.placeholder}   ▼")

    def _open_from_event(self, event=None):
        self.open()
        return "break"

    def open(self) -> None:
        selected = str(self.variable.get() or "").strip()
        if selected in self.values:
            self._page = self.values.index(selected) // self.page_size
        self._ensure_overlay()
        self._render_page()
        self._overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._overlay.lift()
        try:
            self._overlay.focus_force()
            self._overlay.grab_set()
        except Exception:
            pass

    def close(self) -> None:
        if self._overlay is None:
            return
        try:
            self._overlay.grab_release()
        except Exception:
            pass
        self._overlay.place_forget()

    def set_invalid(self, invalid: bool) -> None:
        color = self.INVALID_BORDER if invalid else self.NORMAL_BORDER
        background = "#fff1f1" if invalid else "white"
        self.config(highlightbackground=color, highlightcolor=color, bg=background)

    def _ensure_overlay(self) -> None:
        if self._overlay is not None:
            return

        overlay = tk.Frame(self.overlay_parent, bg="#101820", cursor="none")
        card = tk.Frame(overlay, bg="#f5f5f5", padx=26, pady=22, bd=1, relief="solid")
        card.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.90, relheight=0.92)

        tk.Label(
            card,
            text="ИЗАБЕРИТЕ РАЗЛОГ",
            font=("Arial", max(24, int(round(24 * self.ui_scale))), "bold"),
            bg="#f5f5f5",
            fg="#111111",
        ).pack(pady=(0, 12))

        self._rows_frame = tk.Frame(card, bg="#f5f5f5")
        self._rows_frame.pack(fill="both", expand=True)

        nav = tk.Frame(card, bg="#f5f5f5")
        nav.pack(fill="x", pady=(12, 0))
        TouchButton(
            nav,
            text="ПРЕТХОДНО",
            command=lambda: self._change_page(-1),
            font=("Arial", max(16, int(round(16 * self.ui_scale))), "bold"),
            padx=20,
            pady=12,
            bg="#dddddd",
            fg="#111111",
            activebackground="#e7e7e7",
            activeforeground="#111111",
        ).pack(side="left")
        self._page_label = tk.Label(
            nav,
            text="",
            font=("Arial", max(15, int(round(15 * self.ui_scale))), "bold"),
            bg="#f5f5f5",
            fg="#444444",
        )
        self._page_label.pack(side="left", expand=True)
        TouchButton(
            nav,
            text="СЉЕДЕЋЕ",
            command=lambda: self._change_page(1),
            font=("Arial", max(16, int(round(16 * self.ui_scale))), "bold"),
            padx=20,
            pady=12,
            bg="#111111",
            fg="white",
            activebackground="#202020",
            activeforeground="white",
        ).pack(side="right")
        TouchButton(
            card,
            text="ЗАТВОРИ",
            command=self.close,
            font=("Arial", max(15, int(round(15 * self.ui_scale))), "bold"),
            padx=24,
            pady=10,
            bg="#8B1D1D",
            fg="white",
            activebackground="#a52323",
            activeforeground="white",
        ).pack(pady=(12, 0))

        self._overlay = overlay

    def _change_page(self, delta: int) -> None:
        _items, current, page_count = paginate_values(self.values, self._page + delta, self.page_size)
        self._page = max(0, min(current, page_count - 1))
        self._render_page()

    def _render_page(self) -> None:
        if self._rows_frame is None:
            return
        for child in self._rows_frame.winfo_children():
            child.destroy()

        items, self._page, page_count = paginate_values(self.values, self._page, self.page_size)
        if self._page_label is not None:
            self._page_label.config(text=f"Страница {self._page + 1}/{page_count}")

        selected = str(self.variable.get() or "").strip()
        for value in items:
            is_selected = value == selected
            TouchButton(
                self._rows_frame,
                text=value,
                command=lambda selected_value=value: self._select(selected_value),
                font=("Arial", max(18, int(round(18 * self.ui_scale))), "bold" if is_selected else "normal"),
                padx=20,
                pady=12,
                wraplength=max(650, int(round(860 * self.ui_scale))),
                justify="left",
                anchor="w",
                bg="#dfeee3" if is_selected else "white",
                fg="#111111",
                activebackground="#cce4d2" if is_selected else "#eeeeee",
                activeforeground="#111111",
            ).pack(fill="both", expand=True, pady=4)

    def _select(self, value: str) -> None:
        self.variable.set(value)
        self.set_invalid(False)
        self.close()
        if callable(self.on_selected):
            self.on_selected(value)

    def destroy(self):
        try:
            self.variable.trace_remove("write", self._trace_id)
        except Exception:
            pass
        if self._overlay is not None:
            try:
                self._overlay.destroy()
            except Exception:
                pass
            self._overlay = None
        super().destroy()


def labeled_entry(parent, label_text, placeholder=None, *, font=("Arial", 16), label_font=("Arial", 16, "bold"), entry_height=1):
    """Return (frame, entry) where label is above entry."""
    f = tk.Frame(parent, bg="white")
    lbl = tk.Label(f, text=label_text, font=label_font, bg="white", fg="#111111")
    lbl.pack(anchor="w")
    ent = tk.Entry(
        f,
        font=font,
        relief="solid",
        bd=1,
        highlightthickness=1,
        highlightbackground="#d8d8d8",
        highlightcolor="#111111",
        bg="white",
        fg="#111111",
        insertbackground="#111111",
    )
    ent.pack(fill="x", expand=True, pady=(3, 0), ipady=max(4, entry_height * 3))
    if placeholder:
        add_placeholder(ent, placeholder)
    return f, ent


# === Helper for consistent top-level window setup ===
def create_dialog(title: str, content_builder, *, root=None, max_ratio=0.8, topmost=True):
    win = tk.Toplevel(root) if root is not None else tk.Toplevel()
    win.title(title)
    if topmost:
        win.attributes("-topmost", True)
    win.resizable(False, False)
    if root is not None:
        try:
            win.transient(root.winfo_toplevel())
        except Exception:
            pass

    content_builder(win, tk)

    win.update_idletasks()
    req_w, req_h = win.winfo_reqwidth(), win.winfo_reqheight()
    screen_w, screen_h = win.winfo_screenwidth(), win.winfo_screenheight()

    width = min(req_w, int(screen_w * max_ratio))
    height = min(req_h, int(screen_h * max_ratio))

    x = (screen_w - width) // 2
    y = (screen_h - height) // 2
    win.geometry(f"{width}x{height}+{x}+{y}")

    win.focus_force()
    win.lift()

    return win


def critical_error_window(root=None, message=None):
    if message is None:
        message = "Десила се критична грешка..."

    def build(win, tk):
        tk.Label(win, text=message, fg="red", wraplength=700, font=("Arial", 16)).pack(padx=24, pady=20)
        TouchButton(win, text="OK", command=win.destroy, font=("Arial", 15, "bold"), padx=16, pady=8, bg="#dddddd", fg="#111111", activebackground="#e7e7e7", activeforeground="#111111").pack(pady=(0, 20))

    return create_dialog("Грешка", build, root=root)


def user_error(root=None, message="Десила се грешка."):
    def build(win, tk):
        tk.Label(win, text="Погрешан унос", font=("Arial", 18, "bold"), fg="red").pack(pady=(14, 8))
        tk.Label(win, text=message, wraplength=760, justify="center", font=("Arial", 15)).pack(padx=24, pady=8)
        TouchButton(win, text="OK", command=win.destroy, bg="#dddddd", fg="#111111", activebackground="#e7e7e7", activeforeground="#111111", width=12, font=("Arial", 14, "bold")).pack(pady=(0, 20), ipady=6)

    return create_dialog("Грешка при уносу", build, root=root)
