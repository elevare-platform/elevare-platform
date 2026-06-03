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

from app.modules.applications.models import Application
from app.modules.auth.models import EmailVerificationToken, InviteToken, RefreshToken
from app.modules.candidates.models import (
    CandidateCvs,
    CandidateDocuments,
    CandidateProfile,
    WorkExperience,
    Education,
    Certification,
)
from app.modules.jobs.models import Job
from app.modules.users.models import (
    User,
    EmployerProfile,
    UserProfile
)

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
    "User",
    "UserProfile",
    "EmployerProfile",
    "Application",
]
