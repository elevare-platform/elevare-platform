"""Pydantic and dataclass schemas for the AI module."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.modules.ai.enums import (
    CVParsingStatus,
    JobDescriptionField,
    JobDescriptionMode,
)


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
    """Structured output from the LLM fit-reasoning step.

    ``failed`` is True when the call errored, was cut off at the token limit, or
    returned no usable score. ``score`` is then meaningless: callers must not store
    it, because 0 is also a legitimate score for a candidate who is a poor fit. The
    token counts are still filled whenever a reply arrived, because a failed call
    costs money too.
    """

    score: int = 0
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    fit_summary: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    failed: bool = False


@dataclass
class InterviewScoringResult:
    """Structured output from the LLM interview-scoring step.

    ``failed`` is True when the call errored, was cut off, or returned no
    usable score. ``score`` is then meaningless: callers must not store it,
    because 0 is also a legitimate score for a genuinely poor interview.
    """

    score: int = 0
    summary: str = ""
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    failed: bool = False


Confidence = Literal["high", "medium", "low"]


class CVWorkEntry(BaseModel):
    """One job in a CV's work history, as the extraction model returns it."""

    company: str | None
    title: str | None
    start_date: str | None
    end_date: str | None
    duration_months: int | None
    description: str | None
    is_current: bool


class CVEducationEntry(BaseModel):
    """One education entry in a CV, as the extraction model returns it."""

    institution: str | None
    degree: str | None
    field: str | None
    graduation_year: int | None
    qualification_type: str | None


class CVFieldConfidence(BaseModel):
    """How sure the model is of each part of its answer. A fixed set of keys, not
    a free dictionary, because the structured-output schema must be closed."""

    skills: Confidence
    years_experience: Confidence
    current_title: Confidence
    profession: Confidence
    seniority_level: Confidence
    summary: Confidence
    work_history: Confidence
    education: Confidence


class CVExtractionOutput(BaseModel):
    """What the CV extraction model must return. Sent to the API as a JSON schema,
    so the reply always has this shape; "nothing found" is an empty list or null.

    Every field is required (a missing fact is null or an empty list, never an
    omitted key), which is what lets the API enforce the shape.
    """

    skills: list[str]
    years_experience: int | None
    current_title: str | None
    profession: str | None
    seniority_level: Literal["junior", "mid", "senior", "lead", "executive"] | None
    summary: str | None
    work_history: list[CVWorkEntry]
    education: list[CVEducationEntry]
    field_confidence: CVFieldConfidence


class JobContext(BaseModel):
    """Contextual metadata about the job, used to guide AI generation."""

    title: str
    seniority: str | None = None
    skills: list[str] | None = None
    industry: str | None = None
    company_name: str | None = None


class JobDescriptionRequest(BaseModel):
    """Request payload for the AI job description writer."""

    mode: JobDescriptionMode
    field: JobDescriptionField
    current_text: str | None = None
    job_context: JobContext


class JobDescriptionResponse(BaseModel):
    """Response payload from the AI job description writer."""

    generated_text: str
    mode: JobDescriptionMode
    field: JobDescriptionField
