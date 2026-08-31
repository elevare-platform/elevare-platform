"""Regression tests for the CVParsingCost fix.

Isolates the cost-row-writing logic in `_run_pipeline_async` from the rest
of the extraction pipeline by stubbing `run_extraction_pipeline` itself —
these tests are about "given this LLMExtractionResult, does the right
CVParsingCost row (or none) get written," not about real PDF/NLP
extraction, which is covered elsewhere.
"""
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.core.ai_pricing import ANTHROPIC_TOKEN_PRICES
from app.core.cv_pipeline.layer2_language import LanguageDetectionResult
from app.core.cv_pipeline.layer4_deterministic import DeterministicExtractionResult
from app.core.cv_pipeline.layer7_llm import LLMExtractionResult
from app.core.cv_pipeline.models import CVExtractionResult
from app.modules.ai import tasks as ai_tasks
from app.modules.ai.enums import CVParsingStatus
from app.modules.ai.models import CVParsingCost, ParsedCVSubmission

# A model actually present in ANTHROPIC_TOKEN_PRICES — settings.anthropic_model
# in the real .env may be a different, newer model not yet added to the
# pricing table, which would legitimately (and correctly) price as None.
# Tests pin a known-priced model instead of depending on .env contents.
_PRICED_MODEL = next(iter(ANTHROPIC_TOKEN_PRICES))


class _SameSessionCM:
    """Hands back the test's own db_session instead of a new one — mirrors
    tests/interviews/test_interview_tasks.py's identical helper."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


def _patch_engine_to_use_test_session(monkeypatch, db_session):
    # _run_pipeline_async does its own local
    # `from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine`
    # inside the function body, shadowing the module-level names — patching
    # ai_tasks.create_async_engine wouldn't reach it, so patch the real
    # source module instead.
    monkeypatch.setattr(
        "sqlalchemy.ext.asyncio.create_async_engine",
        lambda *a, **k: AsyncMock(dispose=AsyncMock()),
    )
    monkeypatch.setattr(
        "sqlalchemy.ext.asyncio.async_sessionmaker",
        lambda *a, **k: (lambda: _SameSessionCM(db_session)),
    )


def _make_cv_result(**overrides) -> CVExtractionResult:
    defaults = {
        "full_name": "Test Candidate",
        "email": "test@example.com",
        "phone": None,
        "linkedin_url": None,
        "location": None,
        "current_title": None,
        "seniority_level": None,
        "years_experience": None,
        "skills": ["Python"],
        "taxonomy_matched_skills": [],
        "llm_inferred_skills": [],
        "summary": None,
        "work_history": [],
        "education": [],
        "detected_language": "en",
        "is_english": True,
        "language_confidence": 0.9,
        "overall_confidence": 0.8,
        "field_confidence": {},
        "extraction_layers_used": ["llm"],
        "is_scanned": False,
        "ocr_used": False,
        "extracted_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return CVExtractionResult(**defaults)


async def _run_pipeline_with_llm_result(monkeypatch, db_session, llm_result):
    """Create a submission, stub the extraction pipeline to return
    `llm_result`, and run the real task body against it."""
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    monkeypatch.setattr(ai_tasks.settings, "anthropic_model", _PRICED_MODEL)

    submission = ParsedCVSubmission(
        uploaded_by=None,
        filename="cv.pdf",
        parse_status=CVParsingStatus.PENDING.value,
    )
    db_session.add(submission)
    await db_session.flush()

    deterministic = DeterministicExtractionResult(
        email=None,
        phone=None,
        linkedin_url=None,
        github_url=None,
        website_url=None,
        raw_dates=[],
        field_confidence={},
    )
    lang_result = LanguageDetectionResult(
        language="en",
        confidence=0.9,
        is_english=True,
        should_proceed_fully=True,
        flag_for_review=False,
    )
    cv_result = _make_cv_result()

    async def fake_run_extraction_pipeline(file, nlp, ai_service):
        return cv_result, (deterministic, llm_result, lang_result)

    monkeypatch.setattr(
        "app.core.cv_pipeline.pipeline.run_extraction_pipeline",
        fake_run_extraction_pipeline,
    )

    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()
    monkeypatch.setattr(
        "redis.asyncio.from_url", lambda *a, **k: mock_redis
    )

    from app.core.storage import MockStorageService

    monkeypatch.setattr(
        "app.core.storage.get_storage_service", lambda: MockStorageService()
    )

    await ai_tasks._run_pipeline_async(
        str(submission.id), "test-cache-key", file=b"%PDF-1.4 fake"
    )

    return submission


@pytest.mark.asyncio
async def test_pipeline_writes_real_cost_row_not_hardcoded_zero(db_session, monkeypatch):
    llm_result = LLMExtractionResult(
        skills=["Python"],
        field_confidence={"skills": "high"},
        input_tokens=1800,
        output_tokens=450,
    )
    submission = await _run_pipeline_with_llm_result(monkeypatch, db_session, llm_result)

    result = await db_session.execute(
        select(CVParsingCost).where(CVParsingCost.submission_id == submission.id)
    )
    cost_row = result.scalar_one()
    assert cost_row.input_tokens == 1800
    assert cost_row.output_tokens == 450
    assert cost_row.cost_usd is not None
    assert cost_row.cost_usd > 0


@pytest.mark.asyncio
async def test_low_confidence_with_real_usage_still_gets_cost_row(db_session, monkeypatch):
    """Regression for the original bug: the old gate skipped low-confidence
    extractions entirely, even when a real (billed) LLM call happened."""
    llm_result = LLMExtractionResult(
        skills=[],
        field_confidence={"skills": "low"},
        input_tokens=1200,
        output_tokens=300,
    )
    submission = await _run_pipeline_with_llm_result(monkeypatch, db_session, llm_result)

    result = await db_session.execute(
        select(CVParsingCost).where(CVParsingCost.submission_id == submission.id)
    )
    cost_row = result.scalar_one()
    assert cost_row.input_tokens == 1200
    assert cost_row.output_tokens == 300


@pytest.mark.asyncio
async def test_zero_usage_writes_no_cost_row(db_session, monkeypatch):
    """The exception-fallback LLMExtractionResult() (0/0 tokens) — no LLM
    call happened, so no cost row should be written."""
    llm_result = LLMExtractionResult(skills=[], field_confidence={})
    submission = await _run_pipeline_with_llm_result(monkeypatch, db_session, llm_result)

    result = await db_session.execute(
        select(CVParsingCost).where(CVParsingCost.submission_id == submission.id)
    )
    assert result.scalar_one_or_none() is None
