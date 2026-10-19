"""usability: what "nothing was read from this CV" means, for a fresh parse and for
rows saved before the `usable` field existed."""

import pytest

from app.core.cv_pipeline.usability import (
    UNREADABLE_REASON,
    education_entry_is_empty,
    has_usable_content,
    parsed_data_is_usable,
    work_entry_is_empty,
)

NULL_JOB = {
    "company": None,
    "title": None,
    "start_date": None,
    "end_date": None,
    "description": None,
    "is_current": False,
}


@pytest.mark.parametrize(
    "entry",
    [
        NULL_JOB,
        {**NULL_JOB, "company": "", "title": "   "},
        {**NULL_JOB, "start_date": "2015", "duration_months": 24},
        {},
    ],
)
def test_a_job_with_no_title_company_or_description_is_empty(entry):
    assert work_entry_is_empty(entry) is True


@pytest.mark.parametrize("field", ["company", "title", "description"])
def test_any_one_of_title_company_description_makes_a_job_real(field):
    assert work_entry_is_empty({**NULL_JOB, field: "Something"}) is False


def test_education_with_only_a_year_is_empty_but_a_school_alone_is_not():
    assert education_entry_is_empty({"graduation_year": 2012}) is True
    assert education_entry_is_empty({"institution": "UNILAG"}) is False
    assert education_entry_is_empty({"degree": "BSc"}) is False


def test_content_is_usable_with_a_job_an_education_or_a_skill():
    assert has_usable_content([{"title": "x"}], [], []) is True
    assert has_usable_content([], [{"degree": "BSc"}], []) is True
    assert has_usable_content([], [], ["Excel"]) is True


def test_nothing_or_blank_skills_is_not_usable():
    assert has_usable_content([], [], []) is False
    assert has_usable_content([], [], ["", "  "]) is False


def test_the_reason_names_what_was_missing():
    assert "work history, education or skills" in UNREADABLE_REASON


# --- rows saved before the `usable` field existed ----------------------------------


def test_the_old_all_null_profile_reads_as_unusable():
    """Exactly the row found in production (profile 1663ca3d…): one all-null job and
    no skills."""
    old_row = {"work_history": [NULL_JOB], "education": [], "skills": []}

    assert parsed_data_is_usable(old_row) is False


def test_an_old_row_with_a_real_job_reads_as_usable():
    old_row = {"work_history": [{**NULL_JOB, "title": "Sales Manager"}], "skills": []}

    assert parsed_data_is_usable(old_row) is True


def test_an_old_row_with_only_skills_reads_as_usable():
    assert parsed_data_is_usable({"work_history": [NULL_JOB], "skills": ["Excel"]}) is True


@pytest.mark.parametrize("parsed_data", [None, {}, {"work_history": None, "skills": None}])
def test_missing_parsed_data_is_unusable(parsed_data):
    assert parsed_data_is_usable(parsed_data) is False
