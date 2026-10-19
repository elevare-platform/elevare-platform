"""Whether a parsed CV holds anything to judge a candidate on.

A CV that could not be read used to be saved as an ordinary completed parse: one
all-null work-history entry, no skills. Nothing downstream could tell it from a real
CV, so it was scored (as 0) like one. This module is the single place that decides
what "nothing was read" means, for a fresh parse and for rows saved earlier.
"""

UNREADABLE_REASON = (
    "Could not read this CV: no work history, education or skills were found"
)


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def work_entry_is_empty(entry: dict) -> bool:
    """A job with no title, no company and no description tells us nothing: it is
    the all-null placeholder a model returns when it found no job. Dates alone do
    not make a job."""
    return all(_blank(entry.get(key)) for key in ("title", "company", "description"))


def education_entry_is_empty(entry: dict) -> bool:
    """An education entry with no institution, degree or field tells us nothing (a
    graduation year alone is not an education)."""
    return all(_blank(entry.get(key)) for key in ("institution", "degree", "field"))


def has_usable_content(work_history, education, skills) -> bool:
    """Whether there is at least one job, one education entry or one skill.

    The lists must already have their empty entries removed. Education counts, so a
    fresh graduate whose CV lists only a degree is readable, not "unreadable".
    """
    return bool(work_history or education or [s for s in skills if not _blank(s)])


def parsed_data_is_usable(parsed_data: dict | None) -> bool:
    """Whether a stored parse (``ParsedCVSubmission.parsed_data``) is usable.

    Works on rows saved before the ``usable`` field existed, by reading the content
    itself: empty placeholder entries are ignored, so the old all-null profile reads
    as unusable.
    """
    if not parsed_data:
        return False
    work_history = [
        entry
        for entry in parsed_data.get("work_history") or []
        if not work_entry_is_empty(entry)
    ]
    education = [
        entry
        for entry in parsed_data.get("education") or []
        if not education_entry_is_empty(entry)
    ]
    return has_usable_content(work_history, education, parsed_data.get("skills") or [])
