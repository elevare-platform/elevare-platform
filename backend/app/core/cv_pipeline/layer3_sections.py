"""Layer 3 — section detection for CV text.

Identifies common CV sections (summary, experience, education, skills,
certifications, projects, references) by matching known header strings.
Returns a DetectedSections dataclass with each section's text content.
"""

from dataclasses import dataclass

SECTION_HEADERS = {
    "summary": [
        "summary",
        "profile",
        "objective",
        "about me",
        "professional summary",
        "career objective",
        "personal statement",
        "executive summary",
    ],
    "experience": [
        "experience",
        "work experience",
        "work history",
        "employment",
        "employment history",
        "career history",
        "professional experience",
        "work background",
        "professional background",
    ],
    "education": [
        "education",
        "academic background",
        "academic history",
        "qualifications",
        "educational background",
        "training",
        "academic qualifications",
    ],
    "skills": [
        "skills",
        "technical skills",
        "core competencies",
        "competencies",
        "key skills",
        "expertise",
        "areas of expertise",
        "proficiencies",
        "tools",
        "technologies",
    ],
    "certifications": [
        "certifications",
        "certificates",
        "professional certifications",
        "licenses",
        "accreditations",
        "professional development",
    ],
    "projects": [
        "projects",
        "portfolio",
        "key projects",
        "notable projects",
    ],
    "references": [
        "references",
        "referees",
    ],
}


@dataclass
class DetectedSections:
    """Text content for each detected CV section."""

    summary: str | None
    experience: str | None
    education: str | None
    skills: str | None
    certifications: str | None
    projects: str | None
    references: str | None
    unclassified: str  # everything not matched to a section


def _normalize_header(line: str) -> str:
    """Normalise a potential section header line for matching."""
    return " ".join(line.strip().lower().rstrip(":").split())


def detect_sections(text: str) -> DetectedSections:
    """Parse CV text into labelled sections based on known header strings.

    Lines matching a known section header switch the current section context.
    Lines before any header land in ``unclassified``.
    """
    section_buffers: dict[str, list[str]] = {
        "summary": [],
        "experience": [],
        "education": [],
        "skills": [],
        "certifications": [],
        "projects": [],
        "references": [],
    }

    unclassified: list[str] = []

    current_section: str | None = None

    for line in text.splitlines():
        normalized = _normalize_header(line)

        matched_section = None

        for section_name, headers in SECTION_HEADERS.items():
            if normalized in headers:
                matched_section = section_name
                break

        if matched_section:
            current_section = matched_section
            continue

        if current_section is None:
            unclassified.append(line)
        else:
            section_buffers[current_section].append(line)

    return DetectedSections(
        summary="\n".join(section_buffers["summary"]).strip() or None,
        experience="\n".join(section_buffers["experience"]).strip() or None,
        education="\n".join(section_buffers["education"]).strip() or None,
        skills="\n".join(section_buffers["skills"]).strip() or None,
        certifications="\n".join(section_buffers["certifications"]).strip() or None,
        projects="\n".join(section_buffers["projects"]).strip() or None,
        references="\n".join(section_buffers["references"]).strip() or None,
        unclassified="\n".join(unclassified).strip(),
    )
