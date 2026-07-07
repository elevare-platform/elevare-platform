"""Central registry for all SQLAlchemy ORM models.

This module imports every model class defined in the application. It is
critical for two reasons:
1.  **Alembic Autogenerate**: Alembic needs all models to be imported into
    its environment to correctly detect schema changes.
2.  **SQLAlchemy Mapper**: Models referencing each other via string-based
    class names (e.g., ``relationship("User", ...)``) require the referenced
    models to be loaded into the registry first.

Import order generally follows dependency hierarchy to avoid resolution
issues during initialization.
"""

from app.modules.admin.models import AuditLog
from app.modules.ai.models import CVParsingCost, ParsedCVSubmission
from app.modules.applications.models import Application
from app.modules.auth.models import EmailVerificationToken, InviteToken, RefreshToken
from app.modules.candidates.models import (
    CandidateCvs,
    CandidateDocuments,
    CandidateProfile,
    Certification,
    Education,
    WorkExperience,
)
from app.modules.contact.models import ContactSubmission
from app.modules.jobs.models import Job, JobAccessTokens
from app.modules.talent_pool.models import TalentPoolProfiles
from app.modules.testimonials.models import Testimonial
from app.modules.users.models import EmployerProfile, User, UserProfile

__all__ = [
    "EmailVerificationToken",
    "InviteToken",
    "RefreshToken",
    "CandidateProfile",
    "CandidateCvs",
    "CandidateDocuments",
    "WorkExperience",
    "Certification",
    "Education",
    "Job",
    "JobAccessTokens",
    "TalentPoolProfiles",
    "User",
    "UserProfile",
    "EmployerProfile",
    "Application",
    "AuditLog",
    "ContactSubmission",
    "ParsedCVSubmission",
    "CVParsingCost",
    "Testimonial",
]
