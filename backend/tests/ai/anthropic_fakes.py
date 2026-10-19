"""A fake Anthropic client for tests: it returns a realistic reply (content blocks,
token usage, stop reason) so the real structured-output path runs, with no API call."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

# A complete, valid extraction answer where nothing was found. Every key is
# present because the API enforces the shape; a missing fact is null or [].
NOTHING_FOUND = {
    "skills": [],
    "years_experience": None,
    "current_title": None,
    "profession": None,
    "seniority_level": None,
    "summary": None,
    "work_history": [],
    "education": [],
    "field_confidence": {
        "skills": "low",
        "years_experience": "low",
        "current_title": "low",
        "profession": "low",
        "seniority_level": "low",
        "summary": "low",
        "work_history": "low",
        "education": "low",
    },
}


def extraction(**overrides) -> dict:
    """A valid extraction answer with some fields filled in."""
    return {**NOTHING_FOUND, **overrides}


def fake_client(
    reply: dict | str = NOTHING_FOUND,
    *,
    stop_reason: str = "end_turn",
    input_tokens: int = 10,
    output_tokens: int = 10,
):
    """A client whose ``messages.create`` returns ``reply`` (a dict is sent as JSON,
    a string as it is, to simulate a broken reply)."""
    text = reply if isinstance(reply, str) else json.dumps(reply)
    response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        stop_reason=stop_reason,
    )
    return SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(return_value=response)))


def failing_client(error: Exception):
    """A client whose ``messages.create`` raises ``error`` (the API itself failed)."""
    return SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(side_effect=error)))


def anthropic_service(client):
    """An AnthropicCVExtractionService wired to ``client`` without calling its
    constructor (which would build a real client)."""
    from app.modules.ai.service import AnthropicCVExtractionService

    service = AnthropicCVExtractionService.__new__(AnthropicCVExtractionService)
    service._client = client
    return service
