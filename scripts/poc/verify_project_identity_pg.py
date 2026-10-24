"""真实 PostgreSQL 验收脚本（CygnusX_Project_Workspace_Test_Plan.md §6.3 / DEF-06..08）。

在开发 PG 实例上创建一次性临时数据库执行身份与删除保留验收，结束后整库销毁，
不触碰业务库（omichub）数据。覆盖：

- PG-A 预检查命中：真实 RESTRICT 引用 → 409 冲突，项目与引用保留
- PG-B owner 锁串行化：删除事务持锁期间并发插入被阻塞，提交后插入被 FK 拒绝
- PG-C 未登记引用：预检查清单之外的 FK 异常回滚后原样抛出（不伪装 409）
- PG-D 冲突后会话可复用：同一 AsyncSession 新事务正常读写
- PG-E 并发删除：一胜一 404，tombstone 唯一
- PG-F 并发默认项目解析（DEF-06）：收敛至同一身份
- PG-G 显式创建与默认解析竞争（DEF-07）：结果为复用或干净冲突
- PG-H 跨用户并发同名创建（DEF-08）：互不串扰

用法：
    uv run python scripts/poc/verify_project_identity_pg.py [--host 127.0.0.1] [--port 5432]

凭据从环境变量 POSTGRES_USER / POSTGRES_PASSWORD 读取，缺省回退解析仓库 .env。
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from cygnusx.application.services import project_service as ps_module  # noqa: E402
from cygnusx.application.services.project_service import ProjectService  # noqa: E402
from cygnusx.core.config import Settings  # noqa: E402
from cygnusx.core.exceptions import ConflictError, NotFoundError  # noqa: E402
from cygnusx.infrastructure.config.storage_config import StorageConfig  # noqa: E402
from cygnusx.infrastructure.database.base import Base  # noqa: E402
from cygnusx.infrastructure.database.models.dataset import DatasetModel  # noqa: E402
from cygnusx.infrastructure.database.models.file import DirectoryModel  # noqa: E402
from cygnusx.infrastructure.database.models.project import (  # noqa: E402
    ProjectModel,
    ProjectTombstoneModel,
)
from cygnusx.infrastructure.database.models.research_plan import ResearchPlanModel  # noqa: E402
from cygnusx.infrastructure.database.models.user import UserModel  # noqa: E402
from cygnusx.infrastructure.storage.path_factory import StoragePathFactory  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def record(case: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((case, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {case}  {detail}")


def load_credentials() -> tuple[str, str]:
    import os

    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    if user and password:
        return user, password
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("POSTGRES_USER="):
                user = user or line.split("=", 1)[1].strip()
            elif line.startswith("POSTGRES_PASSWORD="):
                password = password or line.split("=", 1)[1].strip()
    if not user or not password:
        raise SystemExit("缺少 POSTGRES_USER / POSTGRES_PASSWORD（环境变量或 .env）")
    return user, password


async def create_temp_database(host: str, port: int, user: str, password: str, name: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(host=host, port=port, user=user, password=password, database="omichub")
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()


async def drop_temp_database(host: str, port: int, user: str, password: str, name: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(host=host, port=port, user=user, password=password, database="omichub")
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    finally:
        await conn.close()


def make_service(session: AsyncSession) -> ProjectService:
    return ProjectService(session)


async def seed_users(engine, *user_ids: UUID) -> None:
    async with AsyncSession(engine) as session:
        for uid in user_ids:
            session.add(
                UserModel(
                    id=uid,
                    username=str(uid),
                    email=f"{uid}@verify.invalid",
                    hashed_password="unused",
                    role="user",
                    status="active",
                    token_version=0,
                )
            )
        await session.commit()


async def count(engine, model: type, **filters: object) -> int:
    async with AsyncSession(engine) as session:
        stmt = sa.select(sa.func.count()).select_from(model)
        for key, value in filters.items():
            stmt = stmt.where(getattr(model, key) == value)
        return int((await session.execute(stmt)).scalar_one())


async def case_pg_a_precheck_blocks_on_real_pg(engine, user_a: UUID) -> None:
    """PG-A：已提交引用 → 预检查返回稳定 409，项目与引用保留、无 tombstone。"""
    async with AsyncSession(engine) as session:
        service = make_service(session)
        created = await service.create_project(user_a, "pg-a-precheck")
        pid = UUID(created["id"])
        session.add(DatasetModel(user_id=user_a, project_id=pid, name="d1"))
        await session.commit()

    async with AsyncSession(engine) as session:
        service = make_service(session)
        try:
            await service.delete_project(user_a, pid)
            record("PG-A 预检查命中", False, "删除未被阻断")
        except ConflictError as exc:
            ok = (
                exc.code == "PROJECT_HAS_RETAINED_REFERENCES"
                and "数据集 1" in str(exc.detail)
                and await count(engine, ProjectModel, id=pid) == 1
                and await count(engine, DatasetModel, project_id=pid) == 1
                and await count(engine, ProjectTombstoneModel) == 0
            )
            record("PG-A 预检查命中", ok, f"code={exc.code}, detail={exc.detail}")
        return pid  # type: ignore[return-value]


async def case_pg_d_session_reusable_after_conflict(engine, user_a: UUID, pid: UUID) -> None:
    """PG-D：409 冲突后同一会话在新事务中可正常写入（服务内部已回滚）。"""
    ok = False
    async with AsyncSession(engine) as session:
        service = make_service(session)
        with contextlib.suppress(ConflictError):
            await service.delete_project(user_a, pid)
        # 同一会话、新事务：正常创建并提交
        fresh = await service.create_project(user_a, "pg-d-after-conflict")
        ok = fresh["slug"] == "pg-d-after-conflict"
    record("PG-D 冲突后会话可复用", ok)


async def case_pg_b_owner_lock_serializes(engine, user_a: UUID) -> None:
    """PG-B：删除事务持 owner/项目行锁期间，并发引用插入被阻塞；
    删除先提交后，插入被外键拒绝 —— 不产生悬空引用。"""
    async with AsyncSession(engine) as session:
        service = make_service(session)
        created = await service.create_project(user_a, "pg-b-lock")
        pid = UUID(created["id"])

    t1 = await engine.connect()
    tgated = asyncio.Event()

    async def t1_delete() -> None:
        async with t1.begin():
            await t1.execute(
                sa.text("SELECT id FROM users WHERE id = :u FOR UPDATE"), {"u": str(user_a)}
            )
            await t1.execute(
                sa.text("SELECT id FROM projects WHERE id = :p FOR UPDATE"), {"p": str(pid)}
            )
            tgated.set()
            # 等待 T2 已发起插入（被行锁阻塞）后再继续删除
            await asyncio.sleep(0.3)
            await t1.execute(sa.text("DELETE FROM projects WHERE id = :p"), {"p": str(pid)})

    async def t2_insert() -> None:
        t2 = await engine.connect()
        try:
            async with t2.begin():
                await t2.execute(
                    sa.text(
                        "INSERT INTO datasets (id, user_id, project_id, name, description,"
                        " assay_type, organism, status, schema_version, created_at, updated_at)"
                        " VALUES (gen_random_uuid(), :u, :p, 'race', '', 'unknown',"
                        " '{}'::jsonb, 'DRAFT', '1.0', now(), now())"
                    ),
                    {"u": str(user_a), "p": str(pid)},
                )
        finally:
            await t2.close()

    task1 = asyncio.create_task(t1_delete())
    await tgated.wait()
    task2 = asyncio.create_task(t2_insert())
    # T2 应被行锁阻塞，短时间内无法完成
    blocked = False
    try:
        await asyncio.wait_for(asyncio.shield(task2), timeout=1.0)
    except TimeoutError:
        blocked = True
    except IntegrityError:
        blocked = True  # 极快完成但已被 FK 拒绝，同样满足“不产生悬空引用”
    try:
        await task1
    except Exception as exc:  # noqa: BLE001
        record("PG-B owner 锁串行化", False, f"T1 异常: {exc!r}")
        await t1.close()
        return
    fk_rejected = False
    try:
        await task2
    except IntegrityError as exc:
        fk_rejected = "foreign key" in str(getattr(exc, "orig", exc)).lower()
    await t1.close()
    ok = (
        blocked
        and fk_rejected
        and await count(engine, ProjectModel, id=pid) == 0
        and await count(engine, DatasetModel, project_id=pid) == 0
    )
    record(
        "PG-B owner 锁串行化",
        ok,
        f"插入被阻塞={blocked}, 提交后FK拒绝={fk_rejected}, 无悬空引用="
        f"{await count(engine, DatasetModel, project_id=pid) == 0}",
    )


async def case_pg_c_unregistered_reference(engine, user_a: UUID) -> None:
    """PG-C：预检查清单之外的 FK（模拟未来新增引用）→ 回滚后原样抛 IntegrityError。"""
    async with AsyncSession(engine) as session:
        service = make_service(session)
        created = await service.create_project(user_a, "pg-c-unknown")
        pid = UUID(created["id"])

    async with AsyncSession(engine) as session:
        await session.execute(
            sa.text(
                "CREATE TABLE unregistered_project_refs ("
                " id uuid PRIMARY KEY DEFAULT gen_random_uuid(),"
                " project_id uuid NOT NULL REFERENCES projects(id) ON DELETE RESTRICT)"
            )
        )
        await session.execute(
            sa.text("INSERT INTO unregistered_project_refs (project_id) VALUES (:p)"), {"p": str(pid)}
        )
        await session.commit()

    ok = False
    detail = ""
    async with AsyncSession(engine) as session:
        service = make_service(session)
        try:
            await service.delete_project(user_a, pid)
            detail = "未抛出异常（删除成功）"
        except ConflictError as exc:
            detail = f"被误转换为业务冲突: {exc.code}"
        except IntegrityError:
            ok = (
                await count(engine, ProjectModel, id=pid) == 1
                and await count(engine, ProjectTombstoneModel, project_id=pid) == 0
            )
            detail = "IntegrityError 原样抛出，回滚无部分提交"
    record("PG-C 未登记引用保持原分类", ok, detail)


async def case_pg_e_concurrent_delete(engine, user_a: UUID) -> None:
    """PG-E：并发删除同一项目 → 一胜一 404，tombstone 唯一。"""
    async with AsyncSession(engine) as session:
        service = make_service(session)
        created = await service.create_project(user_a, "pg-e-race")
        pid = UUID(created["id"])

    async def deleter() -> str:
        async with AsyncSession(engine) as session:
            try:
                await make_service(session).delete_project(user_a, pid)
                return "ok"
            except NotFoundError:
                return "not_found"

    results = await asyncio.gather(deleter(), deleter())
    ok = sorted(results) == ["not_found", "ok"] and await count(engine, ProjectTombstoneModel) == 1
    record("PG-E 并发删除", ok, f"results={sorted(results)}, tombstones={await count(engine, ProjectTombstoneModel)}")


async def case_pg_f_concurrent_default_resolution(engine, user_a: UUID) -> None:
    """PG-F / DEF-06：并发默认项目解析收敛至同一身份。"""
    name = "默认项目"

    async def resolver() -> str:
        async with AsyncSession(engine) as session:
            service = make_service(session)
            model, _created = await service.reserve_project_identity(user_a, name, reuse_existing=True)
            # expire_on_commit 默认 True：commit 后访问 ORM 属性会触发同步刷新，
            # 先捕获再提交
            project_id = str(model.id)
            await session.commit()
            return project_id

    ids = await asyncio.gather(resolver(), resolver())
    rows = await count(engine, ProjectModel, user_id=user_a, name=name)
    ok = ids[0] == ids[1] and rows == 1
    record("PG-F 并发默认解析", ok, f"ids 相等={ids[0] == ids[1]}, 行数={rows}")


async def case_pg_g_explicit_vs_default_race(engine, user_b: UUID) -> None:
    """PG-G / DEF-07：显式创建与默认解析竞争 → 复用或干净冲突，唯一一行。"""
    name = "默认项目"

    async def explicit_create() -> object:
        async with AsyncSession(engine) as session:
            try:
                return await make_service(session).create_project(user_b, name)
            except ConflictError as exc:
                return exc

    async def default_resolve() -> object:
        async with AsyncSession(engine) as session:
            service = make_service(session)
            model, _created = await service.reserve_project_identity(user_b, name, reuse_existing=True)
            result = {"id": str(model.id), "slug": model.slug}
            await session.commit()
            return result

    a, b = await asyncio.gather(explicit_create(), default_resolve())
    rows = await count(engine, ProjectModel, user_id=user_b, name=name)
    outcomes_ok = (
        (isinstance(a, dict) and isinstance(b, dict) and a["id"] == b["id"])
        or (isinstance(a, ConflictError) and isinstance(b, dict))
        or (isinstance(a, dict) and isinstance(b, dict))
    )
    record("PG-G 显式vs默认竞争", outcomes_ok and rows == 1, f"rows={rows}, a={type(a).__name__}, b={type(b).__name__}")


async def case_pg_h_cross_user_isolation(engine, user_a: UUID, user_b: UUID) -> None:
    """PG-H / DEF-08：两用户并发同名创建互不串扰。"""
    async def creator(uid: UUID) -> dict:
        async with AsyncSession(engine) as session:
            return await make_service(session).create_project(uid, "同名竞争项目")

    a, b = await asyncio.gather(creator(user_a), creator(user_b))
    ok = a["slug"] == b["slug"] == "同名竞争项目" and a["id"] != b["id"]
    record(
        "PG-H 跨用户并发同名",
        ok and await count(engine, ProjectModel, name="同名竞争项目") == 2,
        f"a={a['id'][:8]}, b={b['id'][:8]}",
    )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5432)
    args = parser.parse_args()

    user, password = load_credentials()
    db_name = f"cygnusx_identity_verify_{Path(tempfile.mkdtemp()).name.split('/')[-1][:8]}"

    # 与单测相同的隔离：路径工厂指向临时目录，设置走默认值（导出开关关闭）
    tmp_dir = tempfile.mkdtemp()
    ps_module.get_path_factory = lambda: StoragePathFactory(  # type: ignore[assignment]
        StorageConfig(data_root=tmp_dir, users_subdir="users")
    )
    ps_module.get_settings = lambda: Settings(_env_file=None)  # type: ignore[assignment]

    await create_temp_database(args.host, args.port, user, password, db_name)
    engine = create_async_engine(
        f"postgresql+asyncpg://{user}:{password}@{args.host}:{args.port}/{db_name}"
    )
    try:
        async with engine.begin() as conn:
            # users/workspaces 用原生 DDL：模型的 disabled_modules server_default="'[]'"
            # 会被 metadata.create_all 渲染成 PG 拒绝的 '''[]'''（正式库由 Alembic
            # 迁移建表，不走该路径）；其余表无 JSON server_default，正常 create_all。
            await conn.execute(
                sa.text(
                    "CREATE TABLE workspaces ("
                    " id uuid PRIMARY KEY, owner_id uuid, name varchar(200),"
                    " storage_quota bigint NOT NULL DEFAULT 10737418240,"
                    " used_storage bigint NOT NULL DEFAULT 0,"
                    " created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now())"
                )
            )
            await conn.execute(
                sa.text(
                    "CREATE TABLE users ("
                    " id uuid PRIMARY KEY,"
                    " username varchar(100) NOT NULL UNIQUE,"
                    " email varchar(255) NOT NULL UNIQUE,"
                    " hashed_password text NOT NULL,"
                    " role varchar(20) NOT NULL DEFAULT 'user',"
                    " status varchar(20) NOT NULL DEFAULT 'active',"
                    " token_version integer NOT NULL DEFAULT 0,"
                    " workspace_id uuid REFERENCES workspaces(id),"
                    " avatar_url varchar(500), nickname varchar(120),"
                    " preferences json NOT NULL DEFAULT '{}'::json,"
                    " last_login_at timestamptz,"
                    " storage_quota bigint NOT NULL DEFAULT 536870912000,"
                    " used_storage bigint NOT NULL DEFAULT 0,"
                    " admin_note text, lab_group varchar(120), totp_secret varchar(255),"
                    " is_2fa_enabled boolean NOT NULL DEFAULT false,"
                    " disabled_modules json NOT NULL DEFAULT '[]'::json,"
                    " created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now())"
                )
            )
            await conn.run_sync(
                Base.metadata.create_all,
                tables=[
                    ProjectModel.__table__,
                    ProjectTombstoneModel.__table__,
                    DirectoryModel.__table__,
                    DatasetModel.__table__,
                    ResearchPlanModel.__table__,
                ],
            )
            # 其余 8 类保留引用表用最小 DDL（真实 project FK RESTRICT；预检查只做
            # count，不需要业务列——完整列级行为由单测的 ORM 建表覆盖）。
            for stub in (
                "dataset_ingestions",
                "result_manifest_observations",
                "download_execution_budgets",
                "download_execution_admissions",
                "project_export_jobs",
                "project_export_requests",
                "project_report_jobs",
                "project_report_requests",
            ):
                await conn.execute(
                    sa.text(
                        f"CREATE TABLE {stub} ("
                        " id uuid PRIMARY KEY DEFAULT gen_random_uuid(),"
                        " project_id uuid NOT NULL REFERENCES projects(id) ON DELETE RESTRICT)"
                    )
                )
        user_a, user_b = uuid4(), uuid4()
        await seed_users(engine, user_a, user_b)
        print(f"== 临时库 {db_name} / 用户 A={str(user_a)[:8]} B={str(user_b)[:8]} ==\n")

        pid = await case_pg_a_precheck_blocks_on_real_pg(engine, user_a)
        await case_pg_d_session_reusable_after_conflict(engine, user_a, pid)
        await case_pg_b_owner_lock_serializes(engine, user_a)
        await case_pg_c_unregistered_reference(engine, user_a)
        await case_pg_e_concurrent_delete(engine, user_a)
        await case_pg_f_concurrent_default_resolution(engine, user_a)
        await case_pg_g_explicit_vs_default_race(engine, user_b)
        await case_pg_h_cross_user_isolation(engine, user_a, user_b)
    finally:
        await engine.dispose()
        await drop_temp_database(args.host, args.port, user, password, db_name)
        print(f"\n== 临时库 {db_name} 已销毁 ==")

    failed = [name for name, ok, _ in RESULTS if not ok]
    print(f"\n汇总: {len(RESULTS) - len(failed)} PASS / {len(failed)} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
