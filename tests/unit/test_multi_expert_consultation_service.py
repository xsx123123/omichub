"""多专家并行会诊的无网络服务测试。"""

from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest

from cygnusx.application.services.multi_expert_consultation_service import (
    MultiExpertConsultationService,
)
from cygnusx.infrastructure.ai_provider.openai_compatible import ChatChunk


class ContextBuilderStub:
    async def assemble(
        self,
        agent_id: str,
        user_id: str,
        *,
        user_message: str | None = None,
        mode: str = "chat",
    ):
        assert user_id == ""
        assert user_message == "请分析这个项目"
        assert mode == "consultation"
        return SimpleNamespace(
            agent=SimpleNamespace(agent_id=agent_id, name=f"{agent_id} 专家"),
            model_config=SimpleNamespace(),
            system_prompt="专家系统提示",
        )


@pytest.mark.asyncio
async def test_collect_runs_experts_and_ignores_failed_opinion(monkeypatch) -> None:
    async def fake_stream(**kwargs) -> AsyncIterator[ChatChunk]:
        if kwargs["config"] is None:
            raise RuntimeError("missing config")
        yield ChatChunk(type="text", content="建议先检查输入数据质量。")

    monkeypatch.setattr(
        "cygnusx.application.services.multi_expert_consultation_service.provider_manager.chat_stream",
        fake_stream,
    )
    service = MultiExpertConsultationService(
        object(),
        context_builder=ContextBuilderStub(),  # type: ignore[arg-type]
    )

    opinions = await service.collect(["agent-rnaseq", "agent-viz"], "请分析这个项目")

    assert [item["agent_id"] for item in opinions] == ["agent-rnaseq", "agent-viz"]
    assert "多专家会诊意见" in service.render_prompt_context(opinions)


@pytest.mark.asyncio
async def test_collect_gives_each_expert_its_own_db_session(monkeypatch) -> None:
    """回归：多专家共享同一 AsyncSession 并发装配会被 SQLAlchemy 拒绝
    （InvalidRequestError: concurrent operations are not permitted），
    异常被 return_exceptions 静默丢弃导致意见缺失；
    默认路径必须为每位专家开独立会话（assemble 期间会话存活且互不相同）。"""

    # 强引用所有会话对象直至断言完成，避免 id() 因 GC 复用导致假重复。
    sessions_seen: list[object] = []

    class _FakeSession:
        async def __aenter__(self) -> "_FakeSession":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

    class _FakeBuilder:
        def __init__(self, session: object, agent_service: object) -> None:
            sessions_seen.append(session)

        async def assemble(
            self,
            agent_id: str,
            user_id: str,
            *,
            user_message: str | None = None,
            mode: str = "chat",
        ):
            return SimpleNamespace(
                agent=SimpleNamespace(agent_id=agent_id, name=f"{agent_id} 专家"),
                model_config=SimpleNamespace(),
                system_prompt="专家系统提示",
            )

    async def fake_stream(**kwargs) -> AsyncIterator[ChatChunk]:
        yield ChatChunk(type="text", content="建议先检查输入数据质量。")

    monkeypatch.setattr(
        "cygnusx.application.services.multi_expert_consultation_service.provider_manager.chat_stream",
        fake_stream,
    )
    # 注意：collect 内引用的是本模块全局绑定的 AgentContextBuilder，
    # 必须 patch multi_expert_consultation_service 模块上的名字。
    monkeypatch.setattr(
        "cygnusx.application.services.multi_expert_consultation_service.AgentContextBuilder",
        _FakeBuilder,
    )
    # get_session_factory()() → 独立会话上下文管理器
    monkeypatch.setattr(
        "cygnusx.infrastructure.database.session.get_session_factory",
        lambda: (lambda: _FakeSession()),
    )

    service = MultiExpertConsultationService(object())
    opinions = await service.collect(["agent-a", "agent-b", "agent-c"], "请分析这个项目")

    assert len(sessions_seen) == 3
    assert len({id(session) for session in sessions_seen}) == 3
    assert [item["agent_id"] for item in opinions] == ["agent-a", "agent-b", "agent-c"]
