from dataclasses import dataclass, field


@dataclass
class LLMExtractionResult:
    skills: list[str] = field(default_factory=list)
    years_experience: int | None = None
    current_title: str | None = None
    seniority_level: str | None = None
    summary: str | None = None
    work_history: list[dict] = field(default_factory=list)
    education: list[dict] = field(default_factory=list)
    field_confidence: dict[str, str] = field(default_factory=lambda: {
        "skills": "low",
        "years_experience": "low",
        "current_title": "low",
        "seniority_level": "low",
        "summary": "low",
        "work_history": "low",
        "education": "low",
    })