"""
Maximo credential validation via OSLC whoami endpoint.

Flow:
  1. Client sends username + password.
  2. We call GET {maximo_base_url}/oslc/whoami with Authorization: Basic <b64(user:pass)>.
  3. Maximo returns 200 + JSON with the user's display name and groups on success,
     or 401/403 on bad credentials.
  4. We return a MaximoUser dataclass on success, None on failure.
"""
import base64
import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class MaximoUser:
    username: str
    display_name: str
    groups: list[str]


async def validate_maximo_credentials(
    username: str,
    password: str,
    maximo_base_url: str,
    timeout: int = 30,
) -> MaximoUser | None:
    """
    Validate username/password against Maximo's OSLC whoami endpoint.

    Returns a MaximoUser on success, None if the credentials are wrong or
    if Maximo is unreachable.

    The whoami response looks like:
      {
        "spi:loginID": "JANEDOE",
        "dcterms:title": "Jane Doe",
        "spi:groupList": [
            { "spi:groupname": "MAXEVERYONE" },
            { "spi:groupname": "INVOPT_VIEWER" }
        ]
      }
    """
    # Build Basic auth header
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {
        "Authorization": f"Basic {token}",
        "Accept": "application/json",
    }

    # Strip trailing slash then build the whoami URL.
    # MAS 9.x OSLC endpoint: /maximo/oslc/whoami
    base = maximo_base_url.rstrip("/")
    url = f"{base}/oslc/whoami"

    try:
        async with httpx.AsyncClient(verify=False, timeout=timeout) as client:
            resp = await client.get(url, headers=headers)
    except httpx.RequestError as exc:
        logger.warning("Maximo whoami request failed: %s", exc)
        return None

    if resp.status_code == 401 or resp.status_code == 403:
        logger.info("Maximo rejected credentials for user %s (HTTP %s)", username, resp.status_code)
        return None

    if not resp.is_success:
        logger.warning("Unexpected Maximo whoami status %s for user %s", resp.status_code, username)
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

    logger.info("Maximo auth OK for %s — groups: %s", username, groups)
    return MaximoUser(
        username=data.get("spi:loginID", username).upper(),
        display_name=display_name,
        groups=groups,
    )
