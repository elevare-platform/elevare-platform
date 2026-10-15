"""The pipeline must hand the model the full CV text on every extraction call.

PDF reading (layer 1) and spaCy (layer 6) are stubbed; layers 2-5 and 8 run for
real. The fake AI service records what it is called with.
"""

from unittest.mock import AsyncMock

import pytest

from app.core.cv_pipeline import pipeline
from app.core.cv_pipeline.layer1_extraction import TextExtractionResult
from app.core.cv_pipeline.layer6_nlp import NLPExtractionResult
from app.core.cv_pipeline.layer7_llm import LLMExtractionResult

# "Career Summary" is not a heading the section matcher knows, so the work
# history lands in `unclassified` and the experience section comes out empty.
CV_TEXT = (
    "Amaka Obi\n"
    "amaka@example.com\n"
    "Career Summary\n"
    "Regional Sales Manager at Unilever Nigeria, 2015 to 2022.\n"
    "Grew distributor network from 12 to 40 partners.\n"
)


@pytest.fixture(autouse=True)
def stub_slow_layers(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "extract_text_from_pdf",
        lambda pdf_bytes: TextExtractionResult(
            success=True,
            text=CV_TEXT,
            page_count=1,
            is_scanned=False,
            ocr_used=False,
            method_used="pdfplumber",
            error=None,
        ),
    )
    monkeypatch.setattr(
        pipeline,
        "extract_nlp",
        lambda text, sections, nlp: NLPExtractionResult(None, [], [], {}),
    )


def make_ai_service(*results: LLMExtractionResult) -> AsyncMock:
    ai_service = AsyncMock()
    ai_service.extract_cv_data = AsyncMock(side_effect=list(results))
    return ai_service


@pytest.mark.asyncio
async def test_first_call_receives_full_text_when_experience_section_is_empty(
    monkeypatch,
):
    monkeypatch.setattr(pipeline.settings, "ai_tiering_enabled", False)
    ai_service = make_ai_service(LLMExtractionResult())

    await pipeline.run_extraction_pipeline(b"%PDF", nlp=None, ai_service=ai_service)

    sections = ai_service.extract_cv_data.await_args.args[0]
    assert sections.experience is None
    assert (
        "Regional Sales Manager at Unilever Nigeria"
        in ai_service.extract_cv_data.await_args.kwargs["full_text"]
    )


@pytest.mark.asyncio
async def test_escalation_call_also_receives_full_text(monkeypatch):
    monkeypatch.setattr(pipeline.settings, "ai_tiering_enabled", True)
    # An empty low-confidence result makes the pipeline escalate to the deep model.
    ai_service = make_ai_service(LLMExtractionResult(), LLMExtractionResult())

    await pipeline.run_extraction_pipeline(b"%PDF", nlp=None, ai_service=ai_service)

    calls = ai_service.extract_cv_data.await_args_list
    assert len(calls) == 2
    for call in calls:
        assert "Regional Sales Manager at Unilever Nigeria" in call.kwargs["full_text"]
