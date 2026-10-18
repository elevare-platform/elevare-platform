"""The temporary password an admin hands to a new client."""

import pytest

from app.modules.auth.schemas import validate_password_strength
from app.modules.auth.security import generate_temporary_password

LOOK_ALIKES = set("0O1lI")


@pytest.mark.parametrize("_attempt", range(200))
def test_a_temporary_password_passes_the_platform_strength_rule(_attempt):
    password = generate_temporary_password()

    assert len(password) >= 12
    assert validate_password_strength(password) == password


@pytest.mark.parametrize("_attempt", range(200))
def test_a_temporary_password_has_no_look_alike_characters(_attempt):
    """It will be read out over the phone or typed from a message."""
    assert not (set(generate_temporary_password()) & LOOK_ALIKES)


def test_temporary_passwords_differ_every_time():
    assert len({generate_temporary_password() for _ in range(50)}) == 50
