from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from cygnusx.core.exceptions import AuthorizationError
from cygnusx.core.report_preview import (
    context_digest,
    preview_report_id,
    sign_preview_claims,
    verify_preview_grant,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "mutation", ["report", "context", "session_owner", "expiry", "type", "signature", "missing_exp"]
)
def test_grants_fail_closed(mutation: str) -> None:
    report_id = uuid4()
    identity: dict[str, Any] = {
        "sub": str(uuid4()),
        "token_version": 0,
        "binding": context_digest("a" * 64),
        "exp": int(datetime.now(UTC).timestamp()) + 300,
    }
    grant = {**identity, "type": "report_preview", "report_id": str(report_id), "channel": "b" * 32}
    session = {**identity, "type": "report_preview_session"}
    context = "a" * 64
    if mutation == "report":
        report_id = uuid4()
    elif mutation == "context":
        context = "c" * 64
    elif mutation == "session_owner":
        session["sub"] = str(uuid4())
    elif mutation == "expiry":
        grant["exp"] = 1
    elif mutation == "type":
        grant["type"] = "access"
    elif mutation == "missing_exp":
        grant.pop("exp")
    token = sign_preview_claims(grant)
    if mutation == "signature":
        token = "x" + token
    with pytest.raises(AuthorizationError):
        verify_preview_grant(report_id, token, sign_preview_claims(session), context)


def test_only_exact_uuid_content_route_uses_browser_auth() -> None:
    report = uuid4()
    assert preview_report_id(f"/api/v1/reports/{report}/preview-content") == report
    for path in (
        f"/api/v1/reports/{report}",
        f"/api/v1/reports/{report}/preview-url",
        f"/api/v1/reports/{report}/preview-content/extra",
        "/api/v1/reports/stats",
    ):
        assert preview_report_id(path) is None
