"""call_structured: ask the model for a Pydantic model and get it back validated.

The reply shape is sent as a JSON schema, a reply that cannot be used says why
(and still reports its token cost), and a real API error is not swallowed."""

import json
from types import SimpleNamespace
from typing import Literal
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from app.modules.ai.structured import _schema_for, call_structured


class Answer(BaseModel):
    name: str | None
    skills: list[str]


def _client(text="", stop_reason="end_turn", usage=(120, 30)):
    response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=usage[0], output_tokens=usage[1]),
        stop_reason=stop_reason,
    )
    client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(return_value=response)))
    return client


async def _call(client):
    return await call_structured(
        client,
        model="m",
        max_tokens=100,
        system="sys",
        user="usr",
        output_type=Answer,
    )


class Job(BaseModel):
    title: str | None  # a property that is itself called "title"
    company: str | None
    is_current: bool


class Profile(BaseModel):
    jobs: list[Job]
    level: Literal["junior", "senior"] | None


def test_the_schema_drops_label_titles_but_keeps_a_property_called_title():
    schema = _schema_for(Profile)

    # No "title": "Jobs" style labels anywhere ...
    assert '"title": "' not in json.dumps(schema)
    # ... but the job's own "title" property, and that it is required, survive.
    job = schema["$defs"]["Job"]
    assert "title" in job["properties"]
    assert "title" in job["required"]
    assert job["additionalProperties"] is False


def test_a_nullable_field_is_written_as_a_type_array_and_still_means_the_same():
    job = _schema_for(Profile)["$defs"]["Job"]["properties"]

    assert job["title"] == {"type": ["string", "null"]}
    assert job["is_current"] == {"type": "boolean"}
    # An enum that can also be null is left in the longer form (it has more than
    # a type to say).
    assert any(
        option.get("enum") == ["junior", "senior"]
        for option in _schema_for(Profile)["properties"]["level"]["anyOf"]
    )


def test_the_trimmed_schema_accepts_and_rejects_the_same_replies():
    profile = Profile.model_validate_json(
        '{"jobs": [{"title": null, "company": "X", "is_current": false}], "level": null}'
    )

    assert profile.jobs[0].title is None


@pytest.mark.asyncio
async def test_a_valid_reply_comes_back_as_the_model_with_its_cost():
    client = _client('{"name": "Ada", "skills": ["python", "sql"]}')

    result = await _call(client)

    assert result.ok
    assert result.parsed == Answer(name="Ada", skills=["python", "sql"])
    assert (result.input_tokens, result.output_tokens) == (120, 30)
    assert result.stop_reason == "end_turn"
    assert result.error is None


@pytest.mark.asyncio
async def test_a_missing_fact_is_null_and_an_empty_list_not_an_error():
    result = await _call(_client('{"name": null, "skills": []}'))

    assert result.ok
    assert result.parsed == Answer(name=None, skills=[])


@pytest.mark.asyncio
async def test_the_request_carries_the_prompts_and_a_closed_json_schema():
    client = _client('{"name": null, "skills": []}')

    await _call(client)

    kwargs = client.messages.create.await_args.kwargs
    assert (kwargs["model"], kwargs["max_tokens"], kwargs["system"]) == ("m", 100, "sys")
    assert kwargs["messages"] == [{"role": "user", "content": "usr"}]
    output_format = kwargs["output_config"]["format"]
    assert output_format["type"] == "json_schema"
    schema = output_format["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"name", "skills"}


@pytest.mark.asyncio
async def test_a_reply_cut_off_at_the_token_limit_is_a_failure_that_says_so():
    result = await _call(_client('{"name": "Ada", "skills": ["py', stop_reason="max_tokens", usage=(500, 100)))

    assert not result.ok
    assert result.parsed is None
    assert "max_tokens" in result.error
    assert result.stop_reason == "max_tokens"
    # The failed call still cost money; the cost is not lost.
    assert (result.input_tokens, result.output_tokens) == (500, 100)


@pytest.mark.asyncio
async def test_a_refusal_is_a_failure_that_says_so():
    result = await _call(_client("", stop_reason="refusal"))

    assert not result.ok
    assert "refused" in result.error


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    ["", "not json at all", '{"name": "Ada"}', '{"name": "Ada", "skills": "python"}'],
)
async def test_a_reply_that_does_not_match_the_model_is_a_failure(text):
    result = await _call(_client(text))

    assert not result.ok
    assert result.parsed is None
    assert "does not match Answer" in result.error


@pytest.mark.asyncio
async def test_an_error_from_the_api_itself_is_raised_not_swallowed():
    client = SimpleNamespace(
        messages=SimpleNamespace(create=AsyncMock(side_effect=RuntimeError("network down")))
    )

    with pytest.raises(RuntimeError, match="network down"):
        await _call(client)
