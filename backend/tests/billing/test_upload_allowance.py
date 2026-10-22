"""The monthly CV-upload allowance, checked where every employer upload creates a submission.

The real ``stage_cv`` runs here (so the real check does), with only the PDF reading, the
file store, the cache and Celery taken out.
"""

import hashlib
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.core.exceptions import PlanLimitReachedException
from app.core.storage import MockStorageService
from app.modules.ai import cv_parsing_service as parsing_module
from app.modules.ai.cv_parsing_service import CVParsingService
from app.modules.ai.models import ParsedCVSubmission
from app.modules.auth.jwt_handler import create_token_pair
from app.modules.talent_pool.schema import TalentPoolSubmitRequest
from app.modules.talent_pool.service import TalentPoolService
from tests.conftest import (
    make_admin,
    make_employer,
    make_organization_for,
    make_subscription_for,
)
from tests.interviews.conftest import make_candidate_user


class RealStageService(CVParsingService):
    """The real ``stage_cv`` and everything under it; only ``fingerprint`` is replaced so the
    test files need not be real PDFs."""

    def __init__(self, db):
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)  # no cached parse
        super().__init__(db=db, storage=MockStorageService(), redis=cache, ai_service=None, nlp=None)

    def fingerprint(self, file: bytes, filename: str) -> str:
        return hashlib.sha256(file).hexdigest()


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(settings, "plan_gates_enabled", True)
    # Staging queues background work only when dispatched; make sure nothing reaches Celery.
    monkeypatch.setattr(parsing_module.run_full_pipeline_task, "delay", MagicMock())


async def _company(db_session, plan=None):
    owner = make_employer()
    db_session.add(owner)
    await db_session.flush()
    organization = await make_organization_for(db_session, owner)
    if plan:
        await make_subscription_for(db_session, organization, plan_code=plan)
    return owner, organization


async def _earlier_uploads(db_session, user, how_many):
    for i in range(how_many):
        db_session.add(ParsedCVSubmission(uploaded_by=user.id, filename=f"old-{i}.pdf"))
    await db_session.flush()


def _cv(label: str) -> bytes:
    return f"%PDF-1.4 {label} {uuid.uuid4().hex}".encode()


def _pool(db_session):
    return TalentPoolService(db_session, cv_service=RealStageService(db_session))


def _payload():
    return TalentPoolSubmitRequest(source="referral")


# --- the check itself ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_starter_company_can_stage_ten_uploads_and_not_an_eleventh(db_session):
    owner, _organization = await _company(db_session)
    service = RealStageService(db_session)

    for i in range(10):
        await service.stage_cv(owner, _cv("x"), f"cv{i}.pdf", f"hash-{uuid.uuid4().hex}")

    with pytest.raises(PlanLimitReachedException) as refused:
        await service.stage_cv(owner, _cv("x"), "cv11.pdf", f"hash-{uuid.uuid4().hex}")
    assert refused.value.code == "PLAN_LIMIT_REACHED"


@pytest.mark.asyncio
async def test_a_professional_company_is_not_stopped_at_ten(db_session):
    owner, _organization = await _company(db_session, plan="professional")
    await _earlier_uploads(db_session, owner, 10)

    # No error: Professional gets 100 a month.
    await RealStageService(db_session).stage_cv(owner, _cv("x"), "cv.pdf", f"hash-{uuid.uuid4().hex}")


@pytest.mark.asyncio
async def test_admins_and_candidates_are_never_limited(db_session):
    admin = make_admin()
    candidate = make_candidate_user()
    db_session.add_all([admin, candidate])
    await db_session.flush()
    await _earlier_uploads(db_session, admin, 12)
    await _earlier_uploads(db_session, candidate, 12)
    service = RealStageService(db_session)

    await service.stage_cv(admin, _cv("a"), "a.pdf", f"hash-{uuid.uuid4().hex}")
    await service.stage_cv(candidate, _cv("c"), "c.pdf", f"hash-{uuid.uuid4().hex}")


# --- through the Talent Pool upload ---------------------------------------------------------


@pytest.mark.asyncio
async def test_a_new_cv_is_refused_once_the_allowance_is_spent(db_session):
    owner, _organization = await _company(db_session)
    await _earlier_uploads(db_session, owner, 10)

    with pytest.raises(PlanLimitReachedException):
        await _pool(db_session)._add_cv(_cv("new"), "new.pdf", _payload(), owner, False)


@pytest.mark.asyncio
async def test_a_cv_already_in_the_pool_costs_nothing_even_at_the_limit(db_session):
    owner, _organization = await _company(db_session)
    pool = _pool(db_session)
    same_cv = _cv("same")
    await pool._add_cv(same_cv, "first.pdf", _payload(), owner, False)
    await _earlier_uploads(db_session, owner, 9)  # 10 in all: the allowance is now spent

    again = await pool._add_cv(same_cv, "again.pdf", _payload(), owner, False)

    assert again.status == "duplicate"


@pytest.mark.asyncio
async def test_a_batch_reports_the_files_it_could_not_take_and_still_takes_duplicates(db_session):
    owner, _organization = await _company(db_session)
    pool = _pool(db_session)
    known = _cv("known")
    await pool._add_cv(known, "known.pdf", _payload(), owner, False)
    await _earlier_uploads(db_session, owner, 9)

    results = await pool.submit_batch(
        [(_cv("fresh one"), "one.pdf"), (known, "known-again.pdf"), (_cv("fresh two"), "two.pdf")],
        _payload(),
        owner,
    )

    assert [r["status"] for r in results] == ["limit_reached", "duplicate", "limit_reached"]
    assert "10 CV uploads a month" in results[0]["error"]


# --- the CV Parser's batch upload ----------------------------------------------------------


@pytest.mark.asyncio
async def test_the_cv_parser_batch_stops_reading_when_the_allowance_runs_out(client, db_session):
    from app.main import app
    from app.modules.ai.cv_parsing_router import get_cv_parsing_service

    owner, _organization = await _company(db_session, plan="professional")
    await _earlier_uploads(db_session, owner, 99)  # one left of the 100
    app.dependency_overrides[get_cv_parsing_service] = lambda: RealStageService(db_session)
    token = create_token_pair(owner.id, owner.role)["access_token"]
    files = [("files", (f"cv{i}.pdf", _cv(f"batch{i}"), "application/pdf")) for i in range(3)]

    response = await client.post(
        "/api/v1/cv-parsing/submit/batch", files=files, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 201
    body = response.json()
    assert len(body) == 3
    assert body[0].get("status") != "limit_reached"  # the last one that fits is read
    assert [item["status"] for item in body[1:]] == ["limit_reached", "limit_reached"]
    assert "100 CV uploads a month" in body[1]["error"]
