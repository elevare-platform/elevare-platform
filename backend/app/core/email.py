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
        self,
        employer_email: str,
        job_data: dict,
        action: str,
        reason: str | None = None,
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


def _render_email_layout(
    title: str,
    preheader: str,
    body_content_html: str,
    footer_note: str,
) -> str:
    """Wraps email content in a premium, modern, responsive layout."""
    from datetime import datetime

    current_year = datetime.now().year

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <meta name="supported-color-schemes" content="light">
  <title>{title}</title>
  <!--[if mso]>
  <noscript>
    <xml>
      <o:OfficeDocumentSettings>
        <o:AllowPNG/>
        <o:PixelsPerInch>96</o:PixelsPerInch>
      </o:OfficeDocumentSettings>
    </xml>
  </noscript>
  <![endif]-->
  <style>
    :root {{
      color-scheme: light;
      supported-color-schemes: light;
    }}
    body {{
      width: 100% !important;
      height: 100% !important;
      margin: 0 !important;
      padding: 0 !important;
      -webkit-text-size-adjust: 100%;
      -ms-text-size-adjust: 100%;
      background-color: #F8FAFC;
    }}
    table {{
      border-collapse: collapse;
      border-spacing: 0;
      mso-table-lspace: 0pt;
      mso-table-rspace: 0pt;
    }}
    img {{
      border: 0;
      height: auto;
      line-height: 100%;
      outline: none;
      text-decoration: none;
    }}
    .email-container {{
      max-width: 600px;
      margin: 40px auto;
      background-color: #ffffff;
      border: 1px solid #E2E8F0;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 4px 6px -1px rgba(15, 23, 42, 0.03), 0 2px 4px -1px rgba(15, 23, 42, 0.02);
    }}
    @media only screen and (max-width: 600px) {{
      .email-container {{
        margin: 0 !important;
        width: 100% !important;
        border-radius: 0 !important;
        border-left: none !important;
        border-right: none !important;
      }}
      .email-padding {{
        padding: 24px 20px !important;
      }}
    }}
  </style>
</head>
<body style="background-color: #F8FAFC; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased; margin: 0; padding: 0;">
  <div style="display: none; max-height: 0px; max-width: 0px; opacity: 0; overflow: hidden; mso-hide: all; font-size: 1px; color: #F8FAFC; line-height: 1px;">
    {preheader}
  </div>

  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #F8FAFC; min-width: 100%;">
    <tr>
      <td align="center" style="padding: 12px 12px 40px 12px;">
        <table class="email-container" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #ffffff; max-width: 600px; width: 100%;">
          <!-- Logo Header -->
          <tr>
            <td style="padding: 32px 32px 0 32px;" class="email-padding">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td align="left">
                    <a href="{settings.app_url}" target="_blank" style="text-decoration: none;">
                      <span style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 22px; font-weight: 800; color: #1A4D8F; letter-spacing: -0.5px;">elevare</span>
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          
          <!-- Content Body -->
          <tr>
            <td style="padding: 24px 32px 40px 32px;" class="email-padding">
              {body_content_html}
            </td>
          </tr>
        </table>
        
        <!-- Footer -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; width: 100%;">
          <tr>
            <td align="center" style="padding: 24px 20px 0 20px; text-align: center;">
              <p style="margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; line-height: 1.5; color: #64748B; font-weight: 400;">
                © {current_year} Elevare. All rights reserved.
              </p>
              <p style="margin: 4px 0 0 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; line-height: 1.5; color: #94A3B8; font-weight: 400;">
                {footer_note}
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _render_button(text: str, link: str, is_primary: bool = True) -> str:
    """Helper to render a styled, client-safe HTML button."""
    if is_primary:
        bg_color = "#1A4D8F"
        border_color = "#1A4D8F"
        text_color = "#FFFFFF"
    else:
        bg_color = "#FFFFFF"
        border_color = "#E2E8F0"
        text_color = "#1A4D8F"

    return f"""
    <table cellpadding="0" cellspacing="0" border="0" style="margin: 24px 0;">
      <tr>
        <td align="center" style="border-radius: 8px; background-color: {bg_color};">
          <a href="{link}" target="_blank" style="display: inline-block; padding: 12px 28px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; font-weight: 600; line-height: 1.5; text-decoration: none; color: {text_color}; background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 8px; text-align: center;">{text}</a>
        </td>
      </tr>
    </table>
    """


