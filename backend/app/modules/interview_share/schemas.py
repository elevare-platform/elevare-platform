"""Request and response shapes for the shared interview results link."""

from datetime import datetime

from pydantic import BaseModel

from app.modules.interviews.schema import StrictDetail


class ShareLinkResponse(BaseModel):
    """A job's interview results link, as its owner sees it."""

    url: str
    created_at: datetime
    expires_at: datetime
    # True once ``expires_at`` has passed: the link no longer opens, and a new one
    # can be made. Kept in the response so the screen can say so.
    expired: bool
    view_count: int
    last_viewed_at: datetime | None = None


class ShareLinkStatus(BaseModel):
    """The job's current link, or None when it has none (or it was revoked)."""

    link: ShareLinkResponse | None = None


class SharedTurn(BaseModel):
    """One turn of the interview conversation."""

    speaker: str  # "AI" or "Candidate"
    text: str


class SharedCandidate(BaseModel):
    """One candidate on the job's interview list, as the client sees them."""

    name: str
    current_title: str | None = None
    # NOT_INVITED | INVITED | IN_PROGRESS | COMPLETED | ENDED | NOT_COMPLETED
    # (ENDED: the interview ended early, because the candidate left the screen too often or
    # for too long, or chose to stop. ``strict`` says which and shows the notes.)
    status: str
    completed_at: datetime | None = None

    # The AI's assessment of the interview.
    interview_score: int | None = None
    interview_assessment: str | None = None

    # The AI's assessment of the CV for this job, shown alongside.
    cv_score: int | None = None
    cv_summary: str | None = None
    cv_strengths: list[str] | None = None
    cv_weaknesses: list[str] | None = None

    # The recording link works for minutes only, so passing it on does not share it.
    video_url: str | None = None

    # What the AI asked, one question per entry, then the whole conversation. When the
    # transcript has no speaker labels, ``turns`` is empty and ``transcript`` holds it as
    # plain text; ``transcript_note`` says why when that matters.
    questions: list[str] = []
    turns: list[SharedTurn] = []
    transcript: str | None = None
    transcript_note: str | None = None

    # A strict interview only: the rules the candidate accepted (version, date and time), a
    # conduct summary, the timeline and how it ended. Notes for the client to review, never
    # proof, and nothing is decided from them automatically.
    strict: StrictDetail | None = None


class SharedResults(BaseModel):
    """Everything the shared results page shows."""

    job_title: str
    company_name: str | None = None
    # What the AI was told to cover in these interviews (the job's interview brief).
    interview_focus: str | None = None
    expires_at: datetime
    total_candidates: int
    completed_count: int
    # True when the list was longer than the page shows.
    truncated: bool = False
    candidates: list[SharedCandidate]
