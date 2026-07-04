"""Layer 5 — taxonomy-based skill and degree matching.

Matches CV text against curated lists of skills and degrees.
Also identifies Nigerian professional certifications.
"""
import re
from dataclasses import dataclass

from app.core.cv_pipeline.layer3_sections import DetectedSections
from app.core.taxonomies.degree_taxonomy import DEGREE_TAXONOMY
from app.core.taxonomies.skill_taxonomy import SKILLS_NORMALISATION, SKILLS_TAXONOMY

NIGERIAN_CERTS = {
    'ican', 'acca', 'cfa', 'cima', 'cibn', 'cipm',
    'cipd', 'cisa', 'cism', 'cissp', 'nysc', 'aca', 'fca',
}


@dataclass
class TaxonomyMatchResult:
    """Results of matching CV text against skill and degree taxonomies."""

    matched_skills: list[str]
    matched_degrees: list[str]
    nigerian_certifications: list[str]
    field_confidence: dict[str, str]

def _skill_matches(skill: str, text: str) -> bool:
    """Return True if the skill appears as a whole word in the text."""
    pattern = r'\b' + re.escape(skill) + r'\b'
    return bool(re.search(pattern, text, re.IGNORECASE))

def _normalise_text(text: str) -> str:
    """Apply skill normalisation variants to lowercase text."""
    normalised = text.lower()
    for variant, canonical in SKILLS_NORMALISATION.items():
        pattern = r'\b' + re.escape(variant) + r'\b'
        normalised = re.sub(pattern, canonical, normalised)
    return normalised

def match_taxonomy(sections: DetectedSections) -> TaxonomyMatchResult:
    """Match skills and degrees from section text against the taxonomy lists."""
    # Build skills search text from skills + experience sections
    skills_text = " ".join(filter(None, [sections.skills, sections.experience]))
    normalised_skills_text = _normalise_text(skills_text)

    # Match every skill in taxonomy against normalised text
    matched_skills = [
        skill for skill in SKILLS_TAXONOMY
        if _skill_matches(skill, normalised_skills_text)
    ]

    # Nigerian certs are skills that also apear in NIGERIAN_CERTS
    nigerian_certifications = [
        s for s in matched_skills if s.lower() in NIGERIAN_CERTS
    ]

    # Degree matching against education section
    education_text = sections.education or ""
    matched_degrees = [
        degree for degree in DEGREE_TAXONOMY
        if _skill_matches(degree, education_text)
    ]

    return TaxonomyMatchResult(
        matched_skills=matched_skills,
        matched_degrees=matched_degrees,
        nigerian_certifications=nigerian_certifications,
        field_confidence={
            "skills": "high" if matched_skills else "not_found",
            "degrees": "high" if matched_degrees else "not_found",
            "nigerian_certifications": "high" if nigerian_certifications else "not_found",
        },
    )
