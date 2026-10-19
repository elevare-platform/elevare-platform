"""What a scoring attempt leaves behind on a candidate row.

A scored row holds a score and the hashes of the CV and job it was scored on, and the
hashes are what stop it being scored again. A row that could NOT be scored must not
look like that: it used to be saved as a score of 0 with hashes, so nobody could tell
it from a candidate who is a genuinely poor fit, and it was never tried again.

Both scoring tasks (talent pool profiles and applications) use these rules, so the two
cannot drift apart.
"""

# Why a row has no score. Stored in ``ai_score_failure``; NULL means nothing is wrong.
CV_UNREADABLE = "CV_UNREADABLE"  # nothing could be read, so scoring was not attempted
SCORING_FAILED = "SCORING_FAILED"  # the scoring call failed; it can be tried again


class ScoringFailed(Exception):
    """The scoring call failed (it errored, was cut off or gave no usable score).

    Raised after the failure has been saved, so the Celery task's automatic retry
    tries again with backoff and the row says why it has no score in the meantime.
    """


def has_real_score(row) -> bool:
    """Whether the row holds a genuine score.

    A score of 0 with no summary is the shape older code saved when a call failed,
    so it does not count: a real assessment always has a summary.
    """
    if row.ai_score is None:
        return False
    return not (row.ai_score == 0 and not row.ai_fit_summary)


def failure_fields(row, reason: str) -> dict:
    """The values to save when a candidate could not be scored.

    A failure never replaces a real score: if the row has one (say the job was edited
    and the new attempt failed), nothing is changed and the old score stays. Otherwise
    any leftover fake score is cleared, and so are the hashes, so that a later attempt
    is not skipped as "already scored".
    """
    if has_real_score(row):
        return {}
    return {
        "ai_score_failure": reason,
        "ai_score": None,
        "ai_strengths": None,
        "ai_weaknesses": None,
        "ai_fit_summary": None,
        "ai_score_job_hash": None,
        "ai_score_cv_hash": None,
        "ai_score_computed_at": None,
    }
