"""The template library (docs/08_DECISIONS.md, item 46): the built-in role sets, the sets a company
saves (owned by the company, usable by anyone in it), and copying another job of the company."""

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.modules.auth.jwt_handler import create_token_pair
from app.modules.interviews import template_library
from app.modules.interviews.models import (
    InterviewQuestionTemplate,
    JobInterviewQuestion,
    JobScoringProfile,
)
from app.modules.interviews.scoring_profile import DEFAULT_BANDS
from tests.conftest import make_employer, make_job, make_organization_for, make_user

BASE = "/api/v1/interviews"
COMPETENCIES = [
    {"name": "Strategy", "weight": 60, "key": True},
    {"name": "Execution", "weight": 40, "key": False},
]


@pytest.fixture(autouse=True)
def thirty_minute_interviews(monkeypatch):
    monkeypatch.setattr(settings, "interview_max_duration_minutes", 30)


def headers(user):
    return {"Authorization": f"Bearer {create_token_pair(user.id, user.role)['access_token']}"}


async def company(db_session, name="Acme"):
    """A company: its owner, a teammate who did not save anything, and a job of the owner's."""
    owner = make_employer(first_name="Ada", last_name="Obi")
    db_session.add(owner)
    await db_session.flush()
    organization = await make_organization_for(db_session, owner, company_name=name)
    teammate = make_employer(organization_id=organization.id, first_name="Bola", last_name="Eze")
    db_session.add(teammate)
    job = make_job(owner.id, title=f"{name} Sales Manager")
    db_session.add(job)
    await db_session.flush()
    return owner, teammate, job


def question(text, seconds=120, **over):
    return {"text": text, "time_limit_seconds": seconds, "source": "EMPLOYER", **over}


QUESTIONS = [
    question("Tell us about a launch you led and your own part in it.", 120, competency="Strategy", probes="How big was it?\nWhat did it deliver?"),
    question("How do you decide what to measure each week?", 90, competency="Execution", follow_up_seconds=60),
    question("Build a 90-day plan for three regions and state your assumptions.", 240, is_practical=True),
]


async def give_profile(db_session, job):
    db_session.add(JobScoringProfile(job_id=job.id, competencies=COMPETENCIES, bands=dict(DEFAULT_BANDS), key_min_rating=3))
    await db_session.flush()


async def save(client, user, job, name="Sales set", questions=None, **over):
    body = {"job_id": str(job.id), "name": name, "questions": questions or QUESTIONS, **over}
    return await client.post(f"{BASE}/question-templates", json=body, headers=headers(user))


async def library(client, user, q=None):
    response = await client.get(f"{BASE}/question-templates", params={"q": q} if q else None, headers=headers(user))
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Browsing and searching
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_library_lists_the_three_colton_sets_with_their_questions_and_an_empty_company_tab(client, db_session):
    owner, _t, _job = await company(db_session)

    body = await library(client, owner)

    assert [t["name"] for t in body["built_in"]] == ["National Sales Manager", "Commercial Director", "Senior Marketing Manager"]
    first = body["built_in"][0]
    assert (first["kind"], first["id"], first["question_count"], first["has_practical"]) == ("BUILT_IN", "national_sales_manager", 9, True)
    assert first["has_scoring_profile"] is True and first["can_edit"] is False
    assert first["questions"][0]["text"].startswith("You are preparing to launch Seasonings")
    assert body["company"] == [] and body["can_save"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (None, ["National Sales Manager", "Commercial Director", "Senior Marketing Manager"]),
        ("director", ["Commercial Director", "Senior Marketing Manager"]),  # the Marketing questions mention the Commercial Director
        ("DISTRIBUTOR", ["National Sales Manager", "Commercial Director", "Senior Marketing Manager"]),  # in questions or competencies
        ("artwork", ["Senior Marketing Manager"]),
        ("gross-to-net", ["Commercial Director"]),
        ("colton", ["National Sales Manager", "Commercial Director", "Senior Marketing Manager"]),
        ("zzzz nothing", []),
    ],
)
async def test_searching_matches_names_competencies_and_the_text_of_the_questions(client, db_session, query, expected):
    owner, _t, _job = await company(db_session)

    body = await library(client, owner, query)

    assert [t["name"] for t in body["built_in"]] == expected


