from app.core.cv_pipeline.layer2_language import LanguageDetectionResult
from app.core.cv_pipeline.layer7_llm import LLMExtractionResult
from app.core.cv_pipeline.layer4_deterministic import DeterministicExtractionResult
import logging
from datetime import datetime, timezone
from app.core.cv_pipeline.layer1_extraction import extract_text_from_pdf
from app.core.cv_pipeline.layer2_language import language_detection
from app.core.cv_pipeline.layer3_sections import detect_sections
from app.core.cv_pipeline.layer4_deterministic import extract_deterministic
from app.core.cv_pipeline.layer5_taxonomy import match_taxonomy
from app.core.cv_pipeline.layer6_nlp import extract_nlp
from app.core.cv_pipeline.layer8_merger import merge_and_score
from app.core.cv_pipeline.models import CVExtractionResult
from app.modules.ai.service import AIService

logger = logging.getLogger(__name__)

def _failed_result(error: str) -> CVExtractionResult:
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
        extracted_at=datetime.now(timezone.utc),
    )

async def run_extraction_pipeline(
    pdf_bytes: bytes,
    nlp,
    ai_service: AIService,
) -> tuple[CVExtractionResult, tuple[DeterministicExtractionResult, LLMExtractionResult, LanguageDetectionResult]]:

    # Layer 1 - extract text
    logger.info("Extracting text")
    text_result = extract_text_from_pdf(pdf_bytes)
    if not text_result.success:
        logger.info("Error extracting texts from pdf")
        return _failed_result(text_result.error), (DeterministicExtractionResult(None, None, None, None, None, [], {}), LLMExtractionResult(), LanguageDetectionResult("en", 0.0, False, False, True))
    
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

    llm_result = await ai_service.extract_cv_data(
        sections,
        already_extracted
    )

    # Layer 8 - merge and score
    return merge_and_score(
        deterministic,
        taxonomy,
        nlp_result,
        llm_result,
        text_result,
        lang_result
    ), (deterministic, llm_result, lang_result)
