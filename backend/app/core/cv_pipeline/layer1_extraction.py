"""Layer 1 — raw text extraction from PDF files.

Tries pdfplumber first, falls back to PyMuPDF, then Tesseract OCR for
scanned documents. Returns a TextExtractionResult with metadata about
the extraction method used and whether OCR was required.
"""
from dataclasses import dataclass
from io import BytesIO

import fitz
import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes


@dataclass
class TextExtractionResult:
    """Result of extracting text from a PDF file."""

    success: bool
    text: str | None
    page_count: int
    is_scanned: bool
    ocr_used: bool
    method_used: str  # "pdfplumber" | "pymupdf" | "tesseract"
    error: str | None


def _extract_with_pdfplumber(pdf_bytes: bytes) -> tuple[str, int]:
    """Extract text from PDF using pdfplumber. Returns (text, page_count)."""
    text_parts = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        page_count = len(pdf.pages)

        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)

        return "\n\n".join(text_parts), page_count

def _extract_with_pymupdf(pdf_bytes: bytes) -> tuple[str, int]:
    """Extract text from PDF using PyMuPDF. Returns (text, page_count)."""
    text_parts = []

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_count = len(doc)

    for page in doc:
        text_parts.append(page.get_text())

    doc.close()

    return "\n\n".join(text_parts), page_count

def _extract_with_ocr(pdf_bytes: bytes) -> tuple[str, int]:
    """Extract text from a scanned PDF using Tesseract OCR. Returns (text, page_count)."""
    images = convert_from_bytes(pdf_bytes)

    text_parts = []

    for index, image in enumerate(images, start=1):
        page_text = pytesseract.image_to_string(image)

        text_parts.append(
            f"\n\n----- PAGE {index} -----\n\n{page_text}"
        )

    return "".join(text_parts), len(images)

def extract_text_from_pdf(pdf_bytes: bytes) -> TextExtractionResult:
    """Extract text from a PDF, trying pdfplumber → PyMuPDF → OCR in order.

    Returns a TextExtractionResult indicating success, the extracted text,
    and metadata about which method was used.
    """
    # Extract with pdfplumber

    try:
        text, page_count = _extract_with_pdfplumber(pdf_bytes)

        if len(text.strip()) > 150:
            return TextExtractionResult(
                success=True,
                text=text,
                page_count=page_count,
                is_scanned=False,
                ocr_used=False,
                method_used="pdfplumber",
                error=None
            )
    except Exception:
        page_count = 0

    try:
        text, page_count = _extract_with_pymupdf(pdf_bytes)

        if len(text.strip()) > 150:
            return TextExtractionResult(
                success=True,
                text=text,
                page_count=page_count,
                is_scanned=False,
                ocr_used=False,
                method_used="pymupdf",
                error=None,
            )
    except Exception:
        pass

    try:
        text, page_count = _extract_with_ocr(pdf_bytes)

        if len(text.strip()) >= 50:
            return TextExtractionResult(
                success=True,
                text=text,
                page_count=page_count,
                is_scanned=True,
                ocr_used=True,
                method_used="tesseract",
                error=None,
            )
    except Exception:
        pass

    return TextExtractionResult(
        success=False,
        text=None,
        page_count=0,
        is_scanned=True,
        ocr_used=True,
        method_used="tesseract",
        error=(
            "Unable to extract text — document may be image-only "
            "or corrupted"
        ),
    )
