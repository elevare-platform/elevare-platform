"""Monthly allowances: the month window, the limits per plan, and the usage counts."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import settings
from app.core.exceptions import PlanLimitReachedException
from app.modules.ai.models import FitScoringCost, ParsedCVSubmission
from app.modules.billing.allowance import Allowance, AllowanceService, month_window
from app.modules.billing.models import PlanGateExemption
from tests.conftest import (
    make_employer,
    make_job,
    make_organization_for,
    make_subscription_for,
)
from tests.interviews.conftest import (
    make_application,
    make_candidate_user,
    make_talent_pool_profile,
)


@pytest.fixture(autouse=True)
def gates_on(monkeypatch):
    """The local .env turns gating off; most of these tests are about it being on."""
    monkeypatch.setattr(settings, "plan_gates_enabled", True)


async def _company(db_session, plan=None, exempt=False):
    """A company with one owner. Returns (owner, organization)."""
    owner = make_employer()
    db_session.add(owner)
    await db_session.flush()
    organization = await make_organization_for(db_session, owner)
    if plan:
        await make_subscription_for(db_session, organization, plan_code=plan)
    if exempt:
        db_session.add(PlanGateExemption(organization_id=organization.id, reason="Pilot"))
        await db_session.flush()
    return owner, organization


def _this_month():
    return datetime.now(UTC)


def _last_month():
    start, _ = month_window()
    return start - timedelta(days=5)


async def _upload(db_session, user, created_at=None):
    row = ParsedCVSubmission(
        uploaded_by=user.id,
        filename=f"cv-{uuid.uuid4().hex[:6]}.pdf",
        **({"created_at": created_at} if created_at else {}),
    )
    db_session.add(row)
    await db_session.flush()


async def _score_row(db_session, job, *, profile=None, application=None, created_at=None):
    row = FitScoringCost(
        job_id=job.id,
        talent_pool_profile_id=profile.id if profile else None,
        application_id=application.id if application else None,
        input_tokens=100,
        output_tokens=50,
        model="test-model",
        **({"created_at": created_at} if created_at else {}),
    )
    db_session.add(row)
    await db_session.flush()


# --- the month window ----------------------------------------------------------------------


def test_the_month_starts_at_midnight_on_the_1st_in_lagos():
    # Lagos is one hour ahead of UTC, so midnight there is 23:00 UTC the evening before.
    just_before = datetime(2026, 10, 31, 22, 30, tzinfo=UTC)  # 23:30 on 31 Oct in Lagos
    just_after = datetime(2026, 10, 31, 23, 30, tzinfo=UTC)  # 00:30 on 1 Nov in Lagos

    assert month_window(just_before) == (
        datetime(2026, 9, 30, 23, 0, tzinfo=UTC),
        datetime(2026, 10, 31, 23, 0, tzinfo=UTC),
    )
    assert month_window(just_after) == (
        datetime(2026, 10, 31, 23, 0, tzinfo=UTC),
        datetime(2026, 11, 30, 23, 0, tzinfo=UTC),
    )


def test_the_month_window_rolls_over_the_end_of_the_year():
    assert month_window(datetime(2026, 12, 15, tzinfo=UTC)) == (
        datetime(2026, 11, 30, 23, 0, tzinfo=UTC),
        datetime(2026, 12, 31, 23, 0, tzinfo=UTC),
    )


# --- the Allowance value -------------------------------------------------------------------


def test_an_allowance_knows_what_is_left_and_when_it_is_spent():
    resets = datetime(2026, 11, 30, 23, 0, tzinfo=UTC)

    assert Allowance("CV uploads", 10, 4, resets).remaining == 6
    assert not Allowance("CV uploads", 10, 9, resets).exhausted
    assert Allowance("CV uploads", 10, 10, resets).exhausted
    assert Allowance("CV uploads", 10, 12, resets).remaining == 0  # never negative
    assert Allowance("AI scores", 0, 0, resets).exhausted  # 0 means none at all
    unlimited = Allowance("AI scores", None, 999, resets)
    assert unlimited.unlimited and not unlimited.exhausted and unlimited.remaining is None


def test_the_message_says_how_much_was_used_and_when_it_resets():
    resets = datetime(2026, 11, 30, 23, 0, tzinfo=UTC)  # 1 December in Lagos

    message = Allowance("CV uploads", 10, 10, resets).message()

    assert "10 CV uploads a month" in message
    assert "used 10" in message
    assert "1 December" in message


# --- the limits per plan -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_each_plan_gets_its_own_limits(db_session):
    _o, starter = await _company(db_session)
    _o, professional = await _company(db_session, plan="professional")
    _o, enterprise = await _company(db_session, plan="enterprise")
    service = AllowanceService(db_session)

    assert (await service.cv_uploads(starter.id)).limit == 10
    assert (await service.ai_scores(starter.id)).limit == 0
    assert (await service.cv_uploads(professional.id)).limit == 100
    assert (await service.ai_scores(professional.id)).limit == 500
    assert (await service.cv_uploads(enterprise.id)).unlimited
    assert (await service.ai_scores(enterprise.id)).unlimited


@pytest.mark.asyncio
async def test_an_exempt_starter_company_gets_the_professional_limits(db_session):
    _o, organization = await _company(db_session, exempt=True)

    assert (await AllowanceService(db_session).cv_uploads(organization.id)).limit == 100


@pytest.mark.asyncio
async def test_no_limits_apply_while_plan_gating_is_off(db_session, monkeypatch):
    """Production today: gating is off and every company resolves to Professional. The
    allowances must not start capping live companies the moment this code is deployed."""
    monkeypatch.setattr(settings, "plan_gates_enabled", False)
    owner, organization = await _company(db_session)
    for _ in range(12):
        await _upload(db_session, owner)
    service = AllowanceService(db_session)

    assert (await service.cv_uploads(organization.id)).unlimited
    assert (await service.ai_scores(organization.id)).unlimited
    await service.require_cv_upload(organization.id)  # no error, although 12 were uploaded


@pytest.mark.asyncio
async def test_a_company_without_an_organization_record_has_no_limit(db_session):
    assert (await AllowanceService(db_session).cv_uploads(None)).unlimited


# --- counting uploads ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_uploads_count_this_month_by_everyone_in_the_company_only(db_session):
    owner, organization = await _company(db_session)
    teammate = make_employer(organization_id=organization.id)
    db_session.add(teammate)
    await db_session.flush()
    other_owner, _other = await _company(db_session)

    await _upload(db_session, owner)
    await _upload(db_session, teammate)  # a colleague's upload counts for the company
    await _upload(db_session, owner, created_at=_last_month())  # last month: not counted
    await _upload(db_session, other_owner)  # another company: not counted

    assert (await AllowanceService(db_session).cv_uploads(organization.id)).used == 2


@pytest.mark.asyncio
async def test_the_tenth_upload_is_allowed_and_the_eleventh_is_refused_on_starter(db_session):
    owner, organization = await _company(db_session)
    service = AllowanceService(db_session)
    for _ in range(9):
        await _upload(db_session, owner)

    await service.require_cv_upload(organization.id)  # the 10th may still come in
    await _upload(db_session, owner)

    with pytest.raises(PlanLimitReachedException) as refused:
        await service.require_cv_upload(organization.id)
    assert refused.value.code == "PLAN_LIMIT_REACHED"
    assert "10 CV uploads a month" in refused.value.message


@pytest.mark.asyncio
async def test_last_months_uploads_do_not_hold_a_company_back_this_month(db_session):
    owner, organization = await _company(db_session)
    for _ in range(10):
        await _upload(db_session, owner, created_at=_last_month())

    await AllowanceService(db_session).require_cv_upload(organization.id)  # no error


# --- counting AI scores --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_score_is_counted_once_per_candidate_and_job_even_after_retries(db_session):
    owner, organization = await _company(db_session, plan="professional")
    job_a = make_job(owner.id)
    job_b = make_job(owner.id, title="Another job")
    db_session.add_all([job_a, job_b])
    await db_session.flush()
    profile = await make_talent_pool_profile(db_session, owner.id)

    # Three calls to score the same profile for the same job (two retries): one score.
    for _ in range(3):
        await _score_row(db_session, job_a, profile=profile)
    # The same profile for another job is a second score.
    await _score_row(db_session, job_b, profile=profile)

    assert (await AllowanceService(db_session).ai_scores(organization.id)).used == 2


@pytest.mark.asyncio
async def test_applicants_and_pool_profiles_both_count_as_scores(db_session):
    owner, organization = await _company(db_session, plan="professional")
    job = make_job(owner.id)
    db_session.add(job)
    candidate_user = make_candidate_user()
    db_session.add(candidate_user)
    await db_session.flush()
    application = await make_application(db_session, candidate_user.id, job.id)
    profile = await make_talent_pool_profile(db_session, owner.id)

    await _score_row(db_session, job, application=application)
    await _score_row(db_session, job, profile=profile)

    assert (await AllowanceService(db_session).ai_scores(organization.id)).used == 2


@pytest.mark.asyncio
async def test_scores_of_last_month_and_of_other_companies_are_not_counted(db_session):
    owner, organization = await _company(db_session, plan="professional")
    other_owner, _other = await _company(db_session, plan="professional")
    job = make_job(owner.id)
    other_job = make_job(other_owner.id)
    db_session.add_all([job, other_job])
    await db_session.flush()
    profile = await make_talent_pool_profile(db_session, owner.id)
    other_profile = await make_talent_pool_profile(db_session, other_owner.id)

    await _score_row(db_session, job, profile=profile, created_at=_last_month())
    await _score_row(db_session, other_job, profile=other_profile)

    assert (await AllowanceService(db_session).ai_scores(organization.id)).used == 0
