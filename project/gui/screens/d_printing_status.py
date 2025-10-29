# gui/screens/d_printing_status.py
import os
import traceback
import tkinter as tk
from typing import Optional, Callable, Any

from project.core.config import OUTPUT_FILE, TEMPLATE_FILE, \
                                DJELOVODNI_BROJ, DANASNJI_DATUM
from project.db.db_insert_query import insert_entry

from project.utils.docs.docx_replace_placeholders import replace_dynamic_text
from project.utils.docs.pdf_converter import convert_docx_to_pdf

from project.utils.printing.print_with_hplip import print_with_hplip

from project.utils import clean_project
from project.utils.logging_utils import error_logging


class PrintingStatusScreen(tk.Frame):
    """Screen that shows processing/printing status."""

    def __init__(self, parent, manager: Optional[object] = None):
        super().__init__(parent)
        self.manager = manager
        self._last_job_kwargs = None

    def _retry_last(self):
        if self._last_job_kwargs:
            self.process_data(**self._last_job_kwargs)
        else:
            print("Nothing to retry")

    def _on_job_success(self, result: Any):
        try:
            if self.manager and "SuccessScreen" in getattr(self.manager, "frames", {}):
                self.after(2000, lambda: self.manager.show_frame("SuccessScreen"))
        except Exception as e:
            error_logging(f"Failed to show SuccessScreen: {e}")

    def _on_job_error(self, exc: Exception):
        tb = traceback.format_exc()
        error_logging(f"Job error: {exc}\n{tb}")

    def process_data(
        self,
        ime: str,
        roditelj: str,
        mjesto: str,
        opstina: str,
        razred: str,
        struka: str,
        razlog: str,
        dan: str,
        mjesec: str,
        godina: str,
        **kwargs
    ):
        """Process a single job (synchronously)."""

        # Save args for retry
        self._last_job_kwargs = dict(
            ime=ime, 
            roditelj=roditelj, 
            mjesto=mjesto, 
            opstina=opstina,
            razred=razred, 
            struka=struka, 
            razlog=razlog,
            dan=dan, 
            mjesec=mjesec, 
            godina=godina, 
            **kwargs
        )

        do_print = kwargs.get("do_print", True)
        on_success_cb: Optional[Callable[[Any], None]] = kwargs.get("on_success")
        on_error_cb: Optional[Callable[[Exception], None]] = kwargs.get("on_error")

        try:
            # 1) Prepare placeholders and generate DOCX
            datum_rodjenja = f"{dan}.{mjesec}.{godina}"
            placeholders = {
                "{{DJELOVODNI_BROJ}}": DJELOVODNI_BROJ,
                "{{DANASNJI_DATUM}}": DANASNJI_DATUM,
                "{{IME}}": ime,
                "{{RODITELJ}}": roditelj,
                "{{DATUM_RODJENJA}}": datum_rodjenja,
                "{{MJESTO}}": mjesto,
                "{{OPSTINA}}": opstina,
                "{{RAZRED}}": razred,
                "{{STRUKA}}": struka,
                "{{RAZLOG}}": razlog,
            }

            # 2) Insert into DB
            if kwargs.get("do_db_insert", True):
                insert_entry(
                    ime=ime,
                    roditelj=roditelj,
                    godina=int(godina),
                    mjesec=int(mjesec),
                    dan=int(dan),
                    mjesto=mjesto,
                    opstina=opstina,
                    razred=razred,
                    struka=struka,
                    razlog=razlog
                )

            # 3) Replace dynamic text in DOCX template file
            os.makedirs(os.path.dirname(OUTPUT_FILE) or ".", exist_ok=True)
            replace_dynamic_text(TEMPLATE_FILE, OUTPUT_FILE, placeholders)

            # 4) Convert to PDF
            pdf_path = convert_docx_to_pdf(OUTPUT_FILE)

            # 5) Print PDF file
            #print_with_hplip(pdf_path)

            # 6) Delete leftover print files (both .docx and .pdf)
            clean_project.delete_print_queue()

            result = {"docx": OUTPUT_FILE, "pdf": pdf_path, "printed": do_print}
            self._on_job_success(result)
            if on_success_cb:
                on_success_cb(result)

        except Exception as e:
            self._on_job_error(e)
            if on_error_cb:
                on_error_cb(e)