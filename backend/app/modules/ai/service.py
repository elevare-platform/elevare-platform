"""AI service module — AIService interface and concrete implementations."""

import json
import logging
import re
from abc import ABC, abstractmethod
from datetime import UTC, datetime

import numpy as np
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.cv_pipeline.layer3_sections import DetectedSections
from app.core.cv_pipeline.layer7_llm import LLMExtractionResult

from .schema import FitReasoningResult, MatchResult

logger = logging.getLogger(__name__)

_STOP_WORDS = {
    "the",
    "and",
    "or",
    "for",
    "to",
    "a",
    "in",
    "of",
    "with",
    "is",
    "are",
    "we",
    "you",
    "will",
    "experience",
    "required",
    "must",
    "have",
    "able",
    "good",
    "strong",
    "excellent",
    "knowledge",
    "understanding",
    "work",
    "working",
    "team",
    "role",
    "position",
    "candidate",
    "looking",
}


def _tokenise(text: str) -> set[str]:
    """Lowercase, strip punctuation, split, remove stop words."""
    tokens = re.split(r"[\s\.,\-\/\(\)\[\]]+", text.lower())
    return {t for t in tokens if t and t not in _STOP_WORDS}


class AIService(ABC):
    """Abstract base class defining the AI service interface."""

    @abstractmethod
    async def compute_match_score(
        self,
        candidate_skills: list[str],
        job_description: str,
        job_title: str,
        required_skills: list[str] | None = None,
    ) -> MatchResult:
        """Compute a match score between a candidate's skills and a job."""
        ...

    @abstractmethod
    async def extract_cv_data(
        self,
        sections: DetectedSections,
        already_extracted: dict,
    ) -> LLMExtractionResult:
        """Extract structured data from CV sections using AI."""
        ...

    @abstractmethod
    async def generate_fit_reasoning(
        self,
        candidate_context: str,
        job_context: str,
    ) -> "FitReasoningResult":
        """Generate fit score and qualitative reasoning for a candidate-job pair."""
        ...

    @abstractmethod
    async def generate_embedding(self, text: str) -> list[float]:
        """Generate a 1536-dim embedding vector for the given text."""
        ...

    @abstractmethod
    async def compute_similarity_score(
        self,
        candidate_embedding: list[float],
        job_embedding: list[float],
    ) -> int:
        """Compute cosine similarity between two embeddings, scaled to 0-100."""
        ...

    @abstractmethod
    async def generate_job_description_text(
        self,
        mode: str,
        field: str,
        current_text: str | None,
        job_context,
    ) -> str:
        """Generate or improve a job description field using AI."""
        ...


class KeywordAIService(AIService):
    """Deterministic keyword-matching implementation of AIService."""

    async def compute_match_score(
        self,
        candidate_skills: list[str],
        job_description: str,
        job_title: str,
        required_skills: list[str] | None = None,
    ) -> MatchResult:
        """Score a candidate against a job using keyword matching."""
        if required_skills:
            required_lower = [s.lower() for s in required_skills]
            matched = [s for s in candidate_skills if s.lower() in required_lower]
            total = len(required_skills)
        else:
            job_tokens = _tokenise(f"{job_title} {job_description}")
            matched = [s for s in candidate_skills if s.lower() in job_tokens]
            total = len(job_tokens)

        score = round(len(matched) / total * 100) if total > 0 else 0
        score = max(0, min(100, score))

        return MatchResult(
            score=score,
            matched_keywords=matched,
            total_job_keywords=total,
            computed_at=datetime.now(UTC),
        )

    async def extract_cv_data(
        self,
        sections,
        already_extracted: dict,
    ) -> "LLMExtractionResult":
        """Return an empty extraction result (keyword service does not parse CVs)."""
        from app.core.cv_pipeline.layer7_llm import LLMExtractionResult

        return LLMExtractionResult()

    async def generate_fit_reasoning(
        self,
        candidate_context: str,
        job_context: str,
    ) -> "FitReasoningResult":
        """Delegate fit reasoning to MockAIService."""
        return await MockAIService().generate_fit_reasoning(
            candidate_context, job_context
        )

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate a 1536-dim embedding vector for the given text."""
        raise NotImplementedError()

    async def compute_similarity_score(
        self,
        candidate_embedding: list[float],
        job_embedding: list[float],
    ) -> int:
        """Compute cosine similarity between two embeddings, scaled to 0-100."""
        raise NotImplementedError()

    async def generate_job_description_text(
        self,
        mode: str,
        field: str,
        current_text: str | None,
        job_context,
    ) -> str:
        """Return a template-based fallback — no LLM required."""
        field_label = field.replace("_", " ")
        if current_text and current_text.strip():
            return f"[Improved] {current_text.strip()}"
        return f"[Generated {field_label} for {job_context.title}]"


class MockAIService(AIService):
    """Fixed-score implementation for tests — no real computation."""

    async def compute_match_score(
        self,
        candidate_skills: list[str],
        job_description: str,
        job_title: str,
        required_skills: list[str] | None = None,
    ) -> MatchResult:
        """Return a fixed score of 75 for test purposes."""
        return MatchResult(
            score=75,
            matched_keywords=candidate_skills[:3] if candidate_skills else [],
            total_job_keywords=10,
            computed_at=datetime.now(UTC),
        )

    async def extract_cv_data(
        self,
        sections: DetectedSections,
        already_extracted: dict,
    ) -> LLMExtractionResult:
        """Return an empty extraction result for test purposes."""
        return LLMExtractionResult()

    async def generate_fit_reasoning(
        self,
        candidate_context: str,
        job_context: str,
    ) -> "FitReasoningResult":
        """Return a canned fit reasoning result for test purposes."""
        return FitReasoningResult(
            score=55,
            strengths=["Strong technical background", "Relevant experience"],
            weaknesses=["Limited leadership exposure"],
            fit_summary="Candidate shows solid alignment with core requirements. Minor gaps in seniority expectations.",
        )

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate a 1536-dim embedding vector for the given text."""
        return [0.1] * 1536

    async def compute_similarity_score(
        self,
        candidate_embedding: list[float],
        job_embedding: list[float],
    ) -> int:
        """Compute cosine similarity between two embeddings, scaled to 0-100."""
        return 75

    async def generate_job_description_text(
        self,
        mode: str,
        field: str,
        current_text: str | None,
        job_context,
    ) -> str:
        """Return a fixed string for test purposes."""
        return f"Mock generated text for {field} in {mode} mode."


