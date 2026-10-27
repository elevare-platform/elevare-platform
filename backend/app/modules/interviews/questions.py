"""A job's list of strict-interview questions: read it, replace it, and have the AI draft it.

Every candidate on a job gets the same list (docs/08_DECISIONS.md). The AI drafts it from the
job's interview brief when the employer asks; the employer reads and edits it and saves it. A
draft is only ever returned, never saved: saving is the employer's decision.

Access follows the shared ownership rule (decision D2): the job's owner, meaning anyone in the
company that owns the job.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

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
from app.modules.interviews import question_templates
from app.modules.interviews import scoring_profile as scoring_rules
from app.modules.interviews.enums import FollowUpMode
from app.modules.interviews.follow_up import load_follow_up_mode, save_follow_up_mode
from app.modules.interviews.models import JobInterviewQuestion
from app.modules.interviews.scoring_profile_service import (
    ScoringProfileService,
    canonical_tag,
    load_profile,
    untested,
)
from app.modules.interviews.template_library import QuestionLibraryService
from app.modules.jobs.repository import JobRepository
from app.modules.users.models import User

# The fewest questions the AI must be asked for before one of them is a practical case.
PRACTICAL_MIN_AI_QUESTIONS = 3


def _as_draft(question) -> dict:
    """A saved question (or a template item) as the plain fields the editor loads."""
    get = question.get if isinstance(question, dict) else lambda name: getattr(question, name, None)
    return {
        "text": get("text"),
        "time_limit_seconds": get("time_limit_seconds"),
        "source": get("source") or "EMPLOYER",
        "competency": get("competency"),
        "probes": get("probes"),
        "follow_up_seconds": get("follow_up_seconds"),
        "is_practical": bool(get("is_practical")),
    }


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

    async def _answer(self, job_id: uuid.UUID, questions: list) -> dict:
        """The response: the questions, plus the limits the screen shows next to them and the
        competencies of the job's scoring profile (and which no question is tagged with)."""
        profile = await load_profile(self._db, job_id)
        competencies = profile.competencies if profile else []
        return {
            "competencies": [item["name"] for item in competencies],
            "untested_competencies": untested(competencies, [q.competency for q in questions]),
            "questions": questions,
            "total_seconds": sum(question.time_limit_seconds for question in questions),
            "max_questions": rules.max_questions(),
            "default_questions": settings.strict_interview_default_questions,
            "max_total_seconds": rules.max_total_seconds(),
            "closing_question": rules.closing_question(),
            "style": settings.interview_style,
            "follow_up_mode": (await load_follow_up_mode(self._db, job_id)).value,
            "question_templates": question_templates.template_summaries(),
        }

    async def list_questions(self, user: User, job_id: uuid.UUID) -> dict:
        await self._job_for(user, job_id)
        return await self._answer(job_id, await self._saved(job_id))

    async def replace_questions(
        self,
        user: User,
        job_id: uuid.UUID,
        items: list[dict],
        follow_up_mode: str | None = None,
        commit: bool = True,
    ) -> dict:
        """Save the employer's list in place of the old one, all or nothing.

        ``items`` are ``{"text", "time_limit_seconds", "source", "competency", "probes"}`` in the
        order shown. An empty list clears the questions. Refused, with every problem named, if the
        list breaks a rule (a bad time, times that do not fit the interview, too many probes).
        ``follow_up_mode`` (NONE, STANDARD or PROBES_ONLY), when given, is saved with the list;
        left out, the job keeps its mode. ``commit=False`` leaves the transaction open, for a
        caller that saves something else with it and commits once.
        """
        await self._job_for(user, job_id)
        drafts = [
            rules.QuestionDraft(
                item["text"],
                item["time_limit_seconds"],
                item.get("probes") or "",
                item.get("follow_up_seconds"),
                bool(item.get("is_practical")),
            )
            for item in items
        ]
        problems = rules.problems_with(drafts)
        # A tag has to be a competency of the job's scoring profile (spelled as the profile does).
        profile = await load_profile(self._db, job_id)
        known = profile.competencies if profile else []
        tags: list[str | None] = []
        for number, item in enumerate(items, start=1):
            wanted = item.get("competency")
            tag = canonical_tag(wanted, known)
            if wanted and tag is None:
                problems.append(
                    f"Question {number} is tagged \"{wanted}\", which is not a competency of this "
                    "job's scoring profile."
                )
            tags.append(tag)
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
        for position, (item, draft, tag) in enumerate(zip(items, drafts, tags, strict=True), start=1):
            self._db.add(
                JobInterviewQuestion(
                    job_id=job_id,
                    position=position,
                    text=rules.clean_text(draft.text),
                    time_limit_seconds=draft.time_limit_seconds,
                    source=item.get("source", "EMPLOYER"),
                    competency=tag,
                    probes="\n".join(rules.clean_probes(draft.probes)) or None,
                    follow_up_seconds=draft.follow_up_seconds,
                    is_practical=draft.is_practical,
                )
            )
        if follow_up_mode:
            await save_follow_up_mode(self._db, job_id, FollowUpMode(follow_up_mode))
        if commit:
            await self._db.commit()
        else:
            await self._db.flush()
        return await self._answer(job_id, await self._saved(job_id))

    async def apply_template(self, user: User, job_id: uuid.UUID, code: str) -> dict:
        """Start the job from one of the Colton Group role templates: the role's scoring profile
        (competencies, weights, key flags, bands) AND its questions with their probes, each
        question tagged with the competency it tests. Replaces the job's current profile and
        questions, in one transaction (all or nothing), and sets the follow-up mode to "follow up
        when needed", which is what the client's framework describes. Interviews already started
        keep the questions they began with.

        When the template's answer times add up to more than the interview's time limit
        (``INTERVIEW_MAX_DURATION_MINUTES``) the questions are NOT saved, because a list that does
        not fit cannot be: they are returned as a draft (``saved`` false) for the employer to shorten
        and save, with the role's scoring profile and follow-up mode already set so the tags are
        valid. The reply is the same either way: the questions to show, and whether they are saved.
        """
        await self._job_for(user, job_id)
        items = question_templates.template_items(code)
        scoring = next((t for t in scoring_rules.TEMPLATES if t["code"] == code), None)
        if items is None or scoring is None:
            raise ValidationException(message="That template does not exist.")
        profile = {
            "competencies": scoring["competencies"],
            "bands": None,
            "key_min_rating": scoring_rules.DEFAULT_KEY_MIN_RATING,
            "template_code": code,
        }
        return await self.apply_set(user, job_id, items, profile, FollowUpMode.STANDARD.value)

    async def apply_saved_template(self, user: User, job_id: uuid.UUID, template_id: uuid.UUID) -> dict:
        """Start the job from a set the user's company saved (see ``template_library``)."""
        await self._job_for(user, job_id)
        items, profile, mode = await QuestionLibraryService(self._db).saved_set(user, template_id)
        return await self.apply_set(user, job_id, items, profile, mode)

    async def apply_from_job(self, user: User, job_id: uuid.UUID, source_job_id: uuid.UUID) -> dict:
        """Start the job from another job of the same company: its questions, its scoring profile
        and its follow-up choice."""
        await self._job_for(user, job_id)
        if source_job_id == job_id:
            raise ValidationException("Choose a different job to copy from.", code="SAME_JOB")
        items, profile, mode = await QuestionLibraryService(self._db).job_set(user, source_job_id)
        return await self.apply_set(user, job_id, items, profile, mode)

    async def apply_set(
        self,
        user: User,
        job_id: uuid.UUID,
        items: list[dict],
        profile: dict | None,
        follow_up_mode: str,
    ) -> dict:
        """Put a ready-made set on a job: its questions, and its scoring profile when it has one
        (``{"competencies", "bands", "key_min_rating", "template_code"}``; without one the job's own
        profile is left as it is), and the follow-up choice. One transaction, all or nothing.

        Shared by the built-in role sets, the company's saved sets and "copy from one of my jobs".
        If the answer times add up to more than the interview's time limit the questions are NOT
        saved: they are returned as a draft (``saved`` false) to be shortened, with the profile and
        the follow-up choice already set so the tags are valid. The reply is the same either way."""
        if profile is not None:
            await ScoringProfileService(self._db).save(
                user,
                job_id,
                profile["competencies"],
                profile.get("bands"),
                profile.get("key_min_rating", scoring_rules.DEFAULT_KEY_MIN_RATING),
                profile.get("template_code"),
                commit=False,
            )
        fits = sum(item["time_limit_seconds"] for item in items) <= rules.max_total_seconds()
        if fits:
            result = await self.replace_questions(
                user, job_id, items, follow_up_mode=follow_up_mode, commit=False
            )
            await self._db.commit()
            return {**result, "questions": [_as_draft(q) for q in result["questions"]], "saved": True}
        await save_follow_up_mode(self._db, job_id, FollowUpMode(follow_up_mode))
        await self._db.commit()
        answer = await self._answer(job_id, [SimpleNamespace(**_as_draft(item)) for item in items])
        return {**answer, "questions": [_as_draft(item) for item in items], "saved": False}

    async def draft_questions(
        self, user: User, job_id: uuid.UUID, count: int | None = None
    ) -> dict:
        """Ask the AI for a draft list from the job's interview brief. Nothing is saved.

        ``count`` defaults to 5 and is never more than the interview's time allows.
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
        # The most that fit: each needs the shortest answer time, and when there is more than one
        # the last place goes to the closing question, which takes its own 90 seconds.
        fits = total_seconds // rules.MIN_SECONDS
        if fits >= 2:
            fits = min(
                fits, (total_seconds - rules.CLOSING_QUESTION_SECONDS) // rules.MIN_SECONDS + 1
            )
        wanted = max(1, min(count or settings.strict_interview_default_questions, fits))

        # The last place goes to the scorecard's standard closing question (motivation, notice
        # period, start date, compensation), which the employer can change or remove. The AI
        # drafts the others, with the time that is left once the closing question has its own.
        with_closing = wanted >= 2
        ai_count = wanted - 1 if with_closing else wanted
        ai_seconds = total_seconds - rules.CLOSING_QUESTION_SECONDS if with_closing else total_seconds

        # Most roles need a practical case, so the last question the AI writes is one (a scenario
        # scored separately out of 5) whenever there are enough questions to keep a few ordinary
        # ones too. The employer can untick it or rewrite it like any other question.
        practical = ai_count >= PRACTICAL_MIN_AI_QUESTIONS

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
                practical=practical,
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

        # The practical case is the last question the AI wrote, but only when it wrote all it was
        # asked for: a short or cleaned-up reply may have lost it, and then no ordinary question is
        # mistaken for one.
        written = len(drafts) - (1 if closing is not None else 0)
        practical_index = written - 1 if practical and written == ai_count else None
        questions = [
            {
                "text": draft.text,
                "time_limit_seconds": draft.time_limit_seconds,
                "source": "AI",
                "is_practical": index == practical_index,
            }
            for index, draft in enumerate(drafts)
        ]
        profile = await load_profile(self._db, job_id)
        return {
            "competencies": [item["name"] for item in profile.competencies] if profile else [],
            "untested_competencies": [],
            "questions": questions,
            "total_seconds": sum(draft.time_limit_seconds for draft in drafts),
            "max_questions": rules.max_questions(),
            "default_questions": settings.strict_interview_default_questions,
            "max_total_seconds": rules.max_total_seconds(),
            "closing_question": rules.closing_question(),
            "style": settings.interview_style,
            "follow_up_mode": (await load_follow_up_mode(self._db, job_id)).value,
        }
