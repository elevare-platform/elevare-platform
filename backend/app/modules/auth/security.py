"""Password hashing and token utilities for authentication.

Wraps ``bcrypt`` for password operations and the standard
``secrets`` / ``hashlib`` modules for secure token generation and
one-way token hashing (used for email-verification and password-reset
tokens stored in the database).
"""

import hashlib
import secrets

import bcrypt

_ROUNDS = 12


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the given plain-text password.

    Args:
        plain: The raw password string supplied by the user.

    Returns:
        A bcrypt-hashed string safe to store in the database.

    """
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=_ROUNDS)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify that the plain-text password matches the hash.

    Args:
        plain: The raw password string supplied by the user.
        hashed: The hashed password from the database.

    Returns:
        True if the password is correct, False otherwise.

    """
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# Characters for a temporary password. No look-alikes (0/O, 1/l/I): it is read out
# over the phone or typed from a message. Every symbol is one the platform's
# strength rule accepts.
_TEMP_LOWER = "abcdefghijkmnopqrstuvwxyz"
_TEMP_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_TEMP_DIGITS = "23456789"
_TEMP_SYMBOLS = "!@#$%&*"
_TEMP_LENGTH = 14


def generate_temporary_password() -> str:
    """Generate a random temporary password for an account an admin provisions.

    Always contains a lowercase letter, an uppercase letter, a digit and a symbol,
    so it passes the platform's own strength rule, and never contains look-alike
    characters. Built from ``secrets`` (a cryptographic source), not ``random``.
    """
    required = [
        secrets.choice(_TEMP_LOWER),
        secrets.choice(_TEMP_UPPER),
        secrets.choice(_TEMP_DIGITS),
        secrets.choice(_TEMP_SYMBOLS),
    ]
    pool = _TEMP_LOWER + _TEMP_UPPER + _TEMP_DIGITS + _TEMP_SYMBOLS
    rest = [secrets.choice(pool) for _ in range(_TEMP_LENGTH - len(required))]
    characters = required + rest
    secrets.SystemRandom().shuffle(characters)
    return "".join(characters)


def generate_token() -> str:
    """Generate a secure random token.

    Returns:
        A URL-safe token string.

    """
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    """Return a SHA-256 hex digest of the raw token for safe DB storage."""
    return hashlib.sha256(raw_token.encode()).hexdigest()
