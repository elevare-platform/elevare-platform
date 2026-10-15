"""Shared ownership rules.

Decision D2: jobs, applications and the lists hanging off them belong to the
organization, not to the one user who created them. New code asks the helpers
here instead of writing ``job.employer_id == current_user.id``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.jobs.models import Job
    from app.modules.users.models import User


def can_manage_job(user: User, job: Job) -> bool:
    """Whether ``user`` may act on ``job`` on behalf of its owner.

    True for the job's creator, and for anyone in the same organization as the
    creator. A user with no organization (for example an Elevare admin) can
    only manage the jobs they created themselves, and being an admin grants
    nothing extra here.

    ``job.employer`` must be loaded; ``JobRepository.get_by_id`` does that.
    """
    if job.employer_id == user.id:
        return True
    employer = job.employer
    return (
        user.organization_id is not None
        and employer is not None
        and employer.organization_id == user.organization_id
    )
