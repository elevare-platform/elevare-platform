"""Seed demo applicants for a given job ID.

Run this against any job on the production or staging server to populate
it with 6 realistic candidates and AI scores — perfect for demos.

Usage (inside the api container or with the venv active):

    # Seed applicants for a specific job:
    python scripts/seed_demo_applicants.py --job-id <JOB_UUID>

    # Dry-run — shows what would be created without writing to DB:
    python scripts/seed_demo_applicants.py --job-id <JOB_UUID> --dry-run

    # Reset — deletes existing demo applicants for this job then re-seeds:
    python scripts/seed_demo_applicants.py --job-id <JOB_UUID> --reset

Via docker compose (from project root):
    docker compose exec api python scripts/seed_demo_applicants.py --job-id <JOB_UUID>

Via docker compose prod:
    docker compose -f docker-compose.prod.yml exec api python scripts/seed_demo_applicants.py --job-id <JOB_UUID>
"""

import argparse
import asyncio
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Make app importable when running the script directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.core.model_registry  # noqa: F401 — registers all ORM mappers

from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.modules.applications.enums import ApplicationStatus
from app.modules.applications.models import Application
from app.modules.auth.security import hash_password
from app.modules.candidates.models import CandidateProfile
from app.modules.jobs.models import Job
from app.modules.users.enums import AccountStatus, UserRole
from app.modules.users.models import User

# ---------------------------------------------------------------------------
# Candidate personas
# ---------------------------------------------------------------------------

