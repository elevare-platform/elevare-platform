"""Email service abstraction for Elevare.

Provides an abstract EmailService interface with two implementations:
- ResendEmailService: sends real emails via the Resend API
- StubEmailService: logs to stdout, used in tests and CI

Wire into FastAPI via get_email_service() dependency.
"""

import html as html_lib
import logging
import re
from abc import ABC, abstractmethod

from app.modules.email_preferences.links import (
    list_unsubscribe_headers,
    with_unsubscribe,
    without_unsubscribe,
)
from app.modules.email_preferences.suppression import suppressed_addresses
from app.modules.email_preferences.tokens import normalize_email

from .config import settings

logger = logging.getLogger(__name__)

# Shown in every email's footer. The name and address are the ones the website's
# contact page publishes.
COMPANY_NAME = "Elevare Human Solutions Ltd"
COMPANY_ADDRESS = "Lekki Gardens, Eti-Osa, Lekki 106104, Lagos, Nigeria"

# The logo is served by the website itself (frontend/public/email/), because an email
# can only show an image from a public web address, not from a file in the project.
# It is the official logo on a white background so it stays readable in dark mode.
EMAIL_LOGO_PATH = "/email/elevare-logo.png"

# The name an inbox shows next to the sender address.
SENDER_NAME = "Elevare"


