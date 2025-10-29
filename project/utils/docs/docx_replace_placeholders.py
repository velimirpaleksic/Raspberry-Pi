# utils/docs/docx_replace_placeholders.py
from docx import Document
import re
from typing import Dict


def replace_dynamic_text(template_path: str, output_path: str, placeholders: Dict[str, str]):
    """Replace placeholders in DOCX template and save to output."""
    doc = Document(template_path)
    if placeholders:
        _replace_placeholders(doc, placeholders)
    doc.save(output_path)


def _replace_placeholders(doc: Document, placeholders: Dict[str, str]):
    """
    Replace placeholders in all paragraphs and tables efficiently.
    Handles multiple placeholders per paragraph and preserves styling.
    """
    # Precompile regex for all placeholders (escape special characters)
    pattern = re.compile("|".join(re.escape(k) for k in placeholders.keys()))

    def replace_in_paragraph(paragraph):
        if not paragraph.runs:
            return
        # Combine all runs text
        full_text = "".join(run.text for run in paragraph.runs)
        # Replace all placeholders at once
        new_text = pattern.sub(lambda m: str(placeholders[m.group(0)]), full_text)
        # Only update if text changed
        if new_text != full_text:
            # Replace text in first run and clear others (keeps some formatting)
            paragraph.runs[0].text = new_text
            for r in paragraph.runs[1:]:
                r.text = ""

    # Replace in all paragraphs
    for para in doc.paragraphs:
        replace_in_paragraph(para)

    # Replace in all tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    replace_in_paragraph(para)