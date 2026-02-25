import json
import os
import time
import uuid
import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from project.core import config
from project.db.db_insert_query import insert_entry
from project.utils.docs.docx_replace_placeholders import replace_dynamic_text
from project.utils.docs.pdf_converter import convert_docx_to_pdf
from project.utils.printing.print_with_hplip import print_with_hplip
from project.utils.printing.printer_status import get_printer_readiness
from project.utils.logging_utils import log_error


StatusCallback = Callable[[str], None]


@dataclass(frozen=True)
class PrintResult:
    ok: bool
    job_id: str
    docx_path: Optional[str] = None
    pdf_path: Optional[str] = None
    error_code: Optional[str] = None
    user_message: Optional[str] = None


def _now_local_str() -> str:
    return datetime.datetime.now().strftime("%d.%m.%Y")


def _job_dir(job_id: str) -> Path:
    return config.JOBS_DIR / job_id


def _write_job_json(job_dir: Path, payload: Dict) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "job.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_print_job(
    form_data: Dict,
    *,
    on_status: Optional[StatusCallback] = None,
    do_print: bool = True,
    do_db_insert: bool = True,
) -> PrintResult:
    """Generate DOCX -> convert to PDF -> send to printer.

    This is intentionally *pure backend* (no Tk calls).
    """

    def status(s: str) -> None:
        if on_status:
            on_status(s)

    job_id = str(uuid.uuid4())
    job_dir = _job_dir(job_id)

    # Persist initial job payload early (power-loss friendly)
    payload = {
        "job_id": job_id,
        "created_at": time.time(),
        "state": "created",
        "form_data": form_data,
    }
    _write_job_json(job_dir, payload)

    try:
        # 0) Printer readiness
        status("CHECK_PRINTER")
        if do_print:
            ready, code, message = get_printer_readiness(config.PRINTER_NAME)
            if not ready:
                payload["state"] = "failed"
                payload["error_code"] = code
                payload["user_message"] = message
                _write_job_json(job_dir, payload)
                return PrintResult(False, job_id, error_code=code, user_message=message)

        # 1) Build placeholders
        status("BUILD")
        dan = str(form_data["dan"]).strip()
        mjesec = str(form_data["mjesec"]).strip()
        godina = str(form_data["godina"]).strip()
        datum_rodjenja = f"{dan}.{mjesec}.{godina}"

        placeholders = {
            "{{DJELOVODNI_BROJ}}": config.DJELOVODNI_BROJ,
            "{{DANASNJI_DATUM}}": _now_local_str(),
            "{{IME}}": form_data["ime"],
            "{{RODITELJ}}": form_data["roditelj"],
            "{{DATUM_RODJENJA}}": datum_rodjenja,
            "{{MJESTO}}": form_data["mjesto"],
            "{{OPSTINA}}": form_data["opstina"],
            "{{RAZRED}}": form_data["razred"],
            "{{STRUKA}}": form_data["struka"],
            "{{RAZLOG}}": form_data["razlog"],
        }

        # 2) DB insert
        if do_db_insert:
            status("DB")
            insert_entry(
                ime=form_data["ime"],
                roditelj=form_data["roditelj"],
                godina=int(godina),
                mjesec=int(mjesec),
                dan=int(dan),
                mjesto=form_data["mjesto"],
                opstina=form_data["opstina"],
                razred=form_data["razred"],
                struka=form_data["struka"],
                razlog=form_data["razlog"],
            )

        # 3) Generate DOCX
        status("DOCX")
        output_docx = job_dir / "output.docx"
        replace_dynamic_text(str(config.TEMPLATE_FILE), str(output_docx), placeholders)
        if not output_docx.exists() or output_docx.stat().st_size == 0:
            raise RuntimeError("DOCX generation failed (empty output)")

        # 4) Convert PDF
        status("PDF")
        pdf_path = Path(convert_docx_to_pdf(str(output_docx), output_dir=str(job_dir)))
        if not pdf_path.exists() or pdf_path.stat().st_size == 0:
            raise RuntimeError("PDF conversion failed (empty output)")

        # 5) Print
        printed = False
        if do_print:
            status("PRINT")
            printed = print_with_hplip(str(pdf_path))
            if not printed:
                # print_with_hplip logs details
                raise RuntimeError("Printing failed")

        payload.update(
            {
                "state": "done",
                "docx_path": str(output_docx),
                "pdf_path": str(pdf_path),
                "printed": bool(printed),
            }
        )
        _write_job_json(job_dir, payload)
        return PrintResult(True, job_id, docx_path=str(output_docx), pdf_path=str(pdf_path))

    except Exception as e:
        log_error(f"[JOB] {job_id} failed: {e}")
        payload["state"] = "failed"
        payload["error_code"] = "UNKNOWN"
        payload["user_message"] = "Nije moguće odštampati. Provjerite printer i pokušajte ponovo."
        payload["exception"] = repr(e)
        _write_job_json(job_dir, payload)
        return PrintResult(False, job_id, error_code="UNKNOWN", user_message=payload["user_message"])
