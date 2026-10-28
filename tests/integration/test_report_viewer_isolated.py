"""Real SQLite/report files + ASGI middleware; no business database or storage access."""

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from cygnusx.api import deps
from cygnusx.api.v1 import reports
from cygnusx.application.services import report_service
from cygnusx.application.services.report_service import ReportService
from cygnusx.core.config import get_settings
from cygnusx.core.exceptions import CygnusXError
from cygnusx.core.report_preview import PREVIEW_CONTEXT_COOKIE, PREVIEW_SESSION_COOKIE
from cygnusx.core.security import create_access_token
from cygnusx.infrastructure.config.storage_config import StorageConfig
from cygnusx.infrastructure.database.models.report import ReportFileModel, ReportModel
from cygnusx.infrastructure.database.models.user import UserModel
from cygnusx.infrastructure.storage.backend import LocalStorageBackend
from cygnusx.infrastructure.storage.path_factory import StoragePathFactory
from cygnusx.middleware.auth import AuthMiddleware

pytestmark = pytest.mark.integration


class InlineSession:
    def __init__(self, session: Session) -> None:
        self.session = session

    async def __aenter__(self) -> "InlineSession":
        return self

    async def __aexit__(self, *_args: Any) -> None:
        pass

    async def get(self, model: Any, key: Any) -> Any:
        return self.session.get(model, key)

    async def execute(self, query: Any) -> Any:
        return self.session.execute(query)

    async def commit(self) -> None:
        self.session.commit()

    async def rollback(self) -> None:
        self.session.rollback()

    async def flush(self) -> None:
        self.session.flush()

    async def refresh(self, model: Any) -> None:
        self.session.refresh(model)

    async def delete(self, model: Any) -> None:
        self.session.delete(model)


@pytest.fixture
def viewer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    engine = create_engine("sqlite://")
    for model in (UserModel, ReportModel, ReportFileModel):
        model.__table__.create(engine)
    session = Session(engine, expire_on_commit=False)
    owner = UserModel(
        id=uuid4(),
        username="preview",
        email="p@example.test",
        hashed_password="-",
        role="user",
        status="active",
        token_version=0,
        disabled_modules=[],
    )
    report = ReportModel(
        id=uuid4(),
        task_id=uuid4(),
        user_id=owner.id,
        flow_id="rna_seq",
        flow_name="RNA-seq",
        title="合成报告",
        status="completed",
        sample_count=2,
        created_at=datetime.now(UTC),
        report_kind="scientific",
    )
    factory = StoragePathFactory(StorageConfig(data_root=str(tmp_path), users_subdir="users"))
    target = tmp_path / "report.html"
    target.write_text(
        "<html><body><button onclick=\"this.textContent='切换成功'\">样本</button></body></html>"
    )
    file = ReportFileModel(
        id=uuid4(),
        report_id=report.id,
        name="report.html",
        type="html",
        size=target.stat().st_size,
        path=str(target),
        is_primary=True,
    )
    session.add_all([owner, report, file])
    session.commit()
    db = InlineSession(session)
    monkeypatch.setattr(deps, "get_session_factory", lambda: lambda: db)
    monkeypatch.setattr(report_service, "get_path_factory", lambda: factory)
    monkeypatch.setattr(get_settings(), "research_delivery_read_enabled", False)
    app = FastAPI()
    app.include_router(reports.router, prefix="/api/v1/reports")
    app.add_middleware(AuthMiddleware)

    def service() -> ReportService:
        return ReportService(cast(AsyncSession, db), LocalStorageBackend(path_factory=factory))

    app.dependency_overrides[reports.get_report_service] = service

    @app.exception_handler(CygnusXError)
    async def error_handler(_request: Request, exc: CygnusXError) -> JSONResponse:
        return JSONResponse({"detail": exc.detail, "code": exc.code}, status_code=exc.status_code)

    token = create_access_token(str(owner.id), token_version=0)
    yield {
        "app": app,
        "owner": owner,
        "report": report,
        "file": file,
        "session": session,
        "target": target,
        "token": token,
        "service": service(),
    }
    session.close()
    engine.dispose()


