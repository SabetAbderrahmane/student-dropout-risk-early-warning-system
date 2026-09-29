from datetime import timedelta

import pytest

from app.core.security import (
    TokenValidationError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_is_hashed_and_verifiable() -> None:
    password = "A-secure-password-123!"
    encoded = hash_password(password)

    assert encoded != password
    assert encoded.startswith("$argon2")
    assert verify_password(password, encoded)
    assert not verify_password("incorrect", encoded)


def test_access_token_round_trip() -> None:
    token = create_access_token("9e783e9a-4b93-4c90-aedd-5034745323f0")
    payload = decode_access_token(token)

    assert payload["sub"] == "9e783e9a-4b93-4c90-aedd-5034745323f0"
    assert payload["type"] == "access"


def test_expired_token_is_rejected() -> None:
    token = create_access_token("user-id", expires_delta=timedelta(seconds=-1))

    with pytest.raises(TokenValidationError):
        decode_access_token(token)


def test_tampered_token_is_rejected() -> None:
    token = create_access_token("user-id")
    tampered = f"{token[:-1]}{'a' if token[-1] != 'a' else 'b'}"

    with pytest.raises(TokenValidationError):
        decode_access_token(tampered)