@pytest.mark.asyncio
async def test_every_word_of_a_search_must_match(client, db_session):
    owner, _t, _job = await company(db_session)

    assert [t["name"] for t in (await library(client, owner, "artwork distributor"))["built_in"]] == ["Senior Marketing Manager"]
    assert (await library(client, owner, "artwork rocketship"))["built_in"] == []


@pytest.mark.asyncio
async def test_the_library_needs_a_logged_in_employer(client, db_session):
    assert (await client.get(f"{BASE}/question-templates")).status_code == 401


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_set_is_saved_for_the_company_with_everything_it_carries(client, db_session):
    owner, _t, job = await company(db_session)
    await give_profile(db_session, job)

    response = await save(client, owner, job, follow_up_mode="PROBES_ONLY")

    assert response.status_code == 201
    saved = response.json()
    assert (saved["kind"], saved["name"], saved["question_count"], saved["total_seconds"]) == ("COMPANY", "Sales set", 3, 450)
    assert saved["has_scoring_profile"] is True and saved["competencies"] == ["Strategy", "Execution"]
    assert saved["has_practical"] is True and saved["follow_up_mode"] == "PROBES_ONLY"
    assert saved["created_by_name"] == "Ada Obi" and saved["can_edit"] is True
    first = saved["questions"][0]
    assert first["competency"] == "Strategy" and first["probes"] == "How big was it?\nWhat did it deliver?"
    assert saved["questions"][1]["follow_up_seconds"] == 60 and saved["questions"][2]["is_practical"] is True


@pytest.mark.asyncio
async def test_a_saved_set_appears_in_the_company_tab_and_is_found_by_search(client, db_session):
    owner, _t, job = await company(db_session)
    await save(client, owner, job)

    body = await library(client, owner)
    found = await library(client, owner, "launch")
    missing = await library(client, owner, "pizza")

    assert [t["name"] for t in body["company"]] == ["Sales set"]
    assert [t["name"] for t in found["company"]] == ["Sales set"] and missing["company"] == []


@pytest.mark.asyncio
async def test_without_the_profile_the_tags_are_dropped_because_they_mean_nothing_alone(client, db_session):
    owner, _t, job = await company(db_session)
    await give_profile(db_session, job)

    saved = (await save(client, owner, job, include_profile=False)).json()

    assert saved["has_scoring_profile"] is False and saved["competencies"] == []
    assert [q["competency"] for q in saved["questions"]] == [None, None, None]


@pytest.mark.asyncio
async def test_asking_for_the_profile_of_a_job_that_has_none_saves_the_set_without_one(client, db_session):
    owner, _t, job = await company(db_session)

    saved = (await save(client, owner, job)).json()

    assert saved["has_scoring_profile"] is False
    assert [q["competency"] for q in saved["questions"]] == [None, None, None]


@pytest.mark.asyncio
async def test_a_set_that_does_not_fit_this_jobs_time_limit_can_still_be_saved(client, db_session, monkeypatch):
    """Saving is not tied to one job's limit; applying it to a job shows it for shortening."""
    monkeypatch.setattr(settings, "interview_max_duration_minutes", 5)
    owner, _t, job = await company(db_session)

    assert (await save(client, owner, job)).status_code == 201  # 7.5 minutes of answers


