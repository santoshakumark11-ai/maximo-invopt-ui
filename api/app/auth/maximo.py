"""
Maximo credential validation via OSLC whoami endpoint.

Flow:
  1. Client sends username + personal API key.
  2. We call GET {maximo_base_url}/oslc/whoami with the apikey header.
     MAS 9.1 routes Authorization: Basic and maxauth through Keycloak/OIDC
     redirects — only the native `apikey` header bypasses that flow.
  3. Maximo returns 200 + JSON with the user's display name and groups on success,
     or 401/403 on bad credentials.
  4. We return a MaximoUser dataclass on success, None on failure.
"""
import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class MaximoUser:
    username: str
    display_name: str
    groups: list[str]


async def validate_api_key(
    username: str,
    api_key: str,
    maximo_base_url: str,
    timeout: int = 30,
) -> MaximoUser | None:
    """
    Validate a personal Maximo API key against the OSLC whoami endpoint.

    Returns a MaximoUser on success, None if the credentials are wrong or
    if Maximo is unreachable.

    The /api/whoami response looks like:
      {
        "spi:loginID": "JANEDOE",
        "dcterms:title": "Jane Doe",
        "spi:groupList": [
            { "spi:groupname": "MAXEVERYONE" },
            { "spi:groupname": "INVOPT_VIEWER" }
        ]
      }
    """
    headers = {
        "apikey": api_key,
        "Accept": "application/json",
    }

    # Strip trailing slash then build the whoami URL.
    # MAS 9.1+: use /api/whoami with apikey header.
    # /oslc/whoami is redirected (302) through Keycloak/OIDC — do not use it.
    base = maximo_base_url.rstrip("/")
    url = f"{base}/api/whoami"

    try:
        async with httpx.AsyncClient(verify=False, timeout=timeout) as client:
            resp = await client.get(url, headers=headers)
    except httpx.RequestError as exc:
        logger.warning("Maximo whoami request failed: %s", exc)
        return None

    if resp.status_code in (401, 403):
        logger.info(
            "Maximo rejected API key for user %s (HTTP %s)", username, resp.status_code
        )
        return None

    if not resp.is_success:
        logger.warning(
            "Unexpected Maximo whoami status %s for user %s", resp.status_code, username
        )
        return None

    try:
        data = resp.json()
    except Exception:
        logger.warning("Maximo whoami returned non-JSON body")
        return None

    # Extract display name — some MAS versions use rdfs:label, others dcterms:title
    display_name = (
        data.get("rdfs:label")
        or data.get("dcterms:title")
        or data.get("spi:loginID")
        or username
    )

    # Extract group memberships
    group_list = data.get("spi:groupList", [])
    groups: list[str] = []
    for entry in group_list:
        name = entry.get("spi:groupname") or entry.get("groupname")
        if name:
            groups.append(name)

    # Verify the returned loginID matches the submitted username (case-insensitive)
    returned_login = data.get("spi:loginID", username).upper()
    if returned_login != username.upper():
        logger.warning(
            "Maximo whoami loginID mismatch: submitted=%s returned=%s",
            username,
            returned_login,
        )
        # Still proceed — the key is valid even if casing differs

    logger.info("Maximo API key OK for %s — groups: %s", returned_login, groups)
    return MaximoUser(
        username=returned_login,
        display_name=display_name,
        groups=groups,
    )