@pytest.fixture
async def browser(viewer: dict[str, Any]) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=viewer["app"]), base_url="http://test"
    ) as client:
        client.headers["Authorization"] = f"Bearer {viewer['token']}"
        client.cookies.set(PREVIEW_CONTEXT_COOKIE, "a" * 64, domain="test.local", path="/")
        yield client


async def issue(browser: AsyncClient, viewer: dict[str, Any]) -> str:
    response = await browser.get(f"/api/v1/reports/{viewer['report'].id}/preview-url")
    assert response.status_code == 200, response.text
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    assert response.headers["cache-control"] == "no-store"
    return str(response.json()["url"])


async def test_browser_bound_url_renders_registered_bytes_and_denies_url_only(
    browser: AsyncClient, viewer: dict[str, Any]
) -> None:
    url = await issue(browser, viewer)
    browser.headers.pop("Authorization")  # native iframe navigation has no Bearer header
    response = await browser.get(url)
    assert response.status_code == 200
    assert "样本" in response.text
    assert 'sandbox="allow-scripts"' in response.text
    csp = response.headers["content-security-policy"]
    assert "sandbox allow-scripts" in csp and "connect-src 'none'" in csp
    assert "allow-same-origin" not in csp
    assert response.headers["referrer-policy"] == "no-referrer"
    async with AsyncClient(
        transport=ASGITransport(app=viewer["app"]), base_url="http://test"
    ) as stranger:
        assert (await stranger.get(url)).status_code == 403
        stranger.headers["Authorization"] = f"Bearer {viewer['token']}"
        assert (
            await stranger.get(url)
        ).status_code == 403  # even access token alone is insufficient
    # A preview URL is never an access token for other report APIs.
    assert (await browser.get(f"/api/v1/reports/{viewer['report'].id}")).status_code == 401


async def test_logout_context_removal_invalidates_even_remaining_httponly_cookie(
    browser: AsyncClient, viewer: dict[str, Any]
) -> None:
    url = await issue(browser, viewer)
    assert browser.cookies.get(PREVIEW_SESSION_COOKIE)
    browser.cookies.delete(PREVIEW_CONTEXT_COOKIE, domain="test.local", path="/")
    assert (await browser.get(url)).status_code == 403


@pytest.mark.parametrize(
    "change", ["disabled", "version", "module", "deleted", "expired", "missing"]
)
async def test_permission_and_file_state_are_rechecked_at_html_read(
    browser: AsyncClient, viewer: dict[str, Any], change: str
) -> None:
    url = await issue(browser, viewer)
    if change == "disabled":
        viewer["owner"].status = "disabled"
    elif change == "version":
        viewer["owner"].token_version = 1
    elif change == "module":
        viewer["owner"].disabled_modules = ["reports"]
    elif change == "deleted":
        viewer["session"].delete(viewer["report"])
    elif change == "expired":
        viewer["report"].status = "expired"
    else:
        viewer["target"].unlink()
    viewer["session"].commit()
    result = await browser.get(url)
    expected = {"deleted": 404, "expired": 409, "missing": 404}.get(change, 403)
    assert result.status_code == expected
    assert "样本" not in result.text


