"""
JWT utilities — HS256 encode / decode using python-jose.
"""
from datetime import datetime, timezone, timedelta
from typing import Any

from jose import JWTError, jwt

ALGORITHM = "HS256"


def create_token(
    username: str,
    display_name: str,
    groups: list[str],
    secret: str,
    expire_seconds: int,
) -> str:
    """Return a signed JWT with standard + custom claims."""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": username,
        "name": display_name,
        "groups": groups,
        "iat": now,
        "exp": now + timedelta(seconds=expire_seconds),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(token: str, secret: str) -> dict[str, Any] | None:
    """
    Decode and verify a JWT.

    Returns the payload dict on success, None if the token is invalid or expired.
    """
    try:
        payload: dict[str, Any] = jwt.decode(token, secret, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
