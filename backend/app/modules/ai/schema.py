"""Pydantic and dataclass schemas for the AI module."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.ai.enums import CVParsingStatus


class MatchResult(BaseModel):
    """Result of a keyword-based candidate-to-job match computation."""

    score: int
    matched_keywords: list[str]
    total_job_keywords: int
    computed_at: datetime


class MatchRequest(BaseModel):
    """Request payload for triggering a match score computation."""

    candidate_id: uuid.UUID
    job_id: uuid.UUID


class SubmissionResponse(BaseModel):
    """Response schema for a parsed CV submission record."""

    id: uuid.UUID
    uploaded_by_email: str | None = None
    filename: str
    parse_status: CVParsingStatus
    parsed_data: dict | None = None
    deterministic_data: dict | None = None
    llm_data: dict | None = None
    flag_reasons: list[str] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_submission(cls, submission) -> "SubmissionResponse":
        """Build a SubmissionResponse from an ORM ParsedCVSubmission instance."""
        return cls(
            id=submission.id,
            uploaded_by_email=(
                submission.uploader.email if submission.uploader else None
            ),
            filename=submission.filename,
            parse_status=submission.parse_status,
            parsed_data=submission.parsed_data,
            deterministic_data=submission.deterministic_data,
            llm_data=submission.llm_data,
            flag_reasons=submission.flag_reasons,
            created_at=submission.created_at,
        )


@dataclass
class FitReasoningResult:
    """Structured output from the LLM fit-reasoning step."""

    score: int = 0
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    fit_summary: str = ""
