# print_subprocess.py
import os
from docx_utils import docx_to_pdf
from print_pycups import print_file_with_pycups, wait_for_job
import cups

def print_docx(docx_path: str, printer: str = None) -> bool:
    """
    Converting DOCX u PDF and sending to printer.
    Return True if its done, False otherwise.
    """
    if not os.path.exists(docx_path):
        raise FileNotFoundError(f"File not found: {docx_path}")

    # 1. Convert to PDF
    pdf_path = docx_to_pdf(docx_path)

    # 2. Sending to printer
    conn = cups.Connection()
    job_id = print_file_with_pycups(pdf_path, printer)

    # 3. Wait for job to finish (or if job leaves the queue)
    ok = wait_for_job(conn, job_id, timeout=60)
    return ok