"""Unit tests for Layer 3: Section detection."""

from app.core.cv_pipeline.layer3_sections import detect_sections

SAMPLE_CV = """
John Adeyemi
john@example.com

Summary
Experienced software engineer with 5 years in backend development.

Experience
Software Engineer at Google
2019 - 2023
Built scalable APIs using Python and FastAPI.

Education
BSc Computer Science
University of Lagos, 2019

Skills
Python, FastAPI, PostgreSQL, Docker, React
"""

NIGERIAN_CV = """
Chukwuemeka Obi
chukwuemeka@email.com

Professional Background
10 years in banking and finance.

Employment History
Senior Manager at Access Bank
2015 - 2023

Academic Qualifications
HND Accountancy
Yaba College of Technology, 2012

Core Competencies
Financial analysis, AML, KYC, Credit risk
"""


def test_section_headers_detected():
    result = detect_sections(SAMPLE_CV)
    assert result.summary is not None
    assert result.experience is not None
    assert result.education is not None
    assert result.skills is not None


def test_section_content_correct():
    result = detect_sections(SAMPLE_CV)
    assert "Google" in result.experience
    assert "University of Lagos" in result.education
    assert "Python" in result.skills


def test_unclassified_contains_header_lines():
    result = detect_sections(SAMPLE_CV)
    assert "John Adeyemi" in result.unclassified


def test_nigerian_cv_headers_handled():
    result = detect_sections(NIGERIAN_CV)
    assert result.experience is not None
    assert result.education is not None
    assert result.skills is not None


def test_missing_section_returns_none():
    result = detect_sections(SAMPLE_CV)
    assert result.certifications is None
    assert result.references is None


def test_header_with_colon_detected():
    cv = "Experience:\nWorked at Andela.\n\nEducation:\nBSc Lagos."
    result = detect_sections(cv)
    assert result.experience is not None
    assert result.education is not None
