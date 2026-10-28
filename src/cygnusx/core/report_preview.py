"""Short-lived report-only grants, bound to a browser's revocable login context.

Neither the URL, the HttpOnly session cookie, nor the readable context nonce is
sufficient alone. Clearing the context nonce on logout invalidates every grant
in that browser synchronously, without changing the platform's Bearer auth.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import jwt

from cygnusx.core.config import get_settings
from cygnusx.core.exceptions import AuthorizationError
from cygnusx.core.security import decode_token

PREVIEW_CONTEXT_COOKIE = "cygnusx_report_context"
PREVIEW_SESSION_COOKIE = "cygnusx_report_session"
PREVIEW_COOKIE_PATH = "/api/v1/reports"
_CONTENT_PATH = re.compile(r"^/api/v1/reports/([0-9a-f-]{36})/preview-content$")


def preview_report_id(path: str) -> UUID | None:
    match = _CONTENT_PATH.fullmatch(path)
    if match:
        try:
            return UUID(match[1])
        except ValueError:
            pass
    return None


def context_digest(context: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", context):
        raise AuthorizationError("报告预览会话无效，请重新打开报告", code="PREVIEW_SESSION_INVALID")
    return hashlib.sha256(context.encode()).hexdigest()


def sign_preview_claims(claims: dict[str, Any]) -> str:
    settings = get_settings()
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_preview_grant(
    report_id: UUID, token: str, session_cookie: str, browser_context: str
) -> dict[str, Any]:
    """Validate both signatures and the browser binding; live ACL is checked by the API."""
    binding = context_digest(browser_context)
    grant = decode_token(token)
    session = decode_token(session_cookie)
    if (
        not grant
        or not session
        or grant.get("type") != "report_preview"
        or session.get("type") != "report_preview_session"
        or grant.get("report_id") != str(report_id)
        or not isinstance(grant.get("channel"), str)
        or not re.fullmatch(r"[0-9a-f]{32}", grant["channel"])
    ):
        raise AuthorizationError("报告预览凭证无效或已过期", code="PREVIEW_GRANT_INVALID")
    now = datetime.now(UTC).timestamp()
    for payload in (grant, session):
        expiry = payload.get("exp")
        if (
            not isinstance(expiry, (int, float))
            or expiry <= now
            or not isinstance(payload.get("sub"), str)
            or not isinstance(payload.get("token_version"), int)
            or not isinstance(payload.get("binding"), str)
            or not hmac.compare_digest(payload["binding"], binding)
        ):
            raise AuthorizationError("报告预览会话已失效", code="PREVIEW_SESSION_INVALID")
    if any(grant.get(key) != session.get(key) for key in ("sub", "token_version")):
        raise AuthorizationError("报告预览会话不匹配", code="PREVIEW_SESSION_INVALID")
    try:
        UUID(grant["sub"])
    except ValueError as exc:
        raise AuthorizationError("报告预览身份无效") from exc
    return grant
