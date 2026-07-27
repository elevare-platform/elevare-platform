"""HTTP endpoints for the users module.

User-facing profile endpoints (candidate profile, avatar) will be added in Phase 4.
Employer-specific endpoints live in app.modules.employer.router.
"""

from fastapi import APIRouter

router = APIRouter()
