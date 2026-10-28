"""The name an employer types in when the name read from a sourced CV is wrong.

Seen on the first real use: names read from CVs were wrong ("Regional Sales Manager", "| +234",
a name with a street on the end), and the client who sees them would be confused. The employer can
now type the right name; it replaces the CV's name wherever the candidate is shown, the CV and its
parsed data are not changed, and clearing it brings the CV's name back."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.modules.ai.enums import CVParsingStatus
from app.modules.ai.models import ParsedCVSubmission
from app.modules.auth.jwt_handler import create_token_pair
from app.modules.interviews.service import resolve_candidate_name
from app.modules.talent_pool.models import TalentPoolProfiles
from app.modules.talent_pool.service import resolve_match_display_fields
from tests.conftest import make_admin, make_employer, make_job, make_organization_for
from tests.interviews.conftest import make_interview_list_entry


def _headers(user):
    return {"Authorization": f"Bearer {create_token_pair(user.id, user.role)['access_token']}"}


async def sourced_profile(db_session, owner, *, parsed_name="Regional Sales Manager", **fields):
    """A sourced profile whose CV was read with the given (possibly wrong) name."""
    submission = ParsedCVSubmission(
        uploaded_by=owner.id,
        filename="cv.pdf",
        parse_status=CVParsingStatus.COMPLETED.value,
        parsed_data={"full_name": parsed_name, "skills": ["sales"], "current_title": "Sales Manager"},
    )
    db_session.add(submission)
    await db_session.flush()
    profile = TalentPoolProfiles(
        parsed_submission_id=submission.id, added_by=owner.id, source="other", status="new", **fields
    )
    db_session.add(profile)
    await db_session.flush()
    await db_session.refresh(profile, ["parsed_submission", "candidate_profile"])
    return profile


async def an_employer(db_session, **org):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    organization = await make_organization_for(db_session, employer, **org)
    return employer, organization


def _url(profile):
    return f"/api/v1/talent-pool/{profile.id}/name"


async def reload(db_session, profile):
    await db_session.refresh(profile, ["parsed_submission"])
    await db_session.refresh(profile.parsed_submission)
    return profile


# ── Setting and clearing it ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_owner_types_the_right_name_and_it_replaces_the_one_read_from_the_cv(client, db_session):
    employer, _ = await an_employer(db_session)
    profile = await sourced_profile(db_session, employer)
    await db_session.commit()

    resp = await client.patch(_url(profile), json={"name": "Lateef Jakande"}, headers=_headers(employer))

    assert resp.status_code == 200
    assert resp.json() == {"id": str(profile.id), "candidate_name": "Lateef Jakande", "name_overridden": True}
    await reload(db_session, profile)
    assert profile.override_name == "Lateef Jakande"
    # The CV itself is not changed.
    assert profile.parsed_submission.parsed_data["full_name"] == "Regional Sales Manager"


@pytest.mark.asyncio
async def test_clearing_it_brings_the_name_from_the_cv_back(client, db_session):
    employer, _ = await an_employer(db_session)
    profile = await sourced_profile(db_session, employer, override_name="Typed Name")
    await db_session.commit()

    for body in ({"name": None}, {"name": ""}, {"name": "   "}):
        profile.override_name = "Typed Name"
        await db_session.commit()
        resp = await client.patch(_url(profile), json=body, headers=_headers(employer))
        assert resp.json() == {
            "id": str(profile.id), "candidate_name": "Regional Sales Manager", "name_overridden": False,
        }
        await reload(db_session, profile)
        assert profile.override_name is None


@pytest.mark.asyncio
async def test_the_name_is_tidied_and_limited(client, db_session):
    employer, _ = await an_employer(db_session)
    profile = await sourced_profile(db_session, employer)
    await db_session.commit()

    tidy = await client.patch(_url(profile), json={"name": "  Ada   Obi \n "}, headers=_headers(employer))
    too_long = await client.patch(_url(profile), json={"name": "x" * 121}, headers=_headers(employer))
    control = await client.patch(_url(profile), json={"name": "Ada\x00Obi"}, headers=_headers(employer))
    exactly = await client.patch(_url(profile), json={"name": "y" * 120}, headers=_headers(employer))

    assert tidy.json()["candidate_name"] == "Ada Obi"
    assert too_long.status_code == 422 and control.status_code == 422
    assert exactly.status_code == 200


# ── Who may ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_teammate_in_the_same_company_may_but_a_stranger_may_not(client, db_session):
    owner, organization = await an_employer(db_session, company_name="Acme")
    teammate = make_employer(organization_id=organization.id)
    stranger, _ = await an_employer(db_session, company_name="Other")
    db_session.add(teammate)
    profile = await sourced_profile(db_session, owner)
    await db_session.commit()

    denied = await client.patch(_url(profile), json={"name": "Nope"}, headers=_headers(stranger))
    allowed = await client.patch(_url(profile), json={"name": "Right Name"}, headers=_headers(teammate))

    assert denied.status_code == 403 and allowed.status_code == 200
    await reload(db_session, profile)
    assert profile.override_name == "Right Name"


@pytest.mark.asyncio
async def test_an_admin_may_rename_any_sourced_candidate(client, db_session):
    employer, _ = await an_employer(db_session)
    admin = make_admin()
    db_session.add(admin)
    profile = await sourced_profile(db_session, employer)
    await db_session.commit()

    resp = await client.patch(_url(profile), json={"name": "Admin Fixed"}, headers=_headers(admin))

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_a_holder_of_an_accepted_introduction_may_not_rename_an_admin_sourced_candidate(client, db_session):
    """The name is shown to everyone who sees the profile, so an employer who only holds an
    introduction to an admin-sourced candidate cannot change it for the others."""
    from app.modules.introductions.enums import IntroductionStatus
    from app.modules.introductions.models import IntroductionRequest

    admin = make_admin()
    employer, _ = await an_employer(db_session)
    db_session.add(admin)
    await db_session.flush()
    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()
    profile = await sourced_profile(db_session, admin)
    db_session.add(
        IntroductionRequest(
            employer_id=employer.id,
            job_id=job.id,
            talent_pool_profile_id=profile.id,
            status=IntroductionStatus.ACCEPTED.value,
            token=uuid4().hex,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
    )
    await db_session.commit()

    resp = await client.patch(_url(profile), json={"name": "Not Mine"}, headers=_headers(employer))

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_a_candidate_cannot_rename_anyone(client, db_session):
    from tests.interviews.test_interview_router import register_and_promote

    employer, _ = await an_employer(db_session)
    profile = await sourced_profile(db_session, employer)
    await db_session.commit()
    token, _user = await register_and_promote(client, db_session, "CANDIDATE")

    resp = await client.patch(_url(profile), json={"name": "X"}, headers={"Authorization": f"Bearer {token}"})
    anonymous = await client.patch(_url(profile), json={"name": "X"})

    assert resp.status_code == 403 and anonymous.status_code in (401, 403)


@pytest.mark.asyncio
async def test_a_self_registered_candidate_keeps_the_name_on_their_own_account(client, db_session):
    from tests.interviews.conftest import make_candidate_profile, make_candidate_user

    employer, _ = await an_employer(db_session)
    user = make_candidate_user()
    db_session.add(user)
    await db_session.flush()
    candidate = await make_candidate_profile(db_session, user)
    profile = TalentPoolProfiles(candidate_profile_id=candidate.id, added_by=employer.id, source="other", status="new")
    db_session.add(profile)
    await db_session.commit()

    resp = await client.patch(_url(profile), json={"name": "Someone Else"}, headers=_headers(employer))

    assert resp.status_code == 422 and resp.json()["code"] == "NAME_NOT_EDITABLE"


@pytest.mark.asyncio
async def test_an_unknown_profile_is_not_found(client, db_session):
    employer, _ = await an_employer(db_session)
    await db_session.commit()

    resp = await client.patch(f"/api/v1/talent-pool/{uuid4()}/name", json={"name": "X"}, headers=_headers(employer))

    assert resp.status_code == 404


# ── Where the typed name is used ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_typed_name_is_what_every_display_shows(db_session):
    employer, _ = await an_employer(db_session)
    profile = await sourced_profile(db_session, employer, override_name="Right Name")

    fields = await resolve_match_display_fields(db_session, profile, employer.id)

    assert (fields["name"], fields["name_overridden"]) == ("Right Name", True)
    assert resolve_candidate_name(profile) == "Right Name"


@pytest.mark.asyncio
async def test_without_a_typed_name_the_cvs_name_is_shown(db_session):
    employer, _ = await an_employer(db_session)
    profile = await sourced_profile(db_session, employer)

    fields = await resolve_match_display_fields(db_session, profile, employer.id)

    assert (fields["name"], fields["name_overridden"]) == ("Regional Sales Manager", False)


@pytest.mark.asyncio
async def test_the_interview_list_and_the_profile_response_carry_the_typed_name(client, db_session):
    employer, _ = await an_employer(db_session)
    job = make_job(employer.id, interview_brief="Probe design.")
    db_session.add(job)
    await db_session.flush()
    profile = await sourced_profile(db_session, employer)
    await make_interview_list_entry(db_session, employer.id, profile.id, job.id)
    await db_session.commit()

    before = (await client.get(f"/api/v1/interview-list?job_id={job.id}", headers=_headers(employer))).json()["items"][0]
    await client.patch(_url(profile), json={"name": "Right Name"}, headers=_headers(employer))
    after = (await client.get(f"/api/v1/interview-list?job_id={job.id}", headers=_headers(employer))).json()["items"][0]
    detail = await client.get(f"/api/v1/talent-pool/{profile.id}", headers=_headers(employer))

    assert (before["candidate_name"], before["name_overridden"]) == ("Regional Sales Manager", False)
    assert (after["candidate_name"], after["name_overridden"]) == ("Right Name", True)
    assert detail.status_code == 200
    assert (detail.json()["candidate_name"], detail.json()["name_overridden"]) == ("Right Name", True)
