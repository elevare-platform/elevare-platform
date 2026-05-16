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

def generate_token() -> str:
    """Generate a secure random token.

    Returns:
        A URL-safe token string.

    """
    return secrets.token_urlsafe(32)

def hash_token(raw_token: str) -> str:
    """Return a SHA-256 hex digest of the raw token for safe DB storage."""
    return hashlib.sha256(raw_token.encode()).hexdigest()
