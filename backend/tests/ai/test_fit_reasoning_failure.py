"""generate_fit_reasoning says honestly when it could not produce a score.

Before, every failure came back as `FitReasoningResult(score=0)`: an API error, a reply
cut off at the token limit, text that was not JSON, and even a reply with no score in
it (the code defaulted a missing score to 0). All of those were then saved as a real
score of 0."""

import json
import logging

import pytest

from app.modules.ai.service import AnthropicCVExtractionService

from .anthropic_fakes import anthropic_service, failing_client, fake_client

GOOD_REPLY = {
    "score": 72,
    "strengths": ["Sales leadership"],
    "weaknesses": ["No retail"],
    "fit_summary": "A strong fit for the role.",
}


async def _reason(service, **kwargs):
    return await service.generate_fit_reasoning(
        candidate_context="Current title: Sales Manager",
        job_context="About the role: Head of Sales",
        model="m",
        **kwargs,
    )


@pytest.mark.asyncio
async def test_a_good_reply_is_a_score_with_its_cost():
    service = anthropic_service(fake_client(GOOD_REPLY, input_tokens=400, output_tokens=150))

    result = await _reason(service)

    assert not result.failed
    assert (result.score, result.fit_summary) == (72, "A strong fit for the role.")
    assert result.strengths == ["Sales leadership"] and result.weaknesses == ["No retail"]
    assert (result.input_tokens, result.output_tokens, result.model) == (400, 150, "m")


@pytest.mark.asyncio
async def test_a_genuine_score_of_zero_is_not_a_failure():
    reply = {**GOOD_REPLY, "score": 0, "fit_summary": "Nothing here relates to the role."}

    result = await _reason(anthropic_service(fake_client(reply)))

    assert not result.failed
    assert result.score == 0


@pytest.mark.asyncio
async def test_a_score_outside_0_to_100_is_clamped_not_failed():
    result = await _reason(anthropic_service(fake_client({**GOOD_REPLY, "score": 140})))

    assert not result.failed
    assert result.score == 100


@pytest.mark.asyncio
async def test_a_score_sent_as_a_number_in_text_is_accepted():
    result = await _reason(anthropic_service(fake_client({**GOOD_REPLY, "score": "64"})))

    assert not result.failed
    assert result.score == 64


@pytest.mark.asyncio
async def test_an_api_error_is_a_failure_with_no_cost():
    result = await _reason(anthropic_service(failing_client(RuntimeError("API down"))))

    assert result.failed
    assert (result.input_tokens, result.output_tokens) == (0, 0)


@pytest.mark.asyncio
async def test_a_reply_cut_off_at_the_token_limit_is_a_failure_and_is_billed(caplog):
    service = anthropic_service(
        fake_client(
            '{"score": 72, "strengths": ["Sales lead',
            stop_reason="max_tokens",
            input_tokens=500,
            output_tokens=2048,
        )
    )

    with caplog.at_level(logging.ERROR):
        result = await _reason(service)

    assert result.failed
    assert (result.input_tokens, result.output_tokens) == (500, 2048)
    assert "max_tokens" in caplog.text  # the reason is in the log


@pytest.mark.asyncio
async def test_a_complete_looking_reply_is_still_a_failure_if_it_hit_the_limit():
    """Even if the cut happens to land on valid JSON, the reply is not trusted."""
    service = anthropic_service(fake_client(GOOD_REPLY, stop_reason="max_tokens"))

    assert (await _reason(service)).failed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "this is not json at all {{{{",
        "",
        "[1, 2, 3]",
        json.dumps({"strengths": ["x"], "fit_summary": "no score here"}),
        json.dumps({"score": None, "fit_summary": "x"}),
        json.dumps({"score": "high", "fit_summary": "x"}),
    ],
)
async def test_a_reply_with_no_usable_score_is_a_failure_not_a_zero(text):
    result = await _reason(anthropic_service(fake_client(text)))

    assert result.failed


@pytest.mark.asyncio
async def test_the_token_cap_is_large_enough_for_a_long_answer():
    client = fake_client(GOOD_REPLY)

    await _reason(anthropic_service(client))

    assert client.messages.create.await_args.kwargs["max_tokens"] == 2048


@pytest.mark.asyncio
async def test_a_failure_does_not_write_the_candidates_text_into_the_log(caplog):
    """The old failure log included the first 300 characters of the candidate's CV
    and of the job: personal data that nothing needs in a log file."""
    service = anthropic_service(failing_client(RuntimeError("API down")))

    with caplog.at_level(logging.ERROR):
        await service.generate_fit_reasoning(
            candidate_context="SECRET-CANDIDATE-TEXT",
            job_context="SECRET-JOB-TEXT",
            model="m",
        )

    assert "API down" in caplog.text
    assert "SECRET-CANDIDATE-TEXT" not in caplog.text
    assert "SECRET-JOB-TEXT" not in caplog.text


def test_the_other_ai_services_never_report_a_failure():
    """Keyword and mock services have nothing to fail at; their results default to
    not failed, so the tasks' failure branch is only about real model calls."""
    from app.modules.ai.schema import FitReasoningResult

    assert FitReasoningResult().failed is False
    assert hasattr(AnthropicCVExtractionService, "generate_fit_reasoning")
