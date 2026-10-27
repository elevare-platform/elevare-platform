"""The strict, text-question interview: starting it, the clock, the answers, the follow-ups.

The server owns the clock and the position (docs/08_DECISIONS.md, "The new strict, text-only AI
interview", item 24). It copies the job's questions when the interview starts, opens ONE turn at
a time (a question or a follow-up) and records when it was shown, so how long is left is the
server's answer and a reload cannot buy a candidate more time or a second look at the
questions. A reload resumes the same question; a question whose time ran out while the page was
away is closed with no answer and the next one is opened as if on time.

Each answer arrives as a short audio clip, is transcribed at once, and the AI may ask ONE
follow-up. The clip itself is not kept (the whole interview is recorded as one video); only the
text of the answer is. If an answer cannot be transcribed the interview carries on, and the text
is filled in later from the recording.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai_pricing import compute_transcription_cost_usd
from app.core.config import settings
from app.core.exceptions import ValidationException
from app.modules.interviews.enums import (
    ENDED_STATUSES,
    ConductEventKind,
    FollowUpMode,
    InterviewCostComponent,
    InterviewStatus,
    TurnKind,
    follow_up_mode_of,
)
from app.modules.interviews.follow_up import load_follow_up_mode
from app.modules.interviews.models import (
    Interview,
    InterviewTurn,
    JobInterviewQuestion,
    StrictInterviewRun,
)
from app.modules.interviews.repository import InterviewRepository
from app.modules.interviews.strict_conduct import ConductMixin

logger = logging.getLogger(__name__)

# (audio bytes, file name) -> (text, seconds of audio). Replaceable so tests never call OpenAI.
Transcriber = Callable[[bytes, str], Awaitable[tuple[str, float]]]

MIN_FOLLOW_UP_CHARS = 10
MAX_FOLLOW_UP_CHARS = 300
# Fewer words than this and there is nothing to follow up on ("I don't know").
MIN_WORDS_FOR_FOLLOW_UP = 6
# A turn shorter than this is not worth showing, so the interview ends instead.
MIN_TURN_SECONDS = 15
# A clip smaller than this holds no speech (an empty or cut-off recording).
MIN_AUDIO_BYTES = 1500
# On a reload, a turn is only counted as run out once it is this far past its time, so a
# candidate who reloads at the very last second is not penalised for the round trip.
RESUME_GRACE_SECONDS = 5
_RULES_VERSION_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
NO_ANSWER_TEXT = "[No answer was recorded]"


def _now() -> datetime:
    return datetime.now(UTC)


def clean_follow_up(text: str | None) -> str | None:
    """The follow-up as the candidate may see it, or None when it is not usable.

    The model's reply is shown to the candidate as it is, so it is held to what a follow-up
    is: one question, a sensible length, ending with a question mark. Anything else (a
    statement, praise, a leaked instruction) is dropped, and the interview just carries on.
    """
    if not text:
        return None
    cleaned = " ".join(text.split()).strip("\"' ")
    if not MIN_FOLLOW_UP_CHARS <= len(cleaned) <= MAX_FOLLOW_UP_CHARS:
        return None
    if not cleaned.endswith("?"):
        return None
    return cleaned


def prepared_probes(text: str | None) -> list[str]:
    """The employer's probes for a question, as the lines they wrote."""
    return [line for line in (" ".join(raw.split()) for raw in (text or "").splitlines()) if line]


def match_prepared_probe(raw: str | None, probes: list[str]) -> str | None:
    """The prepared probe the model chose, exactly as the employer wrote it, or None.

    In PROBES_ONLY mode the model may only pick from the employer's list, so what it returns is
    matched against that list (ignoring case, spacing and a trailing full stop or question mark)
    and the employer's own wording is what the candidate sees. Anything that is not on the list is
    dropped: the interview just carries on."""

    def key(value: str) -> str:
        return " ".join(value.split()).strip("\"' ").rstrip("?.! ").casefold()

    if not raw:
        return None
    wanted = key(raw)
    for probe in probes:
        if key(probe) == wanted:
            return probe
    return None


def valid_rules_version(version: str | None) -> bool:
    """A rules version is a short label such as "1": 1 to 20 letters, digits, dot, dash."""
    return bool(version) and len(version) <= 20 and set(version) <= _RULES_VERSION_CHARS


