from abc import ABC, abstractmethod
from datetime import datetime, timezone
import re
from .schema import MatchResult

_STOP_WORDS = {
    "the", "and", "or", "for", "to", "a", "in", "of", "with", "is", "are",
    "we", "you", "will", "experience", "required", "must", "have", "able",
    "good", "strong", "excellent", "knowledge", "understanding", "work",
    "working", "team", "role", "position", "candidate", "looking",
}


def _tokenise(text: str) -> set[str]:
    """Lowercase, strip punctuation, split, remove stop words."""
    tokens = re.split(r"[\s\.,\-\/\(\)\[\]]+", text.lower())
    return {t for t in tokens if t and t not in _STOP_WORDS}


class AIService(ABC):
    @abstractmethod
    async def compute_match_score(
        self,
        candidate_skills: list[str],
        job_description: str,
        job_title: str,
        required_skills: list[str] | None = None,
    ) -> MatchResult:
        ...


class KeywordAIService(AIService):
    async def compute_match_score(
        self,
        candidate_skills: list[str],
        job_description: str,
        job_title: str,
        required_skills: list[str] | None = None,
    ) -> MatchResult:
        candidate_lower = {s.lower() for s in candidate_skills}

        if required_skills:
            # Primary path: score against explicit required skills.
            # score = matched_required / total_required * 100
            # This is transparent and explainable — "you match 7 of 10 required skills".
            required_lower = [s.lower() for s in required_skills]
            matched = [s for s in candidate_skills if s.lower() in required_lower]
            total = len(required_skills)
        else:
            # Fallback: tokenise title + description and match against that.
            job_tokens = _tokenise(f"{job_title} {job_description}")
            matched = [s for s in candidate_skills if s.lower() in job_tokens]
            total = len(job_tokens)

        score = round(len(matched) / total * 100) if total > 0 else 0
        score = max(0, min(100, score))

        return MatchResult(
            score=score,
            matched_keywords=matched,
            total_job_keywords=total,
            computed_at=datetime.now(timezone.utc),
        )


class MockAIService(AIService):
    """Fixed-score implementation for tests — no real computation."""

    async def compute_match_score(
        self,
        candidate_skills: list[str],
        job_description: str,
        job_title: str,
        required_skills: list[str] | None = None,
    ) -> MatchResult:
        return MatchResult(
            score=75,
            matched_keywords=candidate_skills[:3] if candidate_skills else [],
            total_job_keywords=10,
            computed_at=datetime.now(timezone.utc),
        )


def get_ai_service() -> AIService:
    """FastAPI dependency — returns KeywordAIService. Swap for EmbeddingAIService in Phase 12."""
    return KeywordAIService()

