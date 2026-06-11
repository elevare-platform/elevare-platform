"""Seed script — creates realistic job listings for development and testing.

Idempotent: running this script multiple times will not duplicate data.
It checks for existing jobs before inserting.

Usage (from inside the api container):
    python scripts/seed_jobs.py
"""

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

# Ensure the app package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

import app.core.model_registry  # noqa: F401
from app.core.database import AsyncSessionLocal
from app.modules.auth.security import hash_password
from app.modules.jobs.enums import (
    ContractType,
    JobStatus,
    ModerationStatus,
    SeniorityLevel,
    WorkLocation,
    WorkModel,
)
from app.modules.jobs.models import Job
from app.modules.users.enums import AccountStatus, UserRole
from app.modules.users.models import EmployerProfile, User


def deadline(days: int) -> date:
    """Return today's date offset by the given number of days."""
    return date.today() + timedelta(days=days)

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
    # ── TechCorp Nigeria ──────────────────────────────────────────────────────
    {
        "title": "Senior Backend Engineer",
        "description": "We are looking for a senior backend engineer with 5+ years of experience in Python and distributed systems. You will design and build scalable APIs for our growing platform. Strong knowledge of PostgreSQL, Redis, and async frameworks required.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 800000,
        "salary_max": 1200000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "amaka@techcorp.ng",
        "seniority_level": SeniorityLevel.SENIOR.value,
        "required_years_experience": 5,
        "required_skills": ["Python", "PostgreSQL", "Redis", "FastAPI", "Docker"],
        "openings_count": 2,
        "application_deadline": deadline(45),
    },
    {
        "title": "Frontend Developer (React)",
        "description": "Join our product team to build beautiful, performant user interfaces. You should be comfortable with React, TypeScript, and modern CSS. Experience with state management libraries and testing tools is a plus.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.REMOTE.value,
        "salary_min": 500000,
        "salary_max": 800000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "amaka@techcorp.ng",
        "seniority_level": SeniorityLevel.MID.value,
        "required_years_experience": 2,
        "required_skills": ["React", "TypeScript", "CSS", "REST"],
        "openings_count": 1,
        "application_deadline": deadline(30),
    },
    {
        "title": "DevOps Engineer",
        "description": "Manage our cloud infrastructure on AWS. Experience with Terraform, Kubernetes, and CI/CD pipelines required. You will work closely with engineering to improve deployment velocity and reliability.",
        "location": "Abuja, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.ONSITE.value,
        "salary_min": 700000,
        "salary_max": 1000000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "amaka@techcorp.ng",
        "seniority_level": SeniorityLevel.MID.value,
        "required_years_experience": 3,
        "required_skills": ["AWS", "Terraform", "Kubernetes", "Docker", "CI/CD"],
        "openings_count": 1,
        "application_deadline": deadline(60),
    },
    {
        "title": "Product Manager",
        "description": "Lead product strategy and roadmap for our B2B SaaS platform. 3+ years of product management experience required. You will work with engineering, design, and sales to define and ship impactful features.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 900000,
        "salary_max": 1400000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "amaka@techcorp.ng",
        "seniority_level": SeniorityLevel.SENIOR.value,
        "required_years_experience": 3,
        "required_skills": ["Agile", "Scrum", "Product Strategy", "SQL"],
        "openings_count": 1,
        "application_deadline": deadline(50),
    },
    {
        "title": "Data Analyst Intern",
        "description": "3-month internship for recent graduates. You will work with our data team to build dashboards and analyse user behaviour using Python and SQL.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.INTERNSHIP.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 80000,
        "salary_max": 120000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "amaka@techcorp.ng",
        "seniority_level": SeniorityLevel.JUNIOR.value,
        "required_years_experience": 0,
        "required_skills": ["Python", "SQL", "Excel"],
        "openings_count": 3,
        "application_deadline": deadline(21),
    },
    {
        "title": "Mobile Developer (Flutter)",
        "description": "Build cross-platform mobile apps for iOS and Android. Strong Dart skills and experience shipping production apps required. You'll own features end-to-end from design to deployment.",
        "location": "Remote",
        "contract_type": ContractType.CONTRACT.value,
        "work_model": WorkModel.REMOTE.value,
        "salary_min": 600000,
        "salary_max": 900000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "amaka@techcorp.ng",
        "seniority_level": SeniorityLevel.MID.value,
        "required_years_experience": 2,
        "required_skills": ["Flutter", "Dart", "REST", "Firebase"],
        "openings_count": 1,
        "application_deadline": deadline(35),
    },
    {
        "title": "QA Engineer",
        "description": "Own quality assurance across our web and mobile products. Experience with Selenium, Cypress, or Playwright preferred. You will write automated test suites and own the release sign-off process.",
        "location": "Port Harcourt, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.ONSITE.value,
        "salary_min": 400000,
        "salary_max": 650000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "amaka@techcorp.ng",
        "seniority_level": SeniorityLevel.MID.value,
        "required_years_experience": 2,
        "required_skills": ["Cypress", "Playwright", "Selenium", "SQL"],
        "openings_count": 1,
        "application_deadline": deadline(40),
    },
    {
        "title": "Technical Writer",
        "description": "Create clear, accurate documentation for our developer APIs and internal tools. You will work closely with engineers and produce API references, tutorials, and integration guides.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.PART_TIME.value,
        "work_model": WorkModel.REMOTE.value,
        "salary_min": 200000,
        "salary_max": 350000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.PENDING.value,  # awaiting review
        "employer_email": "amaka@techcorp.ng",
        "seniority_level": SeniorityLevel.MID.value,
        "required_years_experience": 1,
        "required_skills": ["Technical Writing", "REST", "Markdown"],
        "openings_count": 1,
        "application_deadline": deadline(55),
    },
    {
        "title": "UI/UX Designer",
        "description": "Design intuitive user experiences for our web platform. Proficiency in Figma required. You will run user research sessions, create wireframes, and collaborate with engineers on implementation.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 450000,
        "salary_max": 700000,
        "status": JobStatus.DRAFT.value,
        "moderation_status": ModerationStatus.PENDING.value,
        "employer_email": "amaka@techcorp.ng",
        "seniority_level": SeniorityLevel.MID.value,
        "required_years_experience": 2,
        "required_skills": ["Figma", "Sketch", "User Research"],
        "openings_count": 1,
        "application_deadline": deadline(45),
    },
    {
        "title": "Security Engineer",
        "description": "Lead security reviews, penetration testing, and incident response for our infrastructure. Experience with cloud security and OWASP best practices required.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 1000000,
        "salary_max": 1500000,
        "status": JobStatus.CLOSED.value,
        "moderation_status": ModerationStatus.APPROVED.value,  # was live, now closed
        "employer_email": "amaka@techcorp.ng",
        "seniority_level": SeniorityLevel.SENIOR.value,
        "required_years_experience": 4,
        "required_skills": ["AWS", "Penetration Testing", "OWASP", "Python"],
        "openings_count": 1,
        "application_deadline": deadline(30),
    },

    # ── FinTech Solutions Ltd ─────────────────────────────────────────────────
    {
        "title": "Backend Engineer (Node.js)",
        "description": "Build payment processing APIs and integrations with Nigerian banking infrastructure. Experience with Paystack or Flutterwave a plus. You will own the core transaction processing service.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 700000,
        "salary_max": 1100000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "emeka@fintech.ng",
        "seniority_level": SeniorityLevel.MID.value,
        "required_years_experience": 3,
        "required_skills": ["Node.js", "PostgreSQL", "REST", "Paystack", "Docker"],
        "openings_count": 2,
        "application_deadline": deadline(42),
    },
    {
        "title": "Compliance Officer",
        "description": "Ensure our operations comply with CBN regulations and AML/KYC requirements. You will own regulatory filings and work with the legal team on policy updates.",
        "location": "Abuja, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.ONSITE.value,
        "salary_min": 600000,
        "salary_max": 900000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "emeka@fintech.ng",
        "seniority_level": SeniorityLevel.SENIOR.value,
        "required_years_experience": 4,
        "required_skills": ["AML", "KYC", "CBN Regulations", "Risk Management"],
        "openings_count": 1,
        "application_deadline": deadline(60),
    },
    {
        "title": "Data Scientist",
        "description": "Build fraud detection models and credit scoring algorithms using Python and ML frameworks. You will work with large transaction datasets and deploy models to production.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.REMOTE.value,
        "salary_min": 900000,
        "salary_max": 1300000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "emeka@fintech.ng",
        "seniority_level": SeniorityLevel.SENIOR.value,
        "required_years_experience": 4,
        "required_skills": ["Python", "SQL", "Scikit-learn", "MLOps", "PostgreSQL"],
        "openings_count": 1,
        "application_deadline": deadline(50),
    },
    {
        "title": "Customer Success Manager",
        "description": "Own relationships with our enterprise clients and drive product adoption. You will onboard new clients, run QBRs, and identify expansion opportunities.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 500000,
        "salary_max": 750000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "emeka@fintech.ng",
        "seniority_level": SeniorityLevel.MID.value,
        "required_years_experience": 2,
        "required_skills": ["Account Management", "CRM", "SQL"],
        "openings_count": 2,
        "application_deadline": deadline(30),
    },
    {
        "title": "Android Developer",
        "description": "Build and maintain our Android banking app used by 500k+ customers. You will own the payments and onboarding flows and work with our design system.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 650000,
        "salary_max": 950000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "emeka@fintech.ng",
        "seniority_level": SeniorityLevel.MID.value,
        "required_years_experience": 3,
        "required_skills": ["Kotlin", "Java", "Android SDK", "REST", "Agile"],
        "openings_count": 1,
        "application_deadline": deadline(38),
    },
    {
        "title": "iOS Developer",
        "description": "Build and maintain our iOS banking app. Swift and SwiftUI experience required. You will own new feature development and work closely with the Android team for feature parity.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 650000,
        "salary_max": 950000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.PENDING.value,  # awaiting review
        "employer_email": "emeka@fintech.ng",
        "seniority_level": SeniorityLevel.MID.value,
        "required_years_experience": 3,
        "required_skills": ["Swift", "SwiftUI", "REST", "Xcode", "Agile"],
        "openings_count": 1,
        "application_deadline": deadline(38),
    },
    {
        "title": "Risk Analyst",
        "description": "Analyse credit and operational risk across our lending portfolio. You will build risk scorecards, monitor portfolio health, and present findings to senior leadership.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.ONSITE.value,
        "salary_min": 550000,
        "salary_max": 800000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.PENDING.value,  # awaiting review
        "employer_email": "emeka@fintech.ng",
        "seniority_level": SeniorityLevel.MID.value,
        "required_years_experience": 2,
        "required_skills": ["SQL", "Excel", "Risk Modelling", "Python"],
        "openings_count": 1,
        "application_deadline": deadline(45),
    },
    {
        "title": "Finance Intern",
        "description": "6-month internship supporting our finance team with reconciliation and reporting. You will gain exposure to fintech accounting processes and regulatory reporting.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.INTERNSHIP.value,
        "work_model": WorkModel.ONSITE.value,
        "salary_min": 60000,
        "salary_max": 100000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "emeka@fintech.ng",
        "seniority_level": SeniorityLevel.JUNIOR.value,
        "required_years_experience": 0,
        "required_skills": ["Excel", "Accounting", "SQL"],
        "openings_count": 2,
        "application_deadline": deadline(21),
    },
    {
        "title": "Infrastructure Engineer",
        "description": "Manage our on-premise and cloud infrastructure. Experience with high-availability systems required. You will own uptime SLAs and lead our cloud migration initiative.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 800000,
        "salary_max": 1200000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "emeka@fintech.ng",
        "seniority_level": SeniorityLevel.SENIOR.value,
        "required_years_experience": 5,
        "required_skills": ["AWS", "Terraform", "Kubernetes", "Linux", "CI/CD"],
        "openings_count": 1,
        "application_deadline": deadline(55),
    },
    {
        "title": "Growth Marketing Manager",
        "description": "Drive user acquisition and retention through data-driven marketing campaigns. You will own paid channels, lifecycle email, and A/B testing programmes.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 600000,
        "salary_max": 900000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "emeka@fintech.ng",
        "seniority_level": SeniorityLevel.SENIOR.value,
        "required_years_experience": 3,
        "required_skills": ["Growth Marketing", "SQL", "A/B Testing", "Google Ads"],
        "openings_count": 1,
        "application_deadline": deadline(40),
    },
    {
        "title": "Legal Counsel",
        "description": "Provide legal advice on fintech regulations, contracts, and corporate governance. You will manage external counsel relationships and draft commercial agreements.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.ONSITE.value,
        "salary_min": 1000000,
        "salary_max": 1600000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "emeka@fintech.ng",
        "seniority_level": SeniorityLevel.SENIOR.value,
        "required_years_experience": 5,
        "required_skills": ["Corporate Law", "CBN Regulations", "Contract Drafting"],
        "openings_count": 1,
        "application_deadline": deadline(60),
    },
    {
        "title": "Business Analyst",
        "description": "Bridge the gap between business requirements and technical implementation. You will write specifications, facilitate workshops, and own the requirements backlog.",
        "location": "Abuja, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 500000,
        "salary_max": 750000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "emeka@fintech.ng",
        "seniority_level": SeniorityLevel.MID.value,
        "required_years_experience": 2,
        "required_skills": ["SQL", "Agile", "Requirements Analysis", "Scrum"],
        "openings_count": 1,
        "application_deadline": deadline(35),
    },
    {
        "title": "Support Engineer",
        "description": "Provide technical support to merchants and developers integrating our payment APIs. You will triage issues, write runbooks, and improve our developer documentation.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.REMOTE.value,
        "salary_min": 350000,
        "salary_max": 550000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "emeka@fintech.ng",
        "seniority_level": SeniorityLevel.JUNIOR.value,
        "required_years_experience": 1,
        "required_skills": ["REST", "SQL", "Technical Writing", "Node.js"],
        "openings_count": 2,
        "application_deadline": deadline(28),
    },
    {
        "title": "Scrum Master",
        "description": "Facilitate agile ceremonies and remove blockers for our engineering teams. You will coach teams on scrum best practices and track delivery metrics.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.CONTRACT.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 700000,
        "salary_max": 1000000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.PENDING.value,  # awaiting review
        "employer_email": "emeka@fintech.ng",
        "seniority_level": SeniorityLevel.SENIOR.value,
        "required_years_experience": 4,
        "required_skills": ["Scrum", "Agile", "Jira", "Coaching"],
        "openings_count": 1,
        "application_deadline": deadline(45),
    },
    {
        "title": "Head of Engineering",
        "description": "Lead our 30-person engineering organisation. 8+ years of engineering leadership experience required. You will own our technical strategy, hiring, and engineering culture.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 2000000,
        "salary_max": 3000000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "emeka@fintech.ng",
        "seniority_level": SeniorityLevel.EXECUTIVE.value,
        "required_years_experience": 8,
        "required_skills": ["Engineering Leadership", "System Design", "Agile", "AWS"],
        "openings_count": 1,
        "application_deadline": deadline(75),
    },
    {
        "title": "Database Administrator",
        "description": "Manage and optimise our PostgreSQL and MongoDB databases. You will own query performance, backup strategies, and schema migrations.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 700000,
        "salary_max": 1000000,
        "status": JobStatus.DRAFT.value,
        "moderation_status": ModerationStatus.PENDING.value,
        "employer_email": "emeka@fintech.ng",
        "seniority_level": SeniorityLevel.SENIOR.value,
        "required_years_experience": 4,
        "required_skills": ["PostgreSQL", "MongoDB", "SQL", "Redis"],
        "openings_count": 1,
        "application_deadline": deadline(50),
    },
    {
        "title": "Content Writer",
        "description": "Create engaging content for our blog, social media, and marketing materials. You will own our editorial calendar and write long-form thought leadership pieces.",
        "location": "Remote",
        "contract_type": ContractType.PART_TIME.value,
        "work_model": WorkModel.REMOTE.value,
        "salary_min": 150000,
        "salary_max": 250000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "emeka@fintech.ng",
        "seniority_level": SeniorityLevel.JUNIOR.value,
        "required_years_experience": 1,
        "required_skills": ["Content Writing", "SEO", "Social Media"],
        "openings_count": 1,
        "application_deadline": deadline(30),
    },
    {
        "title": "HR Manager",
        "description": "Own talent acquisition, onboarding, and people operations for our 80-person company. You will build our employer brand and lead diversity hiring initiatives.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.ONSITE.value,
        "salary_min": 600000,
        "salary_max": 900000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "emeka@fintech.ng",
        "seniority_level": SeniorityLevel.SENIOR.value,
        "required_years_experience": 5,
        "required_skills": ["Talent Acquisition", "HR Operations", "Employment Law"],
        "openings_count": 1,
        "application_deadline": deadline(45),
    },
    {
        "title": "Sales Executive",
        "description": "Drive B2B sales of our payment solutions to SMEs and enterprises across Nigeria. You will own a named account list and be responsible for full-cycle deals.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "salary_min": 400000,
        "salary_max": 700000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "emeka@fintech.ng",
        "seniority_level": SeniorityLevel.MID.value,
        "required_years_experience": 2,
        "required_skills": ["B2B Sales", "CRM", "Negotiation"],
        "openings_count": 3,
        "application_deadline": deadline(35),
    },
    {
        "title": "Machine Learning Engineer",
        "description": "Deploy and maintain ML models in production. Experience with MLOps and model serving required. You will build our feature store and own model monitoring pipelines.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.REMOTE.value,
        "salary_min": 1000000,
        "salary_max": 1500000,
        "status": JobStatus.ACTIVE.value,
        "moderation_status": ModerationStatus.APPROVED.value,
        "employer_email": "emeka@fintech.ng",
        "seniority_level": SeniorityLevel.SENIOR.value,
        "required_years_experience": 4,
        "required_skills": ["Python", "MLOps", "Docker", "Kubernetes", "SQL"],
        "openings_count": 1,
        "application_deadline": deadline(60),
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
        "moderation_status": ModerationStatus.APPROVED.value,  # was live, now closed
        "employer_email": "emeka@fintech.ng",
        "seniority_level": SeniorityLevel.MID.value,
        "required_years_experience": 2,
        "required_skills": ["Administration", "Vendor Management"],
        "openings_count": 1,
        "application_deadline": deadline(30),
    },
]


async def seed() -> None:
    """Create seed employers, profiles, and job listings if none exist yet."""
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
