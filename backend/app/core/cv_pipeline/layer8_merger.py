"""Layer 8 — merge and score all extraction layer outputs.

Combines results from layers 1–7 into a single CVExtractionResult,
deduplicates skills, validates fields, and computes an overall confidence
score.
"""

import re
from datetime import UTC, datetime

from app.core.cv_pipeline.layer1_extraction import TextExtractionResult
from app.core.cv_pipeline.layer2_language import LanguageDetectionResult
from app.core.cv_pipeline.layer4_deterministic import (
    EMAIL_PATTERN,
    PHONE_PATTERNS,
    DeterministicExtractionResult,
)
from app.core.cv_pipeline.layer5_taxonomy import TaxonomyMatchResult
from app.core.cv_pipeline.layer6_nlp import NLPExtractionResult
from app.core.cv_pipeline.layer7_llm import LLMExtractionResult
from app.core.cv_pipeline.models import CVExtractionResult, EducationEntry, WorkEntry

CONFIDENCE_WEIGHTS = {
    "email": 0.15,
    "phone": 0.10,
    "full_name": 0.15,
    "skills": 0.20,
    "work_history": 0.20,
    "education": 0.10,
    "current_title": 0.10,
}


def _compute_overall_confidence(field_confidence: dict[str, str]) -> float:
    """Compute a weighted overall confidence score from per-field confidence values."""
    score_map = {"high": 1.0, "medium": 0.6, "low": 0.2, "not_found": 0.0}
    total = 0.0

    for field, weight in CONFIDENCE_WEIGHTS.items():
        conf = field_confidence.get(field, "not_found")
        total += score_map[conf] * weight

    return round(total, 2)


def _deduplicate_skills(
    taxonomy_skills: list[str], llm_skills: list[str]
) -> tuple[list[str], list[str]]:
    """Return (taxonomy_skills, llm_only_skills) where llm_only excludes duplicates."""
    normalised_taxonomy = {s.lower().strip() for s in taxonomy_skills}

    llm_only = [s for s in llm_skills if s.lower().strip() not in normalised_taxonomy]

    return taxonomy_skills, llm_only


def _validate_fields(
    email: str | None,
    phone: str | None,
    years_experience: int | None,
    skills: list[str],
    field_confidence: dict[str, str],
) -> tuple[str | None, str | None, int | None, list[str], dict[str, str]]:
    """Validate and clean extracted fields, updating confidence accordingly."""
    confidence = dict(field_confidence)

    # Validate email
    if email and not re.match(EMAIL_PATTERN, email, re.VERBOSE):
        email = None
        confidence["email"] = "low"

    # Validate phone — null if no pattern matches
    if phone:
        matched = any(re.match(pattern, phone) for pattern in PHONE_PATTERNS)
        if not matched:
            phone = None
            confidence["phone"] = "low"

    # Validate years_experience — must be 0-60
    if years_experience is not None:
        if (
            not isinstance(years_experience, int)
            or years_experience < 0
            or years_experience > 60
        ):
            years_experience = None

    # Clean skills — remove items > 50 chars, then deduplicate case-insensitively
    skills = [s for s in skills if len(s) <= 50]
    seen: set[str] = set()
    deduped = []
    for s in skills:
        key = s.lower().strip()
        if key not in seen:
            seen.add(key)
            deduped.append(s)
    skills = deduped

    return email, phone, years_experience, skills, confidence


def merge_and_score(
    deterministic: DeterministicExtractionResult,
    taxonomy: TaxonomyMatchResult,
    nlp_result: NLPExtractionResult,
    llm_result: LLMExtractionResult,
    text_result: TextExtractionResult,
    lang_result: LanguageDetectionResult,
) -> CVExtractionResult:
    """Merge all extraction layer outputs into a final CVExtractionResult."""
    # Build merged field_confidence

    field_confidence = {
        "email": deterministic.field_confidence.get("email", "not_found"),
        "phone": deterministic.field_confidence.get("phone", "not_found"),
        "full_name": nlp_result.field_confidence.get("full_name", "not_found"),
        "skills": taxonomy.field_confidence.get("skills", "not_found"),
        "work_history": llm_result.field_confidence.get("work_history", "low"),
        "education": llm_result.field_confidence.get("education", "low"),
        "current_title": llm_result.field_confidence.get("current_title", "low"),
    }

    # Deduplicate skills
    taxonomy_skills, llm_only_skills = _deduplicate_skills(
        taxonomy.matched_skills, llm_result.skills
    )

    # Combined skills list
    all_skills = taxonomy_skills + llm_only_skills

    # convert work history dicts to WorkEntry dataclass
    work_history = [
        WorkEntry(
            company=entry.get("company"),
            title=entry.get("title"),
            start_date=entry.get("start_date"),
            end_date=entry.get("end_date"),
            duration_months=entry.get("duration_months"),
            description=entry.get("description"),
            is_current=entry.get("is_current", False),
        )
        for entry in llm_result.work_history
    ]

    # Convert education dicts to EducationEntry dataclass
    education = [
        EducationEntry(
            institution=entry.get("institution"),
            degree=entry.get("degree"),
            field=entry.get("field"),
            graduation_year=entry.get("graduation_year"),
            qualification_type=entry.get("qualification_type"),
        )
        for entry in llm_result.education
    ]

    # Validate fields
    email, phone, years_experience, all_skills, field_confidence = _validate_fields(
        email=deterministic.email,
        phone=deterministic.phone,
        years_experience=llm_result.years_experience,
        skills=all_skills,
        field_confidence=field_confidence,
    )

    # Compute overall confidence
    overall_confidence = _compute_overall_confidence(field_confidence)

    # Cap confidence for non-English CVs
    if not lang_result.is_english:
        overall_confidence = min(overall_confidence, 0.5)

    # Name: Prefer spaCy, fallback to llm
    full_name = nlp_result.full_name or llm_result.current_title

    # Build and return final result
    return CVExtractionResult(
        full_name=full_name,
        email=email,
        phone=phone,
        linkedin_url=deterministic.linkedin_url,
        location=None,  # Not extracted by any layer yet
        current_title=llm_result.current_title,
        seniority_level=llm_result.seniority_level,
        years_experience=years_experience,
        skills=all_skills,
        taxonomy_matched_skills=taxonomy_skills,
        llm_inferred_skills=llm_only_skills,
        summary=llm_result.summary,
        work_history=work_history,
        education=education,
        detected_language=lang_result.language,
        is_english=lang_result.is_english,
        language_confidence=lang_result.confidence,
        overall_confidence=overall_confidence,
        field_confidence=field_confidence,
        extraction_layers_used=[
            "layer1",
            "layer2",
            "layer3",
            "layer4",
            "layer5",
            "layer6",
            "layer7",
            "layer8",
        ],
        is_scanned=text_result.is_scanned,
        ocr_used=text_result.ocr_used,
        extracted_at=datetime.now(UTC),
    )
