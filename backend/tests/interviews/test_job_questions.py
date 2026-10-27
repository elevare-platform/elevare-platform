"""A job's list of strict-interview questions: reading, saving and drafting, over HTTP.

The same questions go to every candidate on the job. The employer edits the list; the AI only
ever drafts, and a draft is never saved on its own. Access is the shared company rule (D2): the
job's owner means anyone in the company that owns it.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.modules.auth.jwt_handler import create_token_pair
from app.modules.interviews.models import JobInterviewQuestion
from app.modules.interviews.question_rules import CLOSING_QUESTION_TEXT
from tests.conftest import (
    make_admin,
    make_employer,
    make_job,
    make_organization_for,
)

BRIEF = "Probe system design, testing habits and how they handle an outage."


def q(text="Tell us about a time you handled a production outage.", seconds=120, source="EMPLOYER"):
    return {"text": text, "time_limit_seconds": seconds, "source": source}


async def _company(db_session, brief=BRIEF):
    """A company with an owner, a teammate and a job. Returns (owner, teammate, job)."""
    owner = make_employer()
    db_session.add(owner)
    await db_session.flush()
    organization = await make_organization_for(db_session, owner, company_name="Acme")
    teammate = make_employer(organization_id=organization.id)
    db_session.add(teammate)
    job = make_job(owner.id, interview_brief=brief)
    db_session.add(job)
    await db_session.flush()
    return owner, teammate, job


def _headers(user):
    token = create_token_pair(user.id, user.role)["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _url(job, tail=""):
    return f"/api/v1/interviews/jobs/{job.id}/questions{tail}"


async def _save(client, user, job, questions, follow_up_mode=None):
    body = {"questions": questions}
    if follow_up_mode is not None:
        body["follow_up_mode"] = follow_up_mode
    return await client.put(_url(job), json=body, headers=_headers(user))


async def _rows(db_session, job):
    return (
        await db_session.execute(
            select(JobInterviewQuestion)
            .where(JobInterviewQuestion.job_id == job.id)
            .order_by(JobInterviewQuestion.position)
        )
    ).scalars().all()


# --- reading -------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_job_with_no_questions_returns_an_empty_list_and_the_limits(client, db_session):
    owner, _teammate, job = await _company(db_session)

    response = await client.get(_url(job), headers=_headers(owner))

    assert response.status_code == 200
    assert response.json() == {
        "questions": [],
        "total_seconds": 0,
        # No cap on the count: only what the 20 minutes allow at the shortest answer time.
        "max_questions": 40,
        "default_questions": 5,
        "max_total_seconds": 1200,
        "closing_question": {"text": CLOSING_QUESTION_TEXT, "time_limit_seconds": 90},
        "style": "live",
        "competencies": [],
        "untested_competencies": [],
        "follow_up_mode": "STANDARD",
    }


@pytest.mark.asyncio
async def test_the_response_says_which_interview_new_invitations_use(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "interview_style", "strict")
    owner, _teammate, job = await _company(db_session)

    response = await client.get(_url(job), headers=_headers(owner))

    assert response.json()["style"] == "strict"


# --- saving --------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_saved_list_comes_back_in_order_with_positions_and_a_total(client, db_session):
    owner, _teammate, job = await _company(db_session)
    questions = [
        q("First: describe a system you designed.", 180),
        q("Second: how do you test a risky change?", 120, "AI"),
        q("Third: what would you do when a deploy fails?", 90),
    ]

    saved = await _save(client, owner, job, questions)
    again = await client.get(_url(job), headers=_headers(owner))

    assert saved.status_code == 200
    body = again.json()
    assert [(x["position"], x["text"], x["time_limit_seconds"], x["source"]) for x in body["questions"]] == [
        (1, "First: describe a system you designed.", 180, "EMPLOYER"),
        (2, "Second: how do you test a risky change?", 120, "AI"),
        (3, "Third: what would you do when a deploy fails?", 90, "EMPLOYER"),
    ]
    assert body["total_seconds"] == 390
    assert saved.json() == body  # the save returns exactly what a later read returns


@pytest.mark.asyncio
async def test_saving_replaces_the_old_list_and_an_empty_list_clears_it(client, db_session):
    owner, _teammate, job = await _company(db_session)
    await _save(client, owner, job, [q("The old question number one?"), q("The old question number two?")])

    await _save(client, owner, job, [q("The only new question now?")])
    assert [r.text for r in await _rows(db_session, job)] == ["The only new question now?"]

    cleared = await _save(client, owner, job, [])
    assert cleared.status_code == 200 and cleared.json()["questions"] == []
    assert await _rows(db_session, job) == []


@pytest.mark.asyncio
async def test_saving_the_same_list_twice_is_fine(client, db_session):
    owner, _teammate, job = await _company(db_session)
    questions = [q("Question one is about system design?"), q("Question two is about testing?")]

    assert (await _save(client, owner, job, questions)).status_code == 200
    assert (await _save(client, owner, job, questions)).status_code == 200
    assert len(await _rows(db_session, job)) == 2


@pytest.mark.asyncio
async def test_extra_blanks_in_a_question_are_tidied_when_saved(client, db_session):
    owner, _teammate, job = await _company(db_session)

    await _save(client, owner, job, [q("   Why   do you want    this     role?   ")])

    assert (await _rows(db_session, job))[0].text == "Why do you want this role?"


@pytest.mark.asyncio
async def test_a_list_that_breaks_a_rule_is_refused_naming_every_problem_and_changes_nothing(
    client, db_session
):
    owner, _teammate, job = await _company(db_session)
    await _save(client, owner, job, [q("A good question that is already saved?")])

    refused = await _save(
        client,
        owner,
        job,
        [q("Why?"), q("A perfectly fine question here.", 20)] + [q("Filler question number %d here." % n, 300) for n in range(6)],
    )

    assert refused.status_code == 422
    body = refused.json()
    messages = [detail["message"] for detail in body["details"]]
    assert not any("at most" in m for m in messages)  # the count itself is not limited
    assert "Question 1 is too short to be a question." in messages
    assert any(m.startswith("Question 2 needs between 30 seconds and 10 minutes") for m in messages)
    assert any("add up to" in m and "limited to 20 minutes" in m for m in messages)
    assert all(detail["field"] == "questions" for detail in body["details"])
    # Refused: the saved list is exactly as it was.
    assert [r.text for r in await _rows(db_session, job)] == ["A good question that is already saved?"]


@pytest.mark.asyncio
async def test_ten_questions_are_saved_when_their_times_fit_the_interview(client, db_session):
    """There is no cap on how many questions, only on the total time (Colton's roles have 8 to 10)."""
    owner, _teammate, job = await _company(db_session)

    response = await _save(
        client, owner, job, [q("Question number %d about the work?" % n, 90) for n in range(1, 11)]
    )

    assert response.status_code == 200
    assert len(response.json()["questions"]) == 10
    assert response.json()["total_seconds"] == 900


@pytest.mark.asyncio
async def test_many_questions_are_still_refused_when_their_times_do_not_fit(client, db_session):
    owner, _teammate, job = await _company(db_session)

    refused = await _save(
        client, owner, job, [q("Question number %d about the work?" % n, 120) for n in range(1, 12)]
    )

    assert refused.status_code == 422
    assert any("limited to 20 minutes" in d["message"] for d in refused.json()["details"])


@pytest.mark.asyncio
async def test_probes_are_saved_tidied_and_returned_with_the_question(client, db_session):
    owner, _teammate, job = await _company(db_session)

    response = await _save(
        client,
        owner,
        job,
        [{**q("Tell us about a launch you led."), "probes": "  What was your  own part?  \n\nWhat did it deliver?\nwhat did it deliver?\n"}],
    )

    assert response.status_code == 200
    assert response.json()["questions"][0]["probes"] == "What was your own part?\nWhat did it deliver?"
    assert (await _rows(db_session, job))[0].probes == "What was your own part?\nWhat did it deliver?"


@pytest.mark.asyncio
async def test_a_question_without_probes_has_none(client, db_session):
    owner, _teammate, job = await _company(db_session)

    response = await _save(client, owner, job, [{**q("Tell us about a launch you led."), "probes": "  \n "}])

    assert response.json()["questions"][0]["probes"] is None


@pytest.mark.asyncio
async def test_too_many_or_too_long_probes_are_refused(client, db_session):
    owner, _teammate, job = await _company(db_session)

    refused = await _save(
        client,
        owner,
        job,
        [
            {**q("Tell us about a launch you led."), "probes": "\n".join(f"Probe {n}?" for n in range(7))},
            {**q("And another thing you owned?"), "probes": "x" * 301},
        ],
    )

    assert refused.status_code == 422
    messages = [d["message"] for d in refused.json()["details"]]
    assert any(m.startswith("Question 1 has too many probes") for m in messages)
    assert any(m.startswith("A probe on question 2 is too long") for m in messages)


@pytest.mark.asyncio
async def test_the_follow_up_mode_is_saved_with_the_list_and_kept_when_left_out(client, db_session):
    owner, _teammate, job = await _company(db_session)

    first = await _save(client, owner, job, [q("Tell us about a launch you led.")], follow_up_mode="PROBES_ONLY")
    again = await _save(client, owner, job, [q("Tell us about a launch you led.")])
    read = await client.get(_url(job), headers=_headers(owner))

    assert first.json()["follow_up_mode"] == "PROBES_ONLY"
    assert again.json()["follow_up_mode"] == "PROBES_ONLY"  # left out: the job keeps its mode
    assert read.json()["follow_up_mode"] == "PROBES_ONLY"


@pytest.mark.asyncio
async def test_an_unknown_follow_up_mode_is_refused(client, db_session):
    owner, _teammate, job = await _company(db_session)

    refused = await _save(client, owner, job, [q("Tell us about a launch you led.")], follow_up_mode="ALWAYS")

    assert refused.status_code == 422


@pytest.mark.asyncio
async def test_six_questions_that_fit_the_cap_are_saved(client, db_session):
    owner, _teammate, job = await _company(db_session)

    response = await _save(client, owner, job, [q("Question number %d is about your work." % n, 200) for n in range(6)])

    assert response.status_code == 200 and response.json()["total_seconds"] == 1200


@pytest.mark.asyncio
async def test_an_unknown_source_or_a_huge_request_is_refused(client, db_session):
    owner, _teammate, job = await _company(db_session)

    assert (await _save(client, owner, job, [q(source="ROBOT")])).status_code == 422
    assert (await _save(client, owner, job, [q("x" * 5001)])).status_code == 422
    assert (await _save(client, owner, job, [q()] * 51)).status_code == 422


@pytest.mark.asyncio
async def test_deleting_the_job_deletes_its_questions(client, db_session):
    owner, _teammate, job = await _company(db_session)
    await _save(client, owner, job, [q("A question that will go with the job?")])

    await db_session.delete(job)
    await db_session.flush()

    assert await _rows(db_session, job) == []


# --- who may use it ------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anyone_in_the_company_that_owns_the_job_can_read_and_save(client, db_session):
    owner, teammate, job = await _company(db_session)

    assert (await _save(client, teammate, job, [q("Saved by a teammate, not the creator?")])).status_code == 200
    assert (await client.get(_url(job), headers=_headers(teammate))).status_code == 200
    assert (await client.get(_url(job), headers=_headers(owner))).json()["questions"][0]["text"] == (
        "Saved by a teammate, not the creator?"
    )


@pytest.mark.asyncio
async def test_another_company_cannot_read_save_or_draft(client, db_session):
    _owner, _teammate, job = await _company(db_session)
    stranger = make_employer()
    db_session.add(stranger)
    await db_session.flush()
    await make_organization_for(db_session, stranger, company_name="Other Ltd")

    assert (await client.get(_url(job), headers=_headers(stranger))).status_code == 403
    assert (await _save(client, stranger, job, [q()])).status_code == 403
    assert (await client.post(_url(job, "/draft"), json={}, headers=_headers(stranger))).status_code == 403
    assert await _rows(db_session, job) == []


@pytest.mark.asyncio
async def test_an_admin_gets_no_extra_access_to_a_clients_job(client, db_session):
    """The shared ownership rule (D2) grants an admin nothing extra on someone else's job."""
    _owner, _teammate, job = await _company(db_session)
    admin = make_admin()
    db_session.add(admin)
    await db_session.flush()

    assert (await client.get(_url(job), headers=_headers(admin))).status_code == 403


@pytest.mark.asyncio
async def test_a_job_that_does_not_exist_is_a_404(client, db_session):
    owner, _teammate, _job = await _company(db_session)
    nobody = SimpleNamespace(id=uuid.uuid4())  # an id no job has

    assert (await client.get(_url(nobody), headers=_headers(owner))).status_code == 404
    assert (await _save(client, owner, nobody, [q()])).status_code == 404
    assert (await client.post(_url(nobody, "/draft"), json={}, headers=_headers(owner))).status_code == 404


@pytest.mark.asyncio
async def test_a_candidate_or_a_visitor_cannot_use_it(client, db_session):
    from tests.interviews.conftest import make_candidate_user

    _owner, _teammate, job = await _company(db_session)
    candidate = make_candidate_user()
    db_session.add(candidate)
    await db_session.flush()

    assert (await client.get(_url(job), headers=_headers(candidate))).status_code == 403
    assert (await client.get(_url(job))).status_code == 401
    assert (await client.put(_url(job), json={"questions": []})).status_code == 401


# --- drafting ------------------------------------------------------------------------------


class FakeAI:
    """Stands in for the Anthropic service: hands back the given pairs (or None) and records
    what it was asked."""

    def __init__(self, reply):
        self._reply = reply
        self.asked = []
        self._client = SimpleNamespace(close=AsyncMock())

    async def draft_interview_questions(self, **kwargs):
        self.asked.append(kwargs)
        return self._reply


@pytest.fixture
def ai(monkeypatch):
    """Patch the service the questions code builds, and give the test the fake."""
    holder = SimpleNamespace(current=FakeAI([]))
    monkeypatch.setattr(
        "app.modules.ai.service.AnthropicCVExtractionService", lambda: holder.current
    )

    def use(reply):
        holder.current = FakeAI(reply)
        return holder.current

    return use


@pytest.mark.asyncio
async def test_a_draft_needs_the_interview_brief(client, db_session, ai):
    owner, _teammate, job = await _company(db_session, brief=None)
    fake = ai([("A question that never gets asked?", 60)])

    response = await client.post(_url(job, "/draft"), json={}, headers=_headers(owner))

    assert response.status_code == 422
    assert "Write the interview brief first" in response.json()["message"]
    assert fake.asked == []  # no AI call, so no cost


@pytest.mark.asyncio
async def test_a_blank_brief_counts_as_no_brief(client, db_session, ai):
    owner, _teammate, job = await _company(db_session, brief="   \n  ")
    ai([("A question that never gets asked?", 60)])

    response = await client.post(_url(job, "/draft"), json={}, headers=_headers(owner))

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_a_draft_is_cleaned_marked_as_ai_and_never_saved(client, db_session, ai):
    owner, _teammate, job = await _company(db_session)
    ai([
        ("  Describe a system   you designed and why.  ", 100),
        ("How do you test a risky change before it ships?", 130),
        ("Why?", 60),  # too short: dropped
    ])

    response = await client.post(_url(job, "/draft"), json={}, headers=_headers(owner))

    assert response.status_code == 200
    body = response.json()
    assert body["questions"] == [
        {"text": "Describe a system you designed and why.", "time_limit_seconds": 90, "source": "AI", "competency": None, "probes": None},
        {"text": "How do you test a risky change before it ships?", "time_limit_seconds": 120, "source": "AI", "competency": None, "probes": None},
        # The scorecard's standard closing question is always the last one.
        {"text": CLOSING_QUESTION_TEXT, "time_limit_seconds": 90, "source": "AI", "competency": None, "probes": None},
    ]
    assert body["total_seconds"] == 300
    assert await _rows(db_session, job) == []  # a draft is only ever returned


@pytest.mark.asyncio
async def test_the_draft_is_asked_for_from_the_job_and_five_questions_by_default(
    client, db_session, ai
):
    owner, _teammate, job = await _company(db_session)
    fake = ai([("Describe a system you designed and why.", 90)])

    await client.post(_url(job, "/draft"), json={}, headers=_headers(owner))

    [asked] = fake.asked
    assert asked["count"] == 4  # five in all, the fifth being the standard closing question
    assert asked["interview_brief"] == BRIEF
    assert asked["title"] == job.title


@pytest.mark.asyncio
@pytest.mark.parametrize(("sent", "asked"), [(3, 2), (6, 5), (10, 9), (50, 37), (2, 1), (1, 1)])
async def test_the_count_is_never_more_than_the_interview_time_allows(client, db_session, ai, sent, asked):
    """No cap on the count, only on time: 20 minutes holds 38 questions at 30 seconds, one of them
    the closing question's own 90 seconds, so at most 37 are drafted by the AI."""
    owner, _teammate, job = await _company(db_session)
    fake = ai([("Describe a system you designed and why.", 90)])

    await client.post(_url(job, "/draft"), json={"count": sent}, headers=_headers(owner))

    assert fake.asked[0]["count"] == asked


@pytest.mark.asyncio
async def test_the_model_is_told_how_long_the_interview_is(client, db_session, ai, monkeypatch):
    """INTERVIEW_MAX_DURATION_MINUTES is the one setting for the interview's length, so the
    draft has to follow it (the user changed it to 3 and still got ten minutes of questions)."""
    monkeypatch.setattr(settings, "interview_max_duration_minutes", 3)
    owner, _teammate, job = await _company(db_session)
    fake = ai([(f"Describe how you handled situation number {n} at work.", 120) for n in range(5)])

    response = (await client.post(_url(job, "/draft"), json={}, headers=_headers(owner))).json()

    # The closing question's 90 seconds are kept out of what the AI may share between its own:
    # 3 minutes hold the closing question and three AI questions at the 30 second minimum.
    assert fake.asked[0]["count"] == 3
    assert fake.asked[0]["total_seconds"] == 90
    assert response["max_total_seconds"] == 180
    # Even if the model ignores it, what comes back fits and can be saved.
    assert response["total_seconds"] <= 180
    assert (await _save(client, owner, job, response["questions"])).status_code == 200


@pytest.mark.asyncio
async def test_a_short_interview_is_not_asked_for_more_questions_than_have_room(
    client, db_session, ai, monkeypatch
):
    """One minute holds two questions of the shortest answer time, not five."""
    monkeypatch.setattr(settings, "interview_max_duration_minutes", 1)
    owner, _teammate, job = await _company(db_session)
    fake = ai([("Describe a system you designed and why.", 60)])

    await client.post(_url(job, "/draft"), json={}, headers=_headers(owner))

    assert fake.asked[0]["count"] == 1  # one by the AI, and the closing question


@pytest.mark.asyncio
async def test_the_draft_ends_with_the_standard_closing_question_and_the_editor_is_told_it(
    client, db_session, ai
):
    owner, _teammate, job = await _company(db_session)
    ai([("Describe a system you designed and why.", 120), ("How do you test a risky change?", 90)])

    body = (await client.post(_url(job, "/draft"), json={}, headers=_headers(owner))).json()

    assert body["questions"][-1]["text"] == CLOSING_QUESTION_TEXT
    assert body["closing_question"] == {"text": CLOSING_QUESTION_TEXT, "time_limit_seconds": 90}
    assert (await _save(client, owner, job, body["questions"])).status_code == 200


@pytest.mark.asyncio
async def test_a_draft_of_one_question_has_no_closing_question(client, db_session, ai):
    owner, _teammate, job = await _company(db_session)
    ai([("Describe a system you designed and why.", 120)])

    body = (await client.post(_url(job, "/draft"), json={"count": 1}, headers=_headers(owner))).json()

    assert [q["text"] for q in body["questions"]] == ["Describe a system you designed and why."]


@pytest.mark.asyncio
async def test_a_draft_that_gives_nothing_usable_gets_no_closing_question_alone(client, db_session, ai):
    owner, _teammate, job = await _company(db_session)
    ai([("Why?", 60)])

    response = await client.post(_url(job, "/draft"), json={}, headers=_headers(owner))

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_the_saved_list_also_carries_the_closing_question_for_the_editor(client, db_session, ai):
    owner, _teammate, job = await _company(db_session)

    body = (await client.get(_url(job), headers=_headers(owner))).json()

    assert body["closing_question"]["text"] == CLOSING_QUESTION_TEXT


@pytest.mark.asyncio
async def test_drafted_times_are_shortened_so_the_list_can_always_be_saved(client, db_session, ai):
    owner, _teammate, job = await _company(db_session)
    ai([(f"Describe how you handled situation number {n} at work.", 600) for n in range(5)])  # 50 minutes

    draft = (await client.post(_url(job, "/draft"), json={}, headers=_headers(owner))).json()
    saved = await _save(client, owner, job, draft["questions"])

    assert draft["total_seconds"] <= 1200
    assert saved.status_code == 200  # what the AI drafted can be saved as it is


@pytest.mark.asyncio
@pytest.mark.parametrize("reply", [None, [], [("Why?", 60)], [("", 60), ("   ", 60)]])
async def test_a_draft_that_gives_nothing_usable_is_a_clear_503_and_nothing_is_saved(
    client, db_session, ai, reply
):
    owner, _teammate, job = await _company(db_session)
    ai(reply)

    response = await client.post(_url(job, "/draft"), json={}, headers=_headers(owner))

    assert response.status_code == 503
    assert response.json()["code"] == "INTERVIEW_QUESTIONS_DRAFT_FAILED"
    assert "write them yourself" in response.json()["message"]
    assert await _rows(db_session, job) == []


@pytest.mark.asyncio
async def test_the_ai_client_the_service_opened_is_closed_again(client, db_session, ai):
    owner, _teammate, job = await _company(db_session)
    fake = ai([("Describe a system you designed and why.", 90)])

    await client.post(_url(job, "/draft"), json={}, headers=_headers(owner))

    fake._client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_a_draft_is_limited_to_twenty_an_hour(client, db_session, ai):
    owner, _teammate, job = await _company(db_session)
    ai([("Describe a system you designed and why.", 90)])

    statuses = [
        (await client.post(_url(job, "/draft"), json={}, headers=_headers(owner))).status_code
        for _ in range(21)
    ]

    assert statuses[:20] == [200] * 20
    assert statuses[20] == 429


# --- the pricing screen's field ------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_pricing_response_carries_the_style_too(client, db_session, monkeypatch):
    owner, _teammate, _job = await _company(db_session)

    live = await client.get("/api/v1/interviews/pricing", headers=_headers(owner))
    monkeypatch.setattr(settings, "interview_style", "strict")
    strict = await client.get("/api/v1/interviews/pricing", headers=_headers(owner))

    assert live.json()["style"] == "live"
    assert strict.json()["style"] == "strict"
