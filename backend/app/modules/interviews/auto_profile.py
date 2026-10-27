"""A scoring profile built for a job that has none (docs/08_DECISIONS.md, item 42).

The employer may never set a scoring profile, and a job's interview brief may not name any
competencies. So that every strict interview is still scored on a structured, weighted framework
(the Colton Group method: a few job-related competencies, weights adding up to 100, the heaviest
two key), the first time such a job is scored a profile is drafted for its role, saved on the job
(``template_code`` "AUTO") and used for every candidate of the job, so they are compared on the same
competencies and weights. The employer sees it in "Scoring profile" and can change it.

If the draft fails or cannot be used, nothing is saved and that interview is scored by the simple
scorecard, as before; the next interview tries again.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.modules.interviews import scoring_profile as rules
from app.modules.interviews.models import JobScoringProfile
from app.modules.interviews.scoring_profile_service import load_profile

logger = logging.getLogger(__name__)

AUTO_CODE = "AUTO"
# The most competencies kept from a draft (the prompt asks for four to six).
MAX_DRAFTED = 8
MIN_DRAFTED = 3


def finalise(items: object) -> list[dict] | None:
    """The drafted competencies as a profile that can be saved, or None if they cannot be used.

    The model's output is never trusted as it is: names are tidied, repeated or unusable ones are
    dropped, the weights are scaled to add up to exactly 100 (whole numbers, none below 1), and the
    two heaviest are marked key. The result is checked with the same rules a hand-made profile must
    pass."""
    if not isinstance(items, list):
        return None
    kept: list[tuple[str, float]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        name = rules.clean_name(item.get("name"))
        weight = item.get("weight")
        if (
            not name
            or len(name) > rules.MAX_NAME_CHARS
            or name.casefold() in seen
            or isinstance(weight, bool)
            or not isinstance(weight, int | float)
            or weight <= 0
        ):
            continue
        seen.add(name.casefold())
        kept.append((name, float(weight)))
    kept = kept[:MAX_DRAFTED]
    if len(kept) < MIN_DRAFTED:
        return None

    weights = _scaled_to_100([weight for _, weight in kept])
    heaviest = sorted(range(len(kept)), key=lambda index: (-weights[index], index))[:2]
    profile = [
        {"name": name, "weight": weights[index], "key": index in heaviest}
        for index, (name, _) in enumerate(kept)
    ]
    return profile if not rules.problems_with(profile) else None


def _scaled_to_100(weights: list[float]) -> list[int]:
    """Whole-number weights in the same proportions that add up to exactly 100, each at least 1
    (the largest-remainder method)."""
    total = sum(weights)
    exact = [weight * 100 / total for weight in weights]
    scaled = [max(1, int(value)) for value in exact]
    by_remainder = sorted(range(len(scaled)), key=lambda index: exact[index] - int(exact[index]), reverse=True)
    step = 0
    while sum(scaled) < 100:
        scaled[by_remainder[step % len(scaled)]] += 1
        step += 1
    while sum(scaled) > 100:
        largest = max(range(len(scaled)), key=lambda index: scaled[index])
        if scaled[largest] <= 1:
            break
        scaled[largest] -= 1
    return scaled


def _job_context(job) -> str:
    """The role as text for the drafting model, from the fields the employer filled in."""
    parts = [
        f"Title: {job.title}",
        f"Seniority: {job.seniority_level}" if getattr(job, "seniority_level", None) else "",
        f"About the role: {job.about_the_role}" if job.about_the_role else "",
        f"Key responsibilities: {job.key_responsibilities}" if job.key_responsibilities else "",
        f"Requirements: {job.requirements}" if job.requirements else "",
        f"Technical competencies: {job.technical_competencies}" if job.technical_competencies else "",
    ]
    return "\n\n".join(part for part in parts if part)


async def ensure_profile(db, job, questions: list[dict], ai_service) -> JobScoringProfile | None:
    """The job's scoring profile, building and saving one if it has none.

    ``questions`` are the interview's questions as they were when it started (``[{"text", ...}]``).
    Returns None when there is none and one could not be built; never raises. Two interviews of one
    job scored at the same moment may both ask the model, but only the first profile is kept and
    both use it."""
    try:
        existing = await load_profile(db, job.id)
        if existing is not None:
            return existing
        drafted = await ai_service.draft_scoring_profile(
            job_context=_job_context(job),
            interview_brief=job.interview_brief or "",
            questions=[question["text"] for question in questions or [] if question.get("text")],
        )
        competencies = finalise(drafted)
        if competencies is None:
            logger.warning("auto profile: the draft for job %s could not be used", job.id)
            return None
        await db.execute(
            insert(JobScoringProfile)
            .values(
                id=uuid.uuid4(),
                job_id=job.id,
                competencies=competencies,
                bands=dict(rules.DEFAULT_BANDS),
                key_min_rating=rules.DEFAULT_KEY_MIN_RATING,
                template_code=AUTO_CODE,
            )
            .on_conflict_do_nothing(index_elements=["job_id"])
        )
        await db.flush()
        result = await db.execute(
            select(JobScoringProfile)
            .where(JobScoringProfile.job_id == job.id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()
    except Exception:
        logger.exception("auto profile: could not build a scoring profile for job %s", job.id)
        return None
