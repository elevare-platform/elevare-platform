"""Seed script — creates realistic job listings for development and testing.

Idempotent: running this script multiple times will not duplicate data.
It checks for existing jobs before inserting.

Usage (from inside the api container):
    python scripts/seed_jobs.py
"""

import asyncio
import sys
from pathlib import Path

# Ensure the app package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

import app.core.model_registry  # noqa: F401
from app.core.database import AsyncSessionLocal
from app.modules.auth.security import hash_password
from app.modules.jobs.enums import ContractType, JobStatus, WorkLocation, WorkModel
from app.modules.jobs.models import Job
from app.modules.users.enums import AccountStatus, UserRole
from app.modules.users.models import EmployerProfile, User

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

EMPLOYERS = [
    {
        "first_name": "Amaka",
        "last_name": "Okonkwo",
        "email": "amaka@techcorp.ng",
        "phone_number": "08011111111",
        "password_hash": hash_password("Seed@1234"),
        "role": UserRole.EMPLOYER.value,
        "account_status": AccountStatus.ACTIVE.value,
        "email_verified": True,
    },
    {
        "first_name": "Emeka",
        "last_name": "Nwosu",
        "email": "emeka@fintech.ng",
        "phone_number": "08022222222",
        "password_hash": hash_password("Seed@1234"),
        "role": UserRole.EMPLOYER.value,
        "account_status": AccountStatus.ACTIVE.value,
        "email_verified": True,
    },
]

EMPLOYER_PROFILES = {
    "amaka@techcorp.ng": {
        "company_name": "TechCorp Nigeria",
        "industry": "Software & Technology",
        "company_size": "51-200",
        "website": "https://techcorp.ng",
        "is_profile_complete": True,
    },
    "emeka@fintech.ng": {
        "company_name": "FinTech Solutions Ltd",
        "industry": "Financial Technology",
        "company_size": "51-200",
        "website": "https://fintechsolutions.ng",
        "is_profile_complete": True,
    },
}


