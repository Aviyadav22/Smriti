"""Export legal documents to DOCX and PDF formats.

Provides async export functions that produce properly formatted Indian legal
documents with Times New Roman typography, 1-inch margins, and structured
section headings.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

from docx import Document  # type: ignore[import-untyped]
from docx.enum.text import WD_ALIGN_PARAGRAPH  # type: ignore[import-untyped]
from docx.shared import Inches, Pt  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[import-untyped]
from reportlab.lib.units import inch  # type: ignore[import-untyped]
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer  # type: ignore[import-untyped]

from app.core.drafting.templates import DocumentTemplate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_heading(line: str) -> bool:
    """Return True if *line* looks like a section heading."""
    stripped = line.strip()
    if stripped.startswith("#"):
        return True
    # All-caps lines of 4+ characters (e.g. "PRAYER", "FACTS OF THE CASE")
    if len(stripped) >= 4 and stripped == stripped.upper() and stripped.replace(" ", "").isalpha():
        return True
    return False


def _clean_heading(line: str) -> str:
    """Strip markdown heading markers and return clean text."""
    return line.lstrip("#").strip()


def _parse_sections(content: str) -> list[tuple[str | None, list[str]]]:
    """Parse *content* into (heading, body_lines) pairs.

    A ``None`` heading means body text before the first heading.
    """
    sections: list[tuple[str | None, list[str]]] = []
    current_heading: str | None = None
    current_body: list[str] = []

    for line in content.split("\n"):
        if _is_heading(line):
            # Flush previous section
            sections.append((current_heading, current_body))
            current_heading = _clean_heading(line)
            current_body = []
        else:
            current_body.append(line)

    # Flush last section
    sections.append((current_heading, current_body))
    return sections


# ---------------------------------------------------------------------------
# DOCX export
# ---------------------------------------------------------------------------


async def export_to_docx(
    content: str,
    template: DocumentTemplate,
    *,
    title: str = "",
) -> bytes:
    """Export document content to DOCX format with Indian legal formatting.

    Args:
        content: The full document text (may contain markdown headings).
        template: The DocumentTemplate describing the document type.
        title: Optional title override; defaults to ``template.display_name``.

    Returns:
        The DOCX file as raw bytes.
    """
    doc = Document()

    # -- Page margins: 1 inch all sides --
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # -- Default font --
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Times New Roman"
    font.size = Pt(12)

    # -- Document title --
    doc_title = title or template.display_name
    title_para = doc.add_heading(doc_title, level=0)
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in title_para.runs:
        run.font.name = "Times New Roman"
        run.font.size = Pt(16)
        run.font.bold = True

    # -- Parse and render sections --
    paragraph_number = 1
    sections = _parse_sections(content)

    for heading, body_lines in sections:
        if heading is not None:
            heading_para = doc.add_heading(heading, level=1)
            for run in heading_para.runs:
                run.font.name = "Times New Roman"
                run.font.size = Pt(14)
                run.font.bold = True

        body_text = "\n".join(body_lines).strip()
        if not body_text:
            continue

        for paragraph_text in body_text.split("\n\n"):
            paragraph_text = paragraph_text.strip()
            if not paragraph_text:
                continue

            para = doc.add_paragraph()
            para.paragraph_format.space_after = Pt(6)

            # Add paragraph number for substantive content
            if heading is not None:
                run = para.add_run(f"{paragraph_number}. ")
                run.font.name = "Times New Roman"
                run.font.size = Pt(12)
                run.font.bold = True
                paragraph_number += 1

            run = para.add_run(paragraph_text.replace("\n", " "))
            run.font.name = "Times New Roman"
            run.font.size = Pt(12)

    # -- Document metadata --
    doc.core_properties.title = doc_title
    doc.core_properties.author = "Smriti AI"
    doc.core_properties.created = datetime.now(timezone.utc)
    doc.core_properties.comments = (
        f"Generated by Smriti AI — {template.display_name}"
    )

    # -- Serialise to bytes --
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# PDF export
# ---------------------------------------------------------------------------


async def export_to_pdf(
    content: str,
    template: DocumentTemplate,
    *,
    title: str = "",
) -> bytes:
    """Export document content to PDF format with Indian legal formatting.

    Args:
        content: The full document text (may contain markdown headings).
        template: The DocumentTemplate describing the document type.
        title: Optional title override; defaults to ``template.display_name``.

    Returns:
        The PDF file as raw bytes.
    """
    buf = io.BytesIO()

    doc_title = title or template.display_name

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        title=doc_title,
        author="Smriti AI",
        creator="Smriti AI",
        subject=f"Legal Document — {template.display_name}",
    )

    # -- Styles --
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Title"],
        fontName="Times-Bold",
        fontSize=16,
        alignment=1,  # centre
        spaceAfter=20,
    )

    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading1"],
        fontName="Times-Bold",
        fontSize=14,
        spaceBefore=14,
        spaceAfter=8,
    )

    body_style = ParagraphStyle(
        "BodyText",
        parent=styles["BodyText"],
        fontName="Times-Roman",
        fontSize=12,
        leading=16,
        spaceAfter=6,
    )

    # -- Build flowable list --
    flowables: list[Paragraph | Spacer] = []

    flowables.append(Paragraph(doc_title, title_style))
    flowables.append(Spacer(1, 12))

    paragraph_number = 1
    sections = _parse_sections(content)

    for heading, body_lines in sections:
        if heading is not None:
            flowables.append(Paragraph(heading, heading_style))

        body_text = "\n".join(body_lines).strip()
        if not body_text:
            continue

        for paragraph_text in body_text.split("\n\n"):
            paragraph_text = paragraph_text.strip()
            if not paragraph_text:
                continue

            # Escape XML-sensitive characters for ReportLab
            safe_text = (
                paragraph_text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br/>")
            )

            if heading is not None:
                safe_text = f"<b>{paragraph_number}.</b> {safe_text}"
                paragraph_number += 1

            flowables.append(Paragraph(safe_text, body_style))

    doc.build(flowables)
    buf.seek(0)
    return buf.read()
