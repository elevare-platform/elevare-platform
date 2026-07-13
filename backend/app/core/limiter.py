"""Rate limiting configuration for the Elevare API.

Uses slowapi (Redis-backed) to enforce per-IP and per-user limits.
The limiter instance is imported by routers that need route-level limits.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Default key function — identifies requests by client IP address.
# Routes that need per-user limiting override this with a custom key_func.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],  # global backstop — all routes
)
