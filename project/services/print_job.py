import datetime
import json
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional

from project.core import config
from project.core.runtime_settings import get_selected_printer
from project.services.telegram_notify import notify_telegram_async
from project.utils.docs.docx_replace_placeholders import replace_dynamic_text
from project.utils.docs.pdf_converter import convert_docx_to_pdf
from project.utils.logging_utils import log_error, log_info
from project.utils.printing.print_with_hplip import print_with_hplip
from project.utils.printing.printer_status import wait_for_printer_readiness

StatusCallback = Callable[[str], None]


@dataclass(frozen=True)
class PrintResult:
    ok: bool
    job_id: str
    docx_path: Optional[str] = None
    pdf_path: Optional[str] = None
    error_code: Optional[str] = None
    user_message: Optional[str] = None
    detail: Optional[str] = None


def _now_local_str() -> str:
    return datetime.datetime.now().strftime("%d.%m.%Y")


def _docx_caps(value: str) -> str:
    return str(value or "").strip().upper()


def _job_dir(job_id: str) -> Path:
    return config.JOBS_DIR / job_id


def _write_job_json(job_dir: Path, payload: Dict) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "job.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _notify_job_failure(
    job_id: str,
    payload: Dict,
    error_code: str,
    user_message: str,
    detail: str = "",
    *,
    docx_path: str | None = None,
    pdf_path: str | None = None,
) -> None:
    details = [
        "Uvjerenja Terminal print job failed.",
        f"Job: {job_id}",
        f"State: {payload.get('state') or 'unknown'}",
        f"Error code: {error_code}",
        f"Message: {user_message}",
    ]

    selected_printer = str(payload.get("selected_printer") or "").strip()
    resolved_printer = str(payload.get("resolved_printer") or "").strip()
    attempts = payload.get("printer_check_attempts")

    if selected_printer:
        details.append(f"Selected printer: {selected_printer}")
    if resolved_printer:
        details.append(f"Resolved printer: {resolved_printer}")
    if attempts:
        details.append(f"Printer check attempts: {attempts}")
    if docx_path:
        details.append(f"DOCX: {docx_path}")
    if pdf_path:
        details.append(f"PDF: {pdf_path}")
    if detail:
        details.append(f"Detail: {str(detail)[:1500]}")

    notify_telegram_async("\n".join(details))


def _fail(job_dir: Path, payload: Dict, job_id: str, error_code: str, user_message: str, detail: str = "", *, docx_path: str | None = None, pdf_path: str | None = None) -> PrintResult:
    payload.update({"state": "failed", "error_code": error_code, "user_message": user_message, "detail": detail})
    if docx_path:
        payload["docx_path"] = docx_path
    if pdf_path:
        payload["pdf_path"] = pdf_path
    _write_job_json(job_dir, payload)
    _notify_job_failure(job_id, payload, error_code, user_message, detail, docx_path=docx_path, pdf_path=pdf_path)
    return PrintResult(False, job_id, docx_path=docx_path, pdf_path=pdf_path, error_code=error_code, user_message=user_message, detail=detail)


def _validate_form_data(form_data: Dict[str, str]) -> tuple[bool, str]:
    required = ["ime_ucenika", "prezime", "ime", "roditelj", "mjesto", "opstina", "razred", "struka", "razlog", "dan", "mjesec", "godina"]
    missing = [key for key in required if not str(form_data.get(key, "")).strip()]
    if missing:
        return False, "Nedostaju podaci za štampu. Vrati se na unos i provjeri sva polja."

    try:
        datetime.date(
            int(str(form_data["godina"]).strip()),
            int(str(form_data["mjesec"]).strip()),
            int(str(form_data["dan"]).strip()),
        )
    except (TypeError, ValueError):
        return False, "Datum rođenja nije ispravan. Vrati se na unos i provjeri dan, mjesec i godinu."

    return True, ""


def _normalize_form_data(form_data: Dict) -> Dict[str, str]:
    data = {str(key): str(value).strip() for key, value in form_data.items()}
    ime_ucenika = data.get("ime_ucenika", "")
    prezime = data.get("prezime", "")

    if not ime_ucenika and not prezime:
        parts = data.get("ime", "").split()
        if parts:
            ime_ucenika = parts[0]
            prezime = " ".join(parts[1:])

    data["ime_ucenika"] = ime_ucenika
    data["prezime"] = prezime
    data["ime"] = f"{ime_ucenika} {prezime}".strip()
    return data


