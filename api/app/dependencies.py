"""
FastAPI dependency injection — shared across routers.
"""
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt_utils import decode_token
from app.config import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=True)


class CurrentUser:
    def __init__(self, username: str, display_name: str, groups: list[str]):
        self.username = username
        self.display_name = display_name
        self.groups = groups

    def has_group(self, *groups: str) -> bool:
        return any(g.upper() in [g2.upper() for g2 in self.groups] for g in groups)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentUser:
    """Decode and validate the Bearer JWT issued by POST /auth/login."""
    payload = decode_token(credentials.credentials, settings.jwt_secret)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return CurrentUser(
        username=payload["sub"],
        display_name=payload.get("name", payload["sub"]),
        groups=payload.get("groups", []),
    )
