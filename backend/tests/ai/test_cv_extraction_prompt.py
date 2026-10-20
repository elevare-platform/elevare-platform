"""The extraction prompt must always carry the full CV text, and nothing that
describes the answer's shape (the API enforces that).

A CV whose headings the section matcher does not recognise ("Career Summary",
"Professional Work Experience", ...) produces empty experience and education
sections. The model then had nothing to read and returned an empty profile.
"""

import inspect

import pytest

from app.modules.ai.prompts.cv_extraction import (
    CV_EXTRACTION_SYSTEM_PROMPT,
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

from .anthropic_fakes import anthropic_service, fake_client

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


def test_the_prompts_no_longer_describe_the_json_shape():
    """The reply shape is enforced by the API from CVExtractionOutput. A template
    in the prompt costs tokens on every call, and the old one held an all-null
    work-history entry that models copied into real answers."""
    user_prompt = build_user_prompt({}, full_text=CV_TEXT)

    for prompt in (user_prompt, CV_EXTRACTION_SYSTEM_PROMPT):
        assert "schema" not in prompt.lower()
        assert "ONLY valid JSON" not in prompt
        assert "code fences" not in prompt
        assert '"company": null' not in prompt
        assert '"is_current"' not in prompt


@pytest.mark.asyncio
async def test_service_logs_a_warning_when_it_truncates(caplog):
    service = anthropic_service(fake_client())

    with caplog.at_level("WARNING"):
        await service.extract_cv_data({}, full_text="A" * (MAX_FULL_TEXT_CHARS + 1))

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
def test_every_extract_cv_data_takes_the_same_arguments(service_class):
    """The pipeline holds an AIService and does not know which class it has, so
    every implementation must accept the same arguments or one of them breaks the
    day it is used. The header-matched sections are not among them any more."""
    params = list(inspect.signature(service_class.extract_cv_data).parameters)

    assert params == ["self", "already_extracted", "model", "full_text"]


@pytest.mark.asyncio
async def test_anthropic_service_sends_full_text_to_the_model():
    client = fake_client()
    service = anthropic_service(client)

    await service.extract_cv_data({}, full_text=CV_TEXT)

    sent_prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "Regional Sales Manager at Unilever Nigeria" in sent_prompt
    assert sent_prompt.count("Regional Sales Manager at Unilever Nigeria") == 1
