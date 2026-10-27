"""The employer's choice of what the AI may do after an answer (docs/08_DECISIONS.md, item 40):
NONE (only the written questions), STANDARD (up to two neutral follow-ups, preferring the question's
prepared probes) and PROBES_ONLY (only a probe the employer wrote, in their words). Run through the
emailed-link routes with the speech-to-text and the follow-up model replaced by fakes."""

import pytest
from sqlalchemy import select, text, update

from app.core.config import settings
from app.modules.interviews.enums import FollowUpMode
from app.modules.interviews.follow_up import load_follow_up_mode, save_follow_up_mode
from app.modules.interviews.models import JobInterviewQuestion, StrictInterviewRun
from app.modules.interviews.strict import match_prepared_probe, prepared_probes

from .test_strict_interview import (  # noqa: F401  (the autouse fixture applies to these tests)
    FOLLOW_UP,
    _base,
    _conduct_never_ends_these,
    answer,
    make_strict,
    start,
)

OWN_PART = "What was your own part in it?"
OUTLETS = "How many outlets did that cover?"
PROBES = f"{OWN_PART}\n{OUTLETS}"


async def _prepare(db_session, interview, mode, probes_for_first=PROBES):
    """Give the job a follow-up mode and the first question some probes."""
    await save_follow_up_mode(db_session, interview.job.id, mode)
    await db_session.execute(
        update(JobInterviewQuestion)
        .where(JobInterviewQuestion.job_id == interview.job.id, JobInterviewQuestion.position == 1)
        .values(probes=probes_for_first)
    )
    await db_session.commit()


async def _first_answer(client, interview, clock):
    first = (await start(client, interview.token)).json()
    clock.advance(30)
    return (await answer(client, interview.token, first["turn"]["id"])).json()


# ---------------------------------------------------------------------------
# The helpers
# ---------------------------------------------------------------------------


def test_prepared_probes_are_the_lines_the_employer_wrote():
    assert prepared_probes("  What was your   own part?  \n\nHow big was it?\n") == [
        "What was your own part?",
        "How big was it?",
    ]
    assert prepared_probes(None) == []


def test_a_model_reply_must_match_a_prepared_probe_to_be_used():
    probes = [OWN_PART, "Walk me through the numbers."]

    assert match_prepared_probe("what was your own part in it", probes) == OWN_PART
    assert match_prepared_probe("Walk me through the numbers?", probes) == "Walk me through the numbers."
    assert match_prepared_probe("What did you change afterwards?", probes) is None
    assert match_prepared_probe(None, probes) is None


# ---------------------------------------------------------------------------
# NONE: only the written questions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_with_no_follow_ups_the_next_question_follows_and_the_model_is_not_asked(
    client, db_session, fakes, clock
):
    interview = await make_strict(db_session)
    await _prepare(db_session, interview, FollowUpMode.NONE)
    fakes.ai.replies = [FOLLOW_UP]

    body = await _first_answer(client, interview, clock)

    assert body["turn"]["kind"] == "QUESTION"
    assert body["turn"]["number"] == 2
    assert fakes.ai.calls == []  # not even asked: no cost


# ---------------------------------------------------------------------------
# STANDARD: as before, and the prepared probes are offered to the model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_standard_mode_asks_a_follow_up_and_shows_the_model_the_prepared_probes(
    client, db_session, fakes, clock
):
    interview = await make_strict(db_session)
    await _prepare(db_session, interview, FollowUpMode.STANDARD)
    fakes.ai.replies = [FOLLOW_UP]

    body = await _first_answer(client, interview, clock)

    assert (body["turn"]["kind"], body["turn"]["text"]) == ("FOLLOW_UP", FOLLOW_UP)
    call = fakes.ai.calls[0]
    assert call["prepared_probes"] == PROBES.splitlines()
    assert call["only_prepared"] is False


@pytest.mark.asyncio
async def test_a_job_that_never_chose_a_mode_behaves_as_before(client, db_session, fakes, clock):
    interview = await make_strict(db_session)
    fakes.ai.replies = [FOLLOW_UP]

    body = await _first_answer(client, interview, clock)

    assert body["turn"]["kind"] == "FOLLOW_UP"
    assert fakes.ai.calls[0]["prepared_probes"] == []


# ---------------------------------------------------------------------------
# PROBES_ONLY: a probe the employer wrote, and nothing else
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_probes_only_asks_a_prepared_probe_in_the_employers_words(client, db_session, fakes, clock):
    interview = await make_strict(db_session)
    await _prepare(db_session, interview, FollowUpMode.PROBES_ONLY)
    fakes.ai.replies = ["what was your own part in it?"]  # the model's spelling differs

    body = await _first_answer(client, interview, clock)

    assert (body["turn"]["kind"], body["turn"]["text"]) == ("FOLLOW_UP", OWN_PART)
    assert fakes.ai.calls[0]["only_prepared"] is True


@pytest.mark.asyncio
async def test_probes_only_drops_a_question_the_model_made_up(client, db_session, fakes, clock):
    interview = await make_strict(db_session)
    await _prepare(db_session, interview, FollowUpMode.PROBES_ONLY)
    fakes.ai.replies = [FOLLOW_UP]  # not one of the employer's probes

    body = await _first_answer(client, interview, clock)

    assert body["turn"]["kind"] == "QUESTION" and body["turn"]["number"] == 2


