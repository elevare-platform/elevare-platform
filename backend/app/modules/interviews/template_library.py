"""The template library: sets of interview questions to start a job from (docs/08_DECISIONS.md,
item 46).

Three places to start from, shown together in the questions screen: the Colton Group's role sets
(built in), the sets the employer's COMPANY saved (owned by the company, like jobs and applicants,
decision D2: anyone in the company can use them), and the questions of the company's other jobs
("copy from one of my jobs"). A saved set carries the questions with their probes, times and
practical case, the follow-up choice and, if the employer chose, the scoring profile the question
tags point to. Applying any of them to a job is ``InterviewQuestionService.apply_set``.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    NotFoundException,
    PermissionDeniedException,
    ValidationException,
)
from app.core.ownership import can_manage_job
from app.modules.interviews import question_rules as rules
from app.modules.interviews import question_templates
from app.modules.interviews import scoring_profile as scoring_rules
from app.modules.interviews.enums import FollowUpMode, follow_up_mode_of
from app.modules.interviews.follow_up import load_follow_up_mode
from app.modules.interviews.models import (
    InterviewQuestionTemplate,
    JobInterviewQuestion,
)
from app.modules.interviews.scoring_profile_service import canonical_tag, load_profile
from app.modules.jobs.models import Job
from app.modules.jobs.repository import JobRepository
from app.modules.users.models import Organization, User

MAX_TEMPLATES_PER_COMPANY = 50
MAX_NAME_CHARS = 120
MAX_JOBS_LISTED = 50

NAME_TAKEN = "Your company already has a template with that name. Choose another name, or delete the old one."


def _clean_name(name: str | None) -> str:
    return " ".join((name or "").split())


def _question(item: dict) -> dict:
    """A question as the library shows and stores it (the fields a set carries, nothing else)."""
    return {
        "text": item["text"],
        "time_limit_seconds": item["time_limit_seconds"],
        "source": "EMPLOYER",
        "competency": item.get("competency"),
        "probes": item.get("probes") or None,
        "follow_up_seconds": item.get("follow_up_seconds"),
        "is_practical": bool(item.get("is_practical")),
    }


def _entry(
    *,
    kind: str,
    entry_id: str,
    name: str,
    questions: list[dict],
    profile: dict | None,
    follow_up_mode: str,
    created_by_name: str | None = None,
    created_at=None,
    can_edit: bool = False,
) -> dict:
    return {
        "id": entry_id,
        "kind": kind,
        "name": name,
        "question_count": len(questions),
        "total_seconds": sum(question["time_limit_seconds"] for question in questions),
        "has_practical": any(question["is_practical"] for question in questions),
        "has_scoring_profile": profile is not None,
        "competencies": [item["name"] for item in profile["competencies"]] if profile else [],
        "follow_up_mode": follow_up_mode,
        "created_by_name": created_by_name,
        "created_at": created_at,
        "can_edit": can_edit,
        "questions": questions,
    }


def matches(query: str | None, *parts: str) -> bool:
    """Whether every word of ``query`` appears somewhere in ``parts`` (ignoring case). No query
    matches everything."""
    words = (query or "").casefold().split()
    haystack = " ".join(parts).casefold()
    return all(word in haystack for word in words)


class QuestionLibraryService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------ reading

    async def library(self, user: User, query: str | None) -> dict:
        """The built-in role sets and the company's saved sets that match ``query``."""
        built_in = []
        for code in question_templates.ROLE_CODES:
            items = [_question(item) for item in question_templates.template_items(code)]
            scoring = next(t for t in scoring_rules.TEMPLATES if t["code"] == code)
            title = question_templates.QUESTION_TEMPLATES[code]["title"]
            competencies = [c["name"] for c in scoring["competencies"]]
            if matches(query, title, "Colton Group", *competencies, *(q["text"] for q in items)):
                built_in.append(
                    _entry(
                        kind="BUILT_IN",
                        entry_id=code,
                        name=title,
                        questions=items,
                        profile={"competencies": scoring["competencies"]},
                        follow_up_mode=FollowUpMode.STANDARD.value,
                    )
                )
        company = []
        organization_id = user.organization_id
        if organization_id is not None:
            owner_id = await self._owner_id(organization_id)
            result = await self._db.execute(
                select(InterviewQuestionTemplate)
                .where(InterviewQuestionTemplate.organization_id == organization_id)
                .order_by(func.lower(InterviewQuestionTemplate.name))
            )
            for row in result.scalars().all():
                competencies = [c["name"] for c in (row.scoring_profile or {}).get("competencies", [])]
                if matches(query, row.name, row.created_by_name, *competencies, *(q["text"] for q in row.questions)):
                    company.append(self._saved_entry(row, user, owner_id))
        return {"built_in": built_in, "company": company, "can_save": organization_id is not None}

    def _saved_entry(self, row: InterviewQuestionTemplate, user: User, owner_id: uuid.UUID | None) -> dict:
        return _entry(
            kind="COMPANY",
            entry_id=str(row.id),
            name=row.name,
            questions=[_question(item) for item in row.questions],
            profile=row.scoring_profile,
            follow_up_mode=row.follow_up_mode,
            created_by_name=row.created_by_name,
            created_at=row.created_at,
            can_edit=row.created_by == user.id or owner_id == user.id,
        )

    async def _owner_id(self, organization_id: uuid.UUID) -> uuid.UUID | None:
        return (
            await self._db.execute(select(Organization.created_by).where(Organization.id == organization_id))
        ).scalar_one_or_none()

    async def company_jobs(self, user: User, query: str | None, exclude_job_id: uuid.UUID | None) -> list[dict]:
        """The company's jobs that have interview questions, to copy from: newest first, at most
        50, with how many questions and how long. ``query`` matches the job's title."""
        if user.organization_id is None:
            return []
        stmt = (
            select(
                Job.id,
                Job.title,
                func.count(JobInterviewQuestion.id),
                func.coalesce(func.sum(JobInterviewQuestion.time_limit_seconds), 0),
                func.bool_or(JobInterviewQuestion.is_practical),
            )
            .join(JobInterviewQuestion, JobInterviewQuestion.job_id == Job.id)
            .join(User, User.id == Job.employer_id)
            .where(User.organization_id == user.organization_id)
            .group_by(Job.id, Job.title, Job.created_at)
            .order_by(Job.created_at.desc())
            .limit(MAX_JOBS_LISTED)
        )
        if exclude_job_id is not None:
            stmt = stmt.where(Job.id != exclude_job_id)
        if query and query.strip():
            stmt = stmt.where(Job.title.ilike(f"%{query.strip()}%"))
        rows = (await self._db.execute(stmt)).all()
        return [
            {
                "job_id": job_id,
                "title": title,
                "question_count": count,
                "total_seconds": int(seconds),
                "has_practical": bool(practical),
            }
            for job_id, title, count, seconds, practical in rows
        ]

    # ------------------------------------------------------------------ saving

    async def save(
        self,
        user: User,
        job_id: uuid.UUID,
        name: str,
        items: list[dict],
        include_profile: bool,
        follow_up_mode: str,
    ) -> dict:
        """Save the questions being edited as a template of the user's company.

        The scoring profile is the one the job has now, when ``include_profile`` and it has one; the
        tags are kept only then (they mean nothing without it). The answer times need not fit this
        job's time limit: applying the template to a job shows it for shortening when it does not."""
        organization_id = user.organization_id
        if organization_id is None:
            raise ValidationException(
                "Complete your company profile before saving templates.", code="COMPANY_REQUIRED"
            )
        job = await JobRepository(self._db).get_by_id(job_id)
        if not can_manage_job(user, job):
            raise PermissionDeniedException("You do not have access to this job")

        title = _clean_name(name)
        if not title:
            raise ValidationException("Give the template a name.", code="TEMPLATE_NAME_REQUIRED")
        if len(title) > MAX_NAME_CHARS:
            raise ValidationException(f"Keep the name under {MAX_NAME_CHARS} characters.", code="TEMPLATE_NAME_TOO_LONG")
        if not items:
            raise ValidationException("Add at least one question before saving a template.", code="TEMPLATE_EMPTY")

        drafts = [
            rules.QuestionDraft(
                item["text"], item["time_limit_seconds"], item.get("probes") or "",
                item.get("follow_up_seconds"), bool(item.get("is_practical")),
            )
            for item in items
        ]
        problems = rules.problems_with(drafts, check_total=False)
        if problems:
            raise ValidationException(
                message=" ".join(problems),
                details=[{"field": "questions", "message": problem} for problem in problems],
            )

        profile = None
        if include_profile:
            stored = await load_profile(self._db, job_id)
            if stored is not None:
                profile = {
                    "competencies": stored.competencies,
                    "bands": stored.bands,
                    "key_min_rating": stored.key_min_rating,
                }
        known = profile["competencies"] if profile else []
        questions = []
        for item, draft in zip(items, drafts, strict=True):
            question = _question({**item, "text": rules.clean_text(draft.text)})
            question["competency"] = canonical_tag(item.get("competency"), known)
            question["probes"] = "\n".join(rules.clean_probes(draft.probes)) or None
            questions.append(question)

        taken = (
            await self._db.execute(
                select(func.count())
                .select_from(InterviewQuestionTemplate)
                .where(
                    InterviewQuestionTemplate.organization_id == organization_id,
                    func.lower(InterviewQuestionTemplate.name) == title.casefold(),
                )
            )
        ).scalar_one()
        if taken:
            raise ValidationException(NAME_TAKEN, code="TEMPLATE_NAME_TAKEN")
        total = (
            await self._db.execute(
                select(func.count())
                .select_from(InterviewQuestionTemplate)
                .where(InterviewQuestionTemplate.organization_id == organization_id)
            )
        ).scalar_one()
        if total >= MAX_TEMPLATES_PER_COMPANY:
            raise ValidationException(
                f"Your company can keep {MAX_TEMPLATES_PER_COMPANY} templates. Delete one you no longer use.",
                code="TEMPLATE_LIMIT",
            )

        row = InterviewQuestionTemplate(
            organization_id=organization_id,
            name=title,
            questions=questions,
            scoring_profile=profile,
            follow_up_mode=follow_up_mode_of(follow_up_mode).value,
            created_by=user.id,
            created_by_name=f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
        )
        self._db.add(row)
        try:
            await self._db.commit()
        except IntegrityError:
            # Two saves with the same name at the same moment: the second is told the name is taken.
            await self._db.rollback()
            raise ValidationException(NAME_TAKEN, code="TEMPLATE_NAME_TAKEN") from None
        await self._db.refresh(row)
        return self._saved_entry(row, user, await self._owner_id(organization_id))

    # ------------------------------------------------------------------ changing

    async def _own(self, user: User, template_id: uuid.UUID) -> InterviewQuestionTemplate:
        """The company's template, or not found (also for another company's: its existence is not
        revealed)."""
        row = None
        if user.organization_id is not None:
            row = (
                await self._db.execute(
                    select(InterviewQuestionTemplate).where(
                        InterviewQuestionTemplate.id == template_id,
                        InterviewQuestionTemplate.organization_id == user.organization_id,
                    )
                )
            ).scalar_one_or_none()
        if row is None:
            raise NotFoundException("That template was not found.", code="TEMPLATE_NOT_FOUND")
        return row

    async def _assert_can_change(self, user: User, row: InterviewQuestionTemplate) -> None:
        owner_id = await self._owner_id(row.organization_id)
        if row.created_by != user.id and owner_id != user.id:
            raise PermissionDeniedException("Only the person who saved a template, or the company owner, can change it.")

    async def rename(self, user: User, template_id: uuid.UUID, name: str) -> dict:
        row = await self._own(user, template_id)
        await self._assert_can_change(user, row)
        title = _clean_name(name)
        if not title or len(title) > MAX_NAME_CHARS:
            raise ValidationException(f"Give the template a name of up to {MAX_NAME_CHARS} characters.", code="TEMPLATE_NAME_REQUIRED")
        clash = (
            await self._db.execute(
                select(func.count())
                .select_from(InterviewQuestionTemplate)
                .where(
                    InterviewQuestionTemplate.organization_id == row.organization_id,
                    func.lower(InterviewQuestionTemplate.name) == title.casefold(),
                    InterviewQuestionTemplate.id != row.id,
                )
            )
        ).scalar_one()
        if clash:
            raise ValidationException(NAME_TAKEN, code="TEMPLATE_NAME_TAKEN")
        row.name = title
        try:
            await self._db.commit()
        except IntegrityError:
            await self._db.rollback()
            raise ValidationException(NAME_TAKEN, code="TEMPLATE_NAME_TAKEN") from None
        await self._db.refresh(row)
        return self._saved_entry(row, user, await self._owner_id(row.organization_id))

    async def delete(self, user: User, template_id: uuid.UUID) -> None:
        row = await self._own(user, template_id)
        await self._assert_can_change(user, row)
        await self._db.delete(row)
        await self._db.commit()

    # ------------------------------------------------------------------ using

    async def saved_set(self, user: User, template_id: uuid.UUID) -> tuple[list[dict], dict | None, str]:
        """A saved template as ``(questions, scoring profile or None, follow-up choice)`` to apply."""
        row = await self._own(user, template_id)
        profile = None
        if row.scoring_profile:
            profile = {
                "competencies": row.scoring_profile["competencies"],
                "bands": row.scoring_profile.get("bands"),
                "key_min_rating": row.scoring_profile.get("key_min_rating", scoring_rules.DEFAULT_KEY_MIN_RATING),
                "template_code": None,
            }
        return [_question(item) for item in row.questions], profile, row.follow_up_mode

    async def job_set(self, user: User, source_job_id: uuid.UUID) -> tuple[list[dict], dict | None, str]:
        """Another job of the company as ``(questions, scoring profile or None, follow-up choice)``."""
        source = await JobRepository(self._db).get_by_id(source_job_id)
        if not can_manage_job(user, source):
            raise PermissionDeniedException("You do not have access to that job")
        result = await self._db.execute(
            select(JobInterviewQuestion)
            .where(JobInterviewQuestion.job_id == source_job_id)
            .order_by(JobInterviewQuestion.position)
        )
        rows = list(result.scalars().all())
        if not rows:
            raise ValidationException("That job has no interview questions to copy.", code="NOTHING_TO_COPY")
        stored = await load_profile(self._db, source_job_id)
        profile = None
        if stored is not None:
            profile = {
                "competencies": stored.competencies,
                "bands": stored.bands,
                "key_min_rating": stored.key_min_rating,
                "template_code": None,
            }
        items = [
            _question(
                {
                    "text": row.text,
                    "time_limit_seconds": row.time_limit_seconds,
                    "competency": row.competency,
                    "probes": row.probes,
                    "follow_up_seconds": row.follow_up_seconds,
                    "is_practical": row.is_practical,
                }
            )
            for row in rows
        ]
        if profile is None:
            for item in items:
                item["competency"] = None  # tags mean nothing without the profile they point to
        return items, profile, (await load_follow_up_mode(self._db, source_job_id)).value