class AnthropicCVExtractionService(AIService):
    """CV extraction and fit reasoning service backed by the Anthropic Claude API."""

    def __init__(self) -> None:
        """Initialise the Anthropic async client using the configured API key."""
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Stub for the existing method - this class only handles CV extraction
    async def compute_match_score(
        self, candidate_skills, job_description, job_title, required_skills=None
    ):
        """Delegate match scoring to KeywordAIService (this class handles CV extraction only)."""
        return await KeywordAIService().compute_match_score(
            candidate_skills,
            job_description,
            job_title,
            required_skills,
        )

    async def extract_cv_data(
        self,
        sections: DetectedSections,
        already_extracted: dict,
    ) -> LLMExtractionResult:
        """Extract structured CV data by calling the Claude API."""
        from app.modules.ai.prompts.cv_extraction import (
            CV_EXTRACTION_SYSTEM_PROMPT,
            build_user_prompt,
        )

        user_prompt = build_user_prompt(
            already_extracted=already_extracted,
            experience_text=sections.experience or "",
            education_text=sections.education or "",
        )

        raw = ""

        try:
            response = await self._client.messages.create(
                model=settings.anthropic_model,
                max_tokens=2048,
                system=CV_EXTRACTION_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt,
                    }
                ],
            )

            raw = response.content[0].text
            data = self._parse_response(raw)

            return LLMExtractionResult(
                skills=data.get("skills", []),
                years_experience=data.get("years_experience"),
                current_title=data.get("current_title"),
                profession=data.get("profession"),
                seniority_level=data.get("seniority_level"),
                summary=data.get("summary"),
                work_history=data.get("work_history", []),
                education=data.get("education", []),
                field_confidence=data.get("field_confidence", {}),
            )
        except (KeyError, TypeError, Exception) as e:
            logger.error(
                "LLM CV extraction failed",
                extra={"error": str(e), "raw": raw[:500]},
            )
            return LLMExtractionResult()

    @staticmethod
    def _fallback_response() -> dict:
        """Return a safe default when Claude fails or returns invalid JSON.

        This is a static method so it can be called from anywhere in the class
        without needing an instance.

        Returns:
            dict: Default response structure with null/empty values.
        """
        return LLMExtractionResult()

    def _parse_response(self, claude_response: str) -> dict:
        """Parse Claude's response, handling multiple formats.

        Handles:
        1. JSON wrapped in code fences: ```json {...} ```
        2. Plain JSON: {...}
        3. Malformed responses

        Args:
            claude_response (str): Raw response text from Claude.

        Returns:
            dict: Parsed response dict, or fallback response if parsing fails.
        """
        if not claude_response or not claude_response.strip():
            return self._fallback_response()

        cleaned_response = claude_response.strip()

        # Try 1: Look for JSON in code fences
        dict_match = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```", cleaned_response, re.DOTALL
        )

        if dict_match:
            # Found JSON in code fences
            json_str = dict_match.group(1)
            json_str = json_str.replace("```json", "").replace("```", "").strip()

            try:
                result = json.loads(json_str)

                # Validate it is a dictionary
                if not isinstance(result, dict):
                    logger.error(
                        f"Warning: Expected dict, got {type(result)} - returning fallback"
                    )
                    return self._fallback_response()

                return result

            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON from code fence: {e}")
                logger.error(f"Attempted to parse: {json_str[:200]}...")
                # Fall through to try plain JSON

        # Try 2: Parse as plain JSON (no code fences)
        try:
            result = json.loads(cleaned_response)

            # Validate it is a dictionary
            if not isinstance(result, dict):
                logger.error(
                    f"Warning: Expected dict, got {type(result)} - returning fallback"
                )
                return self._fallback_response()

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing plain JSON: {e}")
            logger.error(f"Raw response: {cleaned_response[:200]}...")
            return self._fallback_response()

    async def generate_fit_reasoning(
        self,
        candidate_context: str,
        job_context: str,
    ) -> "FitReasoningResult":
        """Generate fit score, strengths/weaknesses and summary via Claude."""
        from app.modules.ai.prompts.fit_reasoning import (
            FIT_REASONING_SYSTEM_PROMPT,
            build_fit_reasoning_prompt,
        )
        from app.modules.ai.schema import FitReasoningResult

        user_prompt = build_fit_reasoning_prompt(
            candidate_context=candidate_context,
            job_context=job_context,
        )

        raw = ""

        try:
            response = await self._client.messages.create(
                model=settings.anthropic_model,
                max_tokens=1024,
                system=FIT_REASONING_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )

            raw = response.content[0].text
            data = self._parse_response(raw)

            return FitReasoningResult(
                score=max(0, min(100, int(data.get("score", 0)))),
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                fit_summary=data.get("fit_summary", ""),
            )
        except (KeyError, TypeError, Exception) as e:
            logger.error(
                "LLM Fit Reasoning failed", extra={"error": str(e), "raw": raw[:500]}
            )
            return FitReasoningResult(score=0)

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate a 1536-dim embedding vector for the given text."""
        raise NotImplementedError()

    async def compute_similarity_score(
        self,
        candidate_embedding: list[float],
        job_embedding: list[float],
    ) -> int:
        """Compute cosine similarity between two embeddings, scaled to 0-100."""
        raise NotImplementedError()

    async def generate_job_description_text(
        self,
        mode: str,
        field: str,
        current_text: str | None,
        job_context,
    ) -> str:
        """Generate or improve a job description field via Claude."""
        from app.modules.ai.enums import JobDescriptionField, JobDescriptionMode
        from app.modules.ai.prompts.job_description import (
            JOB_DESCRIPTION_SYSTEM_PROMPT,
            build_job_description_prompt,
        )

        user_prompt = build_job_description_prompt(
            mode=JobDescriptionMode(mode),
            field=JobDescriptionField(field),
            current_text=current_text,
            job_context=job_context,
        )

        try:
            response = await self._client.messages.create(
                model=settings.anthropic_model,
                max_tokens=1024,
                system=JOB_DESCRIPTION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = response.content[0].text.strip()
            # Strip any accidental code fences the model may add
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            return raw.strip()
        except Exception as e:
            logger.error(
                "LLM job description generation failed", extra={"error": str(e)}
            )
            raise


class EmbeddingAIService(AIService):
    """Embedding-based scoring service backed by the OpenAI embedding API."""

    def __init__(self) -> None:
        """Initialise the OpenAI async client using the configured API key."""
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate_embedding(self, text: str) -> list[float]:
        """Call OpenAI text-embedding-3-small and return the 1536-dim vector."""
        response = await self._client.embeddings.create(
            input=text,
            model="text-embedding-3-small",
        )
        return response.data[0].embedding

    async def compute_similarity_score(
        self, candidate_embedding: list[float], job_embedding: list[float]
    ) -> int:
        """Cosine similarity scaled to 0-100."""
        a = np.array(candidate_embedding)
        b = np.array(job_embedding)

        similarity = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
        return max(0, min(100, round((similarity + 1) / 2 * 100)))

    async def compute_match_score(
        self, candidate_skills, job_description, job_title, required_skills=None
    ):
        """Delegate to KeywordAIService for keyword-based match scoring."""
        return await KeywordAIService().compute_match_score(
            candidate_skills, job_description, job_title, required_skills
        )

    async def extract_cv_data(self, sections, already_extracted):
        """Not implemented — EmbeddingAIService does not extract CV data."""
        raise NotImplementedError("EmbeddingAIService does not extract CV data.")

    async def generate_fit_reasoning(
        self, candidate_context: str, job_context: str
    ) -> "FitReasoningResult":
        """Not implemented — EmbeddingAIService does not generate fit reasoning."""
        raise NotImplementedError("EmbeddingAIService does not generate fit reasoning.")

    async def generate_job_description_text(
        self,
        mode: str,
        field: str,
        current_text: str | None,
        job_context,
    ) -> str:
        """Delegate to AnthropicCVExtractionService for job description generation."""
        return await AnthropicCVExtractionService().generate_job_description_text(
            mode, field, current_text, job_context
        )


def get_ai_service() -> AIService:
    """FastAPI dependency — returns EmbeddingAIService when an OpenAI key is configured.

    Falls back to KeywordAIService when the key is absent (CI, local dev without key).
    """
    if settings.openai_api_key:
        return EmbeddingAIService()
    return KeywordAIService()


# Alias used in Phase 12 tests — MockAIService already implements the full interface
MockEmbeddingAIService = MockAIService
