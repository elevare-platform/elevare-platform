"""Unit tests for Layer 7: LLM extraction — MockLLMService, zero real API calls."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.cv_pipeline.layer3_sections import DetectedSections
from app.core.cv_pipeline.layer7_llm import LLMExtractionResult
from app.modules.ai.service import MockAIService


def make_sections(**kwargs) -> DetectedSections:
    defaults = dict(
        summary=None, experience="Worked at Google as Software Engineer 2020-2023.",
        education="BSc Computer Science, Lagos 2018.",
        skills=None, certifications=None, projects=None,
        references=None, unclassified="John Doe\njohn@email.com",
    )
    defaults.update(kwargs)
    return DetectedSections(**defaults)


# ── MockAIService returns valid schema ────────────────────────────────────────

@pytest.mark.asyncio
async def test_mock_service_returns_valid_schema():
    service = MockAIService()
    sections = make_sections()
    result = await service.extract_cv_data(sections, already_extracted={})

    assert isinstance(result, LLMExtractionResult)
    assert isinstance(result.skills, list)
    assert isinstance(result.work_history, list)
    assert isinstance(result.education, list)
    assert isinstance(result.field_confidence, dict)


@pytest.mark.asyncio
async def test_mock_service_returns_empty_result():
    service = MockAIService()
    result = await service.extract_cv_data(make_sections(), {})

    # All fields null/empty — mock returns safe defaults
    assert result.years_experience is None
    assert result.current_title is None
    assert result.summary is None


# ── AnthropicCVExtractionService — malformed JSON handling ───────────────────

@pytest.mark.asyncio
async def test_malformed_json_returns_null_result():
    from app.modules.ai.service import AnthropicCVExtractionService

    service = AnthropicCVExtractionService.__new__(AnthropicCVExtractionService)

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="this is not json at all {{{{")]
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    service._client = mock_client

    result = await service.extract_cv_data(make_sections(), {})

    assert isinstance(result, LLMExtractionResult)
    assert result.skills == []
    assert result.summary is None


@pytest.mark.asyncio
async def test_valid_json_response_parsed_correctly():
    from app.modules.ai.service import AnthropicCVExtractionService

    service = AnthropicCVExtractionService.__new__(AnthropicCVExtractionService)

    valid_response = json.dumps({
        "skills": ["Python", "FastAPI"],
        "years_experience": 5,
        "current_title": "Software Engineer",
        "seniority_level": "senior",
        "summary": "Experienced backend engineer.",
        "work_history": [],
        "education": [],
        "field_confidence": {
            "skills": "high",
            "years_experience": "medium",
            "current_title": "high",
            "seniority_level": "medium",
            "summary": "medium",
            "work_history": "low",
            "education": "low",
        },
    })

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=valid_response)]
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    service._client = mock_client

    result = await service.extract_cv_data(make_sections(), {})

    assert "Python" in result.skills
    assert result.years_experience == 5
    assert result.seniority_level == "senior"
