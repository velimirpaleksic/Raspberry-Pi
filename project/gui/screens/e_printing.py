import threading
import tkinter as tk

from project.gui import screen_ids
from project.gui.ui_components import TouchButton
from project.services.print_job import PrintResult, run_print_job
from project.utils.logging_utils import log_error


STATUS_TEXT = {
    "CHECK_PRINTER": "Провјеравам штампач…",
    "BUILD": "Припремам податке…",
    "DOCX": "Генеришем DOCX…",
    "PDF": "Чувам PDF…",
    "PRINT": "Шаљем на штампу…",
    "OUTSIDE_WORKING_HOURS": "Терминал није доступан",
}

USER_ERROR_TITLE = "ДОШЛО ЈЕ ДО ГРЕШКЕ"
USER_ERROR_MESSAGE = "Молимо вас, јавите се у секретаријат."
ERROR_RETURN_SECONDS = 10


class PrintingScreen(tk.Frame):
    """Run printing job with progress and retry flow."""

    def __init__(self, parent, manager=None):
        super().__init__(parent, bg="#f5f5f5")
        self.manager = manager
        self._worker = None
        self._is_busy = False
        self._last_result: PrintResult | None = None
        self._run_token = 0
        self._error_countdown_after_id = None
        self._error_seconds_left = ERROR_RETURN_SECONDS

        outer = tk.Frame(self, bg="#f5f5f5", padx=24, pady=24)
        outer.pack(fill="both", expand=True)

        tk.Label(outer, text="ШТАМПАЊЕ", font=("Arial", 30, "bold"), bg="#f5f5f5", fg="#111111").pack(pady=(22, 10))

        self.status_label = tk.Label(outer, text="", font=("Arial", 22), bg="#f5f5f5", fg="#111111")
        self.status_label.pack(pady=12)

        self.error_box = tk.Frame(outer, bg="white", bd=1, relief="solid", padx=24, pady=24)
        self.error_title = tk.Label(self.error_box, text="", font=("Arial", 24, "bold"), fg="#a11f1f", bg="white")
        self.error_msg = tk.Label(self.error_box, text="", font=("Arial", 18), wraplength=920, justify="center", bg="white", fg="#111111")
        self.error_detail = tk.Label(self.error_box, text="", font=("Arial", 13), wraplength=920, justify="center", fg="#555555", bg="white")
        self.error_countdown = tk.Label(
            self.error_box,
            text="",
            font=("Arial", 16, "bold"),
            wraplength=920,
            justify="center",
            fg="#8B1D1D",
            bg="white",
        )
        self.error_title.pack(pady=(0, 8))
        self.error_msg.pack()
        self.error_detail.pack(pady=(10, 0))
        self.error_countdown.pack(pady=(14, 0))

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
            text="ПОЧЕТАК",
            font=("Arial", 18, "bold"),
            padx=28,
            pady=14,
            command=self._go_home,
            bg="#dddddd",
            fg="#111111",
            activebackground="#e7e7e7",
            activeforeground="#111111",
        )

        self._set_error_visible(False)

    def on_show(self):
        if self._is_busy:
            return
        self._cancel_error_countdown()
        if self.manager:
            self.manager.set_idle_suspended(True)

        self._last_result = None
        self._set_error_visible(False)
        self._set_status("BUILD")

        form_data = (self.manager.state.get("form_data") if self.manager else None)
        if not form_data:
            self._go_home()
            return

        self._is_busy = True
        self._run_token += 1
        current_token = self._run_token
        self.retry_btn.config(state="disabled")
        self._worker = threading.Thread(target=self._run, args=(form_data, current_token), daemon=True)
        self._worker.start()

    def on_hide(self):
        self._cancel_error_countdown()
        # A Python print thread cannot be force-stopped safely. Keep the busy
        # flag until it really completes so returning to this screen can never
        # start a parallel job. Screen checks below make its old UI callbacks
        # harmless while another screen is visible.

    def _schedule_ui(self, callback):
        manager = self.manager
        if manager is None or bool(getattr(manager, "_is_closing", False)):
            return False
        try:
            manager.post_ui_action(callback)
            return True
        except Exception as exc:
            log_error(f"[PRINT UI] Failed to queue UI callback: {exc}")
            return False

    def _run(self, form_data: dict, run_token: int):
        def on_status(code: str):
            self._schedule_ui(lambda: self._set_status_if_current(code, run_token))

        try:
            result = run_print_job(form_data, on_status=on_status, do_print=True)
        except Exception as exc:
            log_error(f"[PRINT UI] Unhandled print worker error: {exc}")
            result = PrintResult(
                False,
                "",
                error_code="PRINT_WORKER_EXCEPTION",
                user_message=USER_ERROR_MESSAGE,
                detail=repr(exc),
            )
        self._schedule_ui(lambda: self._finish_run_if_current(result, run_token))

    def _set_status_if_current(self, code: str, run_token: int):
        if (
            run_token != self._run_token
            or not self.winfo_exists()
            or (self.manager and getattr(self.manager, "current_frame_name", None) != screen_ids.PRINTING)
        ):
            return
        self._set_status(code)

    def _finish_run_if_current(self, result: PrintResult, run_token: int):
        if run_token != self._run_token or not self.winfo_exists():
            return
        if self.manager and getattr(self.manager, "current_frame_name", None) != screen_ids.PRINTING:
            self._last_result = result
            self._is_busy = False
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
        if result.error_code == "OUTSIDE_WORKING_HOURS":
            self.status_label.config(text="Радно вријеме је завршено")
            self.error_title.config(text="ТЕРМИНАЛ НИЈЕ ДОСТУПАН")
            self.error_msg.config(text=result.user_message or "Терминал тренутно није доступан.")
        else:
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
        self._start_error_countdown()

    def _success(self):
        self._cancel_error_countdown()
        self._is_busy = False
        if self.manager:
            self.manager.set_idle_suspended(False)
            self.manager.state["last_job_id"] = self._last_result.job_id if self._last_result else None
            self.manager.state["last_pdf_path"] = self._last_result.pdf_path if self._last_result else None
            self.manager.show_frame(screen_ids.DONE)

    def _retry(self):
        if self._is_busy:
            return
        self._cancel_error_countdown()
        self.on_show()

    def _start_error_countdown(self):
        self._cancel_error_countdown()
        self._error_seconds_left = ERROR_RETURN_SECONDS
        self._update_error_countdown()

    def _cancel_error_countdown(self):
        if self._error_countdown_after_id is not None:
            try:
                self.after_cancel(self._error_countdown_after_id)
            except Exception:
                pass
            self._error_countdown_after_id = None

    def _update_error_countdown(self):
        self._error_countdown_after_id = None
        if self.manager and getattr(self.manager, "current_frame_name", None) != screen_ids.PRINTING:
            return

        if self._error_seconds_left <= 0:
            self._go_home()
            return

        try:
            self.error_countdown.config(
                text=f"Повратак на почетак за {self._error_seconds_left} с"
            )
            self._error_seconds_left -= 1
            self._error_countdown_after_id = self.after(1000, self._update_error_countdown)
        except Exception as exc:
            log_error(f"[PRINT UI] Error countdown failed: {exc}")
            self._go_home()

    def _go_home(self):
        self._cancel_error_countdown()
        if self.manager:
            self.manager.clear_state()
            self.manager.set_idle_suspended(True)
            self.manager.show_frame(screen_ids.START, force=True)