@pytest.mark.asyncio
async def test_names_are_tidied_and_one_per_company_whatever_the_case(client, db_session):
    owner, teammate, job = await company(db_session)
    first = (await save(client, owner, job, name="   Sales    set  ")).json()

    clash = await save(client, teammate, job, name="SALES SET")

    assert first["name"] == "Sales set"
    assert clash.status_code == 422 and clash.json()["code"] == "TEMPLATE_NAME_TAKEN"
    assert len((await db_session.execute(select(InterviewQuestionTemplate))).scalars().all()) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "code"), [("", "TEMPLATE_NAME_REQUIRED"), ("   ", "TEMPLATE_NAME_REQUIRED"), ("x" * 121, "TEMPLATE_NAME_TOO_LONG")])
async def test_a_template_needs_a_sensible_name(client, db_session, name, code):
    owner, _t, job = await company(db_session)

    response = await save(client, owner, job, name=name)

    assert response.status_code == 422 and response.json()["code"] == code


@pytest.mark.asyncio
async def test_an_empty_list_or_one_that_breaks_a_rule_is_not_saved(client, db_session):
    owner, _t, job = await company(db_session)
    # An empty list is refused by our own check; the request body itself needs a list.
    empty = await client.post(f"{BASE}/question-templates", json={"job_id": str(job.id), "name": "Empty", "questions": []}, headers=headers(owner))
    bad = await save(client, owner, job, name="Bad", questions=[question("Why?"), question("Two practical one.", is_practical=True), question("Two practical two.", is_practical=True)])

    assert empty.status_code == 422 and empty.json()["code"] == "TEMPLATE_EMPTY"
    assert bad.status_code == 422
    messages = [d["message"] for d in bad.json()["details"]]
    assert "Question 1 is too short to be a question." in messages and "Only one question can be the practical case." in messages
    assert (await db_session.execute(select(InterviewQuestionTemplate))).scalars().all() == []


@pytest.mark.asyncio
async def test_a_company_can_keep_only_so_many_templates(client, db_session, monkeypatch):
    monkeypatch.setattr(template_library, "MAX_TEMPLATES_PER_COMPANY", 2)
    owner, _t, job = await company(db_session)
    await save(client, owner, job, name="One")
    await save(client, owner, job, name="Two")

    third = await save(client, owner, job, name="Three")

    assert third.status_code == 422 and third.json()["code"] == "TEMPLATE_LIMIT"


@pytest.mark.asyncio
async def test_someone_with_no_company_yet_cannot_save_and_is_told_so(client, db_session):
    loner = make_employer()
    db_session.add(loner)
    await db_session.flush()
    job = make_job(loner.id)
    db_session.add(job)
    await db_session.flush()

    response = await save(client, loner, job)

    assert response.status_code == 422 and response.json()["code"] == "COMPANY_REQUIRED"
    assert (await library(client, loner))["can_save"] is False


@pytest.mark.asyncio
async def test_only_someone_who_can_manage_the_job_can_save_its_questions_as_a_template(client, db_session):
    _owner, _t, job = await company(db_session)
    other_owner, _x, _y = await company(db_session, name="Other")

    response = await save(client, other_owner, job)

    assert response.status_code == 403
    assert (await db_session.execute(select(InterviewQuestionTemplate))).scalars().all() == []


