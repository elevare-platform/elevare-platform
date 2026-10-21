"""One rule for "is this CV already in the talent pool?", used by manual upload and mail import.

A CV used to be checked three different ways: by hand against (same content, same job); from
mail against "the newest submission with this content that was stored and parsed", ignoring the
job; and neither looked at whose pool it was. So the same CV could be in the pool twice, a
duplicate upload left a submission with no profile behind it, and an upload could be answered
with ANOTHER employer's profile.

The rule, in short:
  * Only profiles the uploader can already see count (their own, and those an admin added to the
    platform pool). Another employer's private profile never does: it is not shown, not linked, and
    the uploader gets a profile of their own.
  * The same CV for the same job (or both without a job) is a duplicate.
  * A CV with no job, when it is already in the pool for a job, is a duplicate too.
  * A CV already in the pool WITHOUT a job, uploaded again for a job, is attached to that job
    (not copied), when it is the uploader's own profile.
  * The same CV for a DIFFERENT job gets its own profile: a profile holds one score, so sharing one
    between two jobs would take away the ability to rank it in the second. (Plan item 5B, a score
    per job, is what makes sharing right.)
  * An archived profile never counts: uploading the CV again is a request to add it again.
It does not matter whether the earlier copy has finished parsing or been stored yet.

Two uploads of the same CV at the same moment take turns (``lock_cv``).
"""

import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.models import ParsedCVSubmission
from app.modules.talent_pool.models import TalentPoolProfiles
from app.modules.users.enums import UserRole
from app.modules.users.models import User

ARCHIVED = "archived"

Action = Literal["create", "duplicate", "attach"]


@dataclass(frozen=True)
class Decision:
    action: Action
    existing: TalentPoolProfiles | None = None


async def lock_cv(db: AsyncSession, cv_hash: str) -> None:
    """Hold a lock on this CV's content until the transaction ends.

    Two people (or one double click) uploading the same CV at the same moment take turns: the
    second looks only after the first has finished, so it finds the profile the first made instead
    of making another. Different CVs do not wait for each other."""
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:cv_hash, 0))"),
        {"cv_hash": cv_hash},
    )


async def find_in_scope(
    db: AsyncSession, cv_hash: str, owner_id: uuid.UUID, owner_is_admin: bool
) -> list[TalentPoolProfiles]:
    """Profiles with this CV content that the uploader can already see, newest first.

    Same visibility as the pool listing: an employer sees what they added and what an admin
    added; an admin's own pool is the platform pool (what admins added), so an admin upload never
    attaches to an employer's private profile."""
    added_by_admin = (
        select(User.id)
        .where(User.id == TalentPoolProfiles.added_by)
        .where(User.role == UserRole.ADMIN.value)
        .correlate(TalentPoolProfiles)
        .exists()
    )
    visible = (
        added_by_admin
        if owner_is_admin
        else or_(TalentPoolProfiles.added_by == owner_id, added_by_admin)
    )
    result = await db.execute(
        select(TalentPoolProfiles)
        .join(
            ParsedCVSubmission,
            TalentPoolProfiles.parsed_submission_id == ParsedCVSubmission.id,
        )
        .where(
            ParsedCVSubmission.cv_text_hash == cv_hash,
            TalentPoolProfiles.status != ARCHIVED,
            visible,
        )
        .order_by(TalentPoolProfiles.created_at.desc(), TalentPoolProfiles.id)
    )
    return list(result.scalars().all())


def decide(
    candidates: list[TalentPoolProfiles], job_id: uuid.UUID | None, owner_id: uuid.UUID
) -> Decision:
    """What to do with an upload for ``job_id``, given the profiles already in the pool."""
    for profile in candidates:
        if profile.sourced_for_job_id == job_id:
            return Decision("duplicate", profile)
    if job_id is None and candidates:
        return Decision("duplicate", candidates[0])
    if job_id is not None:
        for profile in candidates:
            if profile.sourced_for_job_id is None and profile.added_by == owner_id:
                return Decision("attach", profile)
    return Decision("create")
