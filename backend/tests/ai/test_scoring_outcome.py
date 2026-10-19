"""scoring_outcome: what counts as a real score, and what a failure may change."""

from types import SimpleNamespace

import pytest

from app.modules.ai.scoring_outcome import (
    CV_UNREADABLE,
    SCORING_FAILED,
    failure_fields,
    has_real_score,
)


def row(**fields):
    defaults = {"ai_score": None, "ai_fit_summary": None}
    return SimpleNamespace(**{**defaults, **fields})


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({}, False),  # never scored
        ({"ai_score": 0}, False),  # the old failure shape: 0 with no summary
        ({"ai_score": 0, "ai_fit_summary": ""}, False),
        ({"ai_score": 0, "ai_fit_summary": "A poor fit."}, True),  # a genuine zero
        ({"ai_score": 64, "ai_fit_summary": "A fit."}, True),
        ({"ai_score": 64}, True),  # any non-zero score stands on its own
    ],
)
def test_what_counts_as_a_real_score(fields, expected):
    assert has_real_score(row(**fields)) is expected


def test_a_failure_on_an_unscored_row_clears_everything_and_sets_the_reason():
    fields = failure_fields(row(), SCORING_FAILED)

    assert fields == {
        "ai_score_failure": SCORING_FAILED,
        "ai_score": None,
        "ai_strengths": None,
        "ai_weaknesses": None,
        "ai_fit_summary": None,
        "ai_score_job_hash": None,
        "ai_score_cv_hash": None,
        "ai_score_computed_at": None,
    }


def test_a_failure_on_a_fake_zero_replaces_it():
    fields = failure_fields(row(ai_score=0), CV_UNREADABLE)

    assert fields["ai_score"] is None
    assert fields["ai_score_failure"] == CV_UNREADABLE


def test_a_failure_changes_nothing_when_a_real_score_exists():
    assert failure_fields(row(ai_score=64, ai_fit_summary="A fit."), SCORING_FAILED) == {}


def test_the_failure_fields_clear_the_hashes_so_a_retry_is_not_skipped():
    fields = failure_fields(row(), SCORING_FAILED)

    assert fields["ai_score_job_hash"] is None
    assert fields["ai_score_cv_hash"] is None
