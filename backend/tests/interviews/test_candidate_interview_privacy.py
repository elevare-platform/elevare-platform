"""What a candidate may read about their own interview.

The AI score and rationale are the EMPLOYER's assessment of the candidate. No endpoint a candidate
can call may return them: not the one that shows their interview, and not the two that confirm the
recording, which a candidate can call again after the interview has been scored (a replayed
confirmation returns the interview as it is now).
"""

import pytest
from sqlalchemy import select

from app.modules.interviews.enums import InterviewStatus
from app.modules.interviews.models import Interview

from .test_strict_interview import _logged_in_strict, make_strict

EMPLOYER_ONLY = {"ai_score", "ai_rationale", "ai_scored_at"}


async def _score(db_session, interview):
    interview.status = InterviewStatus.SCORED.value
    interview.ai_score = 87
    interview.ai_rationale = "Strong on system design, vague on testing."
    interview.transcript = "AI: question\n\nCandidate: answer"
    await db_session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_the_candidates_own_interview_never_carries_the_employers_assessment(
    client, db_session, strict
):
    token, application = await _logged_in_strict(client, db_session, strict=strict)
    interview = (
        await db_session.execute(select(Interview).where(Interview.application_id == application.id))
    ).scalar_one()
    await _score(db_session, interview)

    resp = await client.get(
        f"/api/v1/interviews/applications/{application.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert not EMPLOYER_ONLY & set(body)
    assert "Strong on system design" not in resp.text and "ai_score" not in resp.text
    # What the candidate's screen does need is still there.
    assert body["status"] == "SCORED"
    assert body["style"] == ("strict" if strict else "live")
    assert body["id"] and "session_start_count" in body


@pytest.mark.asyncio
async def test_confirming_the_recording_again_after_scoring_does_not_reveal_the_assessment(
    client, db_session
):
    token, application = await _logged_in_strict(client, db_session)
    interview = (
        await db_session.execute(select(Interview).where(Interview.application_id == application.id))
    ).scalar_one()
    await _score(db_session, interview)

    resp = await client.post(
        f"/api/v1/interviews/applications/{application.id}/complete",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    assert not EMPLOYER_ONLY & set(resp.json())
    assert "Strong on system design" not in resp.text and "ai_score" not in resp.text
    assert resp.json()["status"] == "SCORED"


@pytest.mark.asyncio
async def test_confirming_the_recording_again_from_the_emailed_link_does_not_reveal_it_either(
    client, db_session
):
    interview = await make_strict(db_session)
    await _score(db_session, interview.interview)

    resp = await client.post(f"/api/v1/public/interviews/{interview.token}/complete", json={})

    assert resp.status_code == 200
    assert not EMPLOYER_ONLY & set(resp.json())
    assert "Strong on system design" not in resp.text and "ai_score" not in resp.text
    assert resp.json()["status"] == "SCORED"