PERSONAS = [
    {
        "first_name": "Adaeze",
        "last_name": "Okonkwo",
        "email": "adaeze.okonkwo@demo-elevare.com",
        "phone": "+2348101110001",
        "location": "Lagos, Nigeria",
        "years_exp": 7,
        "skills": ["Talent Acquisition", "Stakeholder Management", "HRIS",
                   "Performance Management", "Labour Law"],
        "bio": "Senior HR professional with 7 years driving end-to-end recruitment and workforce strategy at scale.",
        "status": ApplicationStatus.SHORTLISTED.value,
        "ai_score": 91,
        "fit_summary": (
            "Adaeze brings a strong alignment with this role, demonstrating deep experience in talent "
            "acquisition and HR operations within high-growth environments. Her skills coverage and "
            "seniority level are an excellent match for the requirements outlined."
        ),
        "strengths": [
            "7 years of hands-on talent acquisition experience directly aligned with the role's core requirement.",
            "Proficient in HRIS platforms and performance management cycles, matching listed technical competencies.",
            "Proven stakeholder management skills relevant to cross-functional HR advisory responsibilities.",
            "Strong working knowledge of Nigerian Labour Law, critical for compliance-driven HR environments.",
        ],
        "weaknesses": [
            "No explicit mention of international recruitment exposure which may limit scope on global mandates.",
            "Leadership of large HR teams not evidenced — could be a gap for senior people management expectations.",
        ],
    },
    {
        "first_name": "Fatima",
        "last_name": "Aliyu",
        "email": "fatima.aliyu@demo-elevare.com",
        "phone": "+2348101110003",
        "location": "Lagos, Nigeria",
        "years_exp": 9,
        "skills": ["HR Strategy", "Organisational Development", "Change Management",
                   "Executive Search", "People Analytics"],
        "bio": "Strategic HR leader with 9 years shaping organisational culture and leading executive search across West Africa.",
        "status": ApplicationStatus.SHORTLISTED.value,
        "ai_score": 88,
        "fit_summary": (
            "Fatima is a high-calibre candidate with strong strategic HR credentials and notable executive "
            "search experience. Her people analytics capability and organisational development background "
            "make her a compelling fit for a consultancy-oriented HR role."
        ),
        "strengths": [
            "9 years of progressive HR leadership with a strong focus on organisational development and strategy.",
            "Executive search experience is directly relevant to the talent acquisition mandate.",
            "People analytics proficiency supports data-driven workforce planning requirements.",
            "Change management expertise adds value for clients undergoing workforce transformation.",
        ],
        "weaknesses": [
            "Profile is weighted toward strategy — operational HR execution depth may need verification.",
            "West Africa regional focus may limit applicability for clients with broader international mandates.",
        ],
    },
    {
        "first_name": "Emeka",
        "last_name": "Nwosu",
        "email": "emeka.nwosu@demo-elevare.com",
        "phone": "+2348101110002",
        "location": "Abuja, Nigeria",
        "years_exp": 5,
        "skills": ["Recruitment", "Employee Relations", "Compensation & Benefits",
                   "Onboarding", "MS Excel"],
        "bio": "HR generalist with 5 years of experience in recruitment and employee relations in financial services.",
        "status": ApplicationStatus.REVIEWING.value,
        "ai_score": 78,
        "fit_summary": (
            "Emeka presents a solid mid-level HR profile with well-rounded generalist experience. "
            "His background in compensation and employee relations is relevant, though seniority gaps "
            "may require closer evaluation against the role's leadership expectations."
        ),
        "strengths": [
            "Solid 5-year recruitment track record with financial sector exposure.",
            "Experience in compensation & benefits design aligns with workforce strategy responsibilities.",
            "Strong onboarding programme delivery skills, relevant to talent integration requirements.",
        ],
        "weaknesses": [
            "Mid-level seniority may fall short if the role demands independent strategic decision-making.",
            "Limited evidence of managing external recruitment vendors or executive search processes.",
        ],
    },
    {
        "first_name": "Ngozi",
        "last_name": "Okafor",
        "email": "ngozi.okafor@demo-elevare.com",
        "phone": "+2348101110005",
        "location": "Lagos, Nigeria",
        "years_exp": 6,
        "skills": ["Learning & Development", "Training Needs Analysis",
                   "Facilitation", "Succession Planning", "LMS Administration"],
        "bio": "L&D specialist with 6 years designing corporate training programmes across FMCG and fintech.",
        "status": ApplicationStatus.REVIEWING.value,
        "ai_score": 61,
        "fit_summary": (
            "Ngozi has a solid L&D background with notable facilitation and programme design experience. "
            "However, her profile skews toward training and development rather than the core recruitment "
            "and HR generalist competencies central to this role."
        ),
        "strengths": [
            "Strong L&D and succession planning skills add value in a workforce solutions context.",
            "Cross-industry experience in FMCG and fintech demonstrates adaptability.",
            "LMS administration experience is relevant if the role involves workforce development tools.",
        ],
        "weaknesses": [
            "Core recruitment and talent acquisition skills are not prominently featured.",
            "Role may require broader HR generalist experience beyond the L&D specialisation.",
            "Limited evidence of direct employer advisory or HR consulting work.",
        ],
    },
    {
        "first_name": "Chukwuemeka",
        "last_name": "Eze",
        "email": "chukwuemeka.eze@demo-elevare.com",
        "phone": "+2348101110004",
        "location": "Port Harcourt, Nigeria",
        "years_exp": 3,
        "skills": ["CV Screening", "Interview Scheduling", "Job Posting", "ATS Management"],
        "bio": "Junior recruiter with 3 years of experience in high-volume screening and ATS management.",
        "status": ApplicationStatus.SUBMITTED.value,
        "ai_score": 54,
        "fit_summary": (
            "Chukwuemeka has relevant foundational recruiting skills but the experience and seniority "
            "fall below the expectations of this role. He may be a stronger fit for a junior or "
            "coordinator position rather than a mid-to-senior HR mandate."
        ),
        "strengths": [
            "Practical ATS management and high-volume screening skills are operationally useful.",
            "Hands-on experience with job posting and candidate coordination demonstrates process familiarity.",
        ],
        "weaknesses": [
            "3 years of experience is below the preferred threshold for this role's seniority expectations.",
            "Skills profile is operational/administrative rather than strategic or advisory.",
            "No evidence of independent stakeholder management or client-facing HR consultancy.",
        ],
    },
    {
        "first_name": "Tunde",
        "last_name": "Bakare",
        "email": "tunde.bakare@demo-elevare.com",
        "phone": "+2348101110006",
        "location": "Ibadan, Nigeria",
        "years_exp": 2,
        "skills": ["Administrative Support", "Data Entry", "Microsoft Word", "Filing"],
        "bio": "Recent graduate with 2 years of administrative support experience in a government agency.",
        "status": ApplicationStatus.SUBMITTED.value,
        "ai_score": 28,
        "fit_summary": (
            "Tunde's profile does not align with the requirements of this HR role. "
            "The skills and experience presented are primarily administrative and entry-level, "
            "with no evidence of HR, recruitment, or people management competencies."
        ),
        "strengths": [
            "Administrative organisation skills may provide a basic foundation for supporting HR operations.",
        ],
        "weaknesses": [
            "No HR, recruitment, or people management experience relevant to this role.",
            "2 years of entry-level administrative work falls significantly below role requirements.",
            "Technical HR skills (HRIS, talent acquisition, compensation) are absent from the profile.",
            "Entry-level seniority is misaligned with the mid-to-senior expectations of this position.",
        ],
    },
]

DEMO_EMAILS = {p["email"] for p in PERSONAS}


