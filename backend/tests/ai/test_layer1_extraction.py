"""Unit tests for Layer 1: PDF text extraction."""

import io
import pytest
from unittest.mock import MagicMock, patch

from app.core.cv_pipeline.layer1_extraction import TextExtractionResult, extract_text_from_pdf


def make_minimal_pdf() -> bytes:
    return b"%PDF-1.4 fake pdf content for testing purposes and extraction"


def make_long_text() -> str:
    return "A" * 200


# ── pdfplumber path ───────────────────────────────────────────────────────────

@patch("app.core.cv_pipeline.layer1_extraction.pdfplumber")
def test_pdfplumber_success(mock_pdfplumber):
    mock_page = MagicMock()
    mock_page.extract_text.return_value = make_long_text()
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdfplumber.open.return_value.__enter__ = lambda s: mock_pdf
    mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

    result = extract_text_from_pdf(make_minimal_pdf())

    assert result.success is True
    assert result.method_used == "pdfplumber"
    assert result.is_scanned is False
    assert result.ocr_used is False
    assert len(result.text) > 150


@patch("app.core.cv_pipeline.layer1_extraction.pdfplumber")
@patch("app.core.cv_pipeline.layer1_extraction.fitz")
def test_pymupdf_fallback_when_pdfplumber_short(mock_fitz, mock_pdfplumber):
    mock_page_plumber = MagicMock()
    mock_page_plumber.extract_text.return_value = "too short"
    mock_pdf_plumber = MagicMock()
    mock_pdf_plumber.pages = [mock_page_plumber]
    mock_pdfplumber.open.return_value.__enter__ = lambda s: mock_pdf_plumber
    mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

    mock_fitz_page = MagicMock()
    mock_fitz_page.get_text.return_value = make_long_text()
    mock_fitz_doc = MagicMock()
    mock_fitz_doc.__iter__ = MagicMock(return_value=iter([mock_fitz_page]))
    mock_fitz_doc.__len__ = MagicMock(return_value=1)
    mock_fitz.open.return_value = mock_fitz_doc

    result = extract_text_from_pdf(make_minimal_pdf())

    assert result.success is True
    assert result.method_used == "pymupdf"


@patch("app.core.cv_pipeline.layer1_extraction.pdfplumber")
@patch("app.core.cv_pipeline.layer1_extraction.fitz")
@patch("app.core.cv_pipeline.layer1_extraction.convert_from_bytes")
@patch("app.core.cv_pipeline.layer1_extraction.pytesseract")
def test_ocr_fallback_for_scanned_pdf(mock_tesseract, mock_convert, mock_fitz, mock_pdfplumber):
    # Both text extractors return short text
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "x"
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdfplumber.open.return_value.__enter__ = lambda s: mock_pdf
    mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

    mock_fitz_page = MagicMock()
    mock_fitz_page.get_text.return_value = "x"
    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter([mock_fitz_page]))
    mock_doc.__len__ = MagicMock(return_value=1)
    mock_fitz.open.return_value = mock_doc

    mock_convert.return_value = [MagicMock()]
    mock_tesseract.image_to_string.return_value = make_long_text()

    result = extract_text_from_pdf(make_minimal_pdf())

    assert result.success is True
    assert result.method_used == "tesseract"
    assert result.is_scanned is True
    assert result.ocr_used is True


@patch("app.core.cv_pipeline.layer1_extraction.pdfplumber")
@patch("app.core.cv_pipeline.layer1_extraction.fitz")
@patch("app.core.cv_pipeline.layer1_extraction.convert_from_bytes")
@patch("app.core.cv_pipeline.layer1_extraction.pytesseract")
def test_corrupted_pdf_returns_failure(mock_tesseract, mock_convert, mock_fitz, mock_pdfplumber):
    mock_page = MagicMock()
    mock_page.extract_text.return_value = ""
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdfplumber.open.return_value.__enter__ = lambda s: mock_pdf
    mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

    mock_fitz_page = MagicMock()
    mock_fitz_page.get_text.return_value = ""
    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter([mock_fitz_page]))
    mock_doc.__len__ = MagicMock(return_value=1)
    mock_fitz.open.return_value = mock_doc

    mock_convert.return_value = [MagicMock()]
    mock_tesseract.image_to_string.return_value = ""

    result = extract_text_from_pdf(b"corrupted")

    assert result.success is False
    assert result.error is not None
