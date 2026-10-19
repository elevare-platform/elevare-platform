"""Unsubscribe tokens: a link can switch off only the address it was made for."""

import base64

import pytest

from app.core.config import settings
from app.modules.email_preferences.tokens import (
    make_unsubscribe_token,
    normalize_email,
    read_unsubscribe_token,
)


def test_a_token_gives_back_the_address_it_was_made_for():
    token = make_unsubscribe_token("ada@example.com")

    assert read_unsubscribe_token(token) == "ada@example.com"


def test_the_address_is_normalised_so_case_and_spaces_do_not_matter():
    assert read_unsubscribe_token(make_unsubscribe_token("  Ada@Example.COM ")) == "ada@example.com"
    assert normalize_email(" Ada@Example.COM ") == "ada@example.com"


def test_a_token_is_safe_to_put_in_a_url():
    token = make_unsubscribe_token("ada+tag@example.com")

    assert all(ch.isalnum() or ch in "-_." for ch in token)
    assert read_unsubscribe_token(token) == "ada+tag@example.com"


def test_a_token_does_not_expire():
    """An unsubscribe link in a year-old email must still work: the same address
    always gets the same token, with nothing time-based in it."""
    assert make_unsubscribe_token("ada@example.com") == make_unsubscribe_token("ada@example.com")


def test_changing_the_address_inside_a_token_invalidates_it():
    """Someone cannot turn their own link into a link for another address."""
    _, signature = make_unsubscribe_token("ada@example.com").split(".")
    forged_address = base64.urlsafe_b64encode(b"victim@example.com").rstrip(b"=").decode()

    assert read_unsubscribe_token(f"{forged_address}.{signature}") is None


def test_a_token_signed_with_a_different_secret_is_rejected(monkeypatch):
    token = make_unsubscribe_token("ada@example.com")
    monkeypatch.setattr(settings, "hmac_secret", "a-completely-different-secret-value")

    assert read_unsubscribe_token(token) is None


@pytest.mark.parametrize(
    "garbage",
    [
        "",
        "no-dot-at-all",
        "a.b.c",
        ".",
        "....",
        "!!!.???",
        "YWRhQGV4YW1wbGUuY29t.",  # an address with no signature
        "YWRhQGV4YW1wbGUuY29t.AAAA",  # a wrong signature
        "é.é",
    ],
)
def test_malformed_or_unsigned_tokens_are_rejected_without_raising(garbage):
    assert read_unsubscribe_token(garbage) is None


def test_the_signature_is_not_valid_for_other_purposes():
    """Signed under its own prefix, so a raw HMAC of the address (which something
    else might one day produce) is not accepted."""
    import hashlib
    import hmac

    raw = hmac.new(settings.hmac_secret.encode(), b"ada@example.com", hashlib.sha256).digest()
    encoded_email = base64.urlsafe_b64encode(b"ada@example.com").rstrip(b"=").decode()
    encoded_raw = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    assert read_unsubscribe_token(f"{encoded_email}.{encoded_raw}") is None
