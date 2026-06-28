
from dataclasses import dataclass
import re


EMAIL_PATTERN = r"""
[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?
"""
PHONE_PATTERNS = [
    r'\+234[\s\-]?[789]\d[\s\-]?\d{4}[\s\-]?\d{4}',  # +234 format
    r'0[789]\d[\s\-]?\d{4}[\s\-]?\d{4}',               # 0XX format
    r'\+[1-9]\d{1,14}',                                  # international E.164
]
LINKEDIN_PATTERN = r'(https?://)?(www\.)?linkedin\.com/in/[^/\s]+'
GITHUB_PATTERN = r'(https?://)?(www\.)?github\.com/[^/\s]+'
URL_PATTERN = r'https?://[^\s]+'

DATE_PATTERNS = [
    r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\b',
    r'\b\d{4}\s*[-–]\s*\d{4}\b',
    r'\b\d{2}/\d{4}\b',
    r'\b(?:present|current|till date|to date)\b',
]


@dataclass
class DeterministicExtractionResult:
    email: str | None
    phone: str | None
    linkedin_url: str | None
    github_url: str | None
    website_url: str | None
    raw_dates: list[str]   # all date strings found — used by LLM for context
    field_confidence: dict[str, str]

def _normalize_phone(raw: str) -> str:
    cleaned = re.sub(r"[\s\-]", "", raw)

    if cleaned.startswith("0"):
        return "+234" + cleaned[1:]

    return cleaned


def extract_deterministic(text: str) -> DeterministicExtractionResult:
    # Get email
    email_match = re.search(EMAIL_PATTERN, text, re.VERBOSE)
    email = email_match.group(0) if email_match else None

    phone = None
    # Get phone Number
    for pattern in PHONE_PATTERNS:
        phone_match = re.search(pattern, text)
        if phone_match:
            # Normalize phone
            phone = _normalize_phone(phone_match.group(0))
            break
            
    
    # Get LinkedIn
    linkedin_match = re.search(LINKEDIN_PATTERN, text)
    linkedin_url = linkedin_match.group(0) if linkedin_match else None

    # Get github
    github_match = re.search(GITHUB_PATTERN, text)
    github_url = github_match.group(0) if github_match else None

    # Website — first URL that isn't LinkedIn or GitHub
    website_links = []
    url_matches = re.findall(URL_PATTERN, text)
    for match in url_matches:
        if 'linkedin' in match or 'github' in match:
            continue
        website_links.append(match)
    website_url = website_links[0] if website_links else None

    # Get dates
    raw_dates = []
    for pattern in DATE_PATTERNS:
        raw_dates.extend(re.findall(pattern, text, re.IGNORECASE))

    field_confidence = {
        "email": "high" if email else "not_found",
        "phone": "high" if phone else "not_found",
        "linkedin_url": "high" if linkedin_url else "not_found",
        "github_url": "high" if github_url else "not_found",
        "website_url": "medium" if website_url else "not_found",
    }

    return DeterministicExtractionResult(
        email=email,
        phone=phone,
        linkedin_url=linkedin_url,
        github_url=github_url,
        website_url=website_url,
        raw_dates=raw_dates,
        field_confidence=field_confidence,
    )
