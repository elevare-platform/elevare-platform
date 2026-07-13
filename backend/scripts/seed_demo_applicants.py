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
        "first_name": "Chidinma",
        "last_name": "Okafor",
        "email": "chidinma.okafor@demo-elevare.com",
        "phone": "+2348101110001",
        "location": "Lagos, Nigeria",
        "years_exp": 3,
        "skills": ["Customer Service", "Complaint Resolution", "Communication",
                   "Shift Work", "POS Operations"],
        "bio": "Friendly and customer-focused service representative with 3 years of experience in retail and hospitality environments across Lagos.",
        "status": ApplicationStatus.SHORTLISTED.value,
        "ai_score": 94,
        "fit_summary": (
            "Chidinma is an excellent match for this Customer Service Representative role, bringing "
            "directly relevant experience in customer-facing environments with strong communication "
            "skills and proven ability to work shift-based schedules in Lagos."
        ),
        "strengths": [
            "3 years of hands-on customer service experience in fast-paced retail and hospitality settings.",
            "Demonstrated ability to handle customer complaints and escalate issues appropriately.",
            "Experienced with shift-based work schedules including early morning and late evening rotations.",
            "Strong interpersonal and communication skills aligned with the role's core requirements.",
            "Based in Lagos and available to work at the required location without relocation.",
        ],
        "weaknesses": [
            "No mention of experience with formal order processing systems which may require brief onboarding.",
            "SSCE qualification meets minimum threshold but further education could strengthen long-term growth.",
        ],
    },
    {
        "first_name": "Amaka",
        "last_name": "Eze",
        "email": "amaka.eze@demo-elevare.com",
        "phone": "+2348101110002",
        "location": "Lagos, Nigeria",
        "years_exp": 2,
        "skills": ["Customer Relations", "Reception", "Communication",
                   "Complaint Handling", "Team Collaboration"],
        "bio": "Polite and well-presented customer relations professional with 2 years of front-desk and reception experience in a hospitality firm.",
        "status": ApplicationStatus.SHORTLISTED.value,
        "ai_score": 88,
        "fit_summary": (
            "Amaka presents a strong profile for this role with relevant customer-facing experience "
            "and the interpersonal qualities required. Her hospitality background maps well to the "
            "customer service expectations outlined in the job description."
        ),
        "strengths": [
            "2 years of front-desk and customer relations experience in a service-oriented environment.",
            "Described as polite, well-groomed, and professional — directly matching the role's personal requirements.",
            "Proven complaint handling and team collaboration skills align with key responsibilities.",
            "Resident in Lagos and comfortable with the shift schedule.",
        ],
        "weaknesses": [
            "Slightly below the preferred experience level — additional on-the-job training may be needed initially.",
            "No specific mention of order processing or product knowledge which will need to be built on the job.",
        ],
    },
    {
        "first_name": "Blessing",
        "last_name": "Adeyemi",
        "email": "blessing.adeyemi@demo-elevare.com",
        "phone": "+2348101110003",
        "location": "Lagos, Nigeria",
        "years_exp": 1,
        "skills": ["Communication", "Customer Handling", "Cashiering",
                   "Teamwork", "Shift Flexibility"],
        "bio": "Energetic and motivated customer service associate with 1 year of experience in a busy supermarket chain in Lagos.",
        "status": ApplicationStatus.REVIEWING.value,
        "ai_score": 76,
        "fit_summary": (
            "Blessing shows genuine potential for this role with relevant entry-level customer service "
            "experience and a demonstrated ability to work in fast-paced environments. Her shift "
            "flexibility and Lagos location are positives, though experience depth is limited."
        ),
        "strengths": [
            "Hands-on customer handling and cashiering experience in a high-volume retail environment.",
            "Comfortable with shift-based schedules and working under pressure.",
            "Friendly and communicative — personal attributes match the role's requirements.",
            "Lagos-based with no accommodation or logistics barriers.",
        ],
        "weaknesses": [
            "Only 1 year of experience — will benefit from closer supervision in the early stages.",
            "Limited exposure to formal complaint resolution processes or customer escalation procedures.",
        ],
    },
    {
        "first_name": "Oluwakemi",
        "last_name": "Fashola",
        "email": "oluwakemi.fashola@demo-elevare.com",
        "phone": "+2348101110004",
        "location": "Lagos, Nigeria",
        "years_exp": 4,
        "skills": ["Customer Service", "Sales Support", "Inquiry Management",
                   "Record Keeping", "Microsoft Office"],
        "bio": "Experienced customer service and sales support officer with 4 years working in telecoms and FMCG distribution in Lagos.",
        "status": ApplicationStatus.REVIEWING.value,
        "ai_score": 82,
        "fit_summary": (
            "Oluwakemi brings above-average experience for this role with a solid customer service "
            "track record across multiple industries. Her inquiry management and record-keeping "
            "skills are directly applicable, making her a reliable candidate for the position."
        ),
        "strengths": [
            "4 years of customer service experience across telecoms and FMCG sectors shows adaptability.",
            "Inquiry management and record-keeping skills directly match the role's key responsibilities.",
            "Comfortable handling both product questions and complaint escalation processes.",
            "Strong organisational skills and familiarity with basic office tools.",
        ],
        "weaknesses": [
            "Telecoms background may require a short adjustment period to align with this specific service environment.",
            "No explicit mention of shift work experience — willingness to work rotational hours should be confirmed.",
        ],
    },
    {
        "first_name": "Ngozi",
        "last_name": "Nwachukwu",
        "email": "ngozi.nwachukwu@demo-elevare.com",
        "phone": "+2348101110005",
        "location": "Ogun State, Nigeria",
        "years_exp": 0,
        "skills": ["Communication", "Customer Interaction", "Teamwork", "Punctuality"],
        "bio": "Recent SSCE graduate with no formal work experience but completed a 3-month customer service volunteer placement at a community health centre.",
        "status": ApplicationStatus.SUBMITTED.value,
        "ai_score": 52,
        "fit_summary": (
            "Ngozi meets the minimum qualification requirement and shows willingness to work in a "
            "customer-facing role. However, her lack of formal work experience and location outside "
            "Lagos are factors that require consideration against more experienced applicants."
        ),
        "strengths": [
            "Meets minimum SSCE qualification as specified in the job requirements.",
            "Volunteer customer interaction experience demonstrates initiative and willingness to learn.",
            "Good communication skills noted during volunteer placement.",
        ],
        "weaknesses": [
            "No formal paid work experience — will require significant onboarding and close supervision.",
            "Currently based in Ogun State — accommodation provision helps but commute logistics need confirmation.",
            "No demonstrated experience with shift-based work schedules.",
        ],
    },
    {
        "first_name": "Hauwa",
        "last_name": "Musa",
        "email": "hauwa.musa@demo-elevare.com",
        "phone": "+2348101110006",
        "location": "Abuja, Nigeria",
        "years_exp": 5,
        "skills": ["Office Administration", "Data Entry", "Filing",
                   "Microsoft Excel", "Report Writing"],
        "bio": "Administrative officer with 5 years of back-office support experience in a federal government ministry in Abuja.",
        "status": ApplicationStatus.SUBMITTED.value,
        "ai_score": 31,
        "fit_summary": (
            "Hauwa's profile is primarily administrative and back-office focused, which does not "
            "align well with the customer-facing, shift-based nature of this role. Her experience "
            "in Abuja and lack of direct customer service exposure are notable gaps."
        ),
        "strengths": [
            "5 years of work experience demonstrates reliability and professional maturity.",
            "Microsoft Office and data entry skills may support administrative aspects of the role.",
        ],
        "weaknesses": [
            "No direct customer service or customer-facing experience in her work history.",
            "Back-office government role is a poor match for a fast-paced retail shift environment.",
            "Based in Abuja — relocation to Lagos for a ₦60,000/month role may not be practical.",
            "No evidence of ability to work rotational shifts or in a physically active service environment.",
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