def _html_to_text(html: str) -> str:
    """A plain-text version of an email's HTML, sent alongside it.

    Email without a text part scores worse with spam filters, and some readers (and
    some clients) show only the text. Links keep their address in brackets after the
    link text, so nothing is lost."""
    text = re.sub(r"<head>.*?</head>", "", html, flags=re.S | re.I)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    # The hidden preview line at the top of the layout is for inboxes, not readers.
    text = re.sub(r'<div style="display: none;.*?</div>', "", text, flags=re.S)

    def link(match: re.Match) -> str:
        address = match.group(1)
        # An image inside the link (the logo) is represented by its alt text.
        inner = re.sub(r'<img[^>]*alt="([^"]*)"[^>]*>', r"\1", match.group(2))
        label = re.sub(r"<[^>]+>", "", inner).strip()
        return address if not label or label == address else f"{label} ({address})"

    text = re.sub(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', link, text, flags=re.S | re.I)
    text = re.sub(r"</(p|div|h1|h2|h3|tr|li|table)>|<br\s*/?>", "\n", text, flags=re.I)
    text = html_lib.unescape(re.sub(r"<[^>]+>", "", text))

    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    cleaned: list[str] = []
    for line in lines:
        if line or (cleaned and cleaned[-1]):
            cleaned.append(line)
    return "\n".join(cleaned).strip() + "\n"


# Mail clients cut a long subject, and a very long one is a sign something is wrong.
MAX_SUBJECT_LENGTH = 200


def _clean_subject(subject: str) -> str:
    """A subject on one line. Subjects include things people typed (a job title, a name,
    a company), and a line break or other control character in an email header is
    refused by the mail provider and is how header injection works. Every run of
    whitespace or control characters, including the Unicode line separators, becomes one
    space."""
    one_line = re.sub(r"[\s\x00-\x1f\x7f-\x9f  ]+", " ", subject).strip()
    return one_line[:MAX_SUBJECT_LENGTH].rstrip()


def _h(value):
    """Text someone typed, made safe to put inside an email's HTML.

    A job title, a name or a company is typed by one person and shown to another; unescaped,
    markup in it becomes real markup (a link that looks like part of the email). Used at the
    top of every ``send_*`` method for each typed value, so everything below it is safe.
    Not for links, tokens or recipient addresses, which Elevare builds itself. A subject is
    plain text, so ``_send_html`` turns the escaping back before it is sent."""
    return value if value is None else html_lib.escape(str(value), quote=True)


def _from_header() -> str:
    """The From header: ``Elevare <noreply@...>`` so the inbox shows a name, not a bare
    address. A configured value that already has a name is left as it is."""
    sender = settings.mail_from or ""
    return sender if "<" in sender else f"{SENDER_NAME} <{sender}>"


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
        self, employer_email: str, job_title: str, candidate_name: str, job_id: str
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
    async def send_verification_reminder(
        self,
        email: str,
        first_name: str,
        verification_token: str,
        role: str,
    ) -> None:
        """Nudge an unverified account, offering a role correction for employers."""
        ...

    @abstractmethod
    async def send_role_switch_corrected(
        self,
        email: str,
        first_name: str,
        role: str,
    ) -> None:
        """Tell a user a role-switch account bug on their profile has been fixed."""
        ...

    @abstractmethod
    async def send_onboarding_reminder(
        self,
        email: str,
        first_name: str,
    ) -> None:
        """Nudge a verified employer who never completed their company profile."""
        ...

    @abstractmethod
    async def send_kyc_reminder(
        self,
        email: str,
        first_name: str,
        company_name: str,
    ) -> None:
        """Nudge an onboarded employer who never submitted KYC documents."""
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

    @abstractmethod
    async def send_introduction_request(
        self,
        candidate_email: str,
        accept_url: str,
        decline_url: str,
        job_title: str,
    ) -> None:
        """Send an introduction request email with accept/decline magic links."""
        ...

    @abstractmethod
    async def send_ai_interview_invite(
        self,
        candidate_email: str,
        interview_url: str,
        job_title: str,
        company_name: str,
    ) -> None:
        """Invite a candidate to a live AI video interview, no login required."""
        ...

    @abstractmethod
    async def send_interview_restart_request(
        self,
        employer_email: str,
        candidate_name: str,
        job_title: str,
        company_name: str,
        manage_url: str,
    ) -> None:
        """Notify an employer that a candidate is locked out of their AI
        interview's restart lock and is asking for it to be reset."""
        ...

    @abstractmethod
    async def send_introduction_accepted(
        self,
        employer_email: str,
        job_title: str,
        profile_url: str,
    ) -> None:
        """Notify employer that a candidate accepted their introduction request."""
        ...

    @abstractmethod
    async def send_kyc_rejection(
        self,
        employer_email: str,
        company_name: str | None,
        reason: str | None,
    ) -> None:
        """Notify employer that their KYC was rejected with a link to resubmit."""
        ...

    @abstractmethod
    async def send_kyc_approved(
        self,
        employer_email: str,
        company_name: str | None,
    ) -> None:
        """Notify employer that their KYC has been approved."""
        ...

    @abstractmethod
    async def send_kyc_submission_notification(
        self,
        admin_email: str,
        company_name: str | None,
        organization_id: str,
    ) -> None:
        """Notify an admin that an employer submitted KYC documents for review."""
        ...

    @abstractmethod
    async def send_subscription_payment_failed(
        self,
        recipient_email: str,
        company_name: str | None,
        plan_name: str,
        retry_by: str,
    ) -> None:
        """Notify a billing manager that a subscription renewal charge
        failed. Access continues (see BillingService grace-period handling)
        until `retry_by` — this email is the only signal they get before
        then, so it needs to say plainly what will happen and when.
        """
        ...

    @abstractmethod
    async def send_introduction_request_admin(
        self,
        admin_email: str,
        employer_name: str,
        job_title: str,
        candidate_name: str,
    ) -> None:
        """Notify the sourcing admin that an employer wants an introduction.

        Sent instead of send_introduction_request when the profile was
        sourced by an admin — the admin does the outreach manually, so this
        has no accept/decline links, just enough context to act on.
        """
        ...

    @abstractmethod
    async def send_invite_email(
        self,
        email: str,
        invite_link: str,
        company_name: str | None = None,
    ) -> None:
        """Send an invite link to a prospective new employer or teammate.

        `company_name` set means this is a teammate invite into an
        existing organization; None means a brand-new employer invite.
        """
        ...

    @abstractmethod
    async def send_role_notification(
        self,
        candidate_email: str,
        employer_name: str,
        job_title: str,
        job_url: str,
        register_url: str,
        employer_email: str | None = None,
    ) -> None:
        """One-way heads-up to a candidate an employer already owns/sourced.

        No accept/decline — the employer already has full access to this
        profile, this just flags that a specific role might interest them.
        Two CTAs, both shown together: "View Job" (primary) and "Create your
        free profile" (secondary, growth channel) — not an either/or choice.
        ``employer_email`` is used as the Reply-To so a candidate who wants
        to respond directly can, since the employer already has this
        relationship (that's what makes it "own_sourced").
        """
        ...


def _render_email_layout(
    title: str,
    preheader: str,
    body_content_html: str,
    footer_note: str,
) -> str:
    """Wraps email content in the shared layout: logo, content, company footer."""
    logo_url = f"{settings.app_url.rstrip('/')}{EMAIL_LOGO_PATH}"

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
            <td align="left" style="padding: 32px 32px 0 32px;" class="email-padding">
              <a href="{settings.app_url}" target="_blank" style="text-decoration: none;">
                <img src="{logo_url}" width="150" alt="Elevare Human Solutions" style="display: block; width: 150px; max-width: 100%; height: auto; border: 0; font-family: Arial, Helvetica, sans-serif; font-size: 18px; font-weight: bold; color: #1A4D8F;">
              </a>
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
                {COMPANY_NAME}<br>{COMPANY_ADDRESS}
              </p>
              <p style="margin: 8px 0 0 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; line-height: 1.5; color: #94A3B8; font-weight: 400;">
                {footer_note}
              </p>
              <!--unsubscribe-->
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
        self,
        subject: str,
        recipients: list[str],
        html_body: str,
        reply_to: str | None = None,
        *,
        essential: bool = False,
    ) -> None:
        """Send an email, unless its recipient has turned emails off.

        Every email Elevare sends passes through here, so this is where "turn emails
        off" is enforced, at the moment of sending (an email already queued when
        someone unsubscribes is stopped too).

        An address that has unsubscribed is skipped, quietly, not an error.
        ``essential`` emails are the ones a person needs to use or protect their
        account (email verification, a teammate's invite, a failed payment) or that go
        to Elevare's own inbox: they are always sent and carry no unsubscribe link.
        Every other email is sent to each recipient separately, with that recipient's
        own signed Unsubscribe link in the footer and in the List-Unsubscribe headers.
        """
        import asyncio

        # The typed values in a subject were escaped for the HTML (see _h); a subject is
        # plain text, so "Sales &amp; Marketing" goes out as "Sales & Marketing".
        subject = _clean_subject(html_lib.unescape(subject))

        # (recipients, html, extra headers) for each separate send.
        deliveries: list[tuple[list[str], str, dict[str, str]]]
        if essential:
            deliveries = [(recipients, without_unsubscribe(html_body), {})]
        else:
            turned_off = await suppressed_addresses(recipients)
            deliveries = []
            for address in recipients:
                if normalize_email(address) in turned_off:
                    logger.info(
                        "Email to %s not sent: the address has turned emails off — subject: %s",
                        address,
                        subject,
                    )
                    continue
                deliveries.append(
                    (
                        [address],
                        with_unsubscribe(html_body, address),
                        list_unsubscribe_headers(address),
                    )
                )

        loop = asyncio.get_event_loop()
        for to, html, headers in deliveries:
            payload = {
                "from": _from_header(),
                "to": to,
                "subject": subject,
                "html": html,
                "text": _html_to_text(html),
            }
            if headers:
                payload["headers"] = headers
            if reply_to:
                # Resend's SDK expects snake_case "reply_to" — only included when
                # set, so the many other email types that don't use this aren't
                # sending a stray null field.
                payload["reply_to"] = reply_to
            try:
                # `payload` is rebuilt each pass, so the closure sees this send's.
                await loop.run_in_executor(
                    None, lambda payload=payload: self._resend.Emails.send(payload)
                )
                logger.info("Email sent to %s — subject: %s", to, subject)
            except Exception as exc:
                logger.error("Resend delivery failed to %s: %s", to, exc)
                raise

    async def send_application_confirmation(
        self, candidate_email: str, job_title: str, company_name: str
    ) -> None:
        """Send an application-received confirmation email to the candidate."""
        job_title, company_name = _h(job_title), _h(company_name)
        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">Application received</h2>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">We've received your application for <strong>{job_title}</strong> at <strong>{company_name}</strong>.</p>
        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">The hiring team will review it and contact you if they want to take it further. You can follow its progress from your dashboard.</p>

        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 20px; margin: 24px 0; text-align: left;">
          <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; font-weight: 700; color: #1A4D8F;  margin-bottom: 8px;">Application</div>
          <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 16px; font-weight: 600; color: #0F172A; margin-bottom: 4px;">{job_title}</div>
          <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; color: #64748B;">{company_name}</div>
        </div>

        {_render_button("View my applications", f"{settings.app_url}/candidate/applications")}
        """

        html_body = _render_email_layout(
            title=f"Application received: {job_title}",
            preheader=f"We've received your application for {job_title} at {company_name}.",
            body_content_html=body_content_html,
            footer_note="You received this email because you applied for a job on Elevare.",
        )

        await self._send_html(
            subject=f"Application received: {job_title}",
            recipients=[candidate_email],
            html_body=html_body,
        )

    async def send_status_update(
        self, candidate_email: str, job_title: str, new_status: str
    ) -> None:
        """Send a status update email to the candidate when their application status changes."""
        job_title = _h(job_title)
        badge_html = _render_badge(new_status)

        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">Application update</h2>
        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">The status of your application has changed.</p>

        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 20px; margin: 24px 0; text-align: left;">
          <table cellpadding="0" cellspacing="0" border="0" width="100%">
            <tr>
              <td style="padding-bottom: 16px;">
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; font-weight: 700; color: #64748B;  margin-bottom: 6px;">Role</div>
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 16px; font-weight: 600; color: #0F172A;">{job_title}</div>
              </td>
            </tr>
            <tr>
              <td style="border-top: 1px solid #E2E8F0; padding-top: 16px;">
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; font-weight: 700; color: #64748B;  margin-bottom: 8px;">New status</div>
                {badge_html}
              </td>
            </tr>
          </table>
        </div>

        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">Log in to your dashboard to see the details.</p>

        {_render_button("View my applications", f"{settings.app_url}/candidate/applications")}
        """

        html_body = _render_email_layout(
            title=f"Application update: {job_title}",
            preheader=f"Your application for {job_title} is now {new_status.lower()}.",
            body_content_html=body_content_html,
            footer_note="You received this email because you have an active application on Elevare.",
        )

        await self._send_html(
            subject=f"Application update: {job_title}",
            recipients=[candidate_email],
            html_body=html_body,
        )

    async def send_employer_notification(
        self, employer_email: str, job_title: str, candidate_name: str, job_id: str
    ) -> None:
        """Notify an employer by email that a new application has been received."""
        job_title, candidate_name = _h(job_title), _h(candidate_name)
        review_url = f"{settings.app_url}/employer/jobs/{job_id}/applicants"
        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">New application</h2>
        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">A candidate has applied for your job posting.</p>

        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 24px; margin: 24px 0; text-align: left;">
          <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; font-weight: 700; color: #1A4D8F;  margin-bottom: 8px;">Candidate</div>
          <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 18px; font-weight: 700; color: #0F172A; margin-bottom: 12px;">{candidate_name}</div>
          <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; color: #475569;">Applied for <strong style="color: #0F172A;">{job_title}</strong></div>
        </div>

        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">You can review their profile, CV and AI match score on your dashboard.</p>

        {_render_button("Review application", review_url)}
        """

        html_body = _render_email_layout(
            title=f"New application: {job_title}",
            preheader=f"{candidate_name} applied for {job_title}.",
            body_content_html=body_content_html,
            footer_note="You received this email because you have an active job posting on Elevare.",
        )

        await self._send_html(
            subject=f"New application: {job_title}",
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
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">Verify your email address</h2>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">Welcome to Elevare. Please verify your email address to activate your account. The link expires in 24 hours.</p>

        {_render_button("Verify email address", verification_link)}

        <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top: 24px; border-top: 1px solid #E2E8F0; padding-top: 20px;">
          <tr>
            <td>
              <p style="margin: 0 0 8px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; line-height: 1.5; color: #64748B; font-weight: 600; ">If the button doesn't work, copy and paste this link into your browser:</p>
              <p style="margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; line-height: 1.5; color: #1A4D8F; word-break: break-all;">
                <a href="{verification_link}" target="_blank" style="color: #1A4D8F; text-decoration: none; word-break: break-all;">{verification_link}</a>
              </p>
            </td>
          </tr>
        </table>
        """

        html_body = _render_email_layout(
            title="Verify your email address",
            preheader="Verify your email address to activate your Elevare account.",
            body_content_html=body_content_html,
            footer_note="If you didn't create an account, you can safely ignore this email.",
        )

        await self._send_html(
            subject="Verify your email address",
            recipients=[email],
            html_body=html_body,
            essential=True,
        )

    async def send_verification_reminder(
        self,
        email: str,
        first_name: str,
        verification_token: str,
        role: str,
    ) -> None:
        """Remind an unverified account to finish signing up.

        For accounts sitting on the EMPLOYER role this doubles as a role
        correction: a sizeable share of them are job seekers who clicked the
        wrong CTA on the homepage, so the email offers two doors: confirm as
        an employer, or switch to a job seeker account. Either one also
        verifies the address. Both links carry the same single-use token, so
        whichever they click is the one that takes effect.
        """
        from urllib.parse import quote

        base = f"{settings.app_url}/verify-email?token={verification_token}"
        is_employer = role.upper() == "EMPLOYER"

        employer_link = f"{base}&role=EMPLOYER&next={quote('/employer/onboarding', safe='')}"
        candidate_link = f"{base}&role=CANDIDATE&next={quote('/candidate/dashboard', safe='')}"
        first_name = _h(first_name)
        greeting = f"Hi {first_name}," if first_name else "Hi,"

        if is_employer:
            body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">One click left to finish your Elevare account</h2>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">{greeting}</p>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">You started signing up on Elevare but never confirmed your email address, so your account isn't active yet.</p>
        <p style="margin: 0 0 8px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">Your account was created as an <strong>employer</strong> account, for posting jobs and hiring. Pick the one that's actually you:</p>

        <p style="margin: 24px 0 0 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; line-height: 1.5; color: #0F172A; font-weight: 600;">I'm hiring, and I want to post jobs and review applicants</p>
        {_render_button("Confirm as an employer", employer_link)}

        <p style="margin: 8px 0 0 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; line-height: 1.5; color: #0F172A; font-weight: 600;">I'm looking for a job, and I want to build a profile and apply to roles</p>
        {_render_button("Switch me to a job seeker account", candidate_link, is_primary=False)}

        <p style="margin: 24px 0 0 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; line-height: 1.5; color: #64748B;">Either link also verifies your email. You only need to click one.</p>
        """
            subject = "Finish your Elevare sign-up: employer or job seeker?"
            preheader = "Confirm your email and pick the right account type."
        else:
            body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">One click left to finish your Elevare account</h2>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">{greeting}</p>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">You started signing up on Elevare but never confirmed your email address. Verify it now to activate your job seeker account, build your profile, and start applying to roles.</p>

        {_render_button("Verify my email", candidate_link)}

        <p style="margin: 24px 0 0 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; line-height: 1.5; color: #64748B;">Signed up to hire rather than to find a role?</p>
        {_render_button("Switch me to an employer account", employer_link, is_primary=False)}
        """
            subject = "Finish your Elevare sign-up: verify your email"
            preheader = "Verify your email to activate your Elevare account."

        html_body = _render_email_layout(
            title="Finish your Elevare sign-up",
            preheader=preheader,
            body_content_html=body_content_html,
            footer_note="You received this email because an account was created with this address on Elevare. If that wasn't you, ignore this email and the account will stay inactive.",
        )

        await self._send_html(
            subject=subject,
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
        # Everything on this form is typed by a stranger: shown as text, never as markup.
        name, sender_email, company, message = (
            _h(name),
            _h(sender_email),
            _h(company),
            _h(message),
        )
        label = (
            "employer inquiry"
            if inquiry_type == "employer_inquiry"
            else "general message"
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
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">New message from the website</h2>
        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">Someone sent a message through the contact form on the Elevare website.</p>

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
              <td style="padding: 10px 0; color: #0F172A; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">{label.capitalize()}</td>
            </tr>
          </table>
        </div>

        <div style="background-color: #ffffff; border: 1px solid #E2E8F0; border-radius: 12px; padding: 24px; text-align: left; margin-top: 20px;">
          <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; font-weight: 700; color: #1A4D8F;  margin-bottom: 12px;">Message</div>
          <p style="margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #0F172A; white-space: pre-wrap;">{message}</p>
        </div>
        """

        html_body = _render_email_layout(
            title=f"New contact form submission from {name}",
            preheader=f"New {label} from {name}.",
            body_content_html=body_content_html,
            footer_note="This message was sent to the Elevare team from the website contact form.",
        )

        await self._send_html(
            subject=f"New {label} from {name}",
            recipients=[recipient],
            html_body=html_body,
            essential=True,  # to Elevare's own inbox, not to a user
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
        job_title = _h(job_data["title"])
        reason = _h(reason)

        if action == "APPROVED":
            subject = f"Your job listing was approved: {job_title}"
            cta_url = f"{settings.app_url}/employer/jobs/{job_id}/publish"

            body_content_html = f"""
            <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">Your job listing was approved</h2>
            <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">We've approved <strong>{job_title}</strong>. You can publish it now so candidates can see it and apply.</p>

            {_render_button("Publish job", cta_url)}
            """
        else:
            subject = f"Your job listing needs changes: {job_title}"
            cta_url = f"{settings.app_url}/employer/jobs/{job_id}/edit"

            reason_block = (
                f"""
            <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px; margin: 0 0 24px 0;">
              <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; font-weight: 600; color: #475569; margin-bottom: 6px;">Feedback from our team</div>
              <p style="margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #0F172A;">{reason}</p>
            </div>
            """
                if reason
                else ""
            )

            body_content_html = f"""
            <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">Your job listing needs changes</h2>
            <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">We can't publish <strong>{job_title}</strong> yet. It needs a few changes first.</p>
            {reason_block}
            <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">Please edit the listing and submit it again for review.</p>

            {_render_button("Edit job listing", cta_url)}
            """

        html_body = _render_email_layout(
            title=subject,
            preheader=f"An update on your job listing: {job_title}.",
            body_content_html=body_content_html,
            footer_note="You received this email because you have an active job posting on Elevare.",
        )

        await self._send_html(
            subject=subject, recipients=[employer_email], html_body=html_body
        )

    async def send_introduction_request(
        self,
        candidate_email: str,
        accept_url: str,
        decline_url: str,
        job_title: str,
    ) -> None:
        """Send introduction request email with accept/decline magic links."""
        job_title = _h(job_title)
        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">You have an introduction request</h2>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">An employer on Elevare would like to connect with you about the <strong>{job_title}</strong> role.</p>
        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">You don't need to log in. Choose Accept or Decline below. The link expires in 7 days.</p>
        {_render_button("Accept introduction", accept_url, is_primary=True)}
        {_render_button("Decline", decline_url, is_primary=False)}
        <p style="margin: 16px 0 0 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; line-height: 1.5; color: #64748B;">If you decline, your identity will not be shared with the employer.</p>
        """
        html_body = _render_email_layout(
            title="Introduction request",
            preheader=f"An employer would like to connect with you about the {job_title} role.",
            body_content_html=body_content_html,
            footer_note="You received this email because your CV is in the Elevare talent pool.",
        )
        await self._send_html(
            subject=f"Introduction request: {job_title}",
            recipients=[candidate_email],
            html_body=html_body,
        )

    async def send_ai_interview_invite(
        self,
        candidate_email: str,
        interview_url: str,
        job_title: str,
        company_name: str,
    ) -> None:
        """Invite a candidate to a live AI video interview, no login required.

        Always the real token link — even for self-registered candidates,
        who aren't guaranteed to have an Application for this specific job
        (they may have been sourced via Candidate Search / Talent
        Matches), so a login-gated dashboard link would be a dead end
        whenever that's the case.
        """
        job_title, company_name = _h(job_title), _h(company_name)
        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">You're invited to an AI video interview</h2>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;"><strong>{company_name}</strong> would like to interview you for the <strong>{job_title}</strong> role.</p>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">The interview is conducted by an AI interviewer, not a person. It asks you questions and follows up on your answers. Your camera records the session so the employer can review it afterwards.</p>
        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">You don't need to log in. Open the link when you're ready, with your camera and microphone available.</p>
        {_render_button("Start interview", interview_url, is_primary=True)}
        """
        html_body = _render_email_layout(
            title=f"Interview invitation: {job_title}",
            preheader=f"{company_name} would like to interview you for the {job_title} role.",
            body_content_html=body_content_html,
            footer_note="You received this email because your CV is in the Elevare talent pool.",
        )
        await self._send_html(
            subject=f"Interview invitation: {job_title} at {company_name}",
            recipients=[candidate_email],
            html_body=html_body,
        )

    async def send_interview_restart_request(
        self,
        employer_email: str,
        candidate_name: str,
        job_title: str,
        company_name: str,
        manage_url: str,
    ) -> None:
        """Notify an employer that a candidate is locked out of their AI
        interview's restart lock and is asking for it to be reset."""
        candidate_name, job_title, company_name = (
            _h(candidate_name),
            _h(job_title),
            _h(company_name),
        )
        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">A candidate needs their AI interview reset</h2>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;"><strong>{candidate_name}</strong> was locked out of their AI interview for <strong>{job_title}</strong> after restarting it twice, and is asking you to resend their invite so they can try again.</p>
        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">Resending their invite from the interview list resets it automatically. Nothing else is needed.</p>
        {_render_button("Manage interview list", manage_url, is_primary=True)}
        """
        html_body = _render_email_layout(
            title=f"Interview reset requested: {job_title}",
            preheader=f"{candidate_name} is asking you to reset their AI interview for {job_title}.",
            body_content_html=body_content_html,
            footer_note=f"You're receiving this because you own the {job_title} posting on {company_name}'s Elevare account.",
        )
        await self._send_html(
            subject=f"Interview reset requested: {candidate_name}, {job_title}",
            recipients=[employer_email],
            html_body=html_body,
        )

    async def send_introduction_accepted(
        self,
        employer_email: str,
        job_title: str,
        profile_url: str,
    ) -> None:
        """Notify employer that a candidate accepted their introduction request."""
        job_title = _h(job_title)
        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">Introduction accepted</h2>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">A candidate has accepted your introduction request for <strong>{job_title}</strong>.</p>
        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">You can now see their full profile and contact details on your dashboard.</p>
        {_render_button("View full profile", profile_url)}
        """
        html_body = _render_email_layout(
            title=f"Introduction accepted: {job_title}",
            preheader=f"A candidate accepted your introduction request for {job_title}.",
            body_content_html=body_content_html,
            footer_note="You received this email because you requested a candidate introduction on Elevare.",
        )
        await self._send_html(
            subject=f"Introduction accepted: {job_title}",
            recipients=[employer_email],
            html_body=html_body,
        )

    async def send_introduction_declined(
        self,
        employer_email: str,
        job_title: str,
    ) -> None:
        """Notify employer that a candidate declined their introduction request."""
        job_title = _h(job_title)
        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">Introduction declined</h2>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">The candidate has declined your introduction request for <strong>{job_title}</strong>.</p>
        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">Your credit has been refunded. You can request introductions with other matched candidates from your dashboard.</p>
        {_render_button("View AI matches", f"{settings.app_url}/employer/jobs")}
        """
        html_body = _render_email_layout(
            title=f"Introduction declined: {job_title}",
            preheader=f"A candidate declined your introduction request for {job_title}. Your credit has been refunded.",
            body_content_html=body_content_html,
            footer_note="You received this email because you requested a candidate introduction on Elevare.",
        )
        await self._send_html(
            subject=f"Introduction declined: {job_title}",
            recipients=[employer_email],
            html_body=html_body,
        )

    async def send_introduction_request_admin(
        self,
        admin_email: str,
        employer_name: str,
        job_title: str,
        candidate_name: str,
    ) -> None:
        """Notify the sourcing admin to manually reach out to the candidate."""
        employer_name, job_title, candidate_name = (
            _h(employer_name),
            _h(job_title),
            _h(candidate_name),
        )
        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">Introduction request for a candidate you sourced</h2>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;"><strong>{employer_name}</strong> would like an introduction to <strong>{candidate_name}</strong> for the role of <strong>{job_title}</strong>.</p>
        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">Please contact the candidate to confirm their interest, then mark the request as accepted or declined in the introductions queue.</p>
        {_render_button("Open introductions queue", f"{settings.app_url}/admin/introductions")}
        """
        html_body = _render_email_layout(
            title="Introduction request: action needed",
            preheader=f"{employer_name} wants an introduction to {candidate_name} for {job_title}.",
            body_content_html=body_content_html,
            footer_note="You received this email because you sourced this candidate into the Elevare talent pool.",
        )
        await self._send_html(
            subject=f"Action needed: introduction request for {candidate_name}",
            recipients=[admin_email],
            html_body=html_body,
        )

    async def send_role_notification(
        self,
        candidate_email: str,
        employer_name: str,
        job_title: str,
        job_url: str,
        register_url: str,
        employer_email: str | None = None,
    ) -> None:
        """One-way notification for a candidate the employer already owns."""
        employer_name, job_title = _h(employer_name), _h(job_title)
        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">A role that might interest you</h2>
        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;"><strong>{employer_name}</strong> thinks you could be a good fit for their <strong>{job_title}</strong> role and wanted to let you know.</p>
        {_render_button("View job", job_url)}
        <p style="margin: 24px 0 0 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; line-height: 1.5; color: #64748B;">Want employers to find you for roles like this one?</p>
        {_render_button("Create your free profile", register_url, is_primary=False)}
        """
        html_body = _render_email_layout(
            title=f"A role at {employer_name}",
            preheader=f"{employer_name} thinks you'd be a good fit for {job_title}.",
            body_content_html=body_content_html,
            footer_note="You received this email because your CV is in the Elevare talent pool.",
        )
        await self._send_html(
            subject=f"{employer_name} has a role that might interest you",
            recipients=[candidate_email],
            html_body=html_body,
            reply_to=employer_email,
        )

    async def send_kyc_rejection(
        self,
        employer_email: str,
        company_name: str | None,
        reason: str | None,
    ) -> None:
        """Notify employer that their KYC was rejected, with a link to resubmit."""
        company_name, reason = _h(company_name), _h(reason)
        cta_url = f"{settings.app_url}/employer/verification"
        company_label = company_name or "your company"
        reason_block = (
            f"""
            <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px; margin: 0 0 24px 0;">
              <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; font-weight: 600; color: #475569; margin-bottom: 6px;">Reason</div>
              <p style="margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #0F172A;">{reason}</p>
            </div>
            """
            if reason
            else ""
        )
        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">Company verification update</h2>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">We couldn't verify <strong>{company_label}</strong> with the documents you submitted.</p>
        {reason_block}
        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">Please upload the correct documents and submit your verification again.</p>
        {_render_button("Resubmit verification", cta_url)}
        """
        html_body = _render_email_layout(
            title="Company verification update",
            preheader=f"Your company verification for {company_label} was not approved. Please resubmit.",
            body_content_html=body_content_html,
            footer_note="You received this email because you submitted a company verification request on Elevare.",
        )
        await self._send_html(
            subject="Company verification: action needed",
            recipients=[employer_email],
            html_body=html_body,
        )

    async def send_kyc_approved(
        self,
        employer_email: str,
        company_name: str | None,
    ) -> None:
        """Notify employer that their KYC has been approved."""
        company_label = _h(company_name) or "your company"
        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">Your company is verified</h2>
        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;"><strong>{company_label}</strong> is now verified. You can post jobs on Elevare.</p>

        {_render_button("Post a job", f"{settings.app_url}/employer/jobs/new")}
        """
        html_body = _render_email_layout(
            title="Your company is verified",
            preheader=f"{company_label} has been verified. You can now post jobs on Elevare.",
            body_content_html=body_content_html,
            footer_note="You received this email because you submitted a company verification request on Elevare.",
        )
        await self._send_html(
            subject="Your company is verified",
            recipients=[employer_email],
            html_body=html_body,
        )

    async def send_kyc_submission_notification(
        self,
        admin_email: str,
        company_name: str | None,
        organization_id: str,
    ) -> None:
        """Notify an admin that an employer submitted KYC documents for review."""
        company_label = _h(company_name) or "An employer"
        review_url = f"{settings.app_url}/admin/kyc"
        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">New KYC submission</h2>
        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;"><strong>{company_label}</strong> has submitted company verification documents and is waiting for review.</p>
        {_render_button("Review submission", review_url)}
        """
        html_body = _render_email_layout(
            title="New KYC submission",
            preheader=f"{company_label} submitted documents for company verification.",
            body_content_html=body_content_html,
            footer_note="You received this email because you are an Elevare platform admin.",
        )
        await self._send_html(
            subject=f"New KYC submission: {company_label}",
            recipients=[admin_email],
            html_body=html_body,
        )

    async def send_subscription_payment_failed(
        self,
        recipient_email: str,
        company_name: str | None,
        plan_name: str,
        retry_by: str,
    ) -> None:
        """Notify a billing manager that a subscription renewal charge
        failed, with the date access continues until."""
        company_label = _h(company_name) or "your organization"
        plan_name, retry_by = _h(plan_name), _h(retry_by)
        cta_url = f"{settings.app_url}/employer/billing"
        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">We couldn't process your payment</h2>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">Your {plan_name} renewal charge for <strong>{company_label}</strong> didn't go through. This is usually caused by an expired card or a temporary decline from the bank.</p>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">Your plan keeps working for now, and we'll retry the charge automatically. If it still fails by <strong>{retry_by}</strong>, your account will move to the Starter plan.</p>
        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">Please update your card to avoid any interruption.</p>
        {_render_button("Update payment method", cta_url)}
        """
        html_body = _render_email_layout(
            title="Payment failed: action needed",
            preheader=f"Your {plan_name} renewal didn't go through. Update your card by {retry_by}.",
            body_content_html=body_content_html,
            footer_note="You received this email because you manage billing for an Elevare organization.",
        )
        await self._send_html(
            subject="Action needed: your Elevare payment failed",
            recipients=[recipient_email],
            html_body=html_body,
            essential=True,  # billing: a silent failure would let a plan lapse unnoticed
        )

    async def send_invite_email(
        self,
        email: str,
        invite_link: str,
        company_name: str | None = None,
    ) -> None:
        """Send an invite link to a prospective new employer or teammate."""
        company_name = _h(company_name)
        if company_name:
            subject = f"You've been invited to join {company_name} on Elevare"
            heading = "You're invited to join a team on Elevare"
            copy = f"You've been invited to join <strong>{company_name}</strong> on Elevare. Use the button below to accept and set up your account."
        else:
            subject = "You've been invited to Elevare"
            heading = "You're invited to Elevare"
            copy = "You've been invited to create an employer account on Elevare. Use the button below to accept and set up your account."

        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">{heading}</h2>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">{copy}</p>
        <p style="margin: 0 0 24px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">This link expires in {settings.invite_expiry} day{"s" if settings.invite_expiry != 1 else ""}.</p>

        {_render_button("Accept invitation", invite_link)}

        <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top: 24px; border-top: 1px solid #E2E8F0; padding-top: 20px;">
          <tr>
            <td>
              <p style="margin: 0 0 8px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; line-height: 1.5; color: #64748B; font-weight: 600; ">If the button doesn't work, copy and paste this link into your browser:</p>
              <p style="margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; line-height: 1.5; color: #1A4D8F; word-break: break-all;">
                <a href="{invite_link}" target="_blank" style="color: #1A4D8F; text-decoration: none; word-break: break-all;">{invite_link}</a>
              </p>
            </td>
          </tr>
        </table>
        """

        html_body = _render_email_layout(
            title=subject,
            preheader=copy,
            body_content_html=body_content_html,
            footer_note="If you weren't expecting this invite, you can safely ignore this email.",
        )

        await self._send_html(
            subject=subject,
            recipients=[email],
            html_body=html_body,
            essential=True,  # a teammate asked for this; it is how the invitee joins
        )

    async def send_role_switch_corrected(
        self,
        email: str,
        first_name: str,
        role: str,
    ) -> None:
        """Tell a user a role-switch account bug on their profile has been fixed.

        Covers the account-type correction flow (see ``send_verification_reminder``):
        switching roles from the verification email used to leave the account
        half-migrated (role changed, but the matching candidate/employer
        profile never created), which surfaced as an error when the person
        tried to use their account. This confirms it's fixed and safe to log
        back in.
        """
        login_link = f"{settings.app_url}/login"
        first_name = _h(first_name)
        greeting = f"Hi {first_name}," if first_name else "Hi,"
        role_label = "job seeker" if role.upper() == "CANDIDATE" else "employer"

        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">Your account is ready</h2>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">{greeting}</p>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">When you switched your Elevare account to a <strong>{role_label}</strong> account, something went wrong on our side and the switch didn't complete properly. You may have seen an error when you tried to use your account.</p>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">We've fixed the problem. Your account is now set up as a {role_label} account and ready to use.</p>

        {_render_button("Log in to Elevare", login_link)}

        <p style="margin: 24px 0 0 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; line-height: 1.5; color: #64748B;">We apologise for the inconvenience. If anything still looks wrong after you log in, please contact us at <a href="mailto:info_admin@elevare.com.ng" style="color: #1A4D8F; text-decoration: none;">info_admin@elevare.com.ng</a>.</p>
        """

        html_body = _render_email_layout(
            title="Your Elevare account is ready",
            preheader="We've fixed the problem with your account.",
            body_content_html=body_content_html,
            footer_note="You received this email because an account was corrected on Elevare following a report of an error.",
        )

        await self._send_html(
            subject="Your Elevare account is ready",
            recipients=[email],
            html_body=html_body,
        )

    async def send_onboarding_reminder(
        self,
        email: str,
        first_name: str,
    ) -> None:
        """Nudge a verified employer who never completed their company profile.

        Sent once, at least 24 hours after email verification, if the
        Organization's company profile is still incomplete. See
        ``UserRepository.list_employers_missing_onboarding``.
        """
        onboarding_link = f"{settings.app_url}/employer/onboarding"
        first_name = _h(first_name)
        greeting = f"Hi {first_name}," if first_name else "Hi,"

        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">Finish setting up your company profile</h2>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">{greeting}</p>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">Your Elevare employer account is verified, but your company profile is still missing a few details. Finishing it is what lets you start posting jobs and searching the talent pool.</p>

        {_render_button("Complete your company profile", onboarding_link)}

        <p style="margin: 24px 0 0 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; line-height: 1.5; color: #64748B;">It only takes a couple of minutes: company name, industry, and size.</p>
        """

        html_body = _render_email_layout(
            title="Finish setting up your company profile",
            preheader="A few details left before you can start hiring on Elevare.",
            body_content_html=body_content_html,
            footer_note="You received this email because you registered an employer account on Elevare.",
        )

        await self._send_html(
            subject="Finish setting up your Elevare company profile",
            recipients=[email],
            html_body=html_body,
        )

    async def send_kyc_reminder(
        self,
        email: str,
        first_name: str,
        company_name: str,
    ) -> None:
        """Nudge an onboarded employer who never submitted KYC documents.

        Sent once, at least 24 hours after the company profile was
        completed, if no KYC documents have been submitted yet. Approved
        KYC is what unlocks posting jobs, so this is the last step. See
        ``UserRepository.list_employers_missing_kyc``.
        """
        verification_link = f"{settings.app_url}/employer/verification"
        first_name = _h(first_name)
        greeting = f"Hi {first_name}," if first_name else "Hi,"
        company_label = _h(company_name) or "your company"

        body_content_html = f"""
        <h2 style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 20px; font-weight: 600; line-height: 1.4; color: #0F172A;">One step left: verify {company_label}</h2>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">{greeting}</p>
        <p style="margin: 0 0 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #334155;">Your company profile is set up, but you haven't submitted verification documents yet. Once approved, you'll be able to post jobs and start hiring on Elevare.</p>

        {_render_button("Submit verification documents", verification_link)}

        <p style="margin: 24px 0 0 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; line-height: 1.5; color: #64748B;">Reviews are usually quick once your documents are in.</p>
        """

        html_body = _render_email_layout(
            title=f"Verify {company_label}",
            preheader="Submit your documents to start posting jobs on Elevare.",
            body_content_html=body_content_html,
            footer_note="You received this email because you registered an employer account on Elevare.",
        )

        await self._send_html(
            subject="One step left before you can post jobs on Elevare",
            recipients=[email],
            html_body=html_body,
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
        self, employer_email: str, job_title: str, candidate_name: str, job_id: str
    ) -> None:
        """Log a stub employer new-application notification email."""
        logger.info(
            "STUB EMAIL SENT to %s: New application for %s by %s (job_id=%s)",
            employer_email,
            job_title,
            candidate_name,
            job_id,
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

    async def send_verification_reminder(
        self,
        email: str,
        first_name: str,
        verification_token: str,
        role: str,
    ) -> None:
        """Log a stub verification reminder with both role-correction links."""
        base = f"{settings.app_url}/verify-email?token={verification_token}"
        logger.info(
            "STUB VERIFICATION REMINDER to %s (role=%s)\n  employer: %s\n  candidate: %s",
            email,
            role,
            f"{base}&role=EMPLOYER",
            f"{base}&role=CANDIDATE",
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

    async def send_introduction_request(
        self,
        candidate_email: str,
        accept_url: str,
        decline_url: str,
        job_title: str,
    ) -> None:
        """Log a stub introduction request email."""
        logger.info(
            "STUB INTRODUCTION REQUEST to %s for role '%s'\n  Accept: %s\n  Decline: %s",
            candidate_email,
            job_title,
            accept_url,
            decline_url,
        )

    async def send_ai_interview_invite(
        self,
        candidate_email: str,
        interview_url: str,
        job_title: str,
        company_name: str,
    ) -> None:
        """Log a stub AI interview invite email."""
        logger.info(
            "STUB AI INTERVIEW INVITE to %s for role '%s' at '%s'\n  Link: %s",
            candidate_email,
            job_title,
            company_name,
            interview_url,
        )

    async def send_interview_restart_request(
        self,
        employer_email: str,
        candidate_name: str,
        job_title: str,
        company_name: str,
        manage_url: str,
    ) -> None:
        """Log a stub interview restart request email."""
        logger.info(
            "STUB INTERVIEW RESTART REQUEST to %s for candidate '%s' on role '%s' at '%s'\n  Manage: %s",
            employer_email,
            candidate_name,
            job_title,
            company_name,
            manage_url,
        )

    async def send_introduction_accepted(
        self,
        employer_email: str,
        job_title: str,
        profile_url: str,
    ) -> None:
        """Log a stub introduction accepted email."""
        logger.info(
            "STUB INTRODUCTION ACCEPTED to %s for role '%s'\n  Profile: %s",
            employer_email,
            job_title,
            profile_url,
        )

    async def send_introduction_declined(
        self,
        employer_email: str,
        job_title: str,
    ) -> None:
        """Log a stub introduction declined email."""
        logger.info(
            "STUB INTRODUCTION DECLINED to %s for role '%s' — credit refunded",
            employer_email,
            job_title,
        )

    async def send_introduction_request_admin(
        self,
        admin_email: str,
        employer_name: str,
        job_title: str,
        candidate_name: str,
    ) -> None:
        """Log a stub admin introduction request email."""
        logger.info(
            "STUB ADMIN INTRODUCTION REQUEST to %s — %s wants an intro to %s for '%s'",
            admin_email,
            employer_name,
            candidate_name,
            job_title,
        )

    async def send_role_notification(
        self,
        candidate_email: str,
        employer_name: str,
        job_title: str,
        job_url: str,
        register_url: str,
        employer_email: str | None = None,
    ) -> None:
        """Log a stub role notification email."""
        logger.info(
            "STUB ROLE NOTIFICATION to %s (reply-to=%s) — %s thinks you'd fit '%s'\n"
            "  View Job: %s\n  Register: %s",
            candidate_email,
            employer_email,
            employer_name,
            job_title,
            job_url,
            register_url,
        )

    async def send_kyc_rejection(
        self,
        employer_email: str,
        company_name: str | None,
        reason: str | None,
    ) -> None:
        """Log a stub KYC rejection email."""
        logger.info(
            "STUB KYC REJECTED to %s — company=%s reason=%s link=%s/employer/verification",
            employer_email,
            company_name,
            reason,
            settings.app_url,
        )

    async def send_kyc_approved(
        self,
        employer_email: str,
        company_name: str | None,
    ) -> None:
        """Log a stub KYC approved email."""
        logger.info(
            "STUB KYC APPROVED to %s — company=%s",
            employer_email,
            company_name,
        )

    async def send_kyc_submission_notification(
        self,
        admin_email: str,
        company_name: str | None,
        organization_id: str,
    ) -> None:
        """Log a stub KYC submission notification email."""
        logger.info(
            "STUB KYC SUBMITTED notify %s — company=%s organization_id=%s",
            admin_email,
            company_name,
            organization_id,
        )

    async def send_subscription_payment_failed(
        self,
        recipient_email: str,
        company_name: str | None,
        plan_name: str,
        retry_by: str,
    ) -> None:
        """Log a stub payment-failed email."""
        logger.info(
            "STUB PAYMENT FAILED to %s — company=%s plan=%s retry_by=%s",
            recipient_email,
            company_name,
            plan_name,
            retry_by,
        )

    async def send_invite_email(
        self,
        email: str,
        invite_link: str,
        company_name: str | None = None,
    ) -> None:
        """Log a stub invite email with a full clickable link."""
        logger.info(
            "STUB INVITE EMAIL to %s — company=%s\n  Accept: %s",
            email,
            company_name,
            invite_link,
        )

    async def send_role_switch_corrected(
        self,
        email: str,
        first_name: str,
        role: str,
    ) -> None:
        """Log a stub role-switch-corrected notification."""
        logger.info(
            "STUB ROLE SWITCH CORRECTED to %s (%s), now a %s account. Login: %s/login",
            email,
            first_name,
            role,
            settings.app_url,
        )

    async def send_onboarding_reminder(
        self,
        email: str,
        first_name: str,
    ) -> None:
        """Log a stub onboarding reminder."""
        logger.info(
            "STUB ONBOARDING REMINDER to %s (%s). Link: %s/employer/onboarding",
            email,
            first_name,
            settings.app_url,
        )

    async def send_kyc_reminder(
        self,
        email: str,
        first_name: str,
        company_name: str,
    ) -> None:
        """Log a stub KYC reminder."""
        logger.info(
            "STUB KYC REMINDER to %s (%s), company=%s. Link: %s/employer/verification",
            email,
            first_name,
            company_name,
            settings.app_url,
        )


def get_email_service() -> EmailService:
    """FastAPI dependency — returns ResendEmailService in production, StubEmailService in CI."""
    if settings.email_stub_mode or not settings.resend_api_key:
        return StubEmailService()
    return ResendEmailService()
