"""Layer 2 — language detection for CV text.

Detects the primary language of extracted CV text using langdetect.
Returns a LanguageDetectionResult indicating whether the document is
in English and whether it should proceed through the full pipeline.
"""

from dataclasses import dataclass

from langdetect import detect_langs


@dataclass
class LanguageDetectionResult:
    """Result of detecting the primary language of CV text."""

    language: str
    confidence: float
    is_english: bool
    should_proceed_fully: bool
    flag_for_review: bool


def _detect_language_with_langdetect(text: str) -> list[tuple[str, float]]:
    """Return a list of (language_code, probability) pairs from langdetect."""
    lang_list = []
    try:
        langs = detect_langs(text)
        for item in langs:
            lang_list.append((item.lang, item.prob))
    except Exception:
        return []

    return lang_list


def language_detection(text: str) -> LanguageDetectionResult:
    """Detect the primary language of the given text.

    Returns a LanguageDetectionResult indicating whether the text is
    English (confidence > 0.8) and whether it should be flagged for review.
    """
    language_list = _detect_language_with_langdetect(text)

    if not language_list:
        return LanguageDetectionResult(
            language="en",
            confidence=0.0,
            is_english=False,
            should_proceed_fully=False,
            flag_for_review=True,
        )

    language, confidence = language_list[0]
    is_english = language == "en" and confidence > 0.8

    return LanguageDetectionResult(
        language=language,
        confidence=confidence,
        is_english=is_english,
        should_proceed_fully=is_english,
        flag_for_review=(not is_english or confidence < 0.6),
    )
