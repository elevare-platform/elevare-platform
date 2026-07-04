"""Domain models (dataclasses) for the CV extraction pipeline results."""
from dataclasses import dataclass
from datetime import datetime


@dataclass
class WorkEntry:
    """A single work experience entry extracted from a CV."""

    company: str | None
    title: str | None
    start_date: str | None
    end_date: str | None
    duration_months: int | None
    description: str | None
    is_current: bool


@dataclass
class EducationEntry:
    """A single education entry extracted from a CV."""

    institution: str | None
    degree: str | None
    field: str | None
    graduation_year: int | None
    qualification_type: str | None


@dataclass
class CVExtractionResult:
    """Final merged result from all 8 CV extraction pipeline layers."""

    # Identity
    full_name: str | None
    email: str | None
    phone: str | None
    linkedin_url: str | None
    location: str | None

    # Professional
    current_title: str | None
    seniority_level: str | None
    years_experience: int | None
    skills: list[str]
    taxonomy_matched_skills: list[str]
    llm_inferred_skills: list[str]
    summary: str | None

    # History
    work_history: list[WorkEntry]
    education: list[EducationEntry]

    # language
    detected_language: str
    is_english: bool
    language_confidence: float

    # Meta
    overall_confidence: float
    field_confidence: dict[str, str]
    extraction_layers_used: list[str]
    is_scanned: bool
    ocr_used: bool
    extracted_at: datetime

