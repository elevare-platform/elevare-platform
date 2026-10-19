"""The Unsubscribe link in an email's footer, and the headers that make a mail
client's own Unsubscribe button work.

Both are made per recipient, because each carries a signed token for that one address.
"""

from app.core.config import settings
from app.modules.email_preferences.tokens import make_unsubscribe_token

# Where the shared email layout leaves room for the link. A recipient who must not be
# offered an unsubscribe (an essential email) gets the slot removed.
UNSUBSCRIBE_SLOT = "<!--unsubscribe-->"


def unsubscribe_page_url(email: str) -> str:
    """The page a person lands on from the footer link (a confirmation step)."""
    return f"{settings.app_url.rstrip('/')}/unsubscribe?token={make_unsubscribe_token(email)}"


def list_unsubscribe_headers(email: str) -> dict[str, str]:
    """RFC 8058 one-click headers, which put an Unsubscribe button in Gmail and other
    mail clients. The mail client POSTs to the URL itself, so it must be the API's
    address; without ``api_public_url`` configured there are no headers and the footer
    link is all the email carries."""
    if not settings.api_public_url:
        return {}
    url = (
        f"{settings.api_public_url.rstrip('/')}"
        f"/api/v1/email-preferences/unsubscribe?token={make_unsubscribe_token(email)}"
    )
    return {
        "List-Unsubscribe": f"<{url}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }


def _footer_html(email: str) -> str:
    return (
        '<p style="margin: 8px 0 0 0; font-family: -apple-system, BlinkMacSystemFont, '
        "'Segoe UI', Roboto, sans-serif; font-size: 12px; line-height: 1.5; "
        'color: #94A3B8; font-weight: 400;">'
        "Don't want emails like this? "
        f'<a href="{unsubscribe_page_url(email)}" target="_blank" '
        'style="color: #64748B; text-decoration: underline;">Unsubscribe</a>'
        "</p>"
    )


def with_unsubscribe(html: str, email: str) -> str:
    """The email's HTML with an Unsubscribe link for this recipient: in the layout's
    slot when it has one, otherwise just before the closing body tag (an email not
    built on the shared layout still gets one)."""
    footer = _footer_html(email)
    if UNSUBSCRIBE_SLOT in html:
        return html.replace(UNSUBSCRIBE_SLOT, footer)
    if "</body>" in html:
        return html.replace("</body>", f"{footer}</body>")
    return html + footer


def without_unsubscribe(html: str) -> str:
    """The email's HTML with the slot emptied (an essential email offers none)."""
    return html.replace(UNSUBSCRIBE_SLOT, "")
