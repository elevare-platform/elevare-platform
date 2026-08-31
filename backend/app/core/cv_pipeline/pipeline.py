"""CV extraction pipeline — orchestrates all 8 extraction layers.

Runs text extraction → language detection → section detection →
deterministic extraction → taxonomy matching → NLP extraction →
LLM extraction → merge and score, returning a CVExtractionResult.
"""

import logging
from datetime import UTC, datetime

from app.core.config import settings
from app.core.cv_pipeline.layer1_extraction import extract_text_from_pdf
from app.core.cv_pipeline.layer2_language import (
    LanguageDetectionResult,
    language_detection,
)
from app.core.cv_pipeline.layer3_sections import detect_sections
from app.core.cv_pipeline.layer4_deterministic import (
    DeterministicExtractionResult,
    extract_deterministic,
)
from app.core.cv_pipeline.layer5_taxonomy import match_taxonomy
from app.core.cv_pipeline.layer6_nlp import extract_nlp
from app.core.cv_pipeline.layer7_llm import LLMExtractionResult
from app.core.cv_pipeline.layer8_merger import merge_and_score
from app.core.cv_pipeline.models import CVExtractionResult
from app.modules.ai.service import AIService

logger = logging.getLogger(__name__)


def _failed_result(error: str) -> CVExtractionResult:
    """Build a CVExtractionResult representing a failed extraction."""
    return CVExtractionResult(
        full_name=None,
        email=None,
        phone=None,
        linkedin_url=None,
        location=None,
        current_title=None,
        seniority_level=None,
        years_experience=None,
        skills=[],
        taxonomy_matched_skills=[],
        llm_inferred_skills=[],
        summary=None,
        work_history=[],
        education=[],
        detected_language="unknown",
        is_english=False,
        language_confidence=0.0,
        overall_confidence=0.0,
        field_confidence={},
        extraction_layers_used=[],
        is_scanned=False,
        ocr_used=False,
        extracted_at=datetime.now(UTC),
    )


def _needs_escalation(llm_result: LLMExtractionResult) -> bool:
    """Decide whether a fast-model CV extraction should be re-run on the deep model.

    Triggers when the fast model's own output signals it struggled: either no
    usable field_confidence signal at all, an average confidence below the
    configured threshold, or an extraction that came back with neither skills
    nor work history despite having run.
    """
    if not llm_result.field_confidence:
        return True

    _CONFIDENCE_SCORES = {"low": 0.0, "medium": 0.5, "high": 1.0}
    scores = [
        _CONFIDENCE_SCORES.get(v, 0.0) for v in llm_result.field_confidence.values()
    ]
    avg_confidence = sum(scores) / len(scores) if scores else 0.0

    if avg_confidence < settings.ai_cv_confidence_escalation_threshold:
        return True

    if not llm_result.skills and not llm_result.work_history:
        return True

    return False


async def run_extraction_pipeline(
    pdf_bytes: bytes,
    nlp,
    ai_service: AIService,
) -> tuple[
    CVExtractionResult,
    tuple[DeterministicExtractionResult, LLMExtractionResult, LanguageDetectionResult],
    list[LLMExtractionResult],
]:
    """Run the full 8-layer CV extraction pipeline.

    Args:
        pdf_bytes: Raw PDF file bytes.
        nlp: A loaded spaCy language model instance.
        ai_service: The AI service used for LLM extraction.

    Returns:
        A tuple of (CVExtractionResult, (deterministic, llm_result, lang_result),
        llm_attempts) — llm_attempts lists every LLM extraction call actually
        made (one, or two if the fast model's result was escalated to the
        deep model), for accurate per-model cost tracking.

    """
    # Layer 1 - extract text
    logger.info("Extracting text")
    text_result = extract_text_from_pdf(pdf_bytes)
    if not text_result.success:
        logger.info("Error extracting texts from pdf")
        return (
            _failed_result(text_result.error),
            (
                DeterministicExtractionResult(None, None, None, None, None, [], {}),
                LLMExtractionResult(),
                LanguageDetectionResult("en", 0.0, False, False, True),
            ),
            [],
        )

    # Layer 2 - detect language
    lang_result = language_detection(text_result.text)

    # Layer 3 - detect sections
    sections = detect_sections(text_result.text)

    # Layer 4 - deterministic extarctions
    deterministic = extract_deterministic(text_result.text)

    # Layer 5 — taxonomy matching
    taxonomy = match_taxonomy(sections)

    # Layer 6 — NLP extraction
    nlp_result = extract_nlp(text_result.text, sections, nlp)

    # Layer 7 - LLM extraction (async)
    already_extracted = {
        "email": deterministic.email,
        "phone": deterministic.phone,
        "linkedin_url": deterministic.linkedin_url,
        "full_name": nlp_result.full_name,
        "taxonomy_skills": taxonomy.matched_skills,
        "organizations": nlp_result.organisations,
        "job_titles": nlp_result.job_titles,
        "raw_dates": deterministic.raw_dates,
    }

    first_model = (
        settings.anthropic_model_fast
        if settings.ai_tiering_enabled
        else settings.anthropic_model
    )
    llm_result = await ai_service.extract_cv_data(
        sections, already_extracted, model=first_model
    )
    llm_attempts = [llm_result]

    if settings.ai_tiering_enabled and _needs_escalation(llm_result):
        logger.info(
            "CV extraction escalated from %s to %s — fast-model confidence too low",
            settings.anthropic_model_fast,
            settings.anthropic_model,
        )
        llm_result = await ai_service.extract_cv_data(
            sections, already_extracted, model=settings.anthropic_model
        )
        llm_attempts.append(llm_result)

    # Layer 8 - merge and score
    return (
        merge_and_score(
            deterministic, taxonomy, nlp_result, llm_result, text_result, lang_result
        ),
        (deterministic, llm_result, lang_result),
        llm_attempts,
    )
