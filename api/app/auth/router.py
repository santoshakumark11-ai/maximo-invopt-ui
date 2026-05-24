"""
Auth router — POST /auth/login, GET /auth/me
"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.maximo import validate_maximo_credentials
from app.auth.jwt_utils import create_token
from app.config import Settings, get_settings
from app.dependencies import CurrentUser, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


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

@router.post("/login", response_model=LoginResponse, summary="Authenticate with Maximo credentials")
async def login(
    body: LoginRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> LoginResponse:
    """
    Validate username/password against Maximo OSLC whoami, then issue a JWT.

    The JWT is signed with HS256 and contains: sub, name, groups, iat, exp.
    Clients should send it as `Authorization: Bearer <token>` on subsequent requests.
    """
    if not body.username or not body.password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="username and password are required",
        )

    maximo_user = await validate_maximo_credentials(
        username=body.username,
        password=body.password,
        maximo_base_url=settings.maximo_base_url,
        timeout=settings.maximo_timeout,
    )

    if maximo_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Maximo credentials",
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
