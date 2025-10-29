# utils/docs/pdf_converter.py
import os
from docx2pdf import convert


def convert_docx_to_pdf(docx_path, output_dir=None):
    """Convert DOCX to PDF and return PDF path."""
    if not os.path.exists(docx_path):
        raise FileNotFoundError(f"{docx_path} not found")

    docx_path = os.path.abspath(docx_path)
    if output_dir is None:
        output_dir = os.path.dirname(docx_path)
    else:
        os.makedirs(output_dir, exist_ok=True)

    pdf_path = os.path.join(output_dir, os.path.splitext(os.path.basename(docx_path))[0] + ".pdf")

    # Convert DOCX to PDF
    convert(docx_path, output_dir)

    if not os.path.exists(pdf_path):
        raise RuntimeError("Failed to generate PDF")

    return pdf_path