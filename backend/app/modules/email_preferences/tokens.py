"""Signed unsubscribe tokens.

A token names one email address and proves Elevare issued it, so a link can switch off
only the address it was made for, and nobody can forge a link for someone else's
address. The address is readable inside the token (it is the person's own address, in
a link sent to them); only the signature stops tampering.

Tokens never expire: an unsubscribe link in a year-old email must still work.
"""

import base64
import hashlib
import hmac

from app.core.config import settings

# Keeps a signature made for unsubscribing from being valid for anything else that
# might one day be signed with the same secret.
_DOMAIN = b"elevare-email-unsubscribe:"


def normalize_email(email: str) -> str:
    """The form an address is stored and compared in."""
    return email.strip().lower()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(email: str) -> bytes:
    return hmac.new(
        settings.hmac_secret.encode(), _DOMAIN + email.encode(), hashlib.sha256
    ).digest()


def make_unsubscribe_token(email: str) -> str:
    """A token for this address: ``<address>.<signature>``, both URL-safe."""
    email = normalize_email(email)
    return f"{_b64(email.encode())}.{_b64(_sign(email))}"


def read_unsubscribe_token(token: str) -> str | None:
    """The address a token was made for, or None if it is malformed or was not made
    by us."""
    try:
        encoded_email, encoded_signature = token.split(".")
        email = _unb64(encoded_email).decode()
        signature = _unb64(encoded_signature)
    except (ValueError, UnicodeDecodeError):
        return None
    if not email or not hmac.compare_digest(signature, _sign(email)):
        return None
    return email