def earlier_exchange(thread: list, latest) -> str:
    """What was already asked and answered on one question before its latest answer, oldest
    first (the question, then each probe), as text for the follow-up model. Empty for the first
    answer to a question."""
    parts = []
    for other in thread:
        if other is latest or other.answered_at is None:
            continue
        label = "Question" if other.kind == TurnKind.QUESTION.value else "Follow-up"
        parts.append(f"{label}: {other.question_text}\nAnswer: {other.answer_text or '(no answer)'}")
    return "\n\n".join(parts)


def seconds_between(later: datetime, earlier: datetime) -> int:
    """Whole seconds from earlier to later, never negative."""
    return max(0, int((later - earlier).total_seconds()))


def audio_file_name(content_type: str | None) -> str:
    """A file name whose extension tells the transcription service the audio format."""
    kind = (content_type or "").split(";")[0].strip().lower()
    extension = {
        "audio/webm": "webm",
        "video/webm": "webm",
        "audio/ogg": "ogg",
        "audio/mp4": "mp4",
        "audio/mpeg": "mp3",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
    }.get(kind, "webm")
    return f"answer.{extension}"


async def whisper_transcribe(audio: bytes, filename: str) -> tuple[str, float]:
    """Transcribe one answer with the configured transcription model.

    ``verbose_json`` is what returns the audio duration that per-minute pricing needs. The
    timeout keeps a slow provider from holding the candidate's screen.
    """
    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=45.0, max_retries=1)
    try:
        response = await client.audio.transcriptions.create(
            file=(filename, audio),
            model=settings.transcription_model,
            response_format="verbose_json",
        )
    finally:
        await client.close()
    return response.text, response.duration


