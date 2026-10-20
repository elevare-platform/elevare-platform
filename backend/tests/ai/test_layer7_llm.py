"""Unit tests for Layer 7: LLM extraction. Zero real API calls: the Anthropic
client is a fake that returns realistic replies (see anthropic_fakes.py)."""

import logging

import pytest

from app.core.cv_pipeline.layer7_llm import LLMExtractionResult
from app.modules.ai.service import MockAIService

from .anthropic_fakes import (
    NOTHING_FOUND,
    anthropic_service,
    extraction,
    failing_client,
    fake_client,
)

# ── MockAIService returns valid schema ────────────────────────────────────────


@pytest.mark.asyncio
async def test_mock_service_returns_valid_schema():
    result = await MockAIService().extract_cv_data(already_extracted={})

    assert isinstance(result, LLMExtractionResult)
    assert isinstance(result.skills, list)
    assert isinstance(result.work_history, list)
    assert isinstance(result.education, list)
    assert isinstance(result.field_confidence, dict)


@pytest.mark.asyncio
async def test_mock_service_returns_empty_result():
    result = await MockAIService().extract_cv_data({})

    # All fields null/empty — mock returns safe defaults
    assert result.years_experience is None
    assert result.current_title is None
    assert result.summary is None


# ── AnthropicCVExtractionService: a good reply ───────────────────────────────


@pytest.mark.asyncio
async def test_valid_reply_is_turned_into_the_extraction_result():
    reply = extraction(
        skills=["Python", "FastAPI"],
        years_experience=5,
        current_title="Software Engineer",
        profession="Software Engineering",
        seniority_level="senior",
        summary="Experienced backend engineer.",
        work_history=[
            {
                "company": "Google",
                "title": "Software Engineer",
                "start_date": "2020-01",
                "end_date": None,
                "duration_months": 36,
                "description": "Built APIs.",
                "is_current": True,
            }
        ],
        education=[
            {
                "institution": "University of Lagos",
                "degree": "BSc Computer Science",
                "field": "Computer Science",
                "graduation_year": 2018,
                "qualification_type": "bsc",
            }
        ],
        field_confidence={**NOTHING_FOUND["field_confidence"], "skills": "high"},
    )
    service = anthropic_service(fake_client(reply, input_tokens=1200, output_tokens=350))

    result = await service.extract_cv_data({}, model="m")

    assert result.model == "m"
    assert result.skills == ["Python", "FastAPI"]
    assert result.years_experience == 5
    assert result.seniority_level == "senior"
    assert result.profession == "Software Engineering"
    # The merger reads these as plain dicts with these keys.
    assert result.work_history == [
        {
            "company": "Google",
            "title": "Software Engineer",
            "start_date": "2020-01",
            "end_date": None,
            "duration_months": 36,
            "description": "Built APIs.",
            "is_current": True,
        }
    ]
    assert result.education[0]["institution"] == "University of Lagos"
    assert result.field_confidence["skills"] == "high"
    assert set(result.field_confidence) == set(NOTHING_FOUND["field_confidence"])


@pytest.mark.asyncio
async def test_nothing_found_is_an_empty_list_not_a_fake_entry():
    """The old prompt's template held one all-null work-history entry that models
    copied. 'Nothing found' is now an empty list, and stays one."""
    service = anthropic_service(fake_client(NOTHING_FOUND))

    result = await service.extract_cv_data({})

    assert result.work_history == []
    assert result.education == []
    assert result.skills == []


@pytest.mark.asyncio
async def test_the_request_asks_the_api_to_enforce_the_answer_shape():
    client = fake_client()
    service = anthropic_service(client)

    await service.extract_cv_data({}, model="m")

    kwargs = client.messages.create.await_args.kwargs
    schema = kwargs["output_config"]["format"]["schema"]
    assert kwargs["output_config"]["format"]["type"] == "json_schema"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) >= {"skills", "work_history", "education", "field_confidence"}
    assert kwargs["model"] == "m"


# ── AnthropicCVExtractionService: a reply that cannot be used ────────────────


@pytest.mark.asyncio
async def test_a_reply_that_is_not_the_requested_shape_gives_an_empty_result():
    service = anthropic_service(fake_client("this is not json at all {{{{"))

    result = await service.extract_cv_data({}, model="m")

    assert isinstance(result, LLMExtractionResult)
    assert result.skills == []
    assert result.summary is None


@pytest.mark.asyncio
async def test_a_reply_missing_required_fields_gives_an_empty_result():
    service = anthropic_service(fake_client({"skills": ["Python"]}))

    result = await service.extract_cv_data({})

    assert result.skills == []


@pytest.mark.asyncio
async def test_a_reply_cut_off_at_the_token_limit_is_logged_with_its_stop_reason(caplog):
    service = anthropic_service(
        fake_client('{"skills": ["Pyth', stop_reason="max_tokens", input_tokens=800, output_tokens=5120)
    )

    with caplog.at_level(logging.ERROR):
        result = await service.extract_cv_data({}, model="m")

    assert result.skills == []
    assert "max_tokens" in caplog.text
    # The call cost money even though it gave nothing: the cost is kept.
    assert (result.model, result.input_tokens, result.output_tokens) == ("m", 800, 5120)


# ── Token usage capture (cost tracking) ────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_cv_data_captures_real_token_usage():
    """The whole point of this fix — response.usage must reach LLMExtractionResult,
    not be silently discarded (see the CVParsingCost bug this closes)."""
    service = anthropic_service(
        fake_client(extraction(skills=["Python"]), input_tokens=987, output_tokens=321)
    )

    result = await service.extract_cv_data({})

    assert result.input_tokens == 987
    assert result.output_tokens == 321


@pytest.mark.asyncio
async def test_extract_cv_data_exception_path_has_zero_usage():
    """The exception-fallback LLMExtractionResult() has no response to read
    usage from — it must stay at the dataclass default (0), not crash."""
    service = anthropic_service(failing_client(RuntimeError("API down")))

    result = await service.extract_cv_data({})

    assert result.input_tokens == 0
    assert result.output_tokens == 0