def _notify_printer_error(
    job_id: str,
    code: str,
    message: str,
    *,
    selected_printer: str = "",
    resolved_printer: str = "",
    attempts: int | None = None,
) -> None:
    details = [
        "Printer error on Uvjerenja Terminal.",
        f"Job: {job_id}",
        f"Error: {code}",
        f"Message: {message}",
    ]
    if selected_printer:
        details.append(f"Selected printer: {selected_printer}")
    if resolved_printer:
        details.append(f"Resolved printer: {resolved_printer}")
    if attempts:
        details.append(f"Attempts: {attempts}")
    notify_telegram_async("\n".join(details))


def _resolve_ready_printer_for_job() -> tuple[bool, str, str, str, str, int]:
    """Return (ready, resolved_printer, code, message, selected_printer, attempts)."""
    selected_printer = get_selected_printer()
    ready, code, message, attempts = wait_for_printer_readiness(selected_printer)
    if ready:
        return True, message, code, "", selected_printer, attempts

    if selected_printer:
        default_ready, default_code, default_message, default_attempts = wait_for_printer_readiness("")
        if default_ready:
            return (
                True,
                default_message,
                default_code,
                f"Selected printer '{selected_printer}' was not ready. Using CUPS default '{default_message}'.",
                selected_printer,
                attempts + default_attempts,
            )

    return False, "", code, message, selected_printer, attempts


