"""Unreadable CVs and unsaved scores are reported, so a rate is visible.

A CV that could not be read ran at 21 to 28% for two months unnoticed. Each such event
is now one structured log line and one grouped Sentry warning."""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core import quality_signals
from app.core.cv_pipeline.layer7_llm import LLMExtractionResult
from app.core.quality_signals import (
    CV_UNREADABLE_PARSE,
    SCORE_NOT_SAVED,
    report_quality_signal,
)
from app.modules.ai import tasks as ai_tasks
from app.modules.ai.scoring_outcome import CV_UNREADABLE, SCORING_FAILED

from .test_cv_parsing_cost import _make_cv_result, _run_pipeline_with_llm_result

LLM = LLMExtractionResult(skills=[], field_confidence={})


# --- the helper -------------------------------------------------------------------------


@pytest.fixture
def sentry(monkeypatch):
    scope = MagicMock()
    scope_manager = MagicMock()
    scope_manager.__enter__.return_value = scope
    scope_manager.__exit__.return_value = False
    fake = MagicMock()
    fake.new_scope.return_value = scope_manager
    monkeypatch.setattr(quality_signals, "sentry_sdk", fake)
    return SimpleNamespace(sdk=fake, scope=scope)


def test_it_logs_one_structured_line_that_is_easy_to_search(caplog, sentry):
    with caplog.at_level(logging.WARNING, logger="app.core.quality_signals"):
        report_quality_signal(SCORE_NOT_SAVED, reason="CV_UNREADABLE", kind="Application", row_id="abc")

    [record] = caplog.records
    assert record.getMessage() == "score_not_saved kind=Application reason=CV_UNREADABLE row_id=abc"


def test_it_sends_sentry_one_issue_per_kind_however_many_events(sentry):
    report_quality_signal(CV_UNREADABLE_PARSE, submission_id="s1")
    report_quality_signal(CV_UNREADABLE_PARSE, submission_id="s2")

    # Grouped by the kind, not by the message or the ids, so Sentry shows one issue
    # with a count and a rate instead of one issue per CV.
    assert sentry.scope.fingerprint == [CV_UNREADABLE_PARSE]
    assert sentry.sdk.capture_message.call_count == 2
    sentry.sdk.capture_message.assert_called_with(CV_UNREADABLE_PARSE, level="warning")
    sentry.scope.set_context.assert_called_with("signal", {"submission_id": "s2"})


def test_a_failing_report_never_breaks_the_work_it_reports_on(monkeypatch):
    broken = MagicMock()
    broken.new_scope.side_effect = RuntimeError("sentry is down")
    monkeypatch.setattr(quality_signals, "sentry_sdk", broken)

    report_quality_signal(SCORE_NOT_SAVED, reason="x")  # must not raise


# --- where it is used -------------------------------------------------------------------


@pytest.fixture
def reported(monkeypatch):
    calls = MagicMock()
    monkeypatch.setattr(ai_tasks, "report_quality_signal", calls)
    return calls


@pytest.mark.asyncio
async def test_an_unreadable_parse_is_reported_with_what_helps_diagnose_it(
    db_session, monkeypatch, reported
):
    unreadable = _make_cv_result(usable=False, overall_confidence=0.9)

    submission = await _run_pipeline_with_llm_result(monkeypatch, db_session, LLM, cv_result=unreadable)

    reported.assert_called_once()
    args, kwargs = reported.call_args
    assert args == (CV_UNREADABLE_PARSE,)
    assert kwargs["submission_id"] == submission.id
    assert {"scanned", "english", "confidence"} <= kwargs.keys()


@pytest.mark.asyncio
async def test_a_readable_parse_reports_nothing(db_session, monkeypatch, reported):
    await _run_pipeline_with_llm_result(
        monkeypatch, db_session, LLM, cv_result=_make_cv_result(usable=True, overall_confidence=0.9)
    )

    reported.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", [CV_UNREADABLE, SCORING_FAILED])
async def test_a_candidate_left_without_a_score_is_reported(reported, reason):
    repo = SimpleNamespace(update=AsyncMock())
    row = SimpleNamespace(id="row-1", ai_score=None, ai_fit_summary=None)

    await ai_tasks._save_unscored(AsyncMock(), repo, row, reason)

    reported.assert_called_once_with(SCORE_NOT_SAVED, reason=reason, kind="SimpleNamespace", row_id="row-1")


@pytest.mark.asyncio
async def test_a_candidate_who_keeps_a_real_score_is_not_reported(reported):
    repo = SimpleNamespace(update=AsyncMock())
    row = SimpleNamespace(id="row-1", ai_score=72, ai_fit_summary="A strong fit.")

    await ai_tasks._save_unscored(AsyncMock(), repo, row, SCORING_FAILED)

    repo.update.assert_not_awaited()
    reported.assert_not_called()