class StrictInterviewService(ConductMixin):
    """Runs one strict interview. Every method that changes anything is called inside the
    request's transaction and takes the interview's row lock first, so a double click or two
    tabs take turns. Leaving, ending, stopping and reinstating are in ``ConductMixin``."""

    def __init__(
        self,
        db: AsyncSession,
        repo: InterviewRepository,
        *,
        transcribe: Transcriber | None = None,
        ai_service=None,
    ) -> None:
        """``transcribe`` and ``ai_service`` are only for tests; real ones are used otherwise."""
        self._db = db
        self._repo = repo
        self._transcribe = transcribe or whisper_transcribe
        self._ai_service = ai_service

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    async def get_run(self, interview_id: uuid.UUID) -> StrictInterviewRun | None:
        result = await self._db.execute(
            select(StrictInterviewRun).where(StrictInterviewRun.interview_id == interview_id)
        )
        return result.scalar_one_or_none()

    async def is_strict(self, interview_id: uuid.UUID) -> bool:
        return await self.get_run(interview_id) is not None

    async def _turns(self, interview_id: uuid.UUID) -> list[InterviewTurn]:
        result = await self._db.execute(
            select(InterviewTurn)
            .where(InterviewTurn.interview_id == interview_id)
            .order_by(InterviewTurn.position)
        )
        return list(result.scalars().all())

    async def _job_questions(self, job_id: uuid.UUID) -> list[JobInterviewQuestion]:
        result = await self._db.execute(
            select(JobInterviewQuestion)
            .where(JobInterviewQuestion.job_id == job_id)
            .order_by(JobInterviewQuestion.position)
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Creating the run (when the invite is created)
    # ------------------------------------------------------------------

    async def require_questions(self, job_id: uuid.UUID) -> None:
        """Refuse to invite anyone to a strict interview that has no questions yet."""
        if not await self._job_questions(job_id):
            raise ValidationException(
                "Set the interview questions for this job before inviting anyone.",
                code="INTERVIEW_QUESTIONS_MISSING",
            )

    async def create_run(self, interview_id: uuid.UUID) -> StrictInterviewRun:
        """Mark an interview as strict. Called once, when the interview is created."""
        run = StrictInterviewRun(interview_id=interview_id)
        self._db.add(run)
        await self._db.flush()
        return run

    # ------------------------------------------------------------------
    # The state the screen shows
    # ------------------------------------------------------------------

    @staticmethod
    def _max_seconds() -> int:
        return settings.interview_max_duration_minutes * 60

    def _deadline(self, run: StrictInterviewRun) -> datetime:
        return run.started_at + timedelta(seconds=self._max_seconds())

    @staticmethod
    def _clock() -> datetime:
        """The server's time. Looked up at call time, so a test can replace ``_now``."""
        return _now()

    async def _state(
        self,
        interview: Interview,
        run: StrictInterviewRun,
        turns: list[InterviewTurn],
        now: datetime,
    ) -> dict:
        summary = await self._conduct_summary(interview.id, run, now)
        # Set once the interview was ended or stopped. Nothing else is then shown: an ended
        # interview must not leak the next question.
        ended = run.end_reason if run.ended_at is not None else None
        current = turns[-1] if turns and turns[-1].answered_at is None else None
        turn = None
        if current is not None and ended is None:
            ends_at = current.opened_at + timedelta(seconds=current.time_limit_seconds)
            turn = {
                "id": current.id,
                "kind": current.kind,
                "number": current.question_number,
                "text": current.question_text,
                "time_limit_seconds": current.time_limit_seconds,
                "seconds_left": min(
                    seconds_between(ends_at, now), seconds_between(self._deadline(run), now)
                ),
            }
        return {
            "interview_id": interview.id,
            "finished": current is None and ended is None,
            "turn": turn,
            "total_questions": len(run.questions or []),
            "seconds_left_total": seconds_between(self._deadline(run), now),
            "max_seconds_total": self._max_seconds(),
            # Why the interview ended early (TOO_MANY_LEAVES, TOO_LONG_AWAY or STOPPED), or None.
            "ended": ended,
            # How many warnings have been used, against what ends it.
            "leaves": summary["leaves"],
            "max_leaves": settings.strict_max_leaves,
            "away_seconds": int(summary["away_seconds"]),
            "max_away_seconds": settings.strict_max_away_seconds,
            "key_presses": summary["key_presses"],
        }

    # ------------------------------------------------------------------
    # Opening turns
    # ------------------------------------------------------------------

    async def _open_turn(
        self,
        interview_id: uuid.UUID,
        turns: list[InterviewTurn],
        *,
        kind: str,
        number: int,
        text: str,
        seconds: int,
        at: datetime,
    ) -> InterviewTurn:
        turn = InterviewTurn(
            interview_id=interview_id,
            position=len(turns) + 1,
            kind=kind,
            question_number=number,
            question_text=text,
            time_limit_seconds=seconds,
            opened_at=at,
        )
        self._db.add(turn)
        await self._db.flush()
        turns.append(turn)
        return turn

    async def _open_next_question(
        self,
        interview_id: uuid.UUID,
        run: StrictInterviewRun,
        turns: list[InterviewTurn],
        *,
        number: int,
        at: datetime,
    ) -> InterviewTurn | None:
        """Open question ``number`` as of time ``at``, or return None when the questions have
        run out or too little time is left to ask another."""
        questions = run.questions or []
        left = seconds_between(self._deadline(run), at)
        if number > len(questions) or left < MIN_TURN_SECONDS:
            return None
        question = questions[number - 1]
        return await self._open_turn(
            interview_id,
            turns,
            kind=TurnKind.QUESTION.value,
            number=number,
            text=question["text"],
            seconds=min(question["time_limit_seconds"], left),
            at=at,
        )

    def _nothing_left_to_do(
        self, run: StrictInterviewRun, turns: list[InterviewTurn], at: datetime
    ) -> bool:
        """True when, as of ``at``, a candidate who came back would have nothing to answer.

        Follows what ``_close_expired`` would do when the interview is opened again: a question
        whose time had already run out is closed, the next one opens as of when it would have
        started, and so on, until one still has time or the questions (or the interview's time)
        are used up. A question the candidate was still answering when it ended counts as
        time left."""
        questions = run.questions or []
        grace = timedelta(seconds=RESUME_GRACE_SECONDS)
        current = turns[-1] if turns and turns[-1].answered_at is None else None
        if current is not None:
            ends = current.opened_at + timedelta(seconds=current.time_limit_seconds)
            if at <= ends + grace:
                usable = min(seconds_between(ends, at), seconds_between(self._deadline(run), at))
                return usable < MIN_TURN_SECONDS
            number, when = current.question_number + 1, ends
        else:
            number, when = (turns[-1].question_number if turns else 0) + 1, at
        while True:
            left = seconds_between(self._deadline(run), when)
            if number > len(questions) or left < MIN_TURN_SECONDS:
                return True
            ends = when + timedelta(seconds=min(questions[number - 1]["time_limit_seconds"], left))
            if at <= ends + grace:
                return False
            number, when = number + 1, ends

    async def _close_expired(
        self,
        interview_id: uuid.UUID,
        run: StrictInterviewRun,
        turns: list[InterviewTurn],
        now: datetime,
    ) -> None:
        """Close turns whose time ran out while nobody answered (the page was away), and open
        what would have come next, as of when it would have started. The server's clock never
        stopped, so the time that went by stays gone."""
        while turns and turns[-1].answered_at is None:
            current = turns[-1]
            ends_at = current.opened_at + timedelta(seconds=current.time_limit_seconds)
            if now <= ends_at + timedelta(seconds=RESUME_GRACE_SECONDS):
                return
            current.answered_at = ends_at
            await self._db.flush()
            if await self._open_next_question(
                interview_id, run, turns, number=current.question_number + 1, at=ends_at
            ) is None:
                return

    # ------------------------------------------------------------------
    # Starting, and resuming
    # ------------------------------------------------------------------

    async def start(
        self, interview: Interview, *, accepted: bool, rules_version: str | None
    ) -> dict:
        """Start the interview, or resume it where the candidate left off.

        The first call needs the candidate's acceptance of the rules (the version they saw is
        stored) and copies the job's questions. Any later call is a resume: the same question
        comes back with the time the server says is left.
        """
        status = await self._repo.lock_status(interview.id)
        if status not in (
            InterviewStatus.PENDING.value,
            InterviewStatus.IN_PROGRESS.value,
            *ENDED_STATUSES,
        ):
            raise ValidationException("This interview has already been completed")

        run = await self.get_run(interview.id)
        if run is None:
            raise ValidationException(
                "This is not a strict interview.", code="INTERVIEW_WRONG_STYLE"
            )

        now = _now()
        turns = await self._turns(interview.id)
        if status in ENDED_STATUSES:
            # Ended early: the screen says so, and nothing else changes.
            return await self._state(interview, run, turns, now)
        was_started = run.started_at is not None
        # A reinstated interview: the clock starts again now that the candidate is back.
        await self.resume_clock(run, turns, now)

        if run.started_at is None:
            if not accepted or not valid_rules_version(rules_version):
                raise ValidationException(
                    "You need to accept the interview rules before you can start.",
                    code="INTERVIEW_RULES_NOT_ACCEPTED",
                )
            saved = await self._job_questions(interview.job_id)
            if not saved:
                raise ValidationException(
                    "The questions for this interview are not ready. Please contact your recruiter.",
                    code="INTERVIEW_QUESTIONS_MISSING",
                )
            # The competency each question was written to test goes with the copy, so the
            # scorer is told it whatever the employer edits later.
            run.questions = [
                {
                    "text": question.text,
                    "time_limit_seconds": question.time_limit_seconds,
                    "competency": question.competency,
                    "probes": question.probes,
                }
                for question in saved
            ]
            # The follow-up mode is copied the same way: an edit made later never changes an
            # interview that has begun.
            run.follow_up_mode = (await load_follow_up_mode(self._db, interview.job_id)).value
            run.rules_version = rules_version
            run.rules_accepted_at = now
            run.started_at = now
            await self._db.flush()
            await self._open_next_question(interview.id, run, turns, number=1, at=now)

        await self._close_expired(interview.id, run, turns, now)

        update = {
            "status": InterviewStatus.IN_PROGRESS.value,
            # Counts the starts and resumes. Also keeps the stale-interview sweep, which looks
            # at when the row last changed, from treating a candidate who is mid-interview as
            # gone.
            "session_start_count": interview.session_start_count + 1,
        }
        if interview.started_at is None:
            update["started_at"] = now
        await self._repo.update(interview.id, update)
        if was_started:
            # A page that comes back is one leave (a reload, or the link opened again). It may
            # be the one that ends the interview.
            await self.note_return(interview, run, now)
        else:
            run.last_seen_at = now
        await self._db.commit()
        return await self._state(interview, run, turns, now)

    # ------------------------------------------------------------------
    # Recording pieces that survived a reload
    # ------------------------------------------------------------------

    async def reserve_recording_part(self, interview: Interview) -> int:
        """Reserve the next part number for a recording the browser kept across a reload.

        The number is handed out (and counted) here, under the interview's row lock, so two
        tabs can never be given the same part. A part that is then never uploaded is skipped
        when the pieces are joined.
        """
        status = await self._repo.lock_status(interview.id)
        if status not in (InterviewStatus.PENDING.value, InterviewStatus.IN_PROGRESS.value):
            raise ValidationException("This interview can no longer accept a recording")
        run = await self.get_run(interview.id)
        if run is None:
            raise ValidationException(
                "This is not a strict interview.", code="INTERVIEW_WRONG_STYLE"
            )
        if run.recording_parts >= settings.strict_recording_max_parts:
            raise ValidationException(
                "This interview has been interrupted too many times to keep every recording.",
                code="INTERVIEW_TOO_MANY_PARTS",
            )
        run.recording_parts += 1
        await self._db.commit()
        return run.recording_parts

    # ------------------------------------------------------------------
    # Answering
    # ------------------------------------------------------------------

    async def answer(
        self,
        interview: Interview,
        *,
        turn_id: uuid.UUID,
        audio: bytes,
        content_type: str | None,
    ) -> dict:
        """Save one answer, transcribe it, ask for a follow-up if one is needed, and return
        the next state. Safe to repeat: an answer already saved is not saved again."""
        if len(audio) > settings.strict_answer_max_bytes:
            raise ValidationException(
                "That recording is too large.", code="INTERVIEW_ANSWER_TOO_LARGE"
            )

        run = await self.get_run(interview.id)
        if run is None or run.started_at is None:
            raise ValidationException("This interview has not been started.")
        turns = await self._turns(interview.id)
        turn = next((candidate for candidate in turns if candidate.id == turn_id), None)
        if turn is None:
            raise ValidationException(
                "That question is not part of this interview.", code="INTERVIEW_TURN_UNKNOWN"
            )
        if turn.answered_at is not None:
            return await self._state(interview, run, turns, _now())

        # The slow part (speech to text) happens before the row is locked, so a reload on
        # another tab is not held up behind it. The lock below then settles who got there first.
        text: str | None = None
        audio_seconds: float | None = None
        if len(audio) >= MIN_AUDIO_BYTES:
            try:
                transcribed, audio_seconds = await self._transcribe(
                    audio, audio_file_name(content_type)
                )
                text = " ".join((transcribed or "").split()) or None
            except Exception:
                logger.exception(
                    "strict interview %s: could not transcribe the answer to turn %s",
                    interview.id,
                    turn.id,
                )

        status = await self._repo.lock_status(interview.id)
        if status in ENDED_STATUSES:
            # It ended while this answer was on its way: the answer is dropped (the recording
            # has it) and the screen is told.
            return await self._state(interview, run, await self._turns(interview.id), _now())
        if status != InterviewStatus.IN_PROGRESS.value:
            raise ValidationException("This interview is not in progress.")
        await self._db.refresh(turn)
        if turn.answered_at is not None:
            turns = await self._turns(interview.id)
            return await self._state(interview, run, turns, _now())

        now = _now()
        run.last_seen_at = now
        turn.answered_at = now
        turn.answer_text = text
        turn.answer_seconds = audio_seconds
        await self._db.flush()
        if audio_seconds:
            await self._repo.create_cost_row(
                interview_id=interview.id,
                component=InterviewCostComponent.TRANSCRIPTION.value,
                model=settings.transcription_model,
                duration_seconds=audio_seconds,
                cost_usd=compute_transcription_cost_usd(
                    settings.transcription_model, audio_seconds
                ),
            )

        follow_up = await self._follow_up_for(interview, run, turns, turn, now)
        if follow_up is not None:
            left = seconds_between(self._deadline(run), now)
            await self._open_turn(
                interview.id,
                turns,
                kind=TurnKind.FOLLOW_UP.value,
                number=turn.question_number,
                text=follow_up,
                seconds=min(settings.strict_follow_up_seconds, left),
                at=now,
            )
        else:
            await self._open_next_question(
                interview.id, run, turns, number=turn.question_number + 1, at=now
            )

        await self._db.commit()
        return await self._state(interview, run, turns, now)

    async def _follow_up_for(
        self,
        interview: Interview,
        run: StrictInterviewRun,
        turns: list[InterviewTurn],
        turn: InterviewTurn,
        now: datetime,
    ) -> str | None:
        """The follow-up probe this answer deserves, or None.

        ``turn`` is the answer just given, to the question or to an earlier probe. A question gets
        at most ``strict_max_follow_ups`` probes (two, the same for every candidate), none for an
        answer too short to follow up, and only when it can be asked without costing a later
        question its full time: what is left after the probe's own allowance must still cover
        every question still to come. The model is shown what was already asked and answered on
        this question, so a second probe never repeats the first.
        """
        mode = follow_up_mode_of(run.follow_up_mode)
        if mode == FollowUpMode.NONE:
            return None  # the employer chose to keep to the written questions
        if not turn.answer_text:
            return None
        if len(turn.answer_text.split()) < MIN_WORDS_FOR_FOLLOW_UP:
            return None
        thread = [other for other in turns if other.question_number == turn.question_number]
        probes_asked = sum(1 for other in thread if other.kind == TurnKind.FOLLOW_UP.value)
        if probes_asked >= settings.strict_max_follow_ups:
            return None

        # The employer's own probes for this question, minus any already asked of this candidate.
        questions = run.questions or []
        asked = {" ".join(other.question_text.split()).casefold() for other in thread}
        probes = [
            probe
            for probe in prepared_probes(
                questions[turn.question_number - 1].get("probes")
                if 0 < turn.question_number <= len(questions)
                else None
            )
            if " ".join(probe.split()).casefold() not in asked
        ]
        only_prepared = mode == FollowUpMode.PROBES_ONLY
        if only_prepared and not probes:
            return None  # nothing prepared (or all used): this mode never makes one up

        left = seconds_between(self._deadline(run), now)
        allowance = min(settings.strict_follow_up_seconds, left)
        later = (run.questions or [])[turn.question_number :]
        needed_later = sum(question["time_limit_seconds"] for question in later)
        if left < settings.strict_follow_up_min_remaining_seconds:
            return None
        if left - allowance < needed_later:
            return None

        ai_service = self._ai_service
        made_here = ai_service is None
        if made_here:
            from app.modules.ai.service import AnthropicCVExtractionService

            ai_service = AnthropicCVExtractionService()
        try:
            raw = await ai_service.decide_interview_follow_up(
                question=turn.question_text,
                answer=turn.answer_text,
                interview_brief=interview.job.interview_brief or "",
                earlier_exchange=earlier_exchange(thread, turn),
                probes_left=settings.strict_max_follow_ups - probes_asked,
                prepared_probes=probes,
                only_prepared=only_prepared,
            )
        except Exception:
            logger.exception("strict interview %s: follow-up decision failed", interview.id)
            return None
        finally:
            if made_here:
                await ai_service._client.close()
        if only_prepared:
            # Only a probe the employer wrote, in the employer's words.
            return match_prepared_probe(raw, probes)
        return clean_follow_up(raw)

    # ------------------------------------------------------------------
    # The transcript the scorer reads
    # ------------------------------------------------------------------

    async def interview_conditions(self, interview_id: uuid.UUID) -> str:
        """Facts about how this interview ran that the scorer must treat as circumstances, not as
        the candidate's behaviour: page reloads, an interview that ended early and was
        reinstated, and answers that could not be written down. Recorded by the platform, never
        from what the candidate said. Empty when nothing unusual happened (and for a live
        interview)."""
        run = await self.get_run(interview_id)
        if run is None:
            return ""
        events = await self._events(interview_id)
        lines: list[str] = []
        reloads = sum(1 for event in events if event.kind == ConductEventKind.RELOAD.value)
        if reloads:
            lines.append(
                f"The page reloaded or reopened {reloads} time{'s' if reloads != 1 else ''}; "
                "the interview carried on at the same question each time."
            )
        reinstated = sum(1 for event in events if event.kind == ConductEventKind.REINSTATED.value)
        if reinstated:
            lines.append(
                f"The interview ended early and was reinstated by the employer {reinstated} "
                f"time{'s' if reinstated != 1 else ''}, so it was taken in {run.attempt} sittings."
            )
        turns = await self._turns(interview_id)
        missing = [
            str(turn.question_number)
            for turn in turns
            if turn.answered_at is not None and not turn.answer_text
        ]
        if missing:
            lines.append(
                "These answers could not be written down (nothing was heard or the transcription "
                f"failed), for question number {', '.join(dict.fromkeys(missing))}: they are "
                "missing from the transcript, not empty answers."
            )
        return "\n".join(f"- {line}" for line in lines)

    async def build_transcript(self, interview_id: uuid.UUID) -> tuple[str, bool] | None:
        """The interview as the scorer reads it, built here from the saved answers.

        Returns ``(text, complete)``, or None when the interview was never started. Questions
        are labelled "AI" and answers "Candidate", the labels the scorer and the transcript
        check already know. ``complete`` is false when any answer has no text (it could not be
        transcribed, or nothing was said), so the recording is transcribed to fill the gap.
        """
        turns = await self._turns(interview_id)
        if not turns:
            return None
        lines: list[str] = []
        complete = True
        for turn in turns:
            lines.append(f"AI: {turn.question_text}")
            if turn.answer_text:
                lines.append(f"Candidate: {turn.answer_text}")
            else:
                complete = False
                lines.append(f"Candidate: {NO_ANSWER_TEXT}")
        return "\n\n".join(lines), complete
