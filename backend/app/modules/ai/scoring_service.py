"""Deterministic scoring for candidate-job fit.
"""

import hashlib

_SENIORITY_ORDER = [
    "JUNIOR",
    "MID",
    "SENIOR",
    "LEAD",
    "EXECUTIVE",
]


# Seniority ladder - used for adjacency scoring.
def compute_deterministic_score(
    candidate_skills: list[str],
    candidate_years_experience: int | None,
    candidate_seniority: str | None,
    job_required_skills: list[str],
    job_seniority_level: str | None,
    job_min_years_experience: int | None = None,
    job_max_years_experience: int | None = None,
) -> int:
    """
    Compute a deterministic match score between a candidate and a job.
    The score is a weighted sum of four components: skills, years_of_experience, seniority, and seniority_plus_years_of_experience.

    Weights:
        - Skills coverage: 50%
        - Experience delta: 30%
        - Seniority match: 20%
    """
    skills_score = _skills_coverage(candidate_skills, job_required_skills)
    experience_score = _experience_score(candidate_years_experience, job_min_years_experience, job_max_years_experience)
    seniority_score = _seniority_score(candidate_seniority, job_seniority_level)

    composite = (
        skills_score * 0.5
        + experience_score * 0.3
        + seniority_score * 0.2
    )

    return max(0, min(100, round(composite)))


# ---------------------------------------------------------------------------
# Component functions
# ---------------------------------------------------------------------------
def _skills_coverage(candidate_skills: list[str], required_skills: list[str]) -> float:
    """Fraction of required skills the candidate has, scaled to 0–100.

    Case-insensitive. Returns 100 if no required skills are specified
    (no requirement means no penalty).
    """
    if not required_skills:
        return 100.0
    
    candidate_lower = {s.lower() for s in candidate_skills}

    matched = sum(1 for s in required_skills if s.lower() in candidate_lower)

    return matched / len(required_skills) * 100

def _experience_score(
    candidate_years: int | None,
    job_min_years: int | None = None,
    job_max_years: int | None = None,
) -> float:
    """Score based on how close the candidate's experience is to the job's range.

    - Inside the range: 100
    - Outside by 1–2 years: 60
    - Outside by 3+ years: 20
    - Either side unknown: 50 (neutral — don't penalise missing data)
    """
    if candidate_years is None or (job_min_years is None and job_max_years is None):
        return 50.0  # Neutral when data is missing
    
    min_years = job_min_years or 0
    max_years = job_max_years or float("inf")

    if min_years <= candidate_years <= max_years:
        return 100.0
    
    # How far outside the range?
    delta = (
        min_years - candidate_years
        if candidate_years < min_years
        else candidate_years - max_years
    )

    if delta <= 2:
        return 60.0
    
    return 20.0

def _seniority_score(candidate_seniority: str | None, job_seniority: str | None) -> float:
    """
    Score based on seniority level match.

    - Exact match: 100
    -  Adjacent level (e.g. MID-SENIOR): 60
    - Distant (2+ levels apart): 0
    - Either unknown: 50 (neutral)
    """
    if not candidate_seniority or not job_seniority:
        return 50.0  # neutral data when data is missing
    

    c = candidate_seniority.upper().strip()
    j = job_seniority.upper().strip()

    if c not in _SENIORITY_ORDER or j not in _SENIORITY_ORDER:
        return 50.0  # unrecognized value - neutral
    
    distance = abs(_SENIORITY_ORDER.index(c) - _SENIORITY_ORDER.index(j))

    if distance == 0:
        return 100.0  # exact match
    elif distance == 1:
        return 60.0  # adjacent level
    else:
        return 0.0  # distant (2+ levels)


def hash_job_scoring_inputs(
    description: str,
    required_skills: list[str] | None,
    seniority_level: str | None,
) -> str:
    """SHA-256 of the job fields that affect scoring.

    Pass raw field values, not the ORM object, so this stays testable
    without a database session.
    """
    payload = f"{description}|{sorted(required_skills or [])}|{seniority_level or ''}"

    return hashlib.sha256(payload.encode()).hexdigest()


def hash_cv_scoring_inputs(
    parsed_data: dict
) -> str:
    """SHA-256 of CV fields that affect scoring."""
    payload = (
        f"{sorted(parsed_data.get('skills') or [])}|"
        f"{parsed_data.get('years_experience')}|"
        f"{parsed_data.get('seniority_level')}"
    )
    return hashlib.sha256(payload.encode()).hexdigest()

    