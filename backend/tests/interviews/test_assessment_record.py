"""The candidate assessment record and the hiring panel's decision (docs/08_DECISIONS.md, item 44;
docs/16_COLTON_BRIEF.md, Section 7): the header, the top three strengths and gaps, what to verify and
what to ask referees, and a person's decision with its reason and sign-off."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select, text, update

from app.modules.ai.schema import InterviewScoringResult
from app.modules.auth.jwt_handler import create_token_pair
from app.modules.interviews import service as service_module
from app.modules.interviews import tasks as interviews_tasks
from app.modules.interviews.enums import InterviewStatus, TurnKind
from app.modules.interviews.models import (
    InterviewPanelDecision,
    InterviewTurn,
    InterviewWeightedScore,
    StrictInterviewRun,
)
from app.modules.interviews.service import (
    RECORD_INTERVIEWER,
    InterviewService,
    minutes_spent,
)
from tests.conftest import make_employer, make_job

from .test_interview_tasks import (
    _mock_anthropic_service,
    _patch_engine_to_use_test_session,
)
from .test_strict_interview import make_strict

T0 = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
GOOD_REASON = "The panel liked the route-to-market answer and wants to see the references."


def headers(user):
    return {"Authorization": f"Bearer {create_token_pair(user.id, user.role)['access_token']}"}


@pytest.fixture(autouse=True)
def storage(monkeypatch):
    fake = MagicMock()
    fake.generate_presigned_url = AsyncMock(return_value="https://signed.example/v")
    monkeypatch.setattr(service_module, "get_storage_service", lambda: fake)


async def scored(
    db_session, record=None, status=InterviewStatus.SCORED.value, started=T0, finished=None, last_answer=None
):
    """A finished strict interview, with the content of the record stored as scoring stores it.
    The candidate's last answer is at ``last_answer`` (17 minutes 40 seconds in by default); the video
    upload finishes at ``finished``."""
    interview = await make_strict(db_session, status=status, transcript="AI: q\n\nCandidate: a")
    interview.interview.completed_at = finished if finished is not None else T0 + timedelta(minutes=17, seconds=40)
    run = (await db_session.execute(select(StrictInterviewRun).where(StrictInterviewRun.interview_id == interview.interview.id))).scalar_one()
    run.started_at = started
    db_session.add(
        InterviewTurn(
            interview_id=interview.interview.id,
            position=1,
            kind=TurnKind.QUESTION.value,
            question_number=1,
            question_text="Tell me about a sale you closed.",
            time_limit_seconds=120,
            opened_at=started,
            answered_at=last_answer if last_answer is not None else T0 + timedelta(minutes=17, seconds=40),
        )
    )
    if record is not None:
        db_session.add(InterviewWeightedScore(interview_id=interview.interview.id, report={"record": record}))
    await db_session.commit()
    return interview


async def detail(client, interview, user=None):
    response = await client.get(
        "/api/v1/interviews/detail",
        params={"job_id": str(interview.job.id), "talent_pool_profile_id": str(interview.interview.talent_pool_profile_id)},
        headers=headers(user or interview.employer),
    )
    assert response.status_code == 200, response.text
    return response.json()


def decide_url(interview):
    return f"/api/v1/interviews/{interview.interview.talent_pool_profile_id}/panel-decision?job_id={interview.job.id}"


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_header_names_the_candidate_by_reference_the_role_the_date_and_how_long(client, db_session):
    interview = await scored(db_session)

    record = (await detail(client, interview))["record"]

    assert record["reference"] == f"EL-{interview.interview.id.hex[:8].upper()}"
    assert record["role"] == interview.job.title
    assert record["interviewer"] == RECORD_INTERVIEWER
    assert record["duration_minutes"] == 18  # 17 minutes 40 seconds
    assert record["interview_date"].startswith("2026-10-20T09:17")


@pytest.mark.asyncio
async def test_the_length_is_the_time_spent_answering_not_the_time_the_video_took_to_upload(client, db_session):
    """A failed or slow upload finishes hours after the last answer; it must not become 132 minutes."""
    interview = await scored(
        db_session,
        last_answer=T0 + timedelta(minutes=29, seconds=40),
        finished=T0 + timedelta(minutes=132),
    )

    record = (await detail(client, interview))["record"]

    assert record["duration_minutes"] == 30


def test_the_minutes_run_to_the_last_answer():
    assert minutes_spent(T0, None, T0 + timedelta(minutes=17, seconds=40)) == 18


def test_an_interview_that_was_stopped_counts_to_the_moment_it_ended():
    assert minutes_spent(T0, T0 + timedelta(minutes=12), T0 + timedelta(minutes=9)) == 12


def test_there_is_no_length_before_anything_was_answered_or_before_the_start():
    assert minutes_spent(T0, None, None) is None
    assert minutes_spent(None, None, T0 + timedelta(minutes=5)) is None


def test_a_clock_that_runs_backwards_is_never_negative():
    assert minutes_spent(T0, None, T0 - timedelta(minutes=3)) == 0


@pytest.mark.asyncio
async def test_the_top_three_strengths_and_gaps_are_the_first_three_in_the_order_given(client, db_session):
    interview = await scored(
        db_session,
        record={
            "strengths": ["One", "Two", "Three", "Four"],
            "gaps": ["Gap one", "", "  ", "Gap two"],
            "claims_to_verify": ["Grew sales 40% (unverified)"],
            "reference_check_questions": ["What did they personally do on the Lagos launch?"],
        },
    )

    record = (await detail(client, interview))["record"]

    assert record["top_strengths"] == ["One", "Two", "Three"]
    assert record["top_gaps"] == ["Gap one", "Gap two"]  # blanks are not gaps
    assert record["claims_to_verify"] == ["Grew sales 40% (unverified)"]
    assert record["reference_check_questions"] == ["What did they personally do on the Lagos launch?"]


@pytest.mark.asyncio
async def test_an_interview_scored_before_the_record_was_kept_has_the_header_and_empty_lists(client, db_session):
    interview = await scored(db_session)

    record = (await detail(client, interview))["record"]

    assert record["reference"].startswith("EL-")
    assert record["top_strengths"] == [] and record["top_gaps"] == []
    assert record["claims_to_verify"] == [] and record["reference_check_questions"] == []
    assert record["panel_decision"] is None


@pytest.mark.asyncio
async def test_a_live_interview_has_no_length_because_it_has_no_strict_clock(client, db_session):
    interview = await make_strict(db_session, strict=False, status=InterviewStatus.SCORED.value, transcript="AI: q\n\nCandidate: a")
    interview.interview.completed_at = T0
    await db_session.commit()

    record = (await detail(client, interview))["record"]

    assert record["duration_minutes"] is None and record["interview_date"] is not None


@pytest.mark.asyncio
async def test_the_record_does_not_change_the_score_report_the_employer_reads(client, db_session):
    interview = await scored(db_session, record={"strengths": ["A"], "gaps": [], "claims_to_verify": [], "reference_check_questions": []})

    body = await detail(client, interview)

    assert body["score_report"] is None  # a stored record alone is not a weighted score
    assert body["practical_case"] is None


# ---------------------------------------------------------------------------
# What scoring stores
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scoring_stores_the_content_of_the_record_for_every_interview(db_session, monkeypatch):
    interview = await make_strict(db_session, status=InterviewStatus.UPLOADED.value, transcript="AI: q\n\nCandidate: a")
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    monkeypatch.setattr(interviews_tasks, "assert_can_score_interviews", AsyncMock())
    _mock_anthropic_service(
        monkeypatch,
        result=InterviewScoringResult(
            score=71,
            summary="Fine.",
            strengths=["Clear route to market", "Owns the numbers"],
            weaknesses=["Light on supply chain"],
            claims_to_verify=["Opened 40 outlets (unverified)"],
            reference_check_questions=["Who led the distributor roll-out?"],
        ),
    )

    await interviews_tasks._transcribe_and_score_interview_async(str(interview.interview.id), notify=False)

    [row] = (await db_session.execute(select(InterviewWeightedScore))).scalars().all()
    assert row.report["record"] == {
        "strengths": ["Clear route to market", "Owns the numbers"],
        "gaps": ["Light on supply chain"],
        "claims_to_verify": ["Opened 40 outlets (unverified)"],
        "reference_check_questions": ["Who led the distributor roll-out?"],
    }
    assert "rows" not in row.report  # not a weighted score: the record is kept on its own


# ---------------------------------------------------------------------------
# The panel's decision
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_decision_is_recorded_with_its_reason_and_who_signed_it_off_and_shows_in_the_record(client, db_session):
    interview = await scored(db_session)
    interview.employer.first_name, interview.employer.last_name = "Ada", "Obi"
    await db_session.commit()

    response = await client.put(
        decide_url(interview), json={"decision": "SHORTLIST", "rationale": f"  {GOOD_REASON}  "}, headers=headers(interview.employer)
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["decision"], body["label"]) == ("SHORTLIST", "Shortlist")
    assert body["rationale"] == GOOD_REASON
    assert body["decided_by_name"] == "Ada Obi"
    shown = (await detail(client, interview))["record"]["panel_decision"]
    assert shown["label"] == "Shortlist" and shown["decided_by_name"] == "Ada Obi" and shown["rationale"] == GOOD_REASON


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("decision", "label"),
    [("STRONG_SHORTLIST", "Strong shortlist"), ("SHORTLIST", "Shortlist"), ("HOLD", "Hold"), ("DO_NOT_SHORTLIST", "Do not shortlist")],
)
async def test_each_of_the_four_decisions_of_the_clients_pack_can_be_recorded(client, db_session, decision, label):
    interview = await scored(db_session)

    response = await client.put(decide_url(interview), json={"decision": decision, "rationale": GOOD_REASON}, headers=headers(interview.employer))

    assert response.status_code == 200 and response.json()["label"] == label


@pytest.mark.asyncio
async def test_a_later_decision_is_added_not_overwritten_and_the_latest_is_shown(client, db_session):
    interview = await scored(db_session)
    await client.put(decide_url(interview), json={"decision": "HOLD", "rationale": "Waiting for the references."}, headers=headers(interview.employer))
    await db_session.execute(update(InterviewPanelDecision).values(decided_at=datetime.now(UTC) - timedelta(days=1)))
    await db_session.commit()

    await client.put(decide_url(interview), json={"decision": "SHORTLIST", "rationale": "References came back well."}, headers=headers(interview.employer))

    rows = (await db_session.execute(select(InterviewPanelDecision).order_by(InterviewPanelDecision.decided_at))).scalars().all()
    assert [row.decision for row in rows] == ["HOLD", "SHORTLIST"]  # both kept
    shown = (await detail(client, interview))["record"]["panel_decision"]
    assert shown["decision"] == "SHORTLIST" and shown["rationale"] == "References came back well."


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["", "   ", "ok", "Fine."])
async def test_a_decision_needs_a_reason_of_a_sentence_or_two(client, db_session, reason):
    interview = await scored(db_session)

    response = await client.put(decide_url(interview), json={"decision": "SHORTLIST", "rationale": reason}, headers=headers(interview.employer))

    assert response.status_code == 422 and response.json()["code"] == "RATIONALE_REQUIRED"
    assert (await db_session.execute(select(InterviewPanelDecision))).scalars().all() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["HIRED", "OFFER", "shortlist", "", None])
async def test_the_decision_stops_at_the_shortlist_hiring_is_not_an_option(client, db_session, decision):
    interview = await scored(db_session)

    response = await client.put(decide_url(interview), json={"decision": decision, "rationale": GOOD_REASON}, headers=headers(interview.employer))

    assert response.status_code == 422
    assert (await db_session.execute(select(InterviewPanelDecision))).scalars().all() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [InterviewStatus.PENDING.value, InterviewStatus.IN_PROGRESS.value])
async def test_nothing_can_be_decided_before_the_interview_has_finished(client, db_session, status):
    interview = await scored(db_session, status=status)

    response = await client.put(decide_url(interview), json={"decision": "SHORTLIST", "rationale": GOOD_REASON}, headers=headers(interview.employer))

    assert response.status_code == 422 and response.json()["code"] == "INTERVIEW_NOT_FINISHED"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [InterviewStatus.UPLOADED.value, InterviewStatus.ENDED_CONDUCT.value, InterviewStatus.STOPPED.value])
async def test_a_decision_can_be_recorded_on_an_interview_that_ended_early_or_is_still_being_scored(client, db_session, status):
    interview = await scored(db_session, status=status)

    response = await client.put(decide_url(interview), json={"decision": "HOLD", "rationale": GOOD_REASON}, headers=headers(interview.employer))

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_only_the_company_that_owns_the_job_can_record_a_decision(client, db_session):
    interview = await scored(db_session)
    outsider = make_employer()
    db_session.add(outsider)
    await db_session.flush()

    response = await client.put(decide_url(interview), json={"decision": "SHORTLIST", "rationale": GOOD_REASON}, headers=headers(outsider))

    assert response.status_code == 403
    assert (await db_session.execute(select(InterviewPanelDecision))).scalars().all() == []


@pytest.mark.asyncio
async def test_a_decision_needs_a_logged_in_employer(client, db_session):
    interview = await scored(db_session)

    assert (await client.put(decide_url(interview), json={"decision": "SHORTLIST", "rationale": GOOD_REASON})).status_code == 401


@pytest.mark.asyncio
async def test_a_candidate_cannot_record_a_decision(client, db_session):
    from tests.conftest import make_user

    interview = await scored(db_session)
    candidate = make_user(role="CANDIDATE")
    db_session.add(candidate)
    await db_session.flush()

    response = await client.put(decide_url(interview), json={"decision": "SHORTLIST", "rationale": GOOD_REASON}, headers=headers(candidate))

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_a_decision_for_a_candidate_who_was_never_interviewed_is_not_found(client, db_session):
    interview = await scored(db_session)
    job = make_job(interview.employer.id)
    db_session.add(job)
    await db_session.flush()
    url = f"/api/v1/interviews/{interview.interview.talent_pool_profile_id}/panel-decision?job_id={job.id}"

    response = await client.put(url, json={"decision": "SHORTLIST", "rationale": GOOD_REASON}, headers=headers(interview.employer))

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# What a shared link shows, and a deploy that has not run the migration yet
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_shared_link_gets_the_record_without_the_companys_own_decision(client, db_session):
    interview = await scored(db_session, record={"strengths": ["Clear"], "gaps": [], "claims_to_verify": [], "reference_check_questions": []})
    await client.put(decide_url(interview), json={"decision": "DO_NOT_SHORTLIST", "rationale": "An internal view not meant for outsiders."}, headers=headers(interview.employer))
    service = InterviewService(db_session)

    shared = await service.build_detail(interview.job, interview.interview, include_panel_decision=False)
    own = await service.build_detail(interview.job, interview.interview)

    assert shared.record.panel_decision is None
    assert shared.record.top_strengths == ["Clear"]
    assert own.record.panel_decision.label == "Do not shortlist"


@pytest.mark.asyncio
async def test_the_detail_still_loads_when_the_decisions_table_is_not_there_yet(client, db_session):
    interview = await scored(db_session)
    await db_session.execute(text("DROP TABLE interview_panel_decisions"))

    record = (await detail(client, interview))["record"]

    assert record["reference"].startswith("EL-") and record["panel_decision"] is None
