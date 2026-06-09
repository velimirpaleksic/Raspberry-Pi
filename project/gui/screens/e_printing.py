import threading
import tkinter as tk

from project.gui import screen_ids
from project.gui.ui_components import TouchButton
from project.services.print_job import PrintResult, run_print_job


STATUS_TEXT = {
    "CHECK_PRINTER": "Провјеравам штампач…",
    "BUILD": "Припремам податке…",
    "DOCX": "Генеришем DOCX…",
    "PDF": "Чувам PDF…",
    "PRINT": "Шаљем на штампу…",
}

USER_ERROR_TITLE = "ДОШЛО ЈЕ ДО ГРЕШКЕ"
USER_ERROR_MESSAGE = "Молимо вас, јавите се у секретаријат."


class PrintingScreen(tk.Frame):
    """Run printing job with progress and retry flow."""

    def __init__(self, parent, manager=None):
        super().__init__(parent, bg="#f5f5f5")
        self.manager = manager
        self._worker = None
        self._is_busy = False
        self._last_result: PrintResult | None = None
        self._run_token = 0

        outer = tk.Frame(self, bg="#f5f5f5", padx=24, pady=24)
        outer.pack(fill="both", expand=True)

        tk.Label(outer, text="ШТАМПАЊЕ", font=("Arial", 30, "bold"), bg="#f5f5f5", fg="#111111").pack(pady=(22, 10))

        self.status_label = tk.Label(outer, text="", font=("Arial", 22), bg="#f5f5f5", fg="#111111")
        self.status_label.pack(pady=12)

        self.error_box = tk.Frame(outer, bg="white", bd=1, relief="solid", padx=24, pady=24)
        self.error_title = tk.Label(self.error_box, text="", font=("Arial", 24, "bold"), fg="#a11f1f", bg="white")
        self.error_msg = tk.Label(self.error_box, text="", font=("Arial", 18), wraplength=920, justify="center", bg="white", fg="#111111")
        self.error_detail = tk.Label(self.error_box, text="", font=("Arial", 13), wraplength=920, justify="center", fg="#555555", bg="white")
        self.error_title.pack(pady=(0, 8))
        self.error_msg.pack()
        self.error_detail.pack(pady=(10, 0))

        self.btns = tk.Frame(outer, bg="#f5f5f5")
        self.btns.pack(pady=30)
        self.retry_btn = TouchButton(
            self.btns,
            text="ПОКУШАЈ ПОНОВО",
            font=("Arial", 18, "bold"),
            padx=28,
            pady=14,
            command=self._retry,
            bg="#111111",
            fg="white",
            activebackground="#202020",
            activeforeground="white",
        )
        self.back_btn = TouchButton(
            self.btns,
            text="НАЗАД",
            font=("Arial", 18, "bold"),
            padx=28,
            pady=14,
            command=self._go_review,
            bg="#dddddd",
            fg="#111111",
            activebackground="#e7e7e7",
            activeforeground="#111111",
        )

        self._set_error_visible(False)

    def on_show(self):
        if self._is_busy:
            return
        if self.manager:
            self.manager.set_idle_suspended(True)

        self._last_result = None
        self._set_error_visible(False)
        self._set_status("CHECK_PRINTER")

        form_data = (self.manager.state.get("form_data") if self.manager else None)
        if not form_data:
            self._go_review()
            return

        self._is_busy = True
        self._run_token += 1
        current_token = self._run_token
        self.retry_btn.config(state="disabled")
        self._worker = threading.Thread(target=self._run, args=(form_data, current_token), daemon=True)
        self._worker.start()

    def _schedule_ui(self, callback):
        try:
            manager_closing = bool(self.manager and getattr(self.manager, "_is_closing", False))
            if manager_closing or not self.winfo_exists():
                return False
            self.after(0, callback)
            return True
        except Exception:
            return False

    def _run(self, form_data: dict, run_token: int):
        def on_status(code: str):
            self._schedule_ui(lambda: self._set_status_if_current(code, run_token))

        result = run_print_job(form_data, on_status=on_status, do_print=True)
        self._schedule_ui(lambda: self._finish_run_if_current(result, run_token))

    def _set_status_if_current(self, code: str, run_token: int):
        if run_token != self._run_token or not self.winfo_exists():
            return
        self._set_status(code)

    def _finish_run_if_current(self, result: PrintResult, run_token: int):
        if run_token != self._run_token or not self.winfo_exists():
            return
        self._last_result = result
        if result.ok:
            self._success()
        else:
            self._show_error(result)

    def _set_status(self, code: str):
        self.status_label.config(text=STATUS_TEXT.get(code, "…"))

    def _derive_error_header(self, result: PrintResult) -> tuple[str, str]:
        code = result.error_code or ""
        print_related = code.startswith("PRN_") or code.startswith("PRINT") or code.startswith("CUPS_")
        if print_related and not result.pdf_path:
            return (
                "Штампа није могућа",
                "Printer nije spreman, pa dokument nije generisan niti poslan na štampu.",
            )
        if result.pdf_path and print_related:
            return (
                "PDF је генерисан, али штампа није успјела",
                "Dokument je sačuvan kao PDF. Problem je u printeru ili CUPS podešavanju.",
            )
        if result.docx_path and not result.pdf_path:
            return (
                "DOCX је генерисан, али PDF није",
                "Template i podaci su obrađeni, ali konverzija u PDF nije uspjela.",
            )
        return (
            "Документ није генерисан",
            "Greška se desila prije nego što je nastao završni PDF za štampu.",
        )

    def _set_error_visible(self, visible: bool):
        if visible:
            self.error_box.pack(pady=10)
            self.retry_btn.pack(side="left", padx=10)
            self.back_btn.pack(side="left", padx=10)
        else:
            self.error_box.pack_forget()
            self.retry_btn.pack_forget()
            self.back_btn.pack_forget()

    def _show_error(self, result: PrintResult):
        """Show only a safe, simple kiosk message.

        Technical printer/CUPS/PDF details are saved in the job log and sent to
        Telegram from the print service. The touchscreen must not expose raw
        paths, error codes, stack traces, or printer diagnostics to students.
        """
        self._is_busy = False
        self.status_label.config(text="Дошло је до грешке")
        self.error_title.config(text=USER_ERROR_TITLE)
        self.error_msg.config(text=USER_ERROR_MESSAGE)
        self.error_detail.config(text="")
        try:
            self.error_detail.pack_forget()
        except Exception:
            pass
        self.retry_btn.config(state="normal")
        self.back_btn.config(state="normal")
        self._set_error_visible(True)
        if self.manager:
            self.manager.state["last_pdf_path"] = result.pdf_path
            self.manager.state["last_print_error_code"] = result.error_code
            self.manager.set_idle_suspended(True)

    def _success(self):
        self._is_busy = False
        if self.manager:
            self.manager.set_idle_suspended(False)
            self.manager.state["last_job_id"] = self._last_result.job_id if self._last_result else None
            self.manager.state["last_pdf_path"] = self._last_result.pdf_path if self._last_result else None
            self.manager.show_frame(screen_ids.DONE)

    def _retry(self):
        if self._is_busy:
            return
        self.on_show()

    def _go_review(self):
        if self.manager:
            self.manager.set_idle_suspended(True)
            self.manager.show_frame(screen_ids.REVIEW)
