"""Claude prompts and schema for structured CV data extraction."""

import json

CV_EXTRACTION_SYSTEM_PROMPT = """
You are a CV parsing engine.

Extract structured information from a CV.

Rules:

1. Return ONLY valid JSON.
2. No markdown.
3. No explanations.
4. No code fences.
5. If information is missing, return null.
6. Never hallucinate.
7. Never invent employers, skills, education, certifications, locations or dates.
8. Use only information explicitly supported by the CV.
9. Self-report confidence for each extracted section.
10. Confidence values must be: high, medium, or low.

11. Nigerian-specific handling:
    - NYSC (National Youth Service Corps) is post-graduate mandatory national service — treat as work experience, not education.
    - OND and HND are valid Nigerian qualifications — treat as formal education equivalent to diploma/associate degree.
    - "Polytechnic" institutions are valid — do not discard them.
    - Nigerian phone numbers start with +234 or 0 followed by 7, 8, or 9.

12. If the CV text is too short, garbled, or unreadable to extract meaningful information,
    return the schema with all fields null and all confidence values set to "low".
    Do not attempt to invent content.

Fields already extracted by deterministic and NLP layers will be provided.
Do not repeat those fields. Focus only on information not already extracted.

For work history:
- Preserve company names exactly.
- Preserve job titles exactly.
- Use null for unknown dates.
- If current role, end_date must be null and is_current must be true.

For education:
- Preserve institution names exactly.
- Graduation year must be an integer or null.
- qualification_type must match a known degree type (e.g. bsc, hnd, msc, phd) or null.

For skills:
- Return only actual skills.
- No sentences.
- Maximum 50 skills.

For summary:
- Maximum 3 sentences.
- Must be supported by the CV.
- Write in plain, natural prose. No em dashes or en dashes; use commas or periods instead.

For profession:
- Return the broad occupational field (e.g. "Healthcare", "Finance", "Software Engineering", "Legal", "Marketing", "Engineering", "Education", "Hospitality").
- One or two words maximum.
- Must be inferred from job titles and work history, not from a self-description.
- Return null if unclear.


For seniority_level, only return one of: junior, mid, senior, lead, executive.
Otherwise return null.

Return JSON matching the supplied schema exactly.
"""

CV_EXTRACTION_USER_PROMPT = """
Already extracted fields:

{already_extracted}

Extract only missing information.

EXPERIENCE SECTION:
{experience_text}

EDUCATION SECTION:
{education_text}

The two sections above were cut out automatically and may be empty or
incomplete. The full CV text below is the source of truth.

FULL CV TEXT:
{full_text}

Return JSON using this schema:

{schema}
"""

CV_EXTRACTION_SCHEMA = {
    "skills": [],
    "years_experience": None,
    "current_title": None,
    "profession": None,
    "seniority_level": None,
    "summary": None,
    "work_history": [
        {
            "company": None,
            "title": None,
            "start_date": None,
            "end_date": None,
            "duration_months": None,
            "description": None,
            "is_current": False,
        }
    ],
    "education": [
        {
            "institution": None,
            "degree": None,
            "field": None,
            "graduation_year": None,
            "qualification_type": None,
        }
    ],
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


# About 7,500 tokens (roughly 4 characters per token). An ordinary 2-4 page CV is
# 6,000-12,000 characters and is never touched; the cap only stops an abnormal
# upload (a 60-page portfolio, pages of OCR junk) from making one call expensive.
MAX_FULL_TEXT_CHARS = 30_000
TRUNCATION_MARKER = "\n[CV text truncated]"


def limit_full_text(text: str) -> str:
    """Keep the start of an over-long CV (contact details and recent roles come
    first) and mark the cut so the model does not read it as a finished CV."""
    if len(text) <= MAX_FULL_TEXT_CHARS:
        return text
    return text[:MAX_FULL_TEXT_CHARS] + TRUNCATION_MARKER


def build_user_prompt(
    already_extracted: dict,
    experience_text: str,
    education_text: str,
    full_text: str = "",
) -> str:
    """Build the user-turn prompt for CV extraction with already-extracted context."""
    return CV_EXTRACTION_USER_PROMPT.format(
        already_extracted=json.dumps(already_extracted, indent=2),
        experience_text=experience_text or "",
        education_text=education_text or "",
        full_text=limit_full_text(full_text or ""),
        schema=json.dumps(CV_EXTRACTION_SCHEMA, indent=2),
    )
