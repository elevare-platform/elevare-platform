"""Unit tests for Layer 6: NLP extraction — uses MockNLP to avoid loading spaCy."""

from unittest.mock import MagicMock, patch

from app.core.cv_pipeline.layer3_sections import DetectedSections
from app.core.cv_pipeline.layer6_nlp import extract_nlp


def make_sections(**kwargs) -> DetectedSections:
    defaults = dict(
        summary=None, experience=None, education=None,
        skills=None, certifications=None, projects=None,
        references=None, unclassified="",
    )
    defaults.update(kwargs)
    return DetectedSections(**defaults)


def make_mock_nlp(entities=None, matcher_matches=None):
    """Build a mock spaCy nlp object."""
    entities = entities or []
    matcher_matches = matcher_matches or []

    mock_ent = lambda text, label: MagicMock(text=text, label_=label,
                                              start_char=0)

    mock_doc = MagicMock()
    mock_doc.ents = [mock_ent(t, l) for t, l in entities]

    mock_nlp = MagicMock()
    mock_nlp.return_value = mock_doc
    mock_nlp.vocab = MagicMock()

    return mock_nlp


def test_person_name_extracted_from_first_lines():
    nlp = make_mock_nlp(entities=[("John Adeyemi", "PERSON")])
    sections = make_sections()
    text = "John Adeyemi\njohn@email.com\n\nSoftware Engineer"

    result = extract_nlp(text, sections, nlp)

    assert result.full_name == "John Adeyemi"
    assert result.field_confidence["full_name"] in ("high", "medium")


def test_no_name_returns_none():
    nlp = make_mock_nlp(entities=[])
    sections = make_sections()

    result = extract_nlp("No name here", sections, nlp)

    assert result.full_name is None
    assert result.field_confidence["full_name"] == "not_found"


def test_organisations_extracted_from_experience():
    nlp = make_mock_nlp(entities=[("Google", "ORG"), ("Meta", "ORG")])
    sections = make_sections(experience="Worked at Google and then Meta.")

    with patch("app.core.cv_pipeline.layer6_nlp.Matcher") as mock_matcher_cls:
        mock_matcher = MagicMock()
        mock_matcher.return_value = []
        mock_matcher_cls.return_value = mock_matcher
        result = extract_nlp("John\n", sections, nlp)

    assert "Google" in result.organisations or "Meta" in result.organisations


def test_duplicate_organisations_deduplicated():
    nlp = make_mock_nlp(entities=[("Google", "ORG"), ("Google", "ORG")])
    sections = make_sections(experience="Google promoted me at Google.")

    with patch("app.core.cv_pipeline.layer6_nlp.Matcher") as mock_matcher_cls:
        mock_matcher = MagicMock()
        mock_matcher.return_value = []
        mock_matcher_cls.return_value = mock_matcher
        result = extract_nlp("John\n", sections, nlp)

    assert result.organisations.count("Google") == 1


def test_empty_experience_returns_no_organisations():
    nlp = make_mock_nlp(entities=[])
    sections = make_sections(experience=None)

    result = extract_nlp("John\n", sections, nlp)

    assert result.organisations == []
