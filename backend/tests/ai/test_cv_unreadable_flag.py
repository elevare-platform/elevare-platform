"""A CV with nothing readable is FLAGGED with a clear reason, not saved as an
ordinary completed parse.

Runs the real task body with the extraction pipeline stubbed (see
test_cv_parsing_cost.py): given this merged result, what does the submission row
say?"""

from unittest.mock import AsyncMock

import pytest

from app.core.cv_pipeline.layer7_llm import LLMExtractionResult
from app.core.cv_pipeline.usability import UNREADABLE_REASON
from app.modules.ai.enums import CVParsingStatus

from .test_cv_parsing_cost import _make_cv_result, _run_pipeline_with_llm_result

LLM = LLMExtractionResult(skills=[], field_confidence={})


@pytest.mark.asyncio
async def test_an_unreadable_cv_is_flagged_with_the_reason(db_session, monkeypatch):
    # Confident enough that "low confidence" is not what flags it.
    unreadable = _make_cv_result(usable=False, overall_confidence=0.9)

    submission = await _run_pipeline_with_llm_result(
        monkeypatch, db_session, LLM, cv_result=unreadable
    )

    assert submission.parse_status == CVParsingStatus.FLAGGED.value
    assert submission.flag_reasons == [UNREADABLE_REASON]
    # The stored parse says so too, for anything that reads it later.
    assert submission.parsed_data["usable"] is False


@pytest.mark.asyncio
async def test_a_readable_cv_is_completed_as_before(db_session, monkeypatch):
    readable = _make_cv_result(usable=True, overall_confidence=0.9)

    submission = await _run_pipeline_with_llm_result(
        monkeypatch, db_session, LLM, cv_result=readable
    )

    assert submission.parse_status == CVParsingStatus.COMPLETED.value
    assert submission.flag_reasons is None
    assert submission.parsed_data["usable"] is True


@pytest.mark.asyncio
async def test_an_unreadable_parse_is_not_cached(db_session, monkeypatch):
    """Cached, it would be handed to the next upload of the same CV for 7 days."""
    redis = AsyncMock()

    await _run_pipeline_with_llm_result(
        monkeypatch,
        db_session,
        LLM,
        cv_result=_make_cv_result(usable=False, overall_confidence=0.9),
        redis=redis,
    )

    redis.setex.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_readable_parse_is_still_cached(db_session, monkeypatch):
    redis = AsyncMock()

    await _run_pipeline_with_llm_result(
        monkeypatch,
        db_session,
        LLM,
        cv_result=_make_cv_result(usable=True, overall_confidence=0.9),
        redis=redis,
    )

    redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_an_unreadable_cv_that_is_also_low_confidence_lists_the_unreadable_reason_first(
    db_session, monkeypatch
):
    unreadable = _make_cv_result(usable=False, overall_confidence=0.1)

    submission = await _run_pipeline_with_llm_result(
        monkeypatch, db_session, LLM, cv_result=unreadable
    )

    assert submission.flag_reasons[0] == UNREADABLE_REASON
    assert "Low confidence extraction" in submission.flag_reasons