@pytest.mark.asyncio
async def test_probes_only_with_nothing_prepared_asks_nothing_and_does_not_call_the_model(
    client, db_session, fakes, clock
):
    interview = await make_strict(db_session)
    await _prepare(db_session, interview, FollowUpMode.PROBES_ONLY, probes_for_first=None)
    fakes.ai.replies = [FOLLOW_UP]

    body = await _first_answer(client, interview, clock)

    assert body["turn"]["kind"] == "QUESTION" and body["turn"]["number"] == 2
    assert fakes.ai.calls == []


@pytest.mark.asyncio
async def test_a_prepared_probe_already_asked_is_not_offered_again(client, db_session, fakes, clock):
    interview = await make_strict(db_session)
    await _prepare(db_session, interview, FollowUpMode.PROBES_ONLY)
    fakes.ai.replies = [OWN_PART, OWN_PART]  # the model tries to ask the same one twice
    first = await _first_answer(client, interview, clock)
    assert first["turn"]["text"] == OWN_PART

    clock.advance(30)
    second = (await answer(client, interview.token, first["turn"]["id"])).json()

    # Only the other probe was on offer the second time, and the repeat is refused.
    assert fakes.ai.calls[1]["prepared_probes"] == [OUTLETS]
    assert second["turn"]["kind"] == "QUESTION" and second["turn"]["number"] == 2


@pytest.mark.asyncio
async def test_probes_only_still_stops_at_the_follow_up_limit(client, db_session, fakes, clock, monkeypatch):
    monkeypatch.setattr(settings, "strict_max_follow_ups", 1)
    interview = await make_strict(db_session)
    await _prepare(db_session, interview, FollowUpMode.PROBES_ONLY)
    fakes.ai.replies = [OWN_PART, OUTLETS]
    first = await _first_answer(client, interview, clock)

    clock.advance(30)
    second = (await answer(client, interview.token, first["turn"]["id"])).json()

    assert second["turn"]["kind"] == "QUESTION" and second["turn"]["number"] == 2


# ---------------------------------------------------------------------------
# The mode belongs to the interview once it has started
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_mode_and_probes_are_copied_when_the_interview_starts(client, db_session, fakes, clock):
    interview = await make_strict(db_session)
    await _prepare(db_session, interview, FollowUpMode.PROBES_ONLY)
    first = (await start(client, interview.token)).json()

    # The employer changes their mind after the candidate has started.
    await save_follow_up_mode(db_session, interview.job.id, FollowUpMode.NONE)
    await db_session.execute(update(JobInterviewQuestion).values(probes=None))
    await db_session.commit()
    fakes.ai.replies = [OWN_PART]
    clock.advance(30)
    body = (await answer(client, interview.token, first["turn"]["id"])).json()

    run = (await db_session.execute(select(StrictInterviewRun))).scalars().one()
    assert run.follow_up_mode == "PROBES_ONLY"
    assert run.questions[0]["probes"] == PROBES
    assert body["turn"]["text"] == OWN_PART  # the interview kept what it started with


@pytest.mark.asyncio
async def test_a_run_started_before_the_mode_existed_is_standard(client, db_session, fakes, clock):
    interview = await make_strict(db_session)
    first = (await start(client, interview.token)).json()
    await db_session.execute(update(StrictInterviewRun).values(follow_up_mode=None))
    await db_session.commit()
    fakes.ai.replies = [FOLLOW_UP]
    clock.advance(30)

    body = (await answer(client, interview.token, first["turn"]["id"])).json()

    assert body["turn"]["kind"] == "FOLLOW_UP"


# ---------------------------------------------------------------------------
# What the candidate's screen is told
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_invite_page_says_which_mode_the_job_uses(client, db_session):
    interview = await make_strict(db_session)
    await _prepare(db_session, interview, FollowUpMode.NONE)

    info = (await client.get(_base(interview.token))).json()

    assert info["style"] == "strict" and info["follow_up_mode"] == "NONE"


@pytest.mark.asyncio
async def test_after_the_start_the_page_says_the_mode_the_interview_started_with(client, db_session):
    interview = await make_strict(db_session)
    await _prepare(db_session, interview, FollowUpMode.PROBES_ONLY)
    await start(client, interview.token)
    await save_follow_up_mode(db_session, interview.job.id, FollowUpMode.NONE)
    await db_session.commit()

    info = (await client.get(_base(interview.token))).json()

    assert info["follow_up_mode"] == "PROBES_ONLY"


@pytest.mark.asyncio
async def test_a_live_interview_reports_the_standard_mode(client, db_session):
    interview = await make_strict(db_session, strict=False)
    await save_follow_up_mode(db_session, interview.job.id, FollowUpMode.NONE)
    await db_session.commit()

    info = (await client.get(_base(interview.token))).json()

    assert info["style"] == "live" and info["follow_up_mode"] == "STANDARD"


@pytest.mark.asyncio
async def test_the_mode_defaults_to_standard_and_a_missing_table_does_not_break_it(db_session):
    interview = await make_strict(db_session)
    assert await load_follow_up_mode(db_session, interview.job.id) == FollowUpMode.STANDARD

    await db_session.execute(text("DROP TABLE job_interview_settings"))
    assert await load_follow_up_mode(db_session, interview.job.id) == FollowUpMode.STANDARD
