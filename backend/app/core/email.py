"""Email service abstraction for Elevare.

Provides an abstract EmailService interface with two implementations:
- ResendEmailService: sends real emails via the Resend API
- StubEmailService: logs to stdout, used in tests and CI

Wire into FastAPI via get_email_service() dependency.
"""
import logging
from abc import ABC, abstractmethod

from .config import settings

logger = logging.getLogger(__name__)


class EmailService(ABC):
    """Abstract interface for email delivery."""

    @abstractmethod
    async def send_application_confirmation(
        self, candidate_email: str, job_title: str, company_name: str
    ) -> None:
        """Send application received confirmation to candidate."""
        ...

    @abstractmethod
    async def send_status_update(
        self, candidate_email: str, job_title: str, new_status: str
    ) -> None:
        """Notify candidate that their application status has changed."""
        ...

    @abstractmethod
    async def send_employer_notification(
        self, employer_email: str, job_title: str, candidate_name: str
    ) -> None:
        """Notify employer that a new application has been received."""
        ...

    @abstractmethod
    async def send_verification_email(
        self, email: str, verification_token: str, next_url: str | None = None
    ) -> None:
        """Send email address verification link to a new user."""
        ...

    @abstractmethod
    async def send_job_moderation_status(
      self, employer_email: str, job_data: dict, action: str, reason: str | None = None
    ) -> None:
      """Send Job's moderation status to respective employers."""
      ...

    @abstractmethod
    async def send_contact_notification(
        self,
        recipient: str,
        name: str,
        sender_email: str,
        company: str | None,
        message: str,
        inquiry_type: str,
    ) -> None:
        """Notify the Elevare team of a new contact form submission."""
        ...


