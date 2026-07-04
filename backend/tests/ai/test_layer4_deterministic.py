"""Unit tests for Layer 4: Deterministic extraction."""

from app.core.cv_pipeline.layer4_deterministic import extract_deterministic

SAMPLE_TEXT = """
John Adeyemi
john.adeyemi@email.com
+2348012345678
linkedin.com/in/johnadeyemi
github.com/johnadeyemi

Experience
Software Engineer 2020 - 2023
"""

LOCAL_FORMAT_TEXT = """
Ade Ola
ade@example.com
08023456789
"""

INTL_FORMAT_TEXT = """
Femi Bello
femi@example.com
+447911123456
"""


def test_email_extracted():
    result = extract_deterministic(SAMPLE_TEXT)
    assert result.email == "john.adeyemi@email.com"
    assert result.field_confidence["email"] == "high"


def test_nigerian_phone_plus234_normalised():
    result = extract_deterministic(SAMPLE_TEXT)
    assert result.phone == "+2348012345678"
    assert result.field_confidence["phone"] == "high"


def test_nigerian_phone_0xx_normalised_to_e164():
    result = extract_deterministic(LOCAL_FORMAT_TEXT)
    assert result.phone == "+2348023456789"


def test_international_phone_extracted():
    result = extract_deterministic(INTL_FORMAT_TEXT)
    assert result.phone == "+447911123456"


def test_linkedin_url_extracted():
    result = extract_deterministic(SAMPLE_TEXT)
    assert "linkedin.com/in/johnadeyemi" in result.linkedin_url


def test_github_url_extracted():
    result = extract_deterministic(SAMPLE_TEXT)
    assert "github.com/johnadeyemi" in result.github_url


def test_no_phone_returns_none():
    result = extract_deterministic("No contact info here at all.")
    assert result.phone is None
    assert result.field_confidence["phone"] == "not_found"


def test_dates_extracted():
    result = extract_deterministic(SAMPLE_TEXT)
    assert any("2020" in d or "2023" in d for d in result.raw_dates)
