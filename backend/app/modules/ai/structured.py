"""One typed call: ask the model for a Pydantic model and get that model back.

The reply shape is sent to the API as a JSON schema, so the model cannot return a
code fence, a missing key or a stray sentence, and nothing here parses text by
hand. Every call also reports why it failed (cut off at the token limit, refused,
or not matching the model) together with the token counts, so a caller can log and
retry instead of treating a failure as an answer.
"""

import logging
from dataclasses import dataclass
from functools import cache
from typing import Generic, TypeVar

from anthropic import transform_schema
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


@dataclass
class StructuredResult(Generic[T]):
    """What came back from one structured call.

    ``parsed`` is the validated answer, or None when the call produced no usable
    one: then ``error`` says why. ``stop_reason`` and the token counts are filled
    either way, because a failed call still cost money and its reason is what
    tells a truncation from a refusal.
    """

    parsed: T | None
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.parsed is not None


def _drop_annotation_titles(node):
    """Remove the ``"title": "Skills"`` labels Pydantic puts on every property.

    They tell the model nothing the field name does not, and the schema is billed
    as input tokens on every call. Only a title that is a string is a label: a
    property that is itself called "title" (a job title) holds an object and stays.
    """
    if isinstance(node, dict):
        return {
            key: _drop_annotation_titles(value)
            for key, value in node.items()
            if not (key == "title" and isinstance(value, str))
        }
    if isinstance(node, list):
        return [_drop_annotation_titles(item) for item in node]
    return node


def _collapse_nullable(node):
    """Write ``anyOf: [{type: X}, {type: null}]`` as ``type: [X, null]``: the same
    meaning in a fraction of the tokens, and every nullable field has one."""
    if isinstance(node, dict):
        options = node.get("anyOf")
        if isinstance(options, list) and len(options) == 2:
            first, second = options
            if second == {"type": "null"} and list(first) == ["type"]:
                rest = {key: value for key, value in node.items() if key != "anyOf"}
                return {"type": [first["type"], "null"], **_collapse_nullable(rest)}
        return {key: _collapse_nullable(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_collapse_nullable(item) for item in node]
    return node


@cache
def _schema_for(output_type: type[BaseModel]) -> dict:
    """The API-ready JSON schema for a model (closed objects, supported keywords
    only), without the parts that only cost tokens. Built once per model class.

    The schema is sent, and billed, with every request; for the CV extraction
    model this trimming saves about a fifth of the request."""
    return _collapse_nullable(_drop_annotation_titles(transform_schema(output_type)))


async def call_structured(
    client,
    *,
    model: str,
    max_tokens: int,
    system: str,
    user: str,
    output_type: type[T],
) -> StructuredResult[T]:
    """Ask ``model`` for an ``output_type`` and return it validated.

    An error from the API itself (network, authentication, rate limit) is raised
    as it is; a reply that arrived but is unusable comes back as a result with
    ``parsed=None`` and the reason in ``error``.
    """
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": _schema_for(output_type)}},
    )
    result: StructuredResult[T] = StructuredResult(
        parsed=None,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        stop_reason=response.stop_reason,
    )

    # A reply cut off at the limit is incomplete JSON; a refusal has no answer.
    # Neither is parsed: the reason is what the caller needs.
    if response.stop_reason == "max_tokens":
        result.error = f"reply cut off at max_tokens ({max_tokens})"
        return result
    if response.stop_reason == "refusal":
        result.error = "the model refused to answer"
        return result

    text = next((block.text for block in response.content if block.type == "text"), "")
    try:
        result.parsed = output_type.model_validate_json(text)
    except ValidationError as exc:
        result.error = f"reply does not match {output_type.__name__}: {exc.error_count()} problem(s)"
        logger.error(
            "Structured reply did not validate",
            extra={"output_type": output_type.__name__, "raw": text[:500]},
        )
    return result