def _render_badge(status: str) -> str:
    """Helper to render a styled badge for application status."""
    status_lower = status.lower()

    palettes = {
        "reviewing": ("#EFF6FF", "#1D4ED8", "#DBEAFE"),
        "shortlisted": ("#ECFDF5", "#047857", "#D1FAE5"),
        "hired": ("#F0FDF4", "#15803D", "#DCFCE7"),
        "rejected": ("#FEF2F2", "#B91C1C", "#FEE2E2"),
        "withdrawn": ("#F8FAFC", "#475569", "#E2E8F0"),
    }

    bg_color, text_color, border_color = palettes.get(
        status_lower, ("#F8FAFC", "#475569", "#E2E8F0")
    )

    return f"""<span style="display: inline-block; background-color: {bg_color}; color: {text_color}; border: 1px solid {border_color}; padding: 4px 12px; border-radius: 9999px; font-size: 13px; font-weight: 600; text-transform: capitalize; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; vertical-align: middle;">{status}</span>"""


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
        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">Application Received</h2>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">Your application for <strong>{job_title}</strong> at <strong>{company_name}</strong> has been successfully submitted.</p>
        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">The hiring team will review your credentials and get in touch if your profile aligns with their needs. You can monitor the progress of your application on your dashboard.</p>
        
        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 20px; margin: 24px 0; text-align: left;">
          <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; font-weight: 700; color: #1A4D8F; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">Application Details</div>
          <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 16px; font-weight: 600; color: #0F172A; margin-bottom: 4px;">{job_title}</div>
          <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; color: #64748B;">{company_name}</div>
        </div>

        {_render_button("View My Applications", f"{settings.app_url}/candidate/applications")}
        """

        html_body = _render_email_layout(
            title=f"Application Received: {job_title}",
            preheader=f"Your application for {job_title} at {company_name} has been successfully submitted.",
            body_content_html=body_content_html,
            footer_note="You received this email because you applied for a job on Elevare.",
        )

        await self._send_html(
            subject=f"Application Received: {job_title}",
            recipients=[candidate_email],
            html_body=html_body,
        )

    async def send_status_update(
        self, candidate_email: str, job_title: str, new_status: str
    ) -> None:
        """Send a status update email to the candidate when their application status changes."""
        badge_html = _render_badge(new_status)

        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">Application Status Update</h2>
        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">Your job application has been updated with a new status.</p>
        
        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 20px; margin: 24px 0; text-align: left;">
          <table cellpadding="0" cellspacing="0" border="0" width="100%">
            <tr>
              <td style="padding-bottom: 16px;">
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px;">Role</div>
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 16px; font-weight: 600; color: #0F172A;">{job_title}</div>
              </td>
            </tr>
            <tr>
              <td style="border-top: 1px solid #E2E8F0; padding-top: 16px;">
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">New Status</div>
                {badge_html}
              </td>
            </tr>
          </table>
        </div>

        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">Log in to your Elevare dashboard to view the complete details and next steps.</p>

        {_render_button("View My Applications", f"{settings.app_url}/candidate/applications")}
        """

        html_body = _render_email_layout(
            title=f"Application Update: {job_title}",
            preheader=f"Your application status for {job_title} is now {new_status.capitalize()}.",
            body_content_html=body_content_html,
            footer_note="You received this email because you have an active application on Elevare.",
        )

        await self._send_html(
            subject=f"Application Update: {job_title}",
            recipients=[candidate_email],
            html_body=html_body,
        )

    async def send_employer_notification(
        self, employer_email: str, job_title: str, candidate_name: str
    ) -> None:
        """Notify an employer by email that a new application has been received."""
        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">New Application Received</h2>
        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">A new candidate has applied to your job posting.</p>
        
        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 24px; margin: 24px 0; text-align: left;">
          <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; font-weight: 700; color: #1A4D8F; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">Candidate Name</div>
          <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 18px; font-weight: 700; color: #0F172A; margin-bottom: 12px;">{candidate_name}</div>
          <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; color: #475569;">Applied for <strong style="color: #0F172A;">{job_title}</strong></div>
        </div>

        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">Review their profile, resume, and AI match score on your Elevare employer dashboard.</p>

        {_render_button("Review Application", f"{settings.app_url}/employer/applications")}
        """

        html_body = _render_email_layout(
            title=f"New Application: {job_title}",
            preheader=f"New application received from {candidate_name} for your job {job_title}.",
            body_content_html=body_content_html,
            footer_note="You received this email because you have an active job posting on Elevare.",
        )

        await self._send_html(
            subject=f"New Application: {job_title}",
            recipients=[employer_email],
            html_body=html_body,
        )

    async def send_verification_email(
        self, email: str, verification_token: str, next_url: str | None = None
    ) -> None:
        """Send an email address verification link to the newly registered user."""
        verification_link = (
            f"{settings.app_url}/verify-email?token={verification_token}"
        )
        if next_url:
            from urllib.parse import quote

            verification_link += f"&next={quote(next_url, safe='')}"

        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">Verify Your Email Address</h2>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">Welcome to Elevare! Click the button below to verify your email address and activate your account. This link will expire in 24 hours.</p>
        
        {_render_button("Verify Email", verification_link)}
        
        <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top: 24px; border-top: 1px solid #E2E8F0; padding-top: 20px;">
          <tr>
            <td>
              <p style="margin: 0 0 8px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; line-height: 1.5; color: #64748B; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Trouble clicking the button?</p>
              <p style="margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; line-height: 1.5; color: #1A4D8F; word-break: break-all;">
                <a href="{verification_link}" target="_blank" style="color: #1A4D8F; text-decoration: none; word-break: break-all;">{verification_link}</a>
              </p>
            </td>
          </tr>
        </table>
        """

        html_body = _render_email_layout(
            title="Verify Your Email Address",
            preheader="Verify your email address to activate your Elevare account.",
            body_content_html=body_content_html,
            footer_note="If you didn't create an account, you can safely ignore this email.",
        )

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
        label = (
            "Employer Inquiry"
            if inquiry_type == "employer_inquiry"
            else "General Contact"
        )
        company_row = (
            f"""
        <tr>
          <td style="padding: 10px 0; border-bottom: 1px solid #F1F5F9; font-weight: 600; color: #475569; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">Company</td>
          <td style="padding: 10px 0; border-bottom: 1px solid #F1F5F9; color: #0F172A; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">{company}</td>
        </tr>
        """
            if company
            else ""
        )

        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">New Contact Submission</h2>
        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">A new inquiry has been submitted via the Elevare website.</p>
        
        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 24px; margin: 24px 0; text-align: left;">
          <table cellpadding="0" cellspacing="0" border="0" width="100%" style="font-size: 14px; line-height: 1.5;">
            <tr>
              <td style="padding: 10px 0; border-bottom: 1px solid #F1F5F9; font-weight: 600; color: #475569; width: 120px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">Name</td>
              <td style="padding: 10px 0; border-bottom: 1px solid #F1F5F9; color: #0F172A; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">{name}</td>
            </tr>
            <tr>
              <td style="padding: 10px 0; border-bottom: 1px solid #F1F5F9; font-weight: 600; color: #475569; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">Email</td>
              <td style="padding: 10px 0; border-bottom: 1px solid #F1F5F9; color: #1A4D8F; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;"><a href="mailto:{sender_email}" style="color: #1A4D8F; text-decoration: none;">{sender_email}</a></td>
            </tr>
            {company_row}
            <tr>
              <td style="padding: 10px 0; font-weight: 600; color: #475569; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">Type</td>
              <td style="padding: 10px 0; color: #0F172A; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">{label}</td>
            </tr>
          </table>
        </div>
        
        <div style="background-color: #ffffff; border: 1px solid #E2E8F0; border-radius: 12px; padding: 24px; text-align: left; margin-top: 20px;">
          <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; font-weight: 700; color: #1A4D8F; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px;">Message</div>
          <p style="margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #0F172A; white-space: pre-wrap;">{message}</p>
        </div>
        """

        html_body = _render_email_layout(
            title=f"New contact form submission — {name}",
            preheader=f"New {label} inquiry from {name}.",
            body_content_html=body_content_html,
            footer_note="Elevare Team Internal Notification.",
        )

        await self._send_html(
            subject=f"[Elevare] New {label} from {name}",
            recipients=[recipient],
            html_body=html_body,
        )

    async def send_job_moderation_status(
        self,
        employer_email: str,
        job_data: dict,
        action: str,
        reason: str | None = None,
    ) -> None:
        """Notify employer of job approval or rejection, with a publish link on approval."""
        job_id = job_data["id"]
        job_title = job_data["title"]

        if action == "APPROVED":
            subject = f"Your job listing has been approved — {job_title}"
            cta_url = f"{settings.app_url}/employer/jobs/{job_id}/publish"

            body_content_html = f"""
            <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">Job Listing Approved</h2>
            
            <div style="background-color: #ECFDF5; border: 1px solid #D1FAE5; border-radius: 12px; padding: 24px; margin: 24px 0; text-align: left;">
              <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; font-weight: 700; color: #047857; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">Status</div>
              <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 16px; font-weight: 700; color: #065F46; margin-bottom: 8px;">Approved & Ready to Publish</div>
              <p style="margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; line-height: 1.5; color: #065F46;">Your job listing <strong>{job_title}</strong> has been approved by our team. You can now publish it to make it visible to candidates and start receiving applications.</p>
            </div>

            {_render_button("Publish Job Now", cta_url)}
            """
        else:
            subject = f"Your job listing requires changes — {job_title}"
            cta_url = f"{settings.app_url}/employer/jobs/{job_id}/edit"

            reason_block = (
                f"""
            <div style="background-color: #ffffff; border: 1px solid #FCD34D; border-radius: 8px; padding: 16px; margin-top: 16px;">
              <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; font-weight: 700; color: #78350F; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px;">Moderator Feedback</div>
              <p style="margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; line-height: 1.5; color: #78350F; font-style: italic;">"{reason}"</p>
            </div>
            """
                if reason
                else ""
            )

            body_content_html = f"""
            <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">Job Listing Requires Changes</h2>
            
            <div style="background-color: #FFFBEB; border: 1px solid #FDE68A; border-radius: 12px; padding: 24px; margin: 24px 0; text-align: left;">
              <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; font-weight: 700; color: #B45309; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">Status</div>
              <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 16px; font-weight: 700; color: #78350F; margin-bottom: 8px;">Revision Needed</div>
              <p style="margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; line-height: 1.5; color: #78350F;">Your job listing <strong>{job_title}</strong> requires some adjustments before it can be published.</p>
              {reason_block}
            </div>

            <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">Please edit the listing to address the feedback above and resubmit it for moderation.</p>

            {_render_button("Edit Job Listing", cta_url)}
            """

        html_body = _render_email_layout(
            title=subject,
            preheader=f"Moderation update for your job listing: {job_title}.",
            body_content_html=body_content_html,
            footer_note="You received this email because you have an active job posting on Elevare.",
        )

        await self._send_html(
            subject=subject, recipients=[employer_email], html_body=html_body
        )


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
        self,
        employer_email: str,
        job_data: dict,
        action: str,
        reason: str | None = None,
    ) -> None:
        """Log stub job moderation status with the correct action link."""
        job_id = job_data["id"]
        if action == "APPROVED":
            cta_url = f"{settings.app_url}/employer/jobs/{job_id}/publish"
            label = "Publish link"
        else:
            cta_url = f"{settings.app_url}/employer/jobs/{job_id}/edit"
            label = "Edit link"
        logger.info(
            "STUB JOB MODERATION to %s: Job '%s' action=%s reason=%s\n%s: %s",
            employer_email,
            job_data["title"],
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
