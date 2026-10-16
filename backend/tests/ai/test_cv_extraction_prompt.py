"""build_user_prompt must always carry the full CV text, never only the sections.

A CV whose headings the section matcher does not recognise ("Career Summary",
"Professional Work Experience", ...) produces empty experience and education
sections. The model then had nothing to read and returned an empty profile.
"""

import inspect
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.cv_pipeline.layer3_sections import DetectedSections
from app.modules.ai.prompts.cv_extraction import (
    MAX_FULL_TEXT_CHARS,
    build_user_prompt,
)
from app.modules.ai.service import (
    AIService,
    AnthropicCVExtractionService,
    EmbeddingAIService,
    KeywordAIService,
    MockAIService,
)

CV_TEXT = (
    "Amaka Obi\n"
    "Career Summary\n"
    "Regional Sales Manager at Unilever Nigeria, 2015 to 2022.\n"
    "Grew distributor network from 12 to 40 partners.\n"
)


def test_prompt_contains_full_text_when_sections_are_empty():
    prompt = build_user_prompt(already_extracted={}, full_text=CV_TEXT)

    assert "Regional Sales Manager at Unilever Nigeria" in prompt
    assert "Grew distributor network from 12 to 40 partners." in prompt


def test_text_within_the_cap_is_sent_untouched():
    text = "A" * MAX_FULL_TEXT_CHARS

    prompt = build_user_prompt({}, full_text=text)

    assert text in prompt
    assert "[CV text truncated]" not in prompt


def test_text_over_the_cap_loses_its_tail_and_says_so():
    text = "A" * MAX_FULL_TEXT_CHARS + "TAILMARKER"

    prompt = build_user_prompt({}, full_text=text)

    assert "A" * MAX_FULL_TEXT_CHARS in prompt
    assert "TAILMARKER" not in prompt
    assert "[CV text truncated]" in prompt


@pytest.mark.asyncio
async def test_service_logs_a_warning_when_it_truncates(caplog):
    service = AnthropicCVExtractionService.__new__(AnthropicCVExtractionService)
    response = MagicMock()
    response.content = [
        MagicMock(text=json.dumps({"skills": [], "field_confidence": {}}))
    ]
    response.usage = MagicMock(input_tokens=10, output_tokens=10)
    client = AsyncMock()
    client.messages.create = AsyncMock(return_value=response)
    service._client = client
    sections = DetectedSections(None, None, None, None, None, None, None, "")

    with caplog.at_level("WARNING"):
        await service.extract_cv_data(
            sections, {}, full_text="A" * (MAX_FULL_TEXT_CHARS + 1)
        )

    assert "truncated" in caplog.text


@pytest.mark.parametrize(
    "service_class",
    [
        AIService,
        KeywordAIService,
        MockAIService,
        AnthropicCVExtractionService,
        EmbeddingAIService,
    ],
)
def test_every_extract_cv_data_accepts_full_text(service_class):
    """The pipeline holds an AIService and does not know which class it has, so
    every implementation must accept full_text or one of them breaks the day it
    is used."""
    params = inspect.signature(service_class.extract_cv_data).parameters

    assert "full_text" in params


@pytest.mark.asyncio
async def test_anthropic_service_sends_full_text_to_the_model():
    service = AnthropicCVExtractionService.__new__(AnthropicCVExtractionService)

    response = MagicMock()
    response.content = [
        MagicMock(text=json.dumps({"skills": [], "field_confidence": {}}))
    ]
    response.usage = MagicMock(input_tokens=10, output_tokens=10)
    client = AsyncMock()
    client.messages.create = AsyncMock(return_value=response)
    service._client = client

    empty_sections = DetectedSections(
        summary=None,
        experience=None,
        education=None,
        skills=None,
        certifications=None,
        projects=None,
        references=None,
        unclassified=CV_TEXT,
    )

    await service.extract_cv_data(empty_sections, {}, full_text=CV_TEXT)

    sent_prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "Regional Sales Manager at Unilever Nigeria" in sent_prompt


@pytest.mark.asyncio
async def test_text_already_in_the_sections_is_not_sent_twice():
    """The full text contains the sections, so sending both only costs tokens."""
    service = AnthropicCVExtractionService.__new__(AnthropicCVExtractionService)
    response = MagicMock()
    response.content = [
        MagicMock(text=json.dumps({"skills": [], "field_confidence": {}}))
    ]
    response.usage = MagicMock(input_tokens=10, output_tokens=10)
    client = AsyncMock()
    client.messages.create = AsyncMock(return_value=response)
    service._client = client

    job_line = "Regional Sales Manager at Unilever Nigeria, 2015 to 2022."
    sections = DetectedSections(
        summary=None,
        experience=job_line,
        education="BSc Marketing, University of Lagos, 2012.",
        skills=None,
        certifications=None,
        projects=None,
        references=None,
        unclassified="",
    )

    await service.extract_cv_data(sections, {}, full_text=CV_TEXT)

    sent_prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert sent_prompt.count(job_line) == 1
    assert "BSc Marketing" not in sent_prompt
