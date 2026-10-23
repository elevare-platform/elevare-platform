"""A job's list of strict-interview questions: read it, replace it, and have the AI draft it.

Every candidate on a job gets the same list (docs/08_DECISIONS.md). The AI drafts it from the
job's interview brief when the employer asks; the employer reads and edits it and saves it. A
draft is only ever returned, never saved: saving is the employer's decision.

Access follows the shared ownership rule (decision D2): the job's owner, meaning anyone in the
company that owns the job.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    PermissionDeniedException,
    QuestionDraftFailedException,
    ValidationException,
)
from app.core.ownership import can_manage_job
from app.modules.interviews import question_rules as rules
from app.modules.interviews.models import JobInterviewQuestion
from app.modules.jobs.repository import JobRepository
from app.modules.users.models import User


class InterviewQuestionService:
    def __init__(self, db: AsyncSession, ai_service=None) -> None:
        """``ai_service`` is only for tests; a real one is made when a draft is asked for."""
        self._db = db
        self._ai_service = ai_service

    async def _job_for(self, user: User, job_id: uuid.UUID):
        job = await JobRepository(self._db).get_by_id(job_id)  # raises JobNotFoundError
        if not can_manage_job(user, job):
            raise PermissionDeniedException("You do not have access to this job")
        return job

    async def _saved(self, job_id: uuid.UUID) -> list[JobInterviewQuestion]:
        result = await self._db.execute(
            select(JobInterviewQuestion)
            .where(JobInterviewQuestion.job_id == job_id)
            .order_by(JobInterviewQuestion.position)
        )
        return list(result.scalars().all())

    @staticmethod
    def _answer(questions: list) -> dict:
        """The response: the questions, plus the limits the screen shows next to them."""
        return {
            "questions": questions,
            "total_seconds": sum(question.time_limit_seconds for question in questions),
            "max_questions": settings.strict_interview_max_questions,
            "default_questions": settings.strict_interview_default_questions,
            "max_total_seconds": rules.max_total_seconds(),
            "closing_question": rules.closing_question(),
            "style": settings.interview_style,
        }

    async def list_questions(self, user: User, job_id: uuid.UUID) -> dict:
        await self._job_for(user, job_id)
        return self._answer(await self._saved(job_id))

    async def replace_questions(
        self, user: User, job_id: uuid.UUID, items: list[dict]
    ) -> dict:
        """Save the employer's list in place of the old one, all or nothing.

        ``items`` are ``{"text", "time_limit_seconds", "source"}`` in the order shown. An
        empty list clears the questions. Refused, with every problem named, if the list breaks
        a rule (too many questions, a bad time, times that do not fit the interview).
        """
        await self._job_for(user, job_id)
        drafts = [
            rules.QuestionDraft(item["text"], item["time_limit_seconds"]) for item in items
        ]
        problems = rules.problems_with(drafts)
        if problems:
            raise ValidationException(
                message=" ".join(problems),
                details=[{"field": "questions", "message": problem} for problem in problems],
            )

        # Delete first and flush, so the (job, position) rule is satisfied by the new rows.
        await self._db.execute(
            delete(JobInterviewQuestion).where(JobInterviewQuestion.job_id == job_id)
        )
        await self._db.flush()
        for position, (item, draft) in enumerate(zip(items, drafts, strict=True), start=1):
            self._db.add(
                JobInterviewQuestion(
                    job_id=job_id,
                    position=position,
                    text=rules.clean_text(draft.text),
                    time_limit_seconds=draft.time_limit_seconds,
                    source=item.get("source", "EMPLOYER"),
                )
            )
        await self._db.commit()
        return self._answer(await self._saved(job_id))

    async def draft_questions(
        self, user: User, job_id: uuid.UUID, count: int | None = None
    ) -> dict:
        """Ask the AI for a draft list from the job's interview brief. Nothing is saved.

        ``count`` defaults to 5 and is never more than the most an interview may have.
        """
        job = await self._job_for(user, job_id)
        brief = (job.interview_brief or "").strip()
        if not brief:
            raise ValidationException(
                message="Write the interview brief first. The questions are drafted from it."
            )
        # The whole interview has a length (INTERVIEW_MAX_DURATION_MINUTES): the AI is told it,
        # and never asked for more questions than can each get the shortest answer time.
        total_seconds = rules.max_total_seconds()
        wanted = max(
            1,
            min(
                count or settings.strict_interview_default_questions,
                settings.strict_interview_max_questions,
                total_seconds // rules.MIN_SECONDS,
            ),
        )

        # The last place goes to the scorecard's standard closing question (motivation, notice
        # period, start date, compensation), which the employer can change or remove. The AI
        # drafts the others, with the time that is left once the closing question has its own.
        with_closing = wanted >= 2
        ai_count = wanted - 1 if with_closing else wanted
        ai_seconds = total_seconds - rules.CLOSING_QUESTION_SECONDS if with_closing else total_seconds

        ai_service = self._ai_service
        made_here = ai_service is None
        if made_here:
            from app.modules.ai.service import AnthropicCVExtractionService

            ai_service = AnthropicCVExtractionService()
        try:
            raw = await ai_service.draft_interview_questions(
                title=job.title,
                seniority=job.seniority_level,
                required_skills=job.required_skills,
                requirements=job.requirements,
                about_the_role=job.about_the_role,
                interview_brief=brief,
                count=ai_count,
                total_seconds=max(ai_seconds, rules.MIN_SECONDS * ai_count),
            )
        finally:
            if made_here:
                # Close the HTTP client we opened, so nothing is left for garbage collection.
                await ai_service._client.close()
        closing = (
            rules.QuestionDraft(rules.CLOSING_QUESTION_TEXT, rules.CLOSING_QUESTION_SECONDS)
            if with_closing
            else None
        )
        drafts = rules.tidy_drafted(raw or [], ai_count, closing=closing)
        if not drafts:
            raise QuestionDraftFailedException()

        questions = [
            {"text": draft.text, "time_limit_seconds": draft.time_limit_seconds, "source": "AI"}
            for draft in drafts
        ]
        return {
            "questions": questions,
            "total_seconds": sum(draft.time_limit_seconds for draft in drafts),
            "max_questions": settings.strict_interview_max_questions,
            "default_questions": settings.strict_interview_default_questions,
            "max_total_seconds": rules.max_total_seconds(),
            "closing_question": rules.closing_question(),
            "style": settings.interview_style,
        }
