from dataclasses import dataclass
from langdetect import detect_langs


@dataclass
class LanguageDetectionResult:
    language: str
    confidence: float
    is_english: bool
    should_proceed_fully: bool
    flag_for_review: bool

def _detect_language_with_langdetect(text: str) -> list[tuple[str, float]]:
    lang_list = []
    try:
        langs = detect_langs(text)
        for item in langs:
            lang_list.append((item.lang, item.prob))
    except Exception:
        return []
    
    return lang_list

def language_detection(text: str) -> LanguageDetectionResult:
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
    is_english = (
        language == "en"
        and confidence > 0.8
    )
    
    return LanguageDetectionResult(
        language=language,
        confidence=confidence,
        is_english=is_english,
        should_proceed_fully=is_english,
        flag_for_review=(not is_english or confidence < 0.6)
    )