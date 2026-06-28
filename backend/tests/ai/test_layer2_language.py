"""Unit tests for Layer 2: Language detection."""

import pytest
from unittest.mock import patch, MagicMock

from app.core.cv_pipeline.layer2_language import LanguageDetectionResult, language_detection


def make_lang_result(lang, prob):
    m = MagicMock()
    m.lang = lang
    m.prob = prob
    return m


@patch("app.core.cv_pipeline.layer2_language.detect_langs")
def test_english_cv_detected_correctly(mock_detect):
    mock_detect.return_value = [make_lang_result("en", 0.95)]

    result = language_detection("This is an English CV with lots of professional experience.")

    assert result.language == "en"
    assert result.is_english is True
    assert result.should_proceed_fully is True
    assert result.flag_for_review is False


@patch("app.core.cv_pipeline.layer2_language.detect_langs")
def test_french_cv_flagged(mock_detect):
    mock_detect.return_value = [make_lang_result("fr", 0.92)]

    result = language_detection("Voici mon curriculum vitae professionnel.")

    assert result.language == "fr"
    assert result.is_english is False
    assert result.should_proceed_fully is False
    assert result.flag_for_review is True


@patch("app.core.cv_pipeline.layer2_language.detect_langs")
def test_low_confidence_detection_flagged(mock_detect):
    mock_detect.return_value = [make_lang_result("en", 0.5)]

    result = language_detection("Some ambiguous text.")

    assert result.flag_for_review is True
    assert result.is_english is False  # confidence < 0.8


@patch("app.core.cv_pipeline.layer2_language.detect_langs")
def test_detection_failure_returns_safe_default(mock_detect):
    from langdetect import LangDetectException
    mock_detect.side_effect = LangDetectException(0, "no features")

    result = language_detection("x")

    assert result.language == "en"
    assert result.confidence == 0.0
    assert result.is_english is False
    assert result.flag_for_review is True
