from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import get_settings

password_hash = PasswordHash.recommended()


class TokenValidationError(ValueError):
    """Raised when an access token cannot be trusted."""


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(
    subject: str, expires_delta: timedelta | None = None, *, token_version: int = 0
) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "type": "access",
        "iat": now,
        "exp": expires_at,
        "ver": token_version,
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "type", "iat", "exp"]},
        )
    except InvalidTokenError as exc:
        raise TokenValidationError("Invalid or expired access token") from exc

    if payload.get("type") != "access" or not isinstance(payload.get("sub"), str):
        raise TokenValidationError("Invalid access token claims")
    # Pre-migration tokens remain valid only for unchanged legacy accounts at v0.
    version = payload.get("ver", 0)
    if type(version) is not int or version < 0:
        raise TokenValidationError("Invalid credential version")
    return payload
