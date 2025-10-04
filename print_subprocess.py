# print_subprocess.py
import os
from docx_utils import docx_to_pdf
from print_hplip import print_file_hplip

def print_docx(docx_path: str, printer: str = None) -> bool:
    """
    Convert DOCX to PDF and send directly to HP printer using HPLIP.
    Returns True if command executed successfully.
    """
    if not os.path.exists(docx_path):
        raise FileNotFoundError(f"File not found: {docx_path}")

    # 1. Convert DOCX to PDF
    pdf_path = docx_to_pdf(docx_path)

    # 2. Send PDF to printer via HPLIP
    try:
        print_file_hplip(pdf_path, printer)
        return True
    except Exception as e:
        print(f"Printing failed: {e}")
        return False