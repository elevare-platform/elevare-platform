"""A name or phone number too long for its column is refused with a 422, not a 500.

first_name and last_name are String(30) and phone_number is String(15), but the register
schema allowed 100 and 16, so a long first name passed validation and then failed in the
database as a server error. These tests tie the limits to the columns."""

import pytest

from app.modules.auth.schemas import (
    MAX_NAME_LENGTH,
    MAX_PHONE_LENGTH,
    AcceptInviteRequest,
    RegisterRequest,
    validate_phone_digits,
)
from app.modules.users.models import User

# A valid international (network) number that is 16 characters in E.164: a "+" and 15 digits.
SIXTEEN_CHARACTERS = "+883510012345678"


def payload(**overrides) -> dict:
    data = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada.limits@example.com",
        "phone_number": "+2348012345678",
        "password": "Password123#",
        "confirm_password": "Password123#",
        "role": "CANDIDATE",
    }
    data.update(overrides)
    return data


# --- the limits match the columns -------------------------------------------------------


def test_the_name_limit_is_exactly_the_length_of_the_name_columns():
    assert MAX_NAME_LENGTH == User.first_name.property.columns[0].type.length
    assert MAX_NAME_LENGTH == User.last_name.property.columns[0].type.length


def test_the_phone_limit_is_exactly_the_length_of_the_phone_column():
    assert MAX_PHONE_LENGTH == User.phone_number.property.columns[0].type.length


# --- the schemas ------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["first_name", "last_name"])
def test_a_name_at_the_limit_is_accepted_and_one_more_is_not(field):
    RegisterRequest(**payload(**{field: "a" * MAX_NAME_LENGTH}))
    with pytest.raises(ValueError):
        RegisterRequest(**payload(**{field: "a" * (MAX_NAME_LENGTH + 1)}))


@pytest.mark.parametrize("field", ["first_name", "last_name"])
def test_the_invite_form_has_the_same_name_limit(field):
    invite = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "phone_number": "+2348012345678",
        "password": "Password123#",
        "confirm_password": "Password123#",
    }
    AcceptInviteRequest(**{**invite, field: "a" * MAX_NAME_LENGTH})
    with pytest.raises(ValueError):
        AcceptInviteRequest(**{**invite, field: "a" * (MAX_NAME_LENGTH + 1)})


def test_a_phone_number_that_is_valid_but_too_long_to_store_is_refused():
    assert len(SIXTEEN_CHARACTERS) == MAX_PHONE_LENGTH + 1
    with pytest.raises(ValueError, match="too long"):
        validate_phone_digits(SIXTEEN_CHARACTERS)
    with pytest.raises(ValueError):
        RegisterRequest(**payload(phone_number=SIXTEEN_CHARACTERS))


def test_ordinary_phone_numbers_still_pass():
    assert validate_phone_digits("+2348012345678") == "+2348012345678"
    assert validate_phone_digits("+44 7911 123456") == "+447911123456"


# --- the symptom, over HTTP -------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_long_first_name_is_a_422_that_names_the_field(client):
    response = await client.post("/api/v1/auth/register", json=payload(first_name="a" * 31))

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert [d["field"] for d in body["details"]] == ["first_name"]


@pytest.mark.asyncio
async def test_a_first_name_at_the_limit_registers(client):
    response = await client.post(
        "/api/v1/auth/register",
        json=payload(first_name="a" * MAX_NAME_LENGTH, email="at.limit@example.com"),
    )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_a_long_valid_phone_number_is_a_422_not_a_500(client):
    response = await client.post(
        "/api/v1/auth/register", json=payload(phone_number=SIXTEEN_CHARACTERS)
    )

    assert response.status_code == 422
    assert [d["field"] for d in response.json()["details"]] == ["phone_number"]
