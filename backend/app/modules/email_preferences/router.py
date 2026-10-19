"""Endpoints for turning emails off and on.

Public (signed link from an email, no login):
  GET  /unsubscribe?token=   what the unsubscribe page shows (does NOT change anything)
  POST /unsubscribe?token=   turn emails off; also what a mail client's own Unsubscribe
                             button calls (RFC 8058 one-click)
  POST /resubscribe?token=   turn them back on (the page's "changed your mind")

Signed in:
  GET  /me                   is the account's address receiving emails?
  PUT  /me                   turn them on or off

Opening the link is a GET that only shows a page; the change happens on a POST, because
email security scanners open every link in a message, and a link that unsubscribed on
GET would unsubscribe people who never asked.
"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.limiter import limiter
from app.modules.email_preferences.schemas import (
    EmailPreferenceResponse,
    EmailPreferenceUpdate,
)
from app.modules.email_preferences.service import EmailPreferenceService
from app.modules.users.models import User

router = APIRouter()

# A signed token is about 120 characters; this only stops absurd input.
TokenQuery = Query(..., min_length=1, max_length=1000)


@router.get("/unsubscribe", response_model=EmailPreferenceResponse)
@limiter.limit("30/minute")
async def preview_unsubscribe(
    request: Request,
    token: str = TokenQuery,
    db: AsyncSession = Depends(get_db),
):
    return await EmailPreferenceService(db).preview(token)


@router.post("/unsubscribe", response_model=EmailPreferenceResponse)
@limiter.limit("30/minute")
async def unsubscribe(
    request: Request,
    token: str = TokenQuery,
    db: AsyncSession = Depends(get_db),
):
    return await EmailPreferenceService(db).unsubscribe_by_token(token)


@router.post("/resubscribe", response_model=EmailPreferenceResponse)
@limiter.limit("30/minute")
async def resubscribe(
    request: Request,
    token: str = TokenQuery,
    db: AsyncSession = Depends(get_db),
):
    return await EmailPreferenceService(db).resubscribe_by_token(token)


@router.get("/me", response_model=EmailPreferenceResponse)
async def get_my_email_preference(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await EmailPreferenceService(db).get_for_account(current_user.email)


@router.put("/me", response_model=EmailPreferenceResponse)
async def set_my_email_preference(
    data: EmailPreferenceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await EmailPreferenceService(db).set_for_account(
        current_user.email, data.emails_enabled
    )
