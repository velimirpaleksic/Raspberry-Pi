import json
import time
import uuid
import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional

from project.core import config
from project.services.document_service import (
    finish_attempt,
    record_system_event,
    reserve_document,
    start_attempt,
    update_document_status,
)
from project.services.notification_service import send_notification
from project.utils.docs.docx_replace_placeholders import replace_dynamic_text
from project.utils.docs.pdf_converter import convert_docx_to_pdf
from project.utils.printing.print_with_hplip import print_with_hplip
from project.utils.printing.printer_status import get_printer_readiness
from project.utils.logging_utils import log_error
from project.services.printer_service import get_active_printer
from project.services.settings_service import get_active_template_path


StatusCallback = Callable[[str], None]


@dataclass(frozen=True)
class PrintResult:
    ok: bool
    job_id: str
    document_number: Optional[str] = None
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
    existing_job_id: Optional[str] = None,
    on_status: Optional[StatusCallback] = None,
    do_print: bool = True,
    do_db_insert: bool = True,
) -> PrintResult:
    """Generate DOCX -> convert to PDF -> send to printer.

    Retries should pass ``existing_job_id`` so the logical document keeps the
    same djelovodni broj while only the attempt number increases.
    """

    def status(s: str) -> None:
        if on_status:
            on_status(s)

    job_id = existing_job_id or str(uuid.uuid4())
    job_dir = _job_dir(job_id)
    attempt_no: Optional[int] = None
    output_docx: Optional[Path] = None
    pdf_path: Optional[Path] = None

    printer_name = get_active_printer()

    if do_db_insert:
        document = reserve_document(job_id, form_data)
        document_number = document["document_number"]
        attempt_no = start_attempt(job_id, printer_name)
        update_document_status(job_id, "rendering")
    else:
        document_number = config.DJELOVODNI_BROJ_SEED

    # Persist initial job payload early (power-loss friendly)
    payload = {
        "job_id": job_id,
        "attempt_no": attempt_no,
        "document_number": document_number,
        "created_at": time.time(),
        "state": "created",
        "form_data": form_data,
    }
    _write_job_json(job_dir, payload)

    try:
        # 0) Printer readiness
        status("CHECK_PRINTER")
        if do_print:
            if do_db_insert:
                update_document_status(job_id, "printing")
            ready, code, message = get_printer_readiness(printer_name)
            if not ready:
                payload["state"] = "failed"
                payload["error_code"] = code
                payload["user_message"] = message
                _write_job_json(job_dir, payload)
                if do_db_insert and attempt_no is not None:
                    update_document_status(job_id, "failed", error_code=code, error_message=message)
                    finish_attempt(job_id, attempt_no, status="failed", error_code=code, error_message=message)
                    record_system_event("printer_not_ready", f"Printer not ready for {document_number}: {code} - {message}", level="warning", job_id=job_id)
                    send_notification(f"⚠️ Printer nije spreman\nPrinter: {printer_name}\nDokument: {document_number}\nKod: {code}\nPoruka: {message}")
                return PrintResult(False, job_id, document_number=document_number, error_code=code, user_message=message)

        # 1) Build placeholders
        status("BUILD")
        dan = str(form_data["dan"]).strip()
        mjesec = str(form_data["mjesec"]).strip()
        godina = str(form_data["godina"]).strip()
        datum_rodjenja = f"{dan}.{mjesec}.{godina}"

        placeholders = {
            "{{DJELOVODNI_BROJ}}": document_number,
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

        # 2) Generate DOCX
        status("DOCX")
        if do_db_insert:
            update_document_status(job_id, "rendering")
        output_docx = job_dir / "output.docx"
        replace_dynamic_text(get_active_template_path(), str(output_docx), placeholders)
        if not output_docx.exists() or output_docx.stat().st_size == 0:
            raise RuntimeError("DOCX generation failed (empty output)")

        # 3) Convert PDF
        status("PDF")
        pdf_path = Path(convert_docx_to_pdf(str(output_docx), output_dir=str(job_dir)))
        if not pdf_path.exists() or pdf_path.stat().st_size == 0:
            raise RuntimeError("PDF conversion failed (empty output)")

        # 4) Print
        printed = False
        if do_print:
            status("PRINT")
            if do_db_insert:
                update_document_status(job_id, "printing")
            printed = print_with_hplip(str(pdf_path), printer_name=printer_name)
            if not printed:
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

        if do_db_insert and attempt_no is not None:
            printed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            update_document_status(job_id, "printed", printed_at=printed_at)
            finish_attempt(
                job_id,
                attempt_no,
                status="printed",
                docx_path=str(output_docx),
                pdf_path=str(pdf_path),
            )
            record_system_event("print_success", f"Document printed successfully: {document_number}", job_id=job_id)

        return PrintResult(True, job_id, document_number=document_number, docx_path=str(output_docx), pdf_path=str(pdf_path))

    except Exception as e:
        log_error(f"[JOB] {job_id} failed: {e}")
        payload["state"] = "failed"
        payload["error_code"] = "UNKNOWN"
        payload["user_message"] = "Nije moguće odštampati. Provjerite printer i pokušajte ponovo."
        payload["exception"] = repr(e)
        if output_docx is not None:
            payload["docx_path"] = str(output_docx)
        if pdf_path is not None:
            payload["pdf_path"] = str(pdf_path)
        _write_job_json(job_dir, payload)

        if do_db_insert and attempt_no is not None:
            update_document_status(
                job_id,
                "failed",
                error_code="UNKNOWN",
                error_message=payload["user_message"],
            )
            finish_attempt(
                job_id,
                attempt_no,
                status="failed",
                error_code="UNKNOWN",
                error_message=payload["user_message"],
                docx_path=str(output_docx) if output_docx is not None else None,
                pdf_path=str(pdf_path) if pdf_path is not None else None,
            )
            record_system_event("print_failed", f"Print pipeline failed for {document_number}: {e}", level="error", job_id=job_id)
            send_notification(f"❌ Print pipeline greška\nPrinter: {printer_name}\nDokument: {document_number}\nJob: {job_id}\nGreška: {payload['user_message']}")

        return PrintResult(False, job_id, document_number=document_number, error_code="UNKNOWN", user_message=payload["user_message"])
