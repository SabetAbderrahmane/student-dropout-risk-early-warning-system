"""Explicit verified request context for older direct-service fixture tests.

New HTTP interleaving regressions authenticate through the real login endpoint.
Direct fixture calls still verify a signed token through get_current_user; they
do not rely on a service trusting an arbitrary ORM User argument.
"""

from fastapi.security import HTTPAuthorizationCredentials

from app.core.permissions import get_current_user
from app.core.security import create_access_token


def authenticated_actor(db, actor):
    return get_current_user(
        HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=create_access_token(
                str(actor.id), token_version=actor.token_version
            ),
        ),
        db,
    )
