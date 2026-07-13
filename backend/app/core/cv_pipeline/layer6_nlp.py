"""Layer 6 — NLP-based entity extraction using spaCy.

Extracts full names, organisations, and job titles from CV text using
spaCy's named entity recognition and a custom Matcher for job titles.
"""

from dataclasses import dataclass

from spacy.matcher import Matcher

from app.core.cv_pipeline.layer3_sections import DetectedSections

TITLE_PATTERNS = [
    [
        {
            "LOWER": {
                "IN": [
                    "senior",
                    "junior",
                    "lead",
                    "head",
                    "chief",
                    "principal",
                    "staff",
                ]
            }
        },
        {"POS": "NOUN", "OP": "?"},
        {"POS": "NOUN"},
    ],
    [
        {"LOWER": {"IN": ["software", "data", "product", "project", "finance", "hr"]}},
        {"POS": "NOUN"},
    ],
]


@dataclass
class NLPExtractionResult:
    """Results of NLP entity extraction from CV text."""

    full_name: str | None
    organisations: list[str]
    job_titles: list[str]
    field_confidence: dict[str, str]


def _extract_name(text: str, nlp) -> tuple[str | None, str]:
    """Extract the candidate's full name from the first 20 lines of the CV."""
    lines = text.splitlines()
    first_20 = "\n".join(lines[:20])

    doc = nlp(first_20)

    for ent in doc.ents:
        if ent.label_ == "PERSON":
            # Figure out which line the name appeared on
            char_position = ent.start_char
            line_number = first_20[:char_position].count(
                "\n"
            )  # Counts how many new line the name appear before the point where it is found

            confidence = "high" if line_number < 5 else "medium"
            return ent.text, confidence

    return None, "not_found"


def _extract_organisations(experience_text: str, nlp) -> list[str]:
    """Extract organisation names from the experience section using NER."""
    if not experience_text:
        return []

    doc = nlp(experience_text)

    return list({ent.text for ent in doc.ents if ent.label_ == "ORG"})


def _extract_job_titles(experience_text: str, nlp) -> list[str]:
    """Extract job titles from the experience section using a spaCy Matcher."""
    if not experience_text:
        return []

    matcher = Matcher(nlp.vocab)
    matcher.add("JOB_TITLE", TITLE_PATTERNS)

    doc = nlp(experience_text)
    matches = matcher(doc)

    titles = list({doc[start:end].text for _, start, end in matches})

    return titles


def extract_nlp(text: str, sections: DetectedSections, nlp) -> NLPExtractionResult:
    """Run NLP extraction on CV text and sections, returning entities."""
    full_name, name_confidence = _extract_name(text, nlp)
    organisations = _extract_organisations(sections.experience or "", nlp)
    job_titles = _extract_job_titles(sections.experience or "", nlp)

    return NLPExtractionResult(
        full_name=full_name,
        organisations=organisations,
        job_titles=job_titles,
        field_confidence={
            "full_name": name_confidence,
            "organisations": "medium" if organisations else "not_found",
            "job_titles": "medium" if job_titles else "not_found",
        },
    )