JOBS = [
    # TechCorp jobs
    {
        "title": "Senior Backend Engineer",
        "description": "We are looking for a senior backend engineer with 5+ years of experience in Python and distributed systems. You will design and build scalable APIs for our growing platform.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 800000,
        "salary_max": 1200000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "amaka@techcorp.ng",
    },
    {
        "title": "Frontend Developer (React)",
        "description": "Join our product team to build beautiful, performant user interfaces. You should be comfortable with React, TypeScript, and modern CSS.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.REMOTE.value,
        "salary_min": 500000,
        "salary_max": 800000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "amaka@techcorp.ng",
    },
    {
        "title": "DevOps Engineer",
        "description": "Manage our cloud infrastructure on AWS. Experience with Terraform, Kubernetes, and CI/CD pipelines required.",
        "location": "Abuja, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.ONSITE.value,
        "salary_min": 700000,
        "salary_max": 1000000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "amaka@techcorp.ng",
    },
    {
        "title": "Product Manager",
        "description": "Lead product strategy and roadmap for our B2B SaaS platform. 3+ years of product management experience required.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 900000,
        "salary_max": 1400000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "amaka@techcorp.ng",
    },
    {
        "title": "Data Analyst Intern",
        "description": "3-month internship for recent graduates. You will work with our data team to build dashboards and analyse user behaviour.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.INTERNSHIP.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 80000,
        "salary_max": 120000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "amaka@techcorp.ng",
    },
    {
        "title": "Mobile Developer (Flutter)",
        "description": "Build cross-platform mobile apps for iOS and Android. Strong Dart skills and experience shipping production apps required.",
        "location": "Remote",
        "contract_type": ContractType.CONTRACT.value,
        "work_model": WorkModel.REMOTE.value,
        "salary_min": 600000,
        "salary_max": 900000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "amaka@techcorp.ng",
    },
    {
        "title": "QA Engineer",
        "description": "Own quality assurance across our web and mobile products. Experience with Selenium, Cypress, or Playwright preferred.",
        "location": "Port Harcourt, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.ONSITE.value,
        "salary_min": 400000,
        "salary_max": 650000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "amaka@techcorp.ng",
    },
    {
        "title": "Technical Writer",
        "description": "Create clear, accurate documentation for our developer APIs and internal tools.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.PART_TIME.value,
        "work_model": WorkModel.REMOTE.value,
        "salary_min": 200000,
        "salary_max": 350000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "amaka@techcorp.ng",
    },
    {
        "title": "UI/UX Designer",
        "description": "Design intuitive user experiences for our web platform. Proficiency in Figma required.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 450000,
        "salary_max": 700000,
        "status": JobStatus.DRAFT.value,
        "employer_email": "amaka@techcorp.ng",
    },
    {
        "title": "Security Engineer",
        "description": "Lead security reviews, penetration testing, and incident response for our infrastructure.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 1000000,
        "salary_max": 1500000,
        "status": JobStatus.CLOSED.value,
        "employer_email": "amaka@techcorp.ng",
    },

    # Fintech jobs
    {
        "title": "Backend Engineer (Node.js)",
        "description": "Build payment processing APIs and integrations with Nigerian banking infrastructure. Experience with Paystack or Flutterwave a plus.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 700000,
        "salary_max": 1100000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "emeka@fintech.ng",
    },
    {
        "title": "Compliance Officer",
        "description": "Ensure our operations comply with CBN regulations and AML/KYC requirements.",
        "location": "Abuja, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.ONSITE.value,
        "salary_min": 600000,
        "salary_max": 900000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "emeka@fintech.ng",
    },
    {
        "title": "Data Scientist",
        "description": "Build fraud detection models and credit scoring algorithms using Python and ML frameworks.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.REMOTE.value,
        "salary_min": 900000,
        "salary_max": 1300000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "emeka@fintech.ng",
    },
    {
        "title": "Customer Success Manager",
        "description": "Own relationships with our enterprise clients and drive product adoption.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 500000,
        "salary_max": 750000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "emeka@fintech.ng",
    },
    {
        "title": "Android Developer",
        "description": "Build and maintain our Android banking app used by 500k+ customers.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 650000,
        "salary_max": 950000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "emeka@fintech.ng",
    },
    {
        "title": "iOS Developer",
        "description": "Build and maintain our iOS banking app. Swift and SwiftUI experience required.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 650000,
        "salary_max": 950000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "emeka@fintech.ng",
    },
    {
        "title": "Risk Analyst",
        "description": "Analyse credit and operational risk across our lending portfolio.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.ONSITE.value,
        "salary_min": 550000,
        "salary_max": 800000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "emeka@fintech.ng",
    },
    {
        "title": "Finance Intern",
        "description": "6-month internship supporting our finance team with reconciliation and reporting.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.INTERNSHIP.value,
        "work_model": WorkModel.ONSITE.value,
        "salary_min": 60000,
        "salary_max": 100000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "emeka@fintech.ng",
    },
    {
        "title": "Infrastructure Engineer",
        "description": "Manage our on-premise and cloud infrastructure. Experience with high-availability systems required.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 800000,
        "salary_max": 1200000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "emeka@fintech.ng",
    },
    {
        "title": "Growth Marketing Manager",
        "description": "Drive user acquisition and retention through data-driven marketing campaigns.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 600000,
        "salary_max": 900000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "emeka@fintech.ng",
    },
    {
        "title": "Legal Counsel",
        "description": "Provide legal advice on fintech regulations, contracts, and corporate governance.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.ONSITE.value,
        "salary_min": 1000000,
        "salary_max": 1600000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "emeka@fintech.ng",
    },
    {
        "title": "Business Analyst",
        "description": "Bridge the gap between business requirements and technical implementation.",
        "location": "Abuja, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 500000,
        "salary_max": 750000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "emeka@fintech.ng",
    },
    {
        "title": "Support Engineer",
        "description": "Provide technical support to merchants and developers integrating our payment APIs.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.REMOTE.value,
        "salary_min": 350000,
        "salary_max": 550000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "emeka@fintech.ng",
    },
    {
        "title": "Scrum Master",
        "description": "Facilitate agile ceremonies and remove blockers for our engineering teams.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.CONTRACT.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 700000,
        "salary_max": 1000000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "emeka@fintech.ng",
    },
    {
        "title": "Head of Engineering",
        "description": "Lead our 30-person engineering organisation. 8+ years of engineering leadership experience required.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 2000000,
        "salary_max": 3000000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "emeka@fintech.ng",
    },
    {
        "title": "Database Administrator",
        "description": "Manage and optimise our PostgreSQL and MongoDB databases.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 700000,
        "salary_max": 1000000,
        "status": JobStatus.DRAFT.value,
        "employer_email": "emeka@fintech.ng",
    },
    {
        "title": "Content Writer",
        "description": "Create engaging content for our blog, social media, and marketing materials.",
        "location": "Remote",
        "contract_type": ContractType.PART_TIME.value,
        "work_model": WorkModel.REMOTE.value,
        "salary_min": 150000,
        "salary_max": 250000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "emeka@fintech.ng",
    },
    {
        "title": "HR Manager",
        "description": "Own talent acquisition, onboarding, and people operations for our 80-person company.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.ONSITE.value,
        "salary_min": 600000,
        "salary_max": 900000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "emeka@fintech.ng",
    },
    {
        "title": "Sales Executive",
        "description": "Drive B2B sales of our payment solutions to SMEs and enterprises across Nigeria.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 400000,
        "salary_max": 700000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "emeka@fintech.ng",
    },
    {
        "title": "Machine Learning Engineer",
        "description": "Deploy and maintain ML models in production. Experience with MLOps and model serving required.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.REMOTE.value,
        "salary_min": 1000000,
        "salary_max": 1500000,
        "status": JobStatus.ACTIVE.value,
        "employer_email": "emeka@fintech.ng",
    },
    {
        "title": "Office Manager",
        "description": "Manage day-to-day office operations and vendor relationships.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.ONSITE.value,
        "salary_min": 250000,
        "salary_max": 400000,
        "status": JobStatus.CLOSED.value,
        "employer_email": "emeka@fintech.ng",
    },
]


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        # Check if already seeded — idempotency guard
        result = await session.execute(
            select(User).where(User.email == "amaka@techcorp.ng")
        )
        if result.scalar_one_or_none():
            print("Seed data already exists. Skipping.")
            return

        # Create employer users
        employer_map: dict[str, User] = {}
        for emp_data in EMPLOYERS:
            user = User(**emp_data)
            session.add(user)
            await session.flush()
            employer_map[emp_data["email"]] = user
            print(f"Created employer: {emp_data['email']}")

        # Create employer profiles
        for email, profile_data in EMPLOYER_PROFILES.items():
            employer = employer_map[email]
            profile = EmployerProfile(user_id=employer.id, **profile_data)
            session.add(profile)
            print(f"Created employer profile for: {email}")

        # Create jobs
        for job_data in JOBS:
            employer_email = job_data.pop("employer_email")
            employer = employer_map[employer_email]
            # Default work_location to INTERNATIONAL for REMOTE jobs, LOCAL otherwise
            if "work_location" not in job_data:
                job_data["work_location"] = (
                    WorkLocation.INTERNATIONAL.value
                    if job_data.get("work_model") == WorkModel.REMOTE.value
                    else WorkLocation.LOCAL.value
                )
            job = Job(**job_data, employer_id=employer.id)
            session.add(job)

        await session.commit()
        print(f"Seeded {len(JOBS)} jobs and {len(EMPLOYER_PROFILES)} employer profiles across {len(EMPLOYERS)} employers.")


if __name__ == "__main__":
    asyncio.run(seed())
