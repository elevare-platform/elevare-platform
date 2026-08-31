"""Tests for the Candidate Search plan gate — Professional+ only, structured
filters included (not just the semantic `query` field)."""

import pytest

from app.core.exceptions import PlanUpgradeRequiredException
from app.core.storage import MockStorageService
from app.modules.candidates.schema import CandidateSearchFilters
from app.modules.candidates.service import CandidateService
from tests.conftest import make_employer, make_organization_for, make_subscription_for


@pytest.mark.asyncio
async def test_search_blocked_on_starter_even_without_query(db_session):
    """Structured-filter-only search (no semantic query) is still gated."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    await make_organization_for(db_session, employer)

    service = CandidateService(db_session, storage=MockStorageService())
    with pytest.raises(PlanUpgradeRequiredException):
        await service.search_candidates(
            CandidateSearchFilters(skills=["Python"]), employer
        )


@pytest.mark.asyncio
async def test_search_allowed_on_professional(db_session):
    """Professional+ orgs can search without raising the plan gate."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    organization = await make_organization_for(db_session, employer)
    await make_subscription_for(db_session, organization)

    service = CandidateService(db_session, storage=MockStorageService())
    # No PlanUpgradeRequiredException means the gate passed — the exact
    # result count depends on unrelated data already in the shared dev DB.
    result = await service.search_candidates(
        CandidateSearchFilters(skills=["Python"]), employer
    )
    assert result.total >= 0