# ---------------------------------------------------------------------------
# Core seed logic
# ---------------------------------------------------------------------------

async def seed(job_id: uuid.UUID, dry_run: bool = False, reset: bool = False) -> None:
    async with AsyncSessionLocal() as db:
        # Verify job exists
        job = await db.get(Job, job_id)
        if not job:
            print(f"ERROR: Job {job_id} not found in the database.")
            sys.exit(1)

        print(f"\nJob found: '{job.title}' (status: {job.status})")
        print(f"Employer ID: {job.employer_id}\n")

        if dry_run:
            print("DRY RUN — no changes will be written.\n")

        # Optional reset — remove existing demo applications for this job
        if reset and not dry_run:
            # Find demo user IDs
            result = await db.execute(
                select(User.id).where(User.email.in_(DEMO_EMAILS))
            )
            demo_user_ids = [row[0] for row in result.fetchall()]

            if demo_user_ids:
                deleted = await db.execute(
                    delete(Application).where(
                        Application.job_id == job_id,
                        Application.candidate_id.in_(demo_user_ids),
                    )
                )
                count = deleted.rowcount
                await db.commit()
                print(f"Reset: removed {count} existing demo application(s) for this job.\n")

        created = 0
        skipped = 0

        for persona in PERSONAS:
            # Find or create candidate user
            result = await db.execute(
                select(User).where(User.email == persona["email"])
            )
            user = result.scalar_one_or_none()

            if user is None:
                if dry_run:
                    print(f"  [DRY RUN] Would create user: {persona['first_name']} {persona['last_name']} <{persona['email']}>")
                else:
                    user = User(
                        id=uuid.uuid4(),
                        first_name=persona["first_name"],
                        last_name=persona["last_name"],
                        email=persona["email"],
                        phone_number=persona["phone"],
                        password_hash=hash_password("DemoCandidate123!"),
                        role=UserRole.CANDIDATE.value,
                        account_status=AccountStatus.ACTIVE.value,
                        email_verified=True,
                        email_verified_at=datetime.now(UTC),
                    )
                    db.add(user)
                    await db.flush()

                    profile = CandidateProfile(
                        id=uuid.uuid4(),
                        user_id=user.id,
                        bio=persona["bio"],
                        skills=persona["skills"],
                        years_of_experience=persona["years_exp"],
                        location=persona["location"],
                    )
                    db.add(profile)
                    await db.flush()
                    print(f"  Created user: {persona['first_name']} {persona['last_name']} <{persona['email']}>")
            else:
                print(f"  Existing user: {persona['first_name']} {persona['last_name']} <{persona['email']}>")

            if dry_run:
                print(f"  [DRY RUN] Would create application — AI score: {persona['ai_score']}, status: {persona['status']}")
                created += 1
                continue

            # Idempotency check
            existing = await db.execute(
                select(Application).where(
                    Application.candidate_id == user.id,
                    Application.job_id == job_id,
                )
            )
            if existing.scalar_one_or_none():
                print(f"  Skipped (already applied): {persona['first_name']} {persona['last_name']}")
                skipped += 1
                continue

            app = Application(
                id=uuid.uuid4(),
                candidate_id=user.id,
                job_id=job_id,
                cv_id=None,
                cover_letter=None,
                status=persona["status"],
                status_updated_at=datetime.now(UTC),
                ai_score=persona["ai_score"],
                ai_fit_summary=persona["fit_summary"],
                ai_strengths=persona["strengths"],
                ai_weaknesses=persona["weaknesses"],
                ai_score_computed_at=datetime.now(UTC),
                ai_score_job_hash="demo",
                ai_score_cv_hash="demo",
            )
            db.add(app)
            print(f"  Created application — {persona['first_name']} {persona['last_name']}: score={persona['ai_score']}, status={persona['status']}")
            created += 1

        if not dry_run:
            await db.commit()

        print(f"\n{'DRY RUN ' if dry_run else ''}Done — {created} created, {skipped} skipped.")
        print(f"View applicants at: /employer/jobs/{job_id}/applicants\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Seed demo applicants for a given job ID."
    )
    parser.add_argument(
        "--job-id",
        required=True,
        help="UUID of the job to seed applicants for",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be created without writing to the DB",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing demo applicants for this job before re-seeding",
    )
    args = parser.parse_args()

    try:
        job_id = uuid.UUID(args.job_id)
    except ValueError:
        print(f"ERROR: '{args.job_id}' is not a valid UUID.")
        sys.exit(1)

    asyncio.run(seed(job_id, dry_run=args.dry_run, reset=args.reset))


if __name__ == "__main__":
    main()