# ---------------------------------------------------------------------------
# Whose they are
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_teammate_sees_and_can_use_the_set_but_cannot_change_it(client, db_session):
    owner, teammate, job = await company(db_session)
    saved = (await save(client, owner, job)).json()

    seen = (await library(client, teammate))["company"]
    rename = await client.patch(f"{BASE}/question-templates/{saved['id']}", json={"name": "Mine now"}, headers=headers(teammate))
    delete = await client.delete(f"{BASE}/question-templates/{saved['id']}", headers=headers(teammate))

    assert [t["name"] for t in seen] == ["Sales set"] and seen[0]["can_edit"] is False
    assert rename.status_code == 403 and delete.status_code == 403
    assert len((await db_session.execute(select(InterviewQuestionTemplate))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_the_company_owner_can_change_a_set_a_teammate_saved(client, db_session):
    owner, teammate, job = await company(db_session)
    saved = (await save(client, teammate, job)).json()

    seen = (await library(client, owner))["company"]
    renamed = await client.patch(f"{BASE}/question-templates/{saved['id']}", json={"name": "Owner's name"}, headers=headers(owner))

    assert seen[0]["can_edit"] is True and seen[0]["created_by_name"] == "Bola Eze"
    assert renamed.status_code == 200 and renamed.json()["name"] == "Owner's name"


@pytest.mark.asyncio
async def test_another_company_cannot_see_use_rename_or_delete_a_set(client, db_session):
    owner, _t, job = await company(db_session)
    saved = (await save(client, owner, job)).json()
    stranger, _x, stranger_job = await company(db_session, name="Other")

    seen = (await library(client, stranger))["company"]
    rename = await client.patch(f"{BASE}/question-templates/{saved['id']}", json={"name": "Stolen"}, headers=headers(stranger))
    delete = await client.delete(f"{BASE}/question-templates/{saved['id']}", headers=headers(stranger))
    use = await client.post(
        f"{BASE}/jobs/{stranger_job.id}/questions/from-saved-template", json={"template_id": saved["id"]}, headers=headers(stranger)
    )

    assert seen == []
    assert (rename.status_code, delete.status_code, use.status_code) == (404, 404, 404)
    assert rename.json()["code"] == "TEMPLATE_NOT_FOUND"
    assert len((await db_session.execute(select(InterviewQuestionTemplate))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_renaming_checks_the_name_like_saving_does(client, db_session):
    owner, _t, job = await company(db_session)
    first = (await save(client, owner, job, name="First")).json()
    await save(client, owner, job, name="Second")

    clash = await client.patch(f"{BASE}/question-templates/{first['id']}", json={"name": "second"}, headers=headers(owner))
    blank = await client.patch(f"{BASE}/question-templates/{first['id']}", json={"name": "  "}, headers=headers(owner))
    same = await client.patch(f"{BASE}/question-templates/{first['id']}", json={"name": "FIRST"}, headers=headers(owner))

    assert clash.status_code == 422 and clash.json()["code"] == "TEMPLATE_NAME_TAKEN"
    assert blank.status_code == 422
    assert same.status_code == 200 and same.json()["name"] == "FIRST"  # changing only the case of its own name is fine


@pytest.mark.asyncio
async def test_deleting_a_set_removes_it_and_leaves_jobs_started_from_it_alone(client, db_session):
    owner, _t, job = await company(db_session)
    saved = (await save(client, owner, job)).json()
    target = make_job(owner.id)
    db_session.add(target)
    await db_session.flush()
    await client.post(f"{BASE}/jobs/{target.id}/questions/from-saved-template", json={"template_id": saved["id"]}, headers=headers(owner))

    deleted = await client.delete(f"{BASE}/question-templates/{saved['id']}", headers=headers(owner))

    assert deleted.status_code == 204
    assert (await library(client, owner))["company"] == []
    rows = (await db_session.execute(select(JobInterviewQuestion).where(JobInterviewQuestion.job_id == target.id))).scalars().all()
    assert len(rows) == 3


# ---------------------------------------------------------------------------
# Using a saved set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_saved_set_with_its_profile_is_put_on_another_job_whole(client, db_session):
    owner, teammate, job = await company(db_session)
    await give_profile(db_session, job)
    saved = (await save(client, owner, job, follow_up_mode="NONE")).json()
    target = make_job(owner.id, title="Another role")
    db_session.add(target)
    await db_session.flush()

    response = await client.post(
        f"{BASE}/jobs/{target.id}/questions/from-saved-template", json={"template_id": saved["id"]}, headers=headers(teammate)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["saved"] is True and body["follow_up_mode"] == "NONE"
    assert [q["competency"] for q in body["questions"]] == ["Strategy", "Execution", None]
    assert body["questions"][0]["probes"] == "How big was it?\nWhat did it deliver?" and body["questions"][2]["is_practical"] is True
    assert body["untested_competencies"] == []
    profile = (await db_session.execute(select(JobScoringProfile).where(JobScoringProfile.job_id == target.id))).scalar_one()
    assert [c["name"] for c in profile.competencies] == ["Strategy", "Execution"] and profile.template_code is None


@pytest.mark.asyncio
async def test_a_saved_set_without_a_profile_leaves_the_jobs_own_profile_alone(client, db_session):
    owner, _t, job = await company(db_session)
    saved = (await save(client, owner, job)).json()  # no profile on the job: none saved
    target = make_job(owner.id)
    db_session.add(target)
    await db_session.flush()
    await give_profile(db_session, target)

    response = await client.post(
        f"{BASE}/jobs/{target.id}/questions/from-saved-template", json={"template_id": saved["id"]}, headers=headers(owner)
    )

    assert response.status_code == 200 and response.json()["saved"] is True
    profile = (await db_session.execute(select(JobScoringProfile).where(JobScoringProfile.job_id == target.id))).scalar_one()
    assert [c["name"] for c in profile.competencies] == ["Strategy", "Execution"]


@pytest.mark.asyncio
async def test_a_saved_set_longer_than_the_time_limit_is_shown_for_shortening_not_refused(client, db_session, monkeypatch):
    owner, _t, job = await company(db_session)
    await give_profile(db_session, job)
    saved = (await save(client, owner, job)).json()
    target = make_job(owner.id)
    db_session.add(target)
    await db_session.flush()
    monkeypatch.setattr(settings, "interview_max_duration_minutes", 5)  # 7.5 minutes of answers do not fit

    response = await client.post(
        f"{BASE}/jobs/{target.id}/questions/from-saved-template", json={"template_id": saved["id"]}, headers=headers(owner)
    )

    body = response.json()
    assert response.status_code == 200 and body["saved"] is False and len(body["questions"]) == 3
    assert (await db_session.execute(select(JobInterviewQuestion).where(JobInterviewQuestion.job_id == target.id))).scalars().all() == []
    assert (await db_session.execute(select(JobScoringProfile).where(JobScoringProfile.job_id == target.id))).scalar_one()


@pytest.mark.asyncio
async def test_only_someone_who_can_manage_the_target_job_can_start_it_from_a_set(client, db_session):
    owner, _t, job = await company(db_session)
    saved = (await save(client, owner, job)).json()
    other_owner, _x, other_job = await company(db_session, name="Other")

    response = await client.post(
        f"{BASE}/jobs/{job.id}/questions/from-saved-template", json={"template_id": saved["id"]}, headers=headers(other_owner)
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Copying another job
# ---------------------------------------------------------------------------


async def job_with_questions(client, db_session, owner, title, tagged=True):
    job = make_job(owner.id, title=title)
    db_session.add(job)
    await db_session.flush()
    if tagged:
        await give_profile(db_session, job)
    await client.put(
        f"{BASE}/jobs/{job.id}/questions",
        json={"questions": QUESTIONS if tagged else [{**q, "competency": None} for q in QUESTIONS], "follow_up_mode": "PROBES_ONLY"},
        headers=headers(owner),
    )
    return job


@pytest.mark.asyncio
async def test_the_companys_jobs_with_questions_are_listed_to_copy_from(client, db_session):
    owner, teammate, job = await company(db_session)
    first = await job_with_questions(client, db_session, owner, "Head of Sales")
    await job_with_questions(client, db_session, owner, "Brand Manager")
    quiet = make_job(owner.id, title="No questions yet")
    db_session.add(quiet)
    await db_session.flush()
    stranger, _x, stranger_job = await company(db_session, name="Other")
    await job_with_questions(client, db_session, stranger, "Other company role")

    everything = (await client.get(f"{BASE}/question-templates/jobs", headers=headers(teammate))).json()["items"]
    filtered = (await client.get(f"{BASE}/question-templates/jobs", params={"q": "brand"}, headers=headers(owner))).json()["items"]
    without = (await client.get(f"{BASE}/question-templates/jobs", params={"exclude_job_id": str(first.id)}, headers=headers(owner))).json()["items"]

    assert {item["title"] for item in everything} == {"Head of Sales", "Brand Manager"}
    head = next(item for item in everything if item["title"] == "Head of Sales")
    assert (head["question_count"], head["total_seconds"], head["has_practical"]) == (3, 450, True)
    assert [item["title"] for item in filtered] == ["Brand Manager"]
    assert {item["title"] for item in without} == {"Brand Manager"}


@pytest.mark.asyncio
async def test_a_job_is_copied_with_its_questions_profile_and_follow_up_choice(client, db_session):
    owner, _t, _job = await company(db_session)
    source = await job_with_questions(client, db_session, owner, "Head of Sales")
    target = make_job(owner.id, title="New role")
    db_session.add(target)
    await db_session.flush()

    response = await client.post(f"{BASE}/jobs/{target.id}/questions/from-job", json={"source_job_id": str(source.id)}, headers=headers(owner))

    body = response.json()
    assert response.status_code == 200 and body["saved"] is True and body["follow_up_mode"] == "PROBES_ONLY"
    assert [q["competency"] for q in body["questions"]] == ["Strategy", "Execution", None]
    assert [q["is_practical"] for q in body["questions"]] == [False, False, True]
    profile = (await db_session.execute(select(JobScoringProfile).where(JobScoringProfile.job_id == target.id))).scalar_one()
    assert [c["name"] for c in profile.competencies] == ["Strategy", "Execution"]
    # The source is untouched.
    assert len((await db_session.execute(select(JobInterviewQuestion).where(JobInterviewQuestion.job_id == source.id))).scalars().all()) == 3


@pytest.mark.asyncio
async def test_copying_a_job_that_has_no_profile_leaves_the_tags_out(client, db_session):
    owner, _t, _job = await company(db_session)
    source = await job_with_questions(client, db_session, owner, "Untagged role", tagged=False)
    target = make_job(owner.id)
    db_session.add(target)
    await db_session.flush()

    body = (await client.post(f"{BASE}/jobs/{target.id}/questions/from-job", json={"source_job_id": str(source.id)}, headers=headers(owner))).json()

    assert [q["competency"] for q in body["questions"]] == [None, None, None]


@pytest.mark.asyncio
async def test_a_job_cannot_be_copied_onto_itself_or_from_nothing(client, db_session):
    owner, _t, job = await company(db_session)
    empty = make_job(owner.id)
    db_session.add(empty)
    await db_session.flush()

    itself = await client.post(f"{BASE}/jobs/{job.id}/questions/from-job", json={"source_job_id": str(job.id)}, headers=headers(owner))
    nothing = await client.post(f"{BASE}/jobs/{job.id}/questions/from-job", json={"source_job_id": str(empty.id)}, headers=headers(owner))

    assert itself.status_code == 422 and itself.json()["code"] == "SAME_JOB"
    assert nothing.status_code == 422 and nothing.json()["code"] == "NOTHING_TO_COPY"


@pytest.mark.asyncio
async def test_another_companys_job_cannot_be_copied(client, db_session):
    owner, _t, job = await company(db_session)
    stranger, _x, _y = await company(db_session, name="Other")
    theirs = await job_with_questions(client, db_session, stranger, "Their role")

    response = await client.post(f"{BASE}/jobs/{job.id}/questions/from-job", json={"source_job_id": str(theirs.id)}, headers=headers(owner))

    assert response.status_code == 403
    assert (await db_session.execute(select(JobInterviewQuestion).where(JobInterviewQuestion.job_id == job.id))).scalars().all() == []


@pytest.mark.asyncio
async def test_a_candidate_cannot_use_the_library(client, db_session):
    candidate = make_user(role="CANDIDATE")
    db_session.add(candidate)
    await db_session.flush()

    assert (await client.get(f"{BASE}/question-templates", headers=headers(candidate))).status_code == 403