def run_print_job(
    form_data: Dict,
    *,
    on_status: Optional[StatusCallback] = None,
    do_print: bool = True,
) -> PrintResult:
    def status(code: str) -> None:
        if on_status:
            on_status(code)

    job_id = str(uuid.uuid4())
    job_dir = _job_dir(job_id)
    form_data = _normalize_form_data(form_data)

    payload = {
        "job_id": job_id,
        "created_at": time.time(),
        "state": "created",
        "form_data": form_data,
    }
    _write_job_json(job_dir, payload)

    is_valid, validation_message = _validate_form_data(form_data)
    if not is_valid:
        return _fail(job_dir, payload, job_id, "FORM_INVALID", validation_message)

    if not config.TEMPLATE_FILE.exists():
        return _fail(job_dir, payload, job_id, "TEMPLATE_MISSING", f"Template nije pronađen: {config.TEMPLATE_FILE}")

    resolved_printer = ""
    if do_print:
        payload["state"] = "CHECK_PRINTER"
        _write_job_json(job_dir, payload)
        status("CHECK_PRINTER")
        printer_ready, resolved_printer, printer_code, printer_message, selected_printer, printer_attempts = _resolve_ready_printer_for_job()
        payload["selected_printer"] = selected_printer
        payload["resolved_printer"] = resolved_printer
        payload["printer_check_attempts"] = printer_attempts
        if printer_message and printer_ready:
            payload["printer_fallback"] = printer_message
            log_info(f"[JOB] {job_id} printer fallback: {printer_message}")
            _notify_printer_error(
                job_id,
                "PRN_FALLBACK",
                printer_message,
                selected_printer=selected_printer,
                resolved_printer=resolved_printer,
                attempts=printer_attempts,
            )
        if not printer_ready:
            return _fail(job_dir, payload, job_id, printer_code, printer_message)

    output_docx: Path | None = None
    pdf_path: Path | None = None

    try:
        payload["state"] = "BUILD"
        _write_job_json(job_dir, payload)
        status("BUILD")
        datum_rodjenja = f"{str(form_data['dan']).strip()}.{str(form_data['mjesec']).strip()}.{str(form_data['godina']).strip()}"
        placeholders = {
            "{{DANASNJI_DATUM}}": _now_local_str(),
            "{{IME}}": form_data["ime_ucenika"],
            "{{IME_PREZIME}}": form_data["ime"],
            "{{IME_UCENIKA}}": form_data["ime_ucenika"],
            "{{PREZIME}}": form_data["prezime"],
            "{{RODITELJ}}": form_data["roditelj"],
            "{{DATUM_RODJENJA}}": datum_rodjenja,
            "{{MJESTO}}": form_data["mjesto"],
            "{{OPSTINA}}": form_data["opstina"],
            "{{RAZRED}}": form_data["razred"],
            "{{STRUKA}}": _docx_caps(form_data["struka"]),
            "{{RAZLOG}}": _docx_caps(form_data["razlog"]),
        }

        payload["state"] = "DOCX"
        _write_job_json(job_dir, payload)
        status("DOCX")
        output_docx = job_dir / "output.docx"
        replace_dynamic_text(str(config.TEMPLATE_FILE), str(output_docx), placeholders)
        if not output_docx.exists() or output_docx.stat().st_size == 0:
            return _fail(job_dir, payload, job_id, "DOCX_FAILED", "Generisanje DOCX dokumenta nije uspjelo.")

        payload["state"] = "PDF"
        payload["docx_path"] = str(output_docx)
        _write_job_json(job_dir, payload)
        status("PDF")
        pdf_path = Path(convert_docx_to_pdf(str(output_docx), output_dir=str(job_dir)))
        if not pdf_path.exists() or pdf_path.stat().st_size == 0:
            return _fail(job_dir, payload, job_id, "PDF_FAILED", "Pretvaranje dokumenta u PDF nije uspjelo.", docx_path=str(output_docx))

        printed = False
        if do_print:
            payload["resolved_printer"] = resolved_printer

            payload["state"] = "PRINT"
            payload["pdf_path"] = str(pdf_path)
            _write_job_json(job_dir, payload)
            status("PRINT")
            print_result = print_with_hplip(str(pdf_path), preferred_printer=resolved_printer)
            if not print_result.ok:
                detail = print_result.detail or ""
                return _fail(
                    job_dir,
                    payload,
                    job_id,
                    print_result.error_code or "PRINT_FAILED",
                    print_result.user_message or "Štampanje nije uspjelo.",
                    detail,
                    docx_path=str(output_docx),
                    pdf_path=str(pdf_path),
                )
            printed = True
            payload["printer_name"] = print_result.printer_name
            if print_result.detail:
                payload["lp_output"] = print_result.detail

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
    except FileNotFoundError as e:
        log_error(f"[JOB] {job_id} file missing: {e}")
        return _fail(
            job_dir,
            payload,
            job_id,
            "FILE_MISSING",
            "Nedostaje fajl potreban za generisanje dokumenta.",
            repr(e),
            docx_path=str(output_docx) if output_docx else None,
            pdf_path=str(pdf_path) if pdf_path else None,
        )
    except subprocess.TimeoutExpired as e:
        stage = str(payload.get("state") or "processing")
        user_message = "Operacija je trajala predugo. Pokušaj ponovo."
        if stage == "PDF":
            user_message = "Pretvaranje u PDF je trajalo predugo. Provjerite LibreOffice i pokušajte ponovo."
        elif stage == "PRINT":
            user_message = "Slanje na štampu je trajalo predugo. Provjerite printer i pokušajte ponovo."
        log_error(f"[JOB] {job_id} timeout during {stage}: {e}")
        return _fail(job_dir, payload, job_id, "TIMEOUT", user_message, repr(e), docx_path=str(output_docx) if output_docx else None, pdf_path=str(pdf_path) if pdf_path else None)
    except RuntimeError as e:
        stage = str(payload.get("state") or "processing")
        detail = str(e)
        lower = detail.lower()
        if "libreoffice" in lower or "soffice" in lower:
            code = "PDF_ENGINE_MISSING"
            user_message = "LibreOffice nije pronađen. PDF konverzija nije moguća dok se ne instalira."
        elif stage == "PDF":
            code = "PDF_FAILED"
            user_message = "Pretvaranje dokumenta u PDF nije uspjelo."
        elif stage == "DOCX":
            code = "DOCX_FAILED"
            user_message = "Generisanje DOCX dokumenta nije uspjelo."
        else:
            code = "RUNTIME_ERROR"
            user_message = "Došlo je do greške tokom obrade dokumenta."
        log_error(f"[JOB] {job_id} runtime error during {stage}: {e}")
        return _fail(job_dir, payload, job_id, code, user_message, detail, docx_path=str(output_docx) if output_docx else None, pdf_path=str(pdf_path) if pdf_path else None)
    except OSError as e:
        stage = str(payload.get("state") or "processing")
        log_error(f"[JOB] {job_id} os error during {stage}: {e}")
        return _fail(
            job_dir,
            payload,
            job_id,
            "OS_ERROR",
            "Sistemska greška je prekinula obradu dokumenta ili štampe.",
            repr(e),
            docx_path=str(output_docx) if output_docx else None,
            pdf_path=str(pdf_path) if pdf_path else None,
        )
    except Exception as e:
        stage = str(payload.get("state") or "processing")
        log_error(f"[JOB] {job_id} unexpected error during {stage}: {e}")
        return _fail(
            job_dir,
            payload,
            job_id,
            "UNKNOWN",
            "Došlo je do neočekivane greške tokom obrade dokumenta ili štampe.",
            repr(e),
            docx_path=str(output_docx) if output_docx else None,
            pdf_path=str(pdf_path) if pdf_path else None,
        )
