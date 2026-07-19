"""Tests for admin employer KYC review — list, approve, reject."""

from uuid import uuid4

import pytest

from app.core.exceptions import ProfileNotFoundException, ValidationException
from app.core.storage import MockStorageService
from app.modules.admin.service import AdminService
from app.modules.employer.models import KYCDocument
from app.modules.users.enums import UserRole
from app.modules.users.models import EmployerProfile
from tests.conftest import make_employer, make_user


async def make_employer_with_pending_kyc(db_session, *, with_document: bool = True):
    """Create an employer with a complete profile and a PENDING KYC submission."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    profile = EmployerProfile(
        user_id=employer.id,
        company_name="Test Corp",
        industry="Tech",
        company_size="11-50",
        is_profile_complete=True,
        kyc_status="PENDING",
    )
    db_session.add(profile)
    await db_session.flush()

    doc = None
    if with_document:
        doc = KYCDocument(
            employer_profile_id=profile.id,
            key=f"kyc/{profile.id}/business_reg.pdf",
            filename="business_reg.pdf",
            document_type="Business Registration",
        )
        db_session.add(doc)
        await db_session.flush()

    return employer, profile, doc


@pytest.mark.asyncio
async def test_list_kyc_submissions_filters_by_status(db_session):
    """list_kyc_submissions only returns profiles matching the given status."""
    _, profile, _doc = await make_employer_with_pending_kyc(db_session)

    other_employer = make_employer()
    db_session.add(other_employer)
    await db_session.flush()
    db_session.add(
        EmployerProfile(
            user_id=other_employer.id,
            company_name="Approved Co",
            industry="Tech",
            company_size="11-50",
            is_profile_complete=True,
            kyc_status="APPROVED",
        )
    )
    await db_session.flush()

    service = AdminService(db_session)
    result = await service.list_kyc_submissions(status="PENDING", limit=100)

    # Filter by the dev DB may hold other PENDING rows — isolate on our own profile.
    matches = [item for item in result["items"] if item.employer_profile_id == profile.id]
    assert len(matches) == 1
    assert matches[0].kyc_status == "PENDING"
    assert matches[0].company_name == "Test Corp"
    assert len(matches[0].documents) == 1
    assert all(item.kyc_status == "PENDING" for item in result["items"])


@pytest.mark.asyncio
async def test_moderate_kyc_approves_and_logs(db_session):
    """moderate_kyc flips kyc_status to APPROVED and writes an audit log entry."""
    from sqlalchemy import select

    from app.modules.admin.models import AuditLog

    admin = make_user(role=UserRole.ADMIN.value)
    db_session.add(admin)
    await db_session.flush()
    _, profile, _doc = await make_employer_with_pending_kyc(db_session)

    service = AdminService(db_session)
    result = await service.moderate_kyc(
        admin_id=admin.id, employer_profile_id=profile.id, action="APPROVED"
    )

    assert result.kyc_status == "APPROVED"

    log_result = await db_session.execute(
        select(AuditLog).where(AuditLog.target_id == profile.id)
    )
    log = log_result.scalar_one()
    assert log.action == "MODERATE_KYC_APPROVED"
    assert log.log_metadata["before"]["kyc_status"] == "PENDING"
    assert log.log_metadata["after"]["kyc_status"] == "APPROVED"


@pytest.mark.asyncio
async def test_moderate_kyc_rejects_with_reason(db_session):
    """moderate_kyc flips kyc_status to REJECTED and stores the rejection reason."""
    admin = make_user(role=UserRole.ADMIN.value)
    db_session.add(admin)
    await db_session.flush()
    _, profile, _doc = await make_employer_with_pending_kyc(db_session)

    service = AdminService(db_session)
    result = await service.moderate_kyc(
        admin_id=admin.id,
        employer_profile_id=profile.id,
        action="REJECTED",
        reason="Business registration document is illegible",
    )

    assert result.kyc_status == "REJECTED"
    assert result.kyc_rejection_reason == "Business registration document is illegible"


@pytest.mark.asyncio
async def test_moderate_kyc_raises_for_unknown_profile(db_session):
    """moderate_kyc raises ProfileNotFoundException for an unknown employer_profile_id."""
    admin = make_user(role=UserRole.ADMIN.value)
    db_session.add(admin)
    await db_session.flush()

    service = AdminService(db_session)
    with pytest.raises(ProfileNotFoundException):
        await service.moderate_kyc(
            admin_id=admin.id, employer_profile_id=uuid4(), action="APPROVED"
        )


@pytest.mark.asyncio
async def test_moderate_kyc_rejects_invalid_action(db_session):
    """moderate_kyc raises ValidationException for an action other than APPROVED/REJECTED."""
    admin = make_user(role=UserRole.ADMIN.value)
    db_session.add(admin)
    await db_session.flush()
    _, profile, _doc = await make_employer_with_pending_kyc(db_session)

    service = AdminService(db_session)
    with pytest.raises(ValidationException):
        await service.moderate_kyc(
            admin_id=admin.id, employer_profile_id=profile.id, action="PENDING"
        )


@pytest.mark.asyncio
async def test_get_kyc_document_url_returns_presigned_url(db_session):
    """get_kyc_document_url returns a presigned URL for an existing document."""
    _, _profile, doc = await make_employer_with_pending_kyc(db_session)

    service = AdminService(db_session, storage=MockStorageService())
    url = await service.get_kyc_document_url(doc.id)

    assert doc.key in url