class ResendEmailService(EmailService):
    """Concrete implementation that delivers email via the Resend API."""

    def __init__(self) -> None:
        """Initialise the service and configure the Resend SDK with the API key."""
        import resend as resend_sdk
        resend_sdk.api_key = settings.resend_api_key
        self._resend = resend_sdk

    async def _send_html(
        self, subject: str, recipients: list[str], html_body: str
    ) -> None:
        """Run the blocking Resend SDK call in a thread pool to avoid blocking the event loop."""
        import asyncio

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self._resend.Emails.send(
                    {
                        "from": settings.mail_from,
                        "to": recipients,
                        "subject": subject,
                        "html": html_body,
                    }
                ),
            )
            logger.info("Email sent to %s — subject: %s", recipients, subject)
        except Exception as exc:
            logger.error("Resend delivery failed to %s: %s", recipients, exc)
            raise

    async def send_application_confirmation(
        self, candidate_email: str, job_title: str, company_name: str
    ) -> None:
        """Send an application-received confirmation email to the candidate."""
        html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F3F4F6;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 16px;">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
        <tr><td style="background:#1E3A5F;padding:28px 32px;text-align:center;">
          <h1 style="color:#ffffff;margin:0;font-size:26px;letter-spacing:1px;">Elevare</h1>
          <p style="color:#93C5FD;margin:4px 0 0;font-size:13px;">Connecting Talent with Opportunity</p>
        </td></tr>
        <tr><td style="padding:36px 32px 24px;">
          <h2 style="color:#1E3A5F;margin:0 0 16px;font-size:20px;">Application Received</h2>
          <p style="color:#374151;line-height:1.6;margin:0 0 12px;">Your application for <strong>{job_title}</strong> at <strong>{company_name}</strong> has been successfully submitted.</p>
          <p style="color:#374151;line-height:1.6;margin:0 0 24px;">The hiring team will review your application and reach out if your profile is a match. You can track your application status on your Elevare dashboard.</p>
        </td></tr>
        <tr><td style="padding:0 32px 36px;text-align:center;">
          <a href="{settings.app_url}/candidate/applications" style="display:inline-block;background:#F59E0B;color:#ffffff;padding:13px 36px;border-radius:6px;text-decoration:none;font-weight:bold;font-size:15px;">View My Applications</a>
        </td></tr>
        <tr><td style="padding:20px 32px;border-top:1px solid #E5E7EB;text-align:center;">
          <p style="color:#9CA3AF;font-size:12px;margin:0;">© 2025 Elevare. All rights reserved.</p>
          <p style="color:#9CA3AF;font-size:12px;margin:4px 0 0;">You received this email because you applied for a job on Elevare.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
        await self._send_html(
            subject=f"Application Received: {job_title}",
            recipients=[candidate_email],
            html_body=html_body,
        )

    async def send_status_update(
        self, candidate_email: str, job_title: str, new_status: str
    ) -> None:
        """Send a status update email to the candidate when their application status changes."""
        status_colours: dict[str, str] = {
            "reviewing":   "#3B82F6",
            "shortlisted": "#10B981",
            "hired":       "#065F46",
            "rejected":    "#EF4444",
            "withdrawn":   "#6B7280",
        }
        badge_colour = status_colours.get(new_status.lower(), "#6B7280")

        html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F3F4F6;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 16px;">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
        <tr><td style="background:#1E3A5F;padding:28px 32px;text-align:center;">
          <h1 style="color:#ffffff;margin:0;font-size:26px;letter-spacing:1px;">Elevare</h1>
          <p style="color:#93C5FD;margin:4px 0 0;font-size:13px;">Connecting Talent with Opportunity</p>
        </td></tr>
        <tr><td style="padding:36px 32px 24px;">
          <h2 style="color:#1E3A5F;margin:0 0 16px;font-size:20px;">Application Status Update</h2>
          <p style="color:#374151;line-height:1.6;margin:0 0 20px;">Your application for <strong>{job_title}</strong> has been updated.</p>
          <table cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
            <tr>
              <td style="color:#374151;font-size:14px;padding-right:12px;">New Status:</td>
              <td><span style="background:{badge_colour};color:#ffffff;padding:4px 14px;border-radius:20px;font-size:13px;font-weight:bold;">{new_status.capitalize()}</span></td>
            </tr>
          </table>
          <p style="color:#374151;line-height:1.6;margin:0 0 24px;">Log in to your dashboard to view the full details of your application.</p>
        </td></tr>
        <tr><td style="padding:0 32px 36px;text-align:center;">
          <a href="{settings.app_url}/candidate/applications" style="display:inline-block;background:#F59E0B;color:#ffffff;padding:13px 36px;border-radius:6px;text-decoration:none;font-weight:bold;font-size:15px;">View My Applications</a>
        </td></tr>
        <tr><td style="padding:20px 32px;border-top:1px solid #E5E7EB;text-align:center;">
          <p style="color:#9CA3AF;font-size:12px;margin:0;">© 2025 Elevare. All rights reserved.</p>
          <p style="color:#9CA3AF;font-size:12px;margin:4px 0 0;">You received this email because you have an active application on Elevare.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
        await self._send_html(
            subject=f"Application Update: {job_title}",
            recipients=[candidate_email],
            html_body=html_body,
        )

    async def send_employer_notification(
        self, employer_email: str, job_title: str, candidate_name: str
    ) -> None:
        """Notify an employer by email that a new application has been received."""
        html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F3F4F6;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 16px;">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
        <tr><td style="background:#1E3A5F;padding:28px 32px;text-align:center;">
          <h1 style="color:#ffffff;margin:0;font-size:26px;letter-spacing:1px;">Elevare</h1>
          <p style="color:#93C5FD;margin:4px 0 0;font-size:13px;">Connecting Talent with Opportunity</p>
        </td></tr>
        <tr><td style="padding:36px 32px 24px;">
          <h2 style="color:#1E3A5F;margin:0 0 16px;font-size:20px;">New Application Received</h2>
          <p style="color:#374151;line-height:1.6;margin:0 0 12px;">A new application has been submitted for your job posting <strong>{job_title}</strong>.</p>
          <table cellpadding="0" cellspacing="0" style="background:#F9FAFB;border-radius:6px;padding:16px;margin:0 0 24px;width:100%;">
            <tr><td style="color:#6B7280;font-size:13px;padding-bottom:6px;">Candidate</td></tr>
            <tr><td style="color:#1E3A5F;font-size:16px;font-weight:bold;">{candidate_name}</td></tr>
          </table>
          <p style="color:#374151;line-height:1.6;margin:0 0 24px;">Review their profile and CV on your Elevare dashboard.</p>
        </td></tr>
        <tr><td style="padding:0 32px 36px;text-align:center;">
          <a href="{settings.app_url}/employer/applications" style="display:inline-block;background:#F59E0B;color:#ffffff;padding:13px 36px;border-radius:6px;text-decoration:none;font-weight:bold;font-size:15px;">Review Application</a>
        </td></tr>
        <tr><td style="padding:20px 32px;border-top:1px solid #E5E7EB;text-align:center;">
          <p style="color:#9CA3AF;font-size:12px;margin:0;">© 2025 Elevare. All rights reserved.</p>
          <p style="color:#9CA3AF;font-size:12px;margin:4px 0 0;">You received this email because you have an active job posting on Elevare.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
        await self._send_html(
            subject=f"New Application: {job_title}",
            recipients=[employer_email],
            html_body=html_body,
        )

    async def send_verification_email(
        self, email: str, verification_token: str, next_url: str | None = None
    ) -> None:
        """Send an email address verification link to the newly registered user."""
        verification_link = f"{settings.app_url}/verify-email?token={verification_token}"
        if next_url:
            from urllib.parse import quote
            verification_link += f"&next={quote(next_url, safe='')}"
        html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F3F4F6;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 16px;">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
        <tr><td style="background:#1E3A5F;padding:28px 32px;text-align:center;">
          <h1 style="color:#ffffff;margin:0;font-size:26px;letter-spacing:1px;">Elevare</h1>
          <p style="color:#93C5FD;margin:4px 0 0;font-size:13px;">Connecting Talent with Opportunity</p>
        </td></tr>
        <tr><td style="padding:36px 32px 24px;">
          <h2 style="color:#1E3A5F;margin:0 0 16px;font-size:20px;">Verify Your Email Address</h2>
          <p style="color:#374151;line-height:1.6;margin:0 0 24px;">Thanks for signing up. Click the button below to verify your email address and activate your account. This link expires in 24 hours.</p>
        </td></tr>
        <tr><td style="padding:0 32px 36px;text-align:center;">
          <a href="{verification_link}" style="display:inline-block;background:#F59E0B;color:#ffffff;padding:13px 36px;border-radius:6px;text-decoration:none;font-weight:bold;font-size:15px;">Verify Email</a>
        </td></tr>
        <tr><td style="padding:0 32px 24px;">
          <p style="color:#6B7280;font-size:13px;line-height:1.6;margin:0;">If the button doesn't work, copy and paste this link into your browser:<br/>
          <a href="{verification_link}" style="color:#1E3A5F;word-break:break-all;">{verification_link}</a></p>
        </td></tr>
        <tr><td style="padding:20px 32px;border-top:1px solid #E5E7EB;text-align:center;">
          <p style="color:#9CA3AF;font-size:12px;margin:0;">© 2025 Elevare. All rights reserved.</p>
          <p style="color:#9CA3AF;font-size:12px;margin:4px 0 0;">If you didn't create an account, you can safely ignore this email.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
        await self._send_html(
            subject="Verify Your Email Address — Elevare",
            recipients=[email],
            html_body=html_body,
        )

    async def send_contact_notification(
        self,
        recipient: str,
        name: str,
        sender_email: str,
        company: str | None,
        message: str,
        inquiry_type: str,
    ) -> None:
        """Send a new contact form submission notification to the Elevare team."""
        label = "Employer Inquiry" if inquiry_type == "employer_inquiry" else "General Contact"
        company_row = f"<tr><td style='color:#6B7280;font-size:13px;padding-bottom:4px;'>Company</td><td style='color:#111827;font-size:14px;'>{company}</td></tr>" if company else ""
        html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#F3F4F6;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 16px;">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
        <tr><td style="background:#1E3A5F;padding:24px 32px;text-align:center;">
          <h1 style="color:#fff;margin:0;font-size:22px;">Elevare — New {label}</h1>
        </td></tr>
        <tr><td style="padding:28px 32px;">
          <table cellpadding="6" cellspacing="0" style="width:100%;border-collapse:collapse;">
            <tr><td style="color:#6B7280;font-size:13px;padding-bottom:4px;">Name</td><td style="color:#111827;font-size:14px;">{name}</td></tr>
            <tr><td style="color:#6B7280;font-size:13px;padding-bottom:4px;">Email</td><td style="color:#111827;font-size:14px;">{sender_email}</td></tr>
            {company_row}
            <tr><td style="color:#6B7280;font-size:13px;padding-bottom:4px;">Type</td><td style="color:#111827;font-size:14px;">{label}</td></tr>
          </table>
          <hr style="border:none;border-top:1px solid #E5E7EB;margin:20px 0;"/>
          <p style="color:#374151;font-size:14px;line-height:1.7;white-space:pre-wrap;">{message}</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
        await self._send_html(
            subject=f"[Elevare] New {label} from {name}",
            recipients=[recipient],
            html_body=html_body,
        )

    async def send_job_moderation_status(
        self, employer_email: str, job_data: dict, action: str, reason: str | None = None
    ) -> None:
        """Notify employer of job approval or rejection, with a publish link on approval."""
        job_id = job_data['id']
        job_title = job_data['title']

        if action == "APPROVED":
            subject = f"Your job listing has been approved — {job_title}"
            cta_url = f"{settings.app_url}/employer/jobs/{job_id}/publish"
            action_block = f"""
          <p style="color:#374151;line-height:1.6;margin:0 0 24px;">
            Your job listing <strong>{job_title}</strong> has been reviewed and approved.
            Click below to publish it and start receiving applications.
          </p>
        </td></tr>
        <tr><td style="padding:0 32px 36px;text-align:center;">
          <a href="{cta_url}" style="display:inline-block;background:#F59E0B;color:#ffffff;padding:13px 36px;border-radius:6px;text-decoration:none;font-weight:bold;font-size:15px;">Publish Job Now</a>"""
        else:
            subject = f"Your job listing requires changes — {job_title}"
            cta_url = f"{settings.app_url}/employer/jobs/{job_id}/edit"
            reason_block = f"<p style='color:#374151;line-height:1.6;margin:12px 0 0;'><strong>Reason:</strong> {reason}</p>" if reason else ""
            action_block = f"""
          <p style="color:#374151;line-height:1.6;margin:0 0 12px;">
            Your job listing <strong>{job_title}</strong> was not approved at this time.
          </p>
          {reason_block}
          <p style="color:#374151;line-height:1.6;margin:12px 0 24px;">
            Please review the feedback, update your listing, and resubmit for approval.
          </p>
        </td></tr>
        <tr><td style="padding:0 32px 36px;text-align:center;">
          <a href="{cta_url}" style="display:inline-block;background:#1E3A5F;color:#ffffff;padding:13px 36px;border-radius:6px;text-decoration:none;font-weight:bold;font-size:15px;">Edit Job Listing</a>"""

        html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F3F4F6;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 16px;">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
        <tr><td style="background:#1E3A5F;padding:28px 32px;text-align:center;">
          <h1 style="color:#ffffff;margin:0;font-size:26px;letter-spacing:1px;">Elevare</h1>
          <p style="color:#93C5FD;margin:4px 0 0;font-size:13px;">Connecting Talent with Opportunity</p>
        </td></tr>
        <tr><td style="padding:36px 32px 24px;">
          <h2 style="color:#1E3A5F;margin:0 0 16px;font-size:20px;">Job Listing {'Approved' if action == 'APPROVED' else 'Not Approved'}</h2>
          {action_block}
        </td></tr>
        <tr><td style="padding:20px 32px;border-top:1px solid #E5E7EB;text-align:center;">
          <p style="color:#9CA3AF;font-size:12px;margin:0;">© 2025 Elevare. All rights reserved.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
        await self._send_html(subject=subject, recipients=[employer_email], html_body=html_body)


