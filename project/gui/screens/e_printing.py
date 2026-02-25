import threading
import tkinter as tk

from project.gui import screen_ids
from project.services.print_job import run_print_job, PrintResult


STATUS_TEXT = {
    "CHECK_PRINTER": "Провјеравам printer…",
    "BUILD": "Припремам документ…",
    "DB": "Евиденција…",
    "DOCX": "Генеришем документ…",
    "PDF": "Претварам у PDF…",
    "PRINT": "Шаљем на printer…",
}


class PrintingScreen(tk.Frame):
    """Step 3/3: Run printing job with progress + dumb-proof errors."""

    def __init__(self, parent, manager=None):
        super().__init__(parent)
        self.manager = manager
        self._worker = None
        self._last_result: PrintResult | None = None

        self.title = tk.Label(self, text="Штампање", font=("Arial", 28, "bold"))
        self.title.pack(pady=(30, 10))

        self.status_label = tk.Label(self, text="", font=("Arial", 18))
        self.status_label.pack(pady=10)

        self.error_box = tk.Frame(self)
        self.error_box.pack(pady=10)

        self.error_title = tk.Label(self.error_box, text="", font=("Arial", 18, "bold"), fg="red")
        self.error_msg = tk.Label(self.error_box, text="", font=("Arial", 16), wraplength=900, justify="center")
        self.error_title.pack(pady=(0, 6))
        self.error_msg.pack()

        self.btns = tk.Frame(self)
        self.btns.pack(pady=30)
        self.retry_btn = tk.Button(self.btns, text="Покушај поново", padx=18, pady=10, command=self._retry)
        self.home_btn = tk.Button(self.btns, text="Назад на почетак", padx=18, pady=10, command=self._home)

        # Hidden initially
        self._set_error_visible(False)

    def on_show(self):
        # Don't idle-reset while printing
        if self.manager:
            self.manager.set_idle_suspended(True)

        self._set_error_visible(False)
        self._set_status("CHECK_PRINTER")

        form_data = (self.manager.state.get("form_data") if self.manager else None)
        if not form_data:
            # Nothing to print; go home
            self._home()
            return

        # Start background job
        self._worker = threading.Thread(
            target=self._run,
            args=(form_data,),
            daemon=True,
        )
        self._worker.start()

    def _run(self, form_data: dict):
        def on_status(code: str):
            self.after(0, lambda: self._set_status(code))

        result = run_print_job(form_data, on_status=on_status, do_print=True, do_db_insert=True)
        self._last_result = result

        if result.ok:
            self.after(0, self._success)
        else:
            self.after(0, lambda: self._show_error(result))

    def _set_status(self, code: str):
        self.status_label.config(text=STATUS_TEXT.get(code, "…"))

    def _set_error_visible(self, visible: bool):
        if visible:
            self.error_box.pack(pady=10)
            self.retry_btn.pack(side="left", padx=10)
            self.home_btn.pack(side="left", padx=10)
        else:
            self.error_box.pack_forget()
            self.retry_btn.pack_forget()
            self.home_btn.pack_forget()

    def _show_error(self, result: PrintResult):
        self._set_status("")
        self.error_title.config(text="Није могуће одштампати")
        self.error_msg.config(text=result.user_message or "Провјерите printer i покушајте поново.")
        self._set_error_visible(True)
        if self.manager:
            self.manager.set_idle_suspended(False)

    def _success(self):
        if self.manager:
            self.manager.set_idle_suspended(False)
            self.manager.state["last_job_id"] = self._last_result.job_id if self._last_result else None
            self.manager.show_frame(screen_ids.DONE)

    def _retry(self):
        # Simply rerun on_show
        self.on_show()

    def _home(self):
        if self.manager:
            self.manager.set_idle_suspended(False)
            self.manager.clear_state()
            self.manager.show_frame(screen_ids.START)
