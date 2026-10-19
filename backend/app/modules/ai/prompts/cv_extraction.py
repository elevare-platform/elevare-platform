"""Claude prompts and schema for structured CV data extraction."""

import json

CV_EXTRACTION_SYSTEM_PROMPT = """
You are a CV parsing engine.

Extract structured information from a CV.

Rules:

1. If a single fact is missing, return null for it. If a whole list (skills, work
   history, education) has nothing in it, return an empty list.
2. Never hallucinate.
3. Never invent employers, skills, education, certifications, locations or dates.
4. Use only information explicitly supported by the CV.
5. Self-report confidence (high, medium or low) for each extracted section.

6. Nigerian-specific handling:
    - NYSC (National Youth Service Corps) is post-graduate mandatory national service — treat as work experience, not education.
    - OND and HND are valid Nigerian qualifications — treat as formal education equivalent to diploma/associate degree.
    - "Polytechnic" institutions are valid — do not discard them.
    - Nigerian phone numbers start with +234 or 0 followed by 7, 8, or 9.

7. If the CV text itself is too short, garbled, or unreadable to extract meaningful
    information, return empty lists for skills, work_history and education, null for
    every other field, and "low" for every confidence value.
    Do not attempt to invent content.

8. CVs use many different headings, or none ("Career Summary", "Employment Record",
    "Professional Experience & Achievements", and so on). Find work history, education
    and skills by what the text says, wherever it appears, not by its heading.
    If the text describes jobs the person held, work_history must not be empty.

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
"""

CV_EXTRACTION_USER_PROMPT = """
Already extracted fields:

{already_extracted}

Extract only missing information.

CV TEXT:
{full_text}
"""

# The shape of the answer is no longer described in the prompt: it is enforced by
# the API from CVExtractionOutput (ai/schema.py). The old example schema also held
# one all-null work-history entry, which models copied into real answers.

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


def build_user_prompt(already_extracted: dict, full_text: str) -> str:
    """Build the user-turn prompt for CV extraction with already-extracted context.

    The model reads the whole CV and finds the work history, education and skills
    itself; the header-matched sections are no longer sent (they only repeated the
    same text, and were empty for a CV with unusual headings).
    """
    return CV_EXTRACTION_USER_PROMPT.format(
        already_extracted=json.dumps(already_extracted, indent=2),
        full_text=limit_full_text(full_text or ""),
    )
