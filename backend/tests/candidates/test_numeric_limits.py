"""A number too big for its database column is refused with a 422, not a 500.

`expected_salary` (Numeric(10, 2)) had no upper limit in the profile schema, so a large
value passed validation and then failed in the database as a server error. The job salary
limit was a different mismatch: it allowed 12 whole digits for a Numeric(12, 2) column
that holds 10. These tests tie every limit to its column so they cannot drift apart again."""

from decimal import Decimal

import pytest

from app.modules.candidates.models import CandidateProfile
from app.modules.candidates.schema import MAX_EXPECTED_SALARY, UpdateProfileSchema
from app.modules.jobs.models import Job
from app.modules.jobs.schemas import MAX_JOB_SALARY, JobCreateRequest, JobUpdateRequest
from tests.candidates.test_candidate_profile import get_active_token
from tests.jobs.test_jobs_router import job_payload, register_and_promote


def largest_value(column) -> Decimal:
    """The biggest number a Numeric(precision, scale) column can hold."""
    precision, scale = column.type.precision, column.type.scale
    return Decimal(10) ** (precision - scale) - Decimal(1) / (Decimal(10) ** scale)


# --- the limits match the columns -------------------------------------------------------


def test_the_expected_salary_limit_is_exactly_what_the_column_holds():
    assert Decimal(str(MAX_EXPECTED_SALARY)) == largest_value(CandidateProfile.expected_salary.property.columns[0])


def test_the_job_salary_limit_is_exactly_what_the_columns_hold():
    for column in (Job.salary_min, Job.salary_max):
        assert MAX_JOB_SALARY == largest_value(column.property.columns[0])


@pytest.mark.parametrize(
    "field,column",
    [
        ("avatar_url", CandidateProfile.avatar_url),
        ("location", CandidateProfile.location),
        ("expected_currency", CandidateProfile.expect3ed_currency),
        ("linkedin_url", CandidateProfile.linkedin_url),
        ("github_url", CandidateProfile.github_url),
        ("portfolio_url", CandidateProfile.portfolio_url),
    ],
)
def test_each_text_limit_is_exactly_the_length_of_its_column(field, column):
    limit = column.property.columns[0].type.length
    constraints = UpdateProfileSchema.model_fields[field].metadata

    assert [c.max_length for c in constraints if hasattr(c, "max_length")] == [limit]


# --- what the schema accepts and refuses ------------------------------------------------


def test_the_largest_storable_salary_is_accepted_and_one_more_is_not():
    UpdateProfileSchema(expected_salary=MAX_EXPECTED_SALARY)
    with pytest.raises(ValueError):
        UpdateProfileSchema(expected_salary=MAX_EXPECTED_SALARY + 0.01)
    with pytest.raises(ValueError):
        UpdateProfileSchema(expected_salary=1e12)


@pytest.mark.parametrize("field", ["expected_salary", "years_of_experience", "notice_period_days"])
def test_a_negative_number_is_refused(field):
    with pytest.raises(ValueError):
        UpdateProfileSchema(**{field: -1})


def test_a_huge_integer_is_refused_before_it_overflows_the_column():
    with pytest.raises(ValueError):
        UpdateProfileSchema(years_of_experience=99_999_999_999)
    with pytest.raises(ValueError):
        UpdateProfileSchema(notice_period_days=99_999_999_999)


def test_ordinary_profile_values_still_pass():
    UpdateProfileSchema(
        expected_salary=450000,
        expected_currency="NGN",
        years_of_experience=0,
        notice_period_days=30,
        location="Lagos, Nigeria",
    )


def test_job_salaries_between_the_old_and_new_limit_are_refused():
    base = job_payload()
    too_big = float(MAX_JOB_SALARY) + 1
    with pytest.raises(ValueError):
        JobCreateRequest(**{**base, "salary_max": too_big})
    with pytest.raises(ValueError):
        JobUpdateRequest(salary_min=too_big)
    JobCreateRequest(**{**base, "salary_min": 0, "salary_max": MAX_JOB_SALARY})


# --- the symptom, over HTTP -------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_too_big_expected_salary_is_a_422_that_names_the_field(client, db_session):
    token = await get_active_token(client, db_session)

    response = await client.put(
        "/api/v1/candidates/me",
        json={"expected_salary": 1_000_000_000_000},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert [d["field"] for d in body["details"]] == ["expected_salary"]


@pytest.mark.asyncio
async def test_the_largest_expected_salary_is_stored(client, db_session):
    token = await get_active_token(client, db_session)

    response = await client.put(
        "/api/v1/candidates/me",
        json={"expected_salary": MAX_EXPECTED_SALARY},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["expected_salary"] == MAX_EXPECTED_SALARY


@pytest.mark.asyncio
async def test_a_too_long_link_is_a_422_not_a_500(client, db_session):
    token = await get_active_token(client, db_session)

    response = await client.put(
        "/api/v1/candidates/me",
        json={"linkedin_url": "https://example.com/" + "a" * 300},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
    assert response.json()["details"][0]["field"] == "linkedin_url"


@pytest.mark.asyncio
async def test_a_job_salary_over_what_the_column_holds_is_a_422_not_a_500(client, db_session):
    token = await register_and_promote(client, db_session, "EMPLOYER")

    response = await client.post(
        "/api/v1/jobs",
        json=job_payload(salary_min=500000, salary_max=50_000_000_000),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
    assert "salary_max" in [d["field"] for d in response.json()["details"]]
