# utils/docs/pdf_converter.py
import os
import shutil
import subprocess

from project.core.config import DOCX_CONVERT_TIMEOUT


def convert_docx_to_pdf(docx_path, output_dir=None):
    if not os.path.exists(docx_path):
        raise FileNotFoundError(f"{docx_path} not found")

    docx_path = os.path.abspath(docx_path)
    if output_dir is None:
        output_dir = os.path.dirname(docx_path)
    os.makedirs(output_dir, exist_ok=True)

    lo_bin = shutil.which("libreoffice") or shutil.which("soffice")
    if not lo_bin:
        raise RuntimeError("LibreOffice is not installed (missing 'libreoffice'/'soffice')")

    cmd = [
        lo_bin,
        "--headless",
        "--nologo",
        "--nofirststartwizard",
        "--convert-to", "pdf",
        "--outdir", output_dir,
        docx_path,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=DOCX_CONVERT_TIMEOUT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Conversion failed: {result.stderr}")

    pdf_path = os.path.join(output_dir, os.path.splitext(os.path.basename(docx_path))[0] + ".pdf")
    return pdf_path