class StubEmailService(EmailService):
    """Concrete implementation that logs to stdout — used in tests and CI."""

    async def send_application_confirmation(
        self, candidate_email: str, job_title: str, company_name: str
    ) -> None:
        """Log a stub application confirmation email."""
        logger.info(
            "STUB EMAIL SENT to %s: Application confirmation for %s at %s",
            candidate_email,
            job_title,
            company_name,
        )

    async def send_status_update(
        self, candidate_email: str, job_title: str, new_status: str
    ) -> None:
        """Log a stub application status update email."""
        logger.info(
            "STUB EMAIL SENT to %s: Status update for %s (now %s)",
            candidate_email,
            job_title,
            new_status,
        )

    async def send_employer_notification(
        self, employer_email: str, job_title: str, candidate_name: str
    ) -> None:
        """Log a stub employer new-application notification email."""
        logger.info(
            "STUB EMAIL SENT to %s: New application for %s by %s",
            employer_email,
            job_title,
            candidate_name,
        )

    async def send_verification_email(
        self, email: str, verification_token: str, next_url: str | None = None
    ) -> None:
        """Log a stub email verification email with a full clickable link."""
        from urllib.parse import quote
        link = f"{settings.app_url}/verify-email?token={verification_token}"
        if next_url:
            link += f"&next={quote(next_url, safe='')}"
        logger.info(
            "STUB VERIFICATION EMAIL to %s — click to verify:\n%s",
            email,
            link,
        )

    async def send_job_moderation_status(
      self, employer_email: str, job_data: dict, action: str, reason: str | None = None
    ) -> None:
      """Log stub job moderation status with the correct action link."""
      job_id = job_data['id']
      if action == "APPROVED":
          cta_url = f"{settings.app_url}/employer/jobs/{job_id}/publish"
          label = "Publish link"
      else:
          cta_url = f"{settings.app_url}/employer/jobs/{job_id}/edit"
          label = "Edit link"
      logger.info(
        "STUB JOB MODERATION to %s: Job '%s' action=%s reason=%s\n%s: %s",
        employer_email,
        job_data['title'],
        action,
        reason,
        label,
        cta_url,
      )

    async def send_contact_notification(
        self,
        recipient: str,
        name: str,
        sender_email: str,
        company: str | None,
        message: str,
        inquiry_type: str,
    ) -> None:
        """Log a stub contact form notification email."""
        logger.info(
            "STUB EMAIL SENT to %s: Contact form from %s (%s) — type=%s",
            recipient,
            name,
            sender_email,
            inquiry_type,
        )


def get_email_service() -> EmailService:
    """FastAPI dependency — returns ResendEmailService in production, StubEmailService in CI."""
    if settings.email_stub_mode or not settings.resend_api_key:
        return StubEmailService()
    return ResendEmailService()