@pytest.mark.parametrize("state", ["expired", "generating", "missing", "no_html", "empty", "too_large"])
async def test_signing_rejects_unavailable_report_without_legacy_placeholder_success(
    browser: AsyncClient, viewer: dict[str, Any], state: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    if state in {"expired", "generating"}:
        viewer["report"].status = state
    elif state == "missing":
        viewer["target"].unlink()
    elif state == "no_html":
        viewer["file"].type = "pdf"
    elif state == "empty":
        viewer["target"].write_bytes(b"")
    else:
        monkeypatch.setattr(get_settings(), "report_preview_max_bytes", 1024)
        viewer["target"].write_text("x" * 2048)
    viewer["session"].commit()
    result = await browser.get(f"/api/v1/reports/{viewer['report'].id}/preview-url")
    assert result.status_code == (
        409 if state in {"expired", "generating"} else 422 if state == "too_large" else 404
    )


async def test_evidence_inner_document_keeps_scripts_disabled(
    browser: AsyncClient, viewer: dict[str, Any]
) -> None:
    viewer["report"].report_kind = "reproducibility"
    # Evidence archives must be under the owner root, as in the existing service.
    root = viewer["service"]._factory.user_root(str(viewer["owner"].id))
    root.mkdir(parents=True)
    target = root / "audit.html"
    target.write_text("<html><body>not_run<script>parent.stolen=true</script></body></html>")
    viewer["file"].path = str(target)
    viewer["session"].commit()
    result = await browser.get(await issue(browser, viewer))
    assert result.status_code == 200
    assert '<iframe sandbox=""' in result.text
    assert "not_run" in result.text


async def test_existing_list_stats_star_read_download_and_delete_remain_authenticated(
    browser: AsyncClient, viewer: dict[str, Any]
) -> None:
    path = f"/api/v1/reports/{viewer['report'].id}"
    listing = await browser.get("/api/v1/reports", params={"flow_id": "rna_seq"})
    assert listing.json()["total"] == 1
    assert (await browser.get("/api/v1/reports/stats")).json()["total"] == 1
    assert (await browser.patch(f"{path}/star", json={"is_starred": True})).json()["is_starred"]
    assert (await browser.patch(f"{path}/read")).json()["is_read"]
    download = await browser.get(f"{path}/files/{viewer['file'].id}/download")
    assert download.status_code == 200 and "attachment" in download.headers["content-disposition"]
    assert download.content == viewer["target"].read_bytes()
    assert (await browser.delete(path)).status_code == 204
    assert (await browser.get(path)).status_code == 404
    assert viewer["target"].exists()  # deleting the record does not delete archived bytes


async def test_cross_owner_url_and_report_id_tampering_are_denied(
    browser: AsyncClient, viewer: dict[str, Any]
) -> None:
    url = await issue(browser, viewer)
    other = UserModel(
        id=uuid4(),
        username="other",
        email="o@example.test",
        hashed_password="-",
        role="user",
        status="active",
        token_version=0,
        disabled_modules=[],
    )
    viewer["session"].add(other)
    viewer["session"].commit()
    async with AsyncClient(
        transport=ASGITransport(app=viewer["app"]), base_url="http://test"
    ) as client:
        client.headers["Authorization"] = (
            f"Bearer {create_access_token(str(other.id), token_version=0)}"
        )
        client.cookies.set(PREVIEW_CONTEXT_COOKIE, "b" * 64, domain="test.local", path="/")
        assert (await client.get(url)).status_code == 403
        assert (
            await client.get(f"/api/v1/reports/{viewer['report'].id}/preview-url")
        ).status_code == 404
    assert (
        await browser.get(url.replace(str(viewer["report"].id), str(uuid4())))
    ).status_code == 403


async def test_preview_reuses_integrity_checks(
    browser: AsyncClient, viewer: dict[str, Any]
) -> None:
    viewer["file"].sha256 = "0" * 64
    viewer["session"].commit()
    result = await browser.get(f"/api/v1/reports/{viewer['report'].id}/preview-url")
    assert result.status_code == 409
    assert "完整性" in result.json()["detail"]


async def test_registered_file_symlink_substitution_cannot_preview_other_data(
    browser: AsyncClient, viewer: dict[str, Any]
) -> None:
    url = await issue(browser, viewer)
    target = viewer["target"]
    other = target.parent / "other-report.html"
    other.write_text("PRIVATE OTHER REPORT")
    target.unlink()
    target.symlink_to(other)
    result = await browser.get(url)
    assert result.status_code == 404
    assert "PRIVATE OTHER REPORT" not in result.text
