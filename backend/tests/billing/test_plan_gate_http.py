"""The Professional-only routes, checked end to end over HTTP for a Starter company, a
Professional company, and a Starter company on the admin's exemption list.

Part of the plan 15.2 audit. These two routes (the bulk CV upload and bulk scoring) had no
test that a Starter company is refused. A request that is allowed through is stopped on
purpose before it can cost anything: the upload gets 21 files (one over the limit), and the
scoring request names a job that does not exist.
"""

import uuid

import pytest

from app.core.config import settings
from app.modules.auth.jwt_handler import create_token_pair
from app.modules.billing.models import PlanGateExemption
from tests.conftest import make_employer, make_organization_for, make_subscription_for

BATCH_URL = "/api/v1/cv-parsing/submit/batch"
SCORE_URL = "/api/v1/talent-pool/score-against-job"


@pytest.fixture(autouse=True)
def gates_on(monkeypatch):
    """The local .env turns gating off; these tests are about it being on."""
    monkeypatch.setattr(settings, "plan_gates_enabled", True)


async def _company(db_session, plan=None, exempt=False):
    """An employer with a company. `plan` gives it a paid subscription; `exempt` puts it on
    the exemption list. Returns the request headers."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    organization = await make_organization_for(db_session, employer)
    if plan:
        await make_subscription_for(db_session, organization, plan_code=plan)
    if exempt:
        db_session.add(
            PlanGateExemption(organization_id=organization.id, reason="Pilot customer")
        )
        await db_session.flush()
    token = create_token_pair(employer.id, employer.role)["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _twenty_one_pdfs():
    return [("files", (f"cv{i}.pdf", b"%PDF-1.4 test", "application/pdf")) for i in range(21)]


# --- bulk CV upload ------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_starter_company_cannot_upload_a_batch_of_cvs(client, db_session):
    headers = await _company(db_session)

    response = await client.post(BATCH_URL, files=_twenty_one_pdfs(), headers=headers)

    assert response.status_code == 403
    assert response.json()["code"] == "PLAN_UPGRADE_REQUIRED"


@pytest.mark.asyncio
async def test_a_professional_company_passes_the_batch_upload_gate(client, db_session):
    headers = await _company(db_session, plan="professional")

    response = await client.post(BATCH_URL, files=_twenty_one_pdfs(), headers=headers)

    # Past the plan gate, stopped by the 20-file limit before anything is parsed.
    assert response.status_code == 400
    assert "Maximum 20 files" in response.json()["message"]


@pytest.mark.asyncio
async def test_an_exempt_starter_company_passes_the_batch_upload_gate(client, db_session):
    headers = await _company(db_session, exempt=True)

    response = await client.post(BATCH_URL, files=_twenty_one_pdfs(), headers=headers)

    assert response.status_code == 400
    assert "Maximum 20 files" in response.json()["message"]


# --- bulk scoring against a job ------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_starter_company_cannot_score_its_pool_against_a_job(client, db_session):
    headers = await _company(db_session)

    response = await client.post(
        SCORE_URL, params={"job_id": str(uuid.uuid4())}, headers=headers
    )

    assert response.status_code == 403
    assert response.json()["code"] == "PLAN_UPGRADE_REQUIRED"


@pytest.mark.asyncio
@pytest.mark.parametrize("how", ["professional", "exempt"])
async def test_a_company_with_professional_access_passes_the_scoring_gate(
    client, db_session, how
):
    headers = await _company(
        db_session, plan="professional" if how == "professional" else None, exempt=how == "exempt"
    )

    response = await client.post(
        SCORE_URL, params={"job_id": str(uuid.uuid4())}, headers=headers
    )

    # Past the plan gate: the job does not exist, which is the answer we want to see here.
    assert response.status_code != 403
    assert response.json().get("code") != "PLAN_UPGRADE_REQUIRED"
