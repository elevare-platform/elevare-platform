"""Tests for the shared organization-level ownership rule (decision D2)."""

from types import SimpleNamespace
from uuid import uuid4

from app.core.ownership import can_manage_job

ORG = uuid4()


def _user(organization_id=None, role="EMPLOYER"):
    return SimpleNamespace(id=uuid4(), organization_id=organization_id, role=role)


def _job(employer):
    return SimpleNamespace(employer_id=employer.id, employer=employer)


def test_the_creator_can_manage_their_own_job():
    creator = _user()

    assert can_manage_job(creator, _job(creator)) is True


def test_a_teammate_in_the_same_organization_can_manage_the_job():
    creator = _user(ORG)
    teammate = _user(ORG)

    assert can_manage_job(teammate, _job(creator)) is True


def test_someone_in_another_organization_cannot():
    creator = _user(ORG)
    outsider = _user(uuid4())

    assert can_manage_job(outsider, _job(creator)) is False


def test_a_user_without_an_organization_only_manages_jobs_they_created():
    creator = _user(ORG)
    loner = _user(None)

    assert can_manage_job(loner, _job(creator)) is False
    assert can_manage_job(loner, _job(loner)) is True


def test_two_users_who_both_have_no_organization_are_not_teammates():
    """None == None must never count as 'the same organization'."""
    creator = _user(None)
    other = _user(None)

    assert can_manage_job(other, _job(creator)) is False


def test_being_an_admin_grants_nothing_extra():
    creator = _user(ORG)
    admin = _user(None, role="ADMIN")

    assert can_manage_job(admin, _job(creator)) is False
