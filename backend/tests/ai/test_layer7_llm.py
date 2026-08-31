"""Unit tests for Layer 7: LLM extraction — MockLLMService, zero real API calls."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.cv_pipeline.layer3_sections import DetectedSections
from app.core.cv_pipeline.layer7_llm import LLMExtractionResult
from app.modules.ai.service import MockAIService


def make_sections(**kwargs) -> DetectedSections:
    defaults = {
        "summary": None,
        "experience": "Worked at Google as Software Engineer 2020-2023.",
        "education": "BSc Computer Science, Lagos 2018.",
        "skills": None,
        "certifications": None,
        "projects": None,
        "references": None,
        "unclassified": "John Doe\njohn@email.com",
    }
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

    valid_response = json.dumps(
        {
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
        }
    )

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=valid_response)]
    mock_response.usage = MagicMock(input_tokens=1200, output_tokens=350)
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    service._client = mock_client

    result = await service.extract_cv_data(make_sections(), {})

    assert "Python" in result.skills
    assert result.years_experience == 5
    assert result.seniority_level == "senior"


# ── Token usage capture (cost tracking) ────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_cv_data_captures_real_token_usage():
    """The whole point of this fix — response.usage must reach LLMExtractionResult,
    not be silently discarded (see the CVParsingCost bug this closes)."""
    from app.modules.ai.service import AnthropicCVExtractionService

    service = AnthropicCVExtractionService.__new__(AnthropicCVExtractionService)

    valid_response = json.dumps({"skills": ["Python"], "field_confidence": {}})
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=valid_response)]
    mock_response.usage = MagicMock(input_tokens=987, output_tokens=321)
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    service._client = mock_client

    result = await service.extract_cv_data(make_sections(), {})

    assert result.input_tokens == 987
    assert result.output_tokens == 321


@pytest.mark.asyncio
async def test_extract_cv_data_exception_path_has_zero_usage():
    """The exception-fallback LLMExtractionResult() has no response to read
    usage from — it must stay at the dataclass default (0), not crash."""
    from app.modules.ai.service import AnthropicCVExtractionService

    service = AnthropicCVExtractionService.__new__(AnthropicCVExtractionService)

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(side_effect=RuntimeError("API down"))
    service._client = mock_client

    result = await service.extract_cv_data(make_sections(), {})

    assert result.input_tokens == 0
    assert result.output_tokens == 0


@pytest.mark.asyncio
async def test_generate_fit_reasoning_captures_real_token_usage():
    """Fit-reasoning (candidate-vs-job scoring, used by both the Application
    and talent-pool "score against job" flows) must also capture usage —
    this was previously discarded, leaving both flows' LLM cost untracked."""
    from app.modules.ai.service import AnthropicCVExtractionService

    service = AnthropicCVExtractionService.__new__(AnthropicCVExtractionService)

    valid_response = json.dumps(
        {"score": 80, "strengths": [], "weaknesses": [], "fit_summary": "Good fit"}
    )
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=valid_response)]
    mock_response.usage = MagicMock(input_tokens=555, output_tokens=111)
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    service._client = mock_client

    result = await service.generate_fit_reasoning(
        candidate_context="Senior engineer", job_context="Backend role"
    )

    assert result.score == 80
    assert result.input_tokens == 555
    assert result.output_tokens == 111


@pytest.mark.asyncio
async def test_generate_fit_reasoning_exception_path_has_zero_usage():
    from app.modules.ai.service import AnthropicCVExtractionService

    service = AnthropicCVExtractionService.__new__(AnthropicCVExtractionService)

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(side_effect=RuntimeError("API down"))
    service._client = mock_client

    result = await service.generate_fit_reasoning(
        candidate_context="Senior engineer", job_context="Backend role"
    )

    assert result.input_tokens == 0
    assert result.output_tokens == 0
