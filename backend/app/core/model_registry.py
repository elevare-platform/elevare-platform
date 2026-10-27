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
from app.modules.ai.models import CVParsingCost, FitScoringCost, ParsedCVSubmission
from app.modules.applications.models import Application
from app.modules.auth.models import EmailVerificationToken, InviteToken, RefreshToken
from app.modules.billing.models import (
    CreditPackage,
    Payment,
    Plan,
    PlanGateExemption,
    Subscription,
    WebhookEvent,
)
from app.modules.candidates.models import (
    CandidateCvs,
    CandidateDocuments,
    CandidateProfile,
    Certification,
    Education,
    WorkExperience,
)
from app.modules.contact.models import ContactSubmission
from app.modules.credits.models import CreditTransaction, EmployerCredits
from app.modules.email_preferences.models import EmailSuppression
from app.modules.employer.models import KYCDocument
from app.modules.ingestion.models import IngestionImportRun, MailIntegration
from app.modules.interview_list.models import InterviewListEntry
from app.modules.interview_share.models import InterviewShareLink
from app.modules.interviews.models import (
    Interview,
    InterviewConductEvent,
    InterviewCost,
    InterviewTurn,
    InterviewWeightedScore,
    JobInterviewQuestion,
    JobInterviewSettings,
    JobScoringProfile,
    StrictInterviewRun,
)
from app.modules.introductions.models import IntroductionRequest
from app.modules.jobs.models import Job, JobAccessTokens
from app.modules.notifications.models import Notification
from app.modules.onboarding.models import UserOnboarding
from app.modules.saved_candidates.models import SavedCandidate
from app.modules.seen.models import (
    ApplicationView,
    EmployerSeenBaseline,
    SharedLinkItemView,
    SharedLinkVisit,
    TalentPoolProfileView,
)
from app.modules.talent_pool.models import TalentPoolProfiles
from app.modules.testimonials.models import Testimonial
from app.modules.users.models import Organization, User, UserProfile

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
    "Organization",
    "Application",
    "AuditLog",
    "ContactSubmission",
    "ParsedCVSubmission",
    "CVParsingCost",
    "FitScoringCost",
    "Testimonial",
    "MailIntegration",
    "IngestionImportRun",
    "EmployerCredits",
    "CreditTransaction",
    "EmailSuppression",
    "IntroductionRequest",
    "KYCDocument",
    "Notification",
    "SavedCandidate",
    "EmployerSeenBaseline",
    "TalentPoolProfileView",
    "ApplicationView",
    "SharedLinkVisit",
    "SharedLinkItemView",
    "InterviewListEntry",
    "JobInterviewQuestion",
    "JobInterviewSettings",
    "StrictInterviewRun",
    "JobScoringProfile",
    "InterviewWeightedScore",
    "InterviewTurn",
    "InterviewConductEvent",
    "InterviewShareLink",
    "UserOnboarding",
    "Interview",
    "InterviewCost",
    "Plan",
    "PlanGateExemption",
    "CreditPackage",
    "Subscription",
    "Payment",
    "WebhookEvent",
]
