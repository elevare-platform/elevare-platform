"""Unit tests for Layer 8: Normalisation, merging, and confidence scoring."""

import pytest
from datetime import datetime, timezone

from app.core.cv_pipeline.layer1_extraction import TextExtractionResult
from app.core.cv_pipeline.layer2_language import LanguageDetectionResult
from app.core.cv_pipeline.layer4_deterministic import DeterministicExtractionResult
from app.core.cv_pipeline.layer5_taxonomy import TaxonomyMatchResult
from app.core.cv_pipeline.layer6_nlp import NLPExtractionResult
from app.core.cv_pipeline.layer7_llm import LLMExtractionResult
from app.core.cv_pipeline.layer8_merger import (
    _compute_overall_confidence,
    _deduplicate_skills,
    _validate_fields,
    merge_and_score,
    CONFIDENCE_WEIGHTS,
)


# ── Confidence scoring ────────────────────────────────────────────────────────

def test_all_high_confidence_gives_max_score():
    field_conf = {f: "high" for f in CONFIDENCE_WEIGHTS}
    score = _compute_overall_confidence(field_conf)
    assert score == 1.0


def test_all_not_found_gives_zero():
    field_conf = {f: "not_found" for f in CONFIDENCE_WEIGHTS}
    score = _compute_overall_confidence(field_conf)
    assert score == 0.0


def test_mixed_confidence_computed_correctly():
    field_conf = {
        "email": "high",       # 0.15
        "phone": "high",       # 0.10
        "full_name": "high",   # 0.15
        "skills": "high",      # 0.20
        "work_history": "not_found",  # 0.0
        "education": "not_found",     # 0.0
        "current_title": "not_found", # 0.0
    }
    score = _compute_overall_confidence(field_conf)
    assert score == round(0.15 + 0.10 + 0.15 + 0.20, 2)


# ── Skill deduplication ───────────────────────────────────────────────────────

def test_deduplicate_removes_llm_skills_in_taxonomy():
    taxonomy = ["python", "fastapi", "docker"]
    llm = ["Python", "FastAPI", "docker", "negotiation", "stakeholder management"]

    tax_out, llm_out = _deduplicate_skills(taxonomy, llm)

    assert tax_out == taxonomy
    assert "negotiation" in llm_out
    assert "Python" not in llm_out
    assert "FastAPI" not in llm_out


def test_deduplicate_case_insensitive():
    taxonomy = ["postgresql"]
    llm = ["PostgreSQL", "MongoDB"]

    _, llm_out = _deduplicate_skills(taxonomy, llm)

    assert "PostgreSQL" not in llm_out
    assert "MongoDB" in llm_out


# ── Field validation ─────────────────────────────────────────────────────────

def test_invalid_email_nulled_and_confidence_downgraded():
    email, _, _, _, conf = _validate_fields(
        email="not-an-email",
        phone=None,
        years_experience=None,
        skills=[],
        field_confidence={"email": "high"},
    )
    assert email is None
    assert conf["email"] == "low"


def test_valid_email_kept():
    email, _, _, _, _ = _validate_fields(
        email="john@example.com",
        phone=None,
        years_experience=None,
        skills=[],
        field_confidence={"email": "high"},
    )
    assert email == "john@example.com"


def test_years_experience_outside_range_nulled():
    _, _, years, _, _ = _validate_fields(
        email=None, phone=None,
        years_experience=100,
        skills=[],
        field_confidence={},
    )
    assert years is None


def test_years_experience_valid_kept():
    _, _, years, _, _ = _validate_fields(
        email=None, phone=None,
        years_experience=5,
        skills=[],
        field_confidence={},
    )
    assert years == 5


def test_skills_over_50_chars_removed():
    long_skill = "A" * 51
    _, _, _, skills, _ = _validate_fields(
        email=None, phone=None, years_experience=None,
        skills=["python", long_skill, "react"],
        field_confidence={},
    )
    assert long_skill not in skills
    assert "python" in skills


def test_duplicate_skills_removed_case_insensitively():
    _, _, _, skills, _ = _validate_fields(
        email=None, phone=None, years_experience=None,
        skills=["python", "Python", "PYTHON", "react"],
        field_confidence={},
    )
    assert len([s for s in skills if s.lower() == "python"]) == 1


# ── Layer 4 wins over Layer 7 for email ──────────────────────────────────────

def make_merge_inputs(email="john@example.com", phone="+2348012345678"):
    deterministic = DeterministicExtractionResult(
        email=email, phone=phone,
        linkedin_url=None, github_url=None, website_url=None,
        raw_dates=[], field_confidence={"email": "high", "phone": "high"},
    )
    taxonomy = TaxonomyMatchResult(
        matched_skills=["python", "fastapi"],
        matched_degrees=["bsc"],
        nigerian_certifications=[],
        field_confidence={"skills": "high", "degrees": "high", "nigerian_certifications": "not_found"},
    )
    nlp_result = NLPExtractionResult(
        full_name="John Doe",
        organisations=["Google"],
        job_titles=["Software Engineer"],
        field_confidence={"full_name": "high", "organisations": "medium", "job_titles": "medium"},
    )
    llm_result = LLMExtractionResult(
        skills=["negotiation"],
        years_experience=5,
        current_title="Software Engineer",
        seniority_level="senior",
        summary="Experienced engineer.",
        work_history=[],
        education=[],
        field_confidence={
            "skills": "medium", "years_experience": "medium",
            "current_title": "high", "seniority_level": "medium",
            "summary": "medium", "work_history": "low", "education": "low",
        },
    )
    text_result = TextExtractionResult(
        success=True, text="cv text", page_count=2,
        is_scanned=False, ocr_used=False, method_used="pdfplumber", error=None,
    )
    lang_result = LanguageDetectionResult(
        language="en", confidence=0.95,
        is_english=True, should_proceed_fully=True, flag_for_review=False,
    )
    return deterministic, taxonomy, nlp_result, llm_result, text_result, lang_result


def test_layer4_email_wins_in_final_result():
    args = make_merge_inputs(email="regex@example.com")
    result = merge_and_score(*args)
    assert result.email == "regex@example.com"


def test_skills_deduplicated_in_final_result():
    args = make_merge_inputs()
    result = merge_and_score(*args)
    all_lower = [s.lower() for s in result.skills]
    assert len(all_lower) == len(set(all_lower))


def test_non_english_confidence_capped():
    args = list(make_merge_inputs())
    args[5] = LanguageDetectionResult(
        language="fr", confidence=0.9,
        is_english=False, should_proceed_fully=False, flag_for_review=True,
    )
    result = merge_and_score(*args)
    assert result.overall_confidence <= 0.5
