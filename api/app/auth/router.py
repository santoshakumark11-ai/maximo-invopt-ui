"""
Auth router — POST /auth/login, GET /auth/me
"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.maximo import validate_api_key
from app.auth.jwt_utils import create_token
from app.config import Settings, get_settings
from app.dependencies import CurrentUser, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    api_key: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    display_name: str
    groups: list[str]


class MeResponse(BaseModel):
    username: str
    display_name: str
    groups: list[str]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse, summary="Authenticate with Maximo API key")
async def login(
    body: LoginRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> LoginResponse:
    """
    Validate username + personal API key against Maximo OSLC whoami, then issue a JWT.

    The JWT is signed with HS256 and contains: sub, name, groups, iat, exp.
    Clients should send it as `Authorization: Bearer <token>` on subsequent requests.

    Note: MAS 9.1 requires the native `apikey` header — Basic auth and maxauth
    are redirected through Keycloak/OIDC and do not work for REST calls.
    """
    if not body.username or not body.api_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="username and api_key are required",
        )

    maximo_user = await validate_api_key(
        username=body.username,
        api_key=body.api_key,
        maximo_base_url=settings.maximo_base_url,
        timeout=settings.maximo_timeout,
    )

    if maximo_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Maximo username or API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_token(
        username=maximo_user.username,
        display_name=maximo_user.display_name,
        groups=maximo_user.groups,
        secret=settings.jwt_secret,
        expire_seconds=settings.jwt_expire_seconds,
    )

    logger.info("Issued JWT for %s", maximo_user.username)

    return LoginResponse(
        access_token=token,
        expires_in=settings.jwt_expire_seconds,
        display_name=maximo_user.display_name,
        groups=maximo_user.groups,
    )


@router.get("/me", response_model=MeResponse, summary="Return current user info from JWT")
def me(current_user: Annotated[CurrentUser, Depends(get_current_user)]) -> MeResponse:
    """Return the authenticated user's identity decoded from their Bearer token."""
    return MeResponse(
        username=current_user.username,
        display_name=current_user.display_name,
        groups=current_user.groups,
    )
