"""真实 HTTP 验收脚本（CygnusX_Project_Workspace_Test_Plan.md §7）。

以进程内 ASGI 方式加载当前工作区代码（含本轮修复），连接开发栈真实
PostgreSQL / Redis 与真实认证中间件，以测试用户 + 真 JWT 走完整 HTTP 链路；
结束后清理本次创建的测试数据（用户行级联 + 物理用户目录）。

覆盖：创建→读取→改名（slug 不变）→overview→删除；空项目 204 / 重复删除 404；
科研引用 409 与错误结构；空 PATCH 422；跨用户 404 不泄露引用计数；list/count；
默认项目经真实会话创建入口触发与复用；删除默认项目后的新身份；sync-from-disk。

用法（宿主机端口映射）：
    POSTGRES_HOST=127.0.0.1 REDIS_HOST=127.0.0.1 \\
    uv run python scripts/poc/verify_project_identity_http.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from cygnusx.application.services.chat.session_management import ChatSessionManagement  # noqa: E402
from cygnusx.core.security import create_access_token, hash_password  # noqa: E402
from cygnusx.infrastructure.database.models.chat import ChatSessionModel  # noqa: E402
from cygnusx.infrastructure.database.models.dataset import DatasetModel  # noqa: E402
from cygnusx.infrastructure.database.models.file import DirectoryModel  # noqa: E402
from cygnusx.infrastructure.database.models.project import (  # noqa: E402
    ProjectModel,
    ProjectTombstoneModel,
)
from cygnusx.infrastructure.database.models.user import UserModel  # noqa: E402
from cygnusx.infrastructure.storage.path_factory import get_path_factory  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def record(case: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((case, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {case}  {detail}")


def db_url(host: str = "127.0.0.1", port: int = 5432) -> str:
    # 注意：导入 cygnusx 模块链会把 .env 的 POSTGRES_HOST 写入 os.environ，
    # 因此主机/端口必须显式传参，不读环境变量；凭据仅用于直连测试库。
    user = os.environ.get("POSTGRES_USER", "omichub")
    password = os.environ.get("POSTGRES_PASSWORD", "omichub_dev_password")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/omichub"


async def create_test_users(engine) -> tuple[UUID, UUID, str, str]:
    a, b = uuid4(), uuid4()
    async with AsyncSession(engine) as session:
        for uid, name in ((a, "verify_http_a"), (b, "verify_http_b")):
            session.add(
                UserModel(
                    id=uid,
                    username=f"{name}_{uid.hex[:8]}",
                    email=f"{name}_{uid.hex[:8]}@verify.invalid",
                    hashed_password=hash_password(f"pwd-{uid.hex}"),
                    role="user",
                    status="active",
                    token_version=0,
                )
            )
        await session.commit()
    token_a = create_access_token(str(a), token_version=0)
    token_b = create_access_token(str(b), token_version=0)
    return a, b, token_a, token_b


async def cleanup(engine, user_a: UUID, user_b: UUID) -> list[str]:
    """清理本次及历史运行残留（username LIKE verify_http_%）的测试数据。"""
    issues: list[str] = []
    rows = await fetch_scalar(
        engine,
        sa.select(sa.func.array_agg(UserModel.id)).where(
            UserModel.username.like("verify_http_%")
        ),
    )
    uids = list(rows or []) or [user_a, user_b]
    async with AsyncSession(engine) as session:
        for model, label in (
            (DatasetModel, "datasets"),
            (ChatSessionModel, "chat_sessions"),
            (DirectoryModel, "user_directories"),
            (ProjectTombstoneModel, "project_tombstones"),
            (ProjectModel, "projects"),
            (UserModel, "users"),
        ):
            try:
                col = ChatSessionModel.user_id if label == "chat_sessions" else None
                if col is not None:
                    await session.execute(sa.delete(model).where(col.in_([str(u) for u in uids])))
                elif model is UserModel:
                    await session.execute(sa.delete(model).where(UserModel.id.in_(uids)))
                else:
                    await session.execute(
                        sa.delete(model).where(model.user_id.in_(uids))
                    )
                await session.commit()
            except Exception as exc:  # noqa: BLE001
                await session.rollback()
                issues.append(f"{label}: {exc!r}")
    factory = get_path_factory()
    for uid in uids:
        try:
            factory.remove_user_root(str(uid))
        except Exception as exc:  # noqa: BLE001
            issues.append(f"storage:{uid}: {exc!r}")
    return issues


async def fetch_scalar(engine, stmt: sa.Select) -> object:
    async with AsyncSession(engine) as session:
        return (await session.execute(stmt)).scalar_one_or_none()


async def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5432)
    args = parser.parse_args()
    engine = create_async_engine(db_url(args.host, args.port))
    user_a, user_b, token_a, token_b = await create_test_users(engine)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    from cygnusx.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # H01 未认证
        resp = await client.get("/api/v1/projects")
        record("H01 未认证拒绝", resp.status_code in (401, 403), f"status={resp.status_code}")

        # H02 创建 P1
        resp = await client.post(
            "/api/v1/projects", json={"name": "Original"}, headers=headers_a
        )
        h02 = resp.status_code == 201 and resp.json().get("slug") == "Original"
        record("H02 创建项目 201", h02, f"status={resp.status_code}, body={resp.json()}")
        pid = resp.json()["id"]

        # H03 读取
        resp = await client.get(f"/api/v1/projects/{pid}", headers=headers_a)
        record(
            "H03 读取详情",
            resp.status_code == 200 and resp.json()["id"] == pid,
            f"status={resp.status_code}",
        )

        # H04 改名保留 slug
        resp = await client.patch(
            f"/api/v1/projects/{pid}", json={"name": "Renamed Project"}, headers=headers_a
        )
        h04 = (
            resp.status_code == 200
            and resp.json()["name"] == "Renamed Project"
            and resp.json()["slug"] == "Original"
            and resp.json()["id"] == pid
        )
        record(
            "H04 改名保留 slug",
            h04,
            f"name={resp.json().get('name')}, slug={resp.json().get('slug')}",
        )

        # H05 overview
        resp = await client.get(f"/api/v1/projects/{pid}/overview", headers=headers_a)
        record("H05 overview", resp.status_code == 200, f"status={resp.status_code}")

        # H06 空 PATCH → 422
        resp = await client.patch(f"/api/v1/projects/{pid}", json={}, headers=headers_a)
        record("H06 空 PATCH 422", resp.status_code == 422, f"status={resp.status_code}")

        # H07 干净项目删除 204 + 重复删除 404
        resp = await client.post(
            "/api/v1/projects", json={"name": "Clean-P2"}, headers=headers_a
        )
        p2 = resp.json()["id"]
        resp = await client.delete(f"/api/v1/projects/{p2}", headers=headers_a)
        first = resp.status_code == 204
        resp = await client.delete(f"/api/v1/projects/{p2}", headers=headers_a)
        record(
            "H07 删除 204 / 重复 404",
            first and resp.status_code == 404,
            f"first={first}, repeat={resp.status_code}",
        )

        # H08 科研引用阻断 409 + 错误结构 + DB 状态
        async with AsyncSession(engine) as session:
            session.add(DatasetModel(user_id=user_a, project_id=UUID(pid), name="verify-ds"))
            await session.commit()
        resp = await client.delete(f"/api/v1/projects/{pid}", headers=headers_a)
        body = resp.json()
        project_alive = await fetch_scalar(
            engine, sa.select(ProjectModel).where(ProjectModel.id == UUID(pid))
        )
        tombstones = await fetch_scalar(
            engine,
            sa.select(sa.func.count())
            .select_from(ProjectTombstoneModel)
            .where(ProjectTombstoneModel.project_id == UUID(pid)),
        )
        h08 = (
            resp.status_code == 409
            and body.get("code") == "PROJECT_HAS_RETAINED_REFERENCES"
            and "数据集" in str(body.get("detail"))
            and project_alive is not None
            and int(tombstones or 0) == 0
        )
        record(
            "H08 科研引用 409",
            h08,
            f"status={resp.status_code}, code={body.get('code')},"
            f" detail={str(body.get('detail'))[:60]}",
        )

        # H09 跨用户 404（读/改/删），不泄露引用计数
        codes = []
        last_detail = ""
        for method in ("get", "patch", "delete"):
            kwargs: dict = {"headers": headers_b}
            if method == "patch":
                kwargs["json"] = {"name": "stolen"}
            resp = await getattr(client, method)(f"/api/v1/projects/{pid}", **kwargs)
            codes.append(resp.status_code)
            last_detail = str(resp.json().get("detail", ""))
        record(
            "H09 跨用户拒绝",
            codes == [404, 404, 404] and "数据集" not in last_detail,
            f"codes={codes}",
        )

        # H10 list / count
        resp = await client.get("/api/v1/projects", headers=headers_a)
        listed = any(p["id"] == pid for p in resp.json())
        resp = await client.get("/api/v1/projects/count", headers=headers_a)
        total = resp.json().get("count", 0)
        record(
            "H10 list/count",
            listed and total >= 1,
            f"listed={listed}, count={total}",
        )

        # H11 默认项目经真实会话入口（project_id 空串 → 默认归档）
        model_id = await fetch_scalar(
            engine, sa.select(sa.text("id")).select_from(sa.text("ai_provider_configs")).limit(1)
        )
        if model_id is None:
            record("H11 默认项目（会话入口）", False, "无可用 ai_provider_configs")
        else:
            resp = await client.post(
                "/api/v1/chat/sessions",
                json={"model_id": str(model_id), "title": "验收会话", "project_id": ""},
                headers=headers_a,
            )
            default_1 = resp.json().get("project_id")
            resp = await client.post(
                "/api/v1/chat/sessions",
                json={"model_id": str(model_id), "title": "验收会话2", "project_id": ""},
                headers=headers_a,
            )
            default_2 = resp.json().get("project_id")
            record(
                "H11 默认项目复用",
                bool(default_1) and default_1 == default_2,
                f"default_1={str(default_1)[:8]}, default_2={str(default_2)[:8]}",
            )

            # H12 删除默认项目后新会话 → 新身份（slug -2）
            resp = await client.delete(f"/api/v1/projects/{default_1}", headers=headers_a)
            deleted = resp.status_code == 204
            resp = await client.post(
                "/api/v1/chat/sessions",
                json={"model_id": str(model_id), "title": "验收会话3", "project_id": ""},
                headers=headers_a,
            )
            default_3 = resp.json().get("project_id")
            new_slug = await fetch_scalar(
                engine,
                sa.select(ProjectModel.slug).where(ProjectModel.id == UUID(str(default_3))),
            )
            record(
                "H12 删除默认后新身份",
                deleted
                and default_3
                and default_3 != default_1
                and new_slug == f"{ChatSessionManagement.DEFAULT_PROJECT_NAME}-2",
                f"deleted={deleted}, new_slug={new_slug}",
            )

        # H13 sync-from-disk
        resp = await client.post("/api/v1/projects/sync-from-disk", headers=headers_a)
        record("H13 sync-from-disk", resp.status_code == 200, f"status={resp.status_code}")

        # H14 物理目录：改名后仍落原 slug 目录，不产生新名称目录
        user_root = get_path_factory().user_root(str(user_a))
        h14 = (user_root / "projects" / "Original").is_dir() and not (
            user_root / "projects" / "Renamed_Project"
        ).exists()
        record("H14 物理目录稳定", h14, f"original={ (user_root / 'projects' / 'Original').is_dir() }")

    issues = await cleanup(engine, user_a, user_b)
    await engine.dispose()
    if issues:
        print(f"\n清理遗留: {issues}")
    failed = [name for name, ok, _ in RESULTS if not ok]
    print(f"\n汇总: {len(RESULTS) - len(failed)} PASS / {len(failed)} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
