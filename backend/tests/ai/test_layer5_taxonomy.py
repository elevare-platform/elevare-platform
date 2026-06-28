"""Unit tests for Layer 5: Taxonomy matching."""

import pytest
from unittest.mock import MagicMock

from app.core.cv_pipeline.layer3_sections import DetectedSections
from app.core.cv_pipeline.layer5_taxonomy import match_taxonomy


def make_sections(**kwargs) -> DetectedSections:
    defaults = dict(
        summary=None, experience=None, education=None,
        skills=None, certifications=None, projects=None,
        references=None, unclassified="",
    )
    defaults.update(kwargs)
    return DetectedSections(**defaults)


def test_taxonomy_skill_matched():
    sections = make_sections(skills="python fastapi postgresql docker")
    result = match_taxonomy(sections)
    assert "python" in result.matched_skills
    assert "fastapi" in result.matched_skills
    assert "postgresql" in result.matched_skills


def test_r_not_matched_in_for_context():
    """Word boundary must prevent 'r' matching inside 'for', 'React', 'HR', etc."""
    sections = make_sections(
        skills="React is great for HR departments and further exploration"
    )
    result = match_taxonomy(sections)
    # "r" the programming language should not match here
    assert "r" not in result.matched_skills


def test_r_matched_when_standalone():
    sections = make_sections(skills="Python, R, MATLAB, data analysis")
    result = match_taxonomy(sections)
    assert "r" in result.matched_skills


def test_word_boundary_enforced():
    """'c' should not match inside words like 'science' or 'access'."""
    sections = make_sections(skills="computer science and database access")
    result = match_taxonomy(sections)
    assert "c" not in result.matched_skills


def test_degree_matched_in_education():
    sections = make_sections(
        education="BSc Computer Science, University of Lagos 2019"
    )
    result = match_taxonomy(sections)
    assert "bsc" in result.matched_degrees


def test_hnd_recognised_as_degree():
    sections = make_sections(
        education="HND Accountancy, Yaba College of Technology 2015"
    )
    result = match_taxonomy(sections)
    assert "hnd" in result.matched_degrees


def test_nigerian_certification_extracted_separately():
    sections = make_sections(skills="ICAN, ACCA, financial reporting, auditing")
    result = match_taxonomy(sections)
    assert "ican" in result.nigerian_certifications
    assert "acca" in result.nigerian_certifications


def test_normalisation_applied():
    """node.js should be normalised to nodejs and match taxonomy."""
    sections = make_sections(skills="node.js react.js vue.js")
    result = match_taxonomy(sections)
    assert "nodejs" in result.matched_skills
    assert "react" in result.matched_skills
