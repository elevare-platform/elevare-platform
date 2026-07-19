"""Claude prompts for AI-assisted job description writing."""

from app.modules.ai.enums import JobDescriptionField, JobDescriptionMode

JOB_DESCRIPTION_SYSTEM_PROMPT = """You are an expert HR copywriter helping employers write clear, compelling, and inclusive job descriptions.

Rules:
1. Return ONLY the requested text — no preamble, no labels, no markdown, no code fences.
2. Write in plain prose. Use bullet points only for key_responsibilities and requirements fields.
3. Be specific and concrete. Avoid filler phrases like "fast-paced environment" or "rock star".
4. Use inclusive, bias-free language. Avoid gendered pronouns and unnecessarily exclusive credentials.
5. Match the seniority and industry context provided.
6. Never hallucinate company details not supplied in the context.
7. Keep output proportionate to the field: about_the_role (2-4 sentences), key_responsibilities (4-8 bullet points), requirements (4-8 bullet points).
"""

_MODE_INSTRUCTIONS: dict[JobDescriptionMode, str] = {
    JobDescriptionMode.GENERATE: "Write a new {field} section from scratch using the job context provided.",
    JobDescriptionMode.IMPROVE: "Improve the existing {field} text below. Fix clarity, tone, and specificity. Preserve the intent.",
    JobDescriptionMode.SHORTEN: "Shorten the existing {field} text below. Remove filler, keep every essential point.",
    JobDescriptionMode.EXPAND: "Expand the existing {field} text below. Add relevant detail and context without padding.",
    JobDescriptionMode.REWRITE_PROFESSIONAL: "Rewrite the existing {field} text below in a polished, professional tone.",
    JobDescriptionMode.MORE_INCLUSIVE: "Rewrite the existing {field} text below using inclusive, bias-free language.",
    JobDescriptionMode.IMPROVE_CLARITY: "Rewrite the existing {field} text below for maximum clarity and readability.",
}

_FIELD_LABELS: dict[JobDescriptionField, str] = {
    JobDescriptionField.ABOUT_THE_ROLE: "about_the_role",
    JobDescriptionField.KEY_RESPONSIBILITIES: "key_responsibilities",
    JobDescriptionField.REQUIREMENTS: "requirements",
}

_JOB_DESCRIPTION_USER_PROMPT = """{mode_instruction}

Job Context:
- Title: {title}
- Seniority: {seniority}
- Industry: {industry}
- Company: {company_name}
- Key Skills: {skills}

{current_text_section}Return only the plain text output for the {field_label} field.
"""


def build_job_description_prompt(
    mode: JobDescriptionMode,
    field: JobDescriptionField,
    current_text: str | None,
    job_context,
) -> str:
    """Build the user-turn prompt for the job description writer.

    Args:
        mode: The operation mode (GENERATE, IMPROVE, etc.)
        field: Which field is being written (about_the_role, etc.)
        current_text: Existing text for improvement modes; None for GENERATE.
        job_context: JobContext instance with title, seniority, skills, etc.

    Returns:
        Formatted user prompt string ready to send to Claude.
    """
    field_label = _FIELD_LABELS[field]
    mode_instruction = _MODE_INSTRUCTIONS[mode].format(field=field_label)

    current_text_section = ""
    if current_text and current_text.strip():
        current_text_section = f"Existing text:\n{current_text.strip()}\n\n"

    return _JOB_DESCRIPTION_USER_PROMPT.format(
        mode_instruction=mode_instruction,
        title=job_context.title,
        seniority=job_context.seniority or "not specified",
        industry=job_context.industry or "not specified",
        company_name=job_context.company_name or "not specified",
        skills=", ".join(job_context.skills) if job_context.skills else "not specified",
        current_text_section=current_text_section,
        field_label=field_label,
    )
