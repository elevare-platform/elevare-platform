"""The Colton Group question bank as templates (docs/08_DECISIONS.md, item 41): the data matches
the client's pack and the scoring templates, and applying one sets the role's scoring profile and
questions together, all or nothing."""

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.modules.auth.jwt_handler import create_token_pair
from app.modules.interviews import question_rules as rules
from app.modules.interviews.models import JobInterviewQuestion, JobScoringProfile
from app.modules.interviews.question_templates import (
    QUESTION_TEMPLATES,
    ROLE_CODES,
    template_items,
    template_summaries,
)
from app.modules.interviews.scoring_profile import TEMPLATES as SCORING_TEMPLATES
from tests.conftest import make_employer, make_job, make_organization_for


def _scoring(code):
    return next(template for template in SCORING_TEMPLATES if template["code"] == code)


# ---------------------------------------------------------------------------
# The data
# ---------------------------------------------------------------------------


def test_there_are_the_clients_26_questions_in_three_roles():
    counts = {code: len(QUESTION_TEMPLATES[code]["questions"]) for code in ROLE_CODES}

    assert counts == {"national_sales_manager": 8, "commercial_director": 8, "senior_marketing_manager": 10}
    assert sum(counts.values()) == 26


@pytest.mark.parametrize("code", ROLE_CODES)
def test_every_question_is_tagged_with_a_competency_of_that_roles_scoring_profile(code):
    names = {item["name"] for item in _scoring(code)["competencies"]}

    tags = {question["competency"] for question in QUESTION_TEMPLATES[code]["questions"]}

    assert tags <= names


@pytest.mark.parametrize("code", ROLE_CODES)
def test_every_weighted_competency_of_the_role_has_a_question(code):
    names = {item["name"] for item in _scoring(code)["competencies"]}

    tags = {question["competency"] for question in QUESTION_TEMPLATES[code]["questions"]}

    assert names == tags  # none is left untested, so no score is incomplete for want of a question


@pytest.mark.parametrize("code", ROLE_CODES)
def test_each_list_passes_the_rules_a_saved_list_must_pass(code):
    drafts = [
        rules.QuestionDraft(item["text"], item["time_limit_seconds"], item["probes"])
        for item in template_items(code)
    ]

    assert rules.problems_with(drafts) == []
    # The suggested times leave room for follow-ups inside the 20 minutes.
    assert sum(draft.time_limit_seconds for draft in drafts) <= rules.max_total_seconds() - 120


@pytest.mark.parametrize("code", ROLE_CODES)
def test_questions_and_probes_are_distinct_and_the_probes_are_the_clients_three(code):
    questions = QUESTION_TEMPLATES[code]["questions"]

    assert len({question["text"] for question in questions}) == len(questions)
    assert all(len(question["probes"]) == 3 for question in questions)
    assert all(rules.clean_text(question["text"]) == question["text"] for question in questions)


def test_the_wording_is_the_clients_word_for_word():
    nsm = QUESTION_TEMPLATES["national_sales_manager"]["questions"]
    smm = QUESTION_TEMPLATES["senior_marketing_manager"]["questions"]
    director = QUESTION_TEMPLATES["commercial_director"]["questions"]

    assert nsm[0]["text"] == (
        "You are preparing to launch Seasonings, Snacks and Breakfast products across Nigeria. "
        "How would you build a phased national route-to-market plan for the first 90 days?"
    )
    assert nsm[0]["probes"][0] == "Which markets and channels would you prioritise, and why?"
    assert nsm[4]["probes"][2] == "Give an example of a decision driven by these metrics."
    assert director[7]["text"].endswith("Walk me through your first 90 days.")
    assert smm[0]["text"].startswith("How would you translate the Commercial Director’s strategy")  # curly apostrophe, as in the pack
    assert smm[9]["probes"][1] == (
        "How would you measure campaign contribution while accounting for distribution and stock availability?"
    )


def test_the_items_are_a_fresh_copy_each_time_and_an_unknown_code_has_none():
    first = template_items("commercial_director")
    first[0]["text"] = "changed"

    assert template_items("commercial_director")[0]["text"] != "changed"
    assert template_items("nobody") is None


def test_the_summaries_name_each_role_with_its_count_and_total_time():
    summaries = {item["code"]: item for item in template_summaries()}

    assert summaries["senior_marketing_manager"]["question_count"] == 10
    assert summaries["national_sales_manager"]["title"] == "National Sales Manager"
    assert summaries["national_sales_manager"]["total_seconds"] == 1050


# ---------------------------------------------------------------------------
# Applying one, over HTTP
# ---------------------------------------------------------------------------


def _headers(user):
    token = create_token_pair(user.id, user.role)["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _company(db_session):
    owner = make_employer()
    db_session.add(owner)
    await db_session.flush()
    await make_organization_for(db_session, owner, company_name="Acme")
    job = make_job(owner.id)
    db_session.add(job)
    await db_session.flush()
    return owner, job


def _url(job, tail=""):
    return f"/api/v1/interviews/jobs/{job.id}/questions{tail}"


async def _apply(client, user, job, code):
    return await client.post(_url(job, "/from-template"), json={"code": code}, headers=_headers(user))


@pytest.mark.asyncio
async def test_applying_a_template_sets_the_scoring_profile_and_the_tagged_questions_with_their_probes(
    client, db_session
):
    owner, job = await _company(db_session)

    response = await _apply(client, owner, job, "national_sales_manager")

    assert response.status_code == 200
    body = response.json()
    assert len(body["questions"]) == 8
    assert body["follow_up_mode"] == "STANDARD"
    assert body["untested_competencies"] == []  # every competency of the role has a question
    assert [item["name"] for item in _scoring("national_sales_manager")["competencies"]] == body["competencies"]
    first = body["questions"][0]
    assert first["text"].startswith("You are preparing to launch Seasonings")
    assert first["competency"] == "Route-to-market and distributor development"
    assert first["probes"].splitlines()[0] == "Which markets and channels would you prioritise, and why?"
    assert first["source"] == "EMPLOYER"
    assert body["total_seconds"] == 1050
    profile = (await db_session.execute(select(JobScoringProfile))).scalar_one()
    assert profile.template_code == "national_sales_manager"
    assert [(c["name"], c["weight"], c["key"]) for c in profile.competencies][0] == (
        "Route-to-market and distributor development",
        30,
        True,
    )


@pytest.mark.asyncio
async def test_a_template_that_fits_is_saved_and_says_so(client, db_session):
    owner, job = await _company(db_session)

    body = (await _apply(client, owner, job, "commercial_director")).json()

    assert body["saved"] is True
    assert len((await db_session.execute(select(JobInterviewQuestion))).scalars().all()) == 8


@pytest.mark.asyncio
async def test_a_template_longer_than_the_interview_time_limit_is_shown_for_shortening_not_refused(
    client, db_session, monkeypatch
):
    """With INTERVIEW_MAX_DURATION_MINUTES at 10 the 17.5 minutes of the Sales Manager set do not
    fit. The questions still come back, to be shortened and saved, with the role's scoring profile
    already set so their tags are valid; nothing about the job's questions changes until then."""
    monkeypatch.setattr(settings, "interview_max_duration_minutes", 10)
    owner, job = await _company(db_session)
    db_session.add(JobInterviewQuestion(job_id=job.id, position=1, text="An existing question to keep?", time_limit_seconds=120))
    await db_session.flush()

    response = await _apply(client, owner, job, "national_sales_manager")

    assert response.status_code == 200
    body = response.json()
    assert body["saved"] is False
    assert len(body["questions"]) == 8
    assert body["questions"][0]["competency"] == "Route-to-market and distributor development"
    assert body["questions"][0]["probes"].startswith("Which markets and channels")
    assert body["total_seconds"] == 1050 and body["max_total_seconds"] == 600
    assert body["untested_competencies"] == [] and body["follow_up_mode"] == "STANDARD"
    rows = (await db_session.execute(select(JobInterviewQuestion).where(JobInterviewQuestion.job_id == job.id))).scalars().all()
    assert [row.text for row in rows] == ["An existing question to keep?"]  # the saved list is untouched
    profile = (await db_session.execute(select(JobScoringProfile))).scalar_one()
    assert profile.template_code == "national_sales_manager"


@pytest.mark.asyncio
async def test_the_shortened_set_can_then_be_saved_with_its_tags(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "interview_max_duration_minutes", 10)
    owner, job = await _company(db_session)
    body = (await _apply(client, owner, job, "national_sales_manager")).json()
    questions = [
        {key: item[key] for key in ("text", "source", "competency", "probes")} | {"time_limit_seconds": 60}
        for item in body["questions"]
    ]

    saved = await client.put(_url(job), json={"questions": questions}, headers=_headers(owner))

    assert saved.status_code == 200 and len(saved.json()["questions"]) == 8
    assert saved.json()["questions"][0]["competency"] == "Route-to-market and distributor development"


@pytest.mark.asyncio
async def test_saving_the_unshortened_set_is_still_refused_with_the_time_message(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "interview_max_duration_minutes", 10)
    owner, job = await _company(db_session)
    body = (await _apply(client, owner, job, "national_sales_manager")).json()
    questions = [
        {key: item[key] for key in ("text", "time_limit_seconds", "source", "competency", "probes")}
        for item in body["questions"]
    ]

    refused = await client.put(_url(job), json={"questions": questions}, headers=_headers(owner))

    assert refused.status_code == 422
    assert any("limited to 10 minutes" in d["message"] for d in refused.json()["details"])
    assert (await db_session.execute(select(JobInterviewQuestion))).scalars().all() == []


@pytest.mark.asyncio
async def test_each_role_can_be_applied(client, db_session):
    for code, count in [("commercial_director", 8), ("senior_marketing_manager", 10)]:
        owner, job = await _company(db_session)

        response = await _apply(client, owner, job, code)

        assert response.status_code == 200 and len(response.json()["questions"]) == count
        assert response.json()["untested_competencies"] == []


@pytest.mark.asyncio
async def test_applying_a_template_replaces_the_jobs_questions_and_profile(client, db_session):
    owner, job = await _company(db_session)
    await _apply(client, owner, job, "commercial_director")

    again = await _apply(client, owner, job, "senior_marketing_manager")

    rows = (await db_session.execute(select(JobInterviewQuestion).where(JobInterviewQuestion.job_id == job.id))).scalars().all()
    assert len(rows) == 10 and len(again.json()["questions"]) == 10
    profile = (await db_session.execute(select(JobScoringProfile))).scalar_one()
    assert profile.template_code == "senior_marketing_manager"


@pytest.mark.asyncio
async def test_an_unknown_template_is_refused_and_changes_nothing(client, db_session):
    owner, job = await _company(db_session)
    await _apply(client, owner, job, "commercial_director")

    refused = await _apply(client, owner, job, "nobody")

    assert refused.status_code == 422
    rows = (await db_session.execute(select(JobInterviewQuestion).where(JobInterviewQuestion.job_id == job.id))).scalars().all()
    assert len(rows) == 8
    assert (await db_session.execute(select(JobScoringProfile))).scalar_one().template_code == "commercial_director"


@pytest.mark.asyncio
async def test_only_the_jobs_own_company_can_apply_a_template(client, db_session):
    _owner, job = await _company(db_session)
    outsider = make_employer()
    db_session.add(outsider)
    await db_session.flush()

    refused = await _apply(client, outsider, job, "commercial_director")

    assert refused.status_code == 403
    assert (await db_session.execute(select(JobInterviewQuestion))).scalars().all() == []


@pytest.mark.asyncio
async def test_a_template_needs_a_logged_in_employer(client, db_session):
    _owner, job = await _company(db_session)

    response = await client.post(_url(job, "/from-template"), json={"code": "commercial_director"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_the_editor_is_told_which_templates_there_are(client, db_session):
    owner, job = await _company(db_session)

    body = (await client.get(_url(job), headers=_headers(owner))).json()

    assert [t["code"] for t in body["question_templates"]] == list(ROLE_CODES)
    assert [t["question_count"] for t in body["question_templates"]] == [8, 8, 10]


@pytest.mark.asyncio
async def test_after_applying_the_employer_can_still_edit_and_save_the_list(client, db_session):
    owner, job = await _company(db_session)
    applied = (await _apply(client, owner, job, "commercial_director")).json()
    questions = [
        {key: item[key] for key in ("text", "time_limit_seconds", "source", "competency", "probes")}
        for item in applied["questions"]
    ]
    questions[0]["time_limit_seconds"] = 240

    saved = await client.put(_url(job), json={"questions": questions}, headers=_headers(owner))

    assert saved.status_code == 200
    assert saved.json()["questions"][0]["time_limit_seconds"] == 240
    assert saved.json()["follow_up_mode"] == "STANDARD"
