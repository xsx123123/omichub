"""并行子 Agent fan-out 的无网络服务测试。

覆盖：并行成立、失败隔离、防递归工具剥离、超时、工具回环与独占 session、
开关与 spawnable 白名单校验。
"""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from cygnusx.application.services import parallel_subagent_service as pss
from cygnusx.infrastructure.ai_provider.openai_compatible import ChatChunk

# --- 桩件 -----------------------------------------------------------------


def _ctx(agent_id: str, tools: list | None = None, spawnable: bool = True):
    return SimpleNamespace(
        agent=SimpleNamespace(agent_id=agent_id, name=f"{agent_id} 名称"),
        model_config=SimpleNamespace(),
        system_prompt="系统提示",
        tools=tools or [],
        features={"subagents_spawnable": spawnable},
        mcp_servers=[],
        skills=[],
        max_tokens=4096,
    )


class AgentServiceStub:
    """按 agent_id 返回预置上下文；记录是否被顺序调用。"""

    def __init__(self, contexts: dict):
        self._contexts = contexts

    async def assemble_context(self, agent_id: str):
        return self._contexts.get(agent_id)


class FakeSession(AsyncSession):
    """ToolInvocationContext.db 按 isinstance(AsyncSession) 校验，故继承真类；
    不调用 super().__init__，仅作占位桩。"""

    created = 0

    def __init__(self):
        type(self).created += 1

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


class FakeSessionCM:
    def __init__(self):
        self.session: FakeSession | None = None

    async def __aenter__(self) -> FakeSession:
        self.session = FakeSession()
        return self.session

    async def __aexit__(self, *exc) -> bool:
        return False


class FakeSessionFactory:
    def __call__(self) -> FakeSessionCM:
        return FakeSessionCM()


class FakeBridge:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def execute(self, user_id, tool_name, arguments, context=None):
        self.calls.append((tool_name, dict(arguments or {})))
        return {"success": True, "llm_payload": {"echo": arguments}}


_SCHEMA_REGISTRY = {
    "workspace_read": SimpleNamespace(invocation_mode="backend_sync", requires_confirm=False),
    "parallel_subagents": SimpleNamespace(invocation_mode="backend_sync", requires_confirm=False),
    "transfer_to_agent": SimpleNamespace(invocation_mode="backend_sync", requires_confirm=False),
    "long_task": SimpleNamespace(invocation_mode="analysis_flow", requires_confirm=False),
    "danger_tool": SimpleNamespace(invocation_mode="backend_sync", requires_confirm=True),
}


@pytest.fixture
def env(monkeypatch, tmp_path):
    """统一打桩：settings / schema_loader / session factory / bridge。"""
    settings = pss.get_settings()
    monkeypatch.setattr(settings, "subagent_fanout_enabled", True)
    monkeypatch.setattr(settings, "subagent_max_parallel", 4)
    monkeypatch.setattr(settings, "subagent_max_concurrent", 3)
    monkeypatch.setattr(settings, "subagent_child_timeout_seconds", 60)
    monkeypatch.setattr(settings, "subagent_max_rounds_per_child", 6)
    monkeypatch.setattr(settings, "subagent_max_children_per_message", 1)
    monkeypatch.setattr(settings, "storage_path", str(tmp_path))

    monkeypatch.setattr(
        pss, "schema_loader", SimpleNamespace(get_tool=lambda name: _SCHEMA_REGISTRY.get(name))
    )
    bridge = FakeBridge()
    monkeypatch.setattr(
        "cygnusx.application.services.tool_bridge_service.get_tool_bridge_service",
        lambda: bridge,
    )
    FakeSession.created = 0
    monkeypatch.setattr(pss, "get_session_factory", lambda: FakeSessionFactory())

    # DB 平台设置开关桩：默认关（env 开关在 settings 上单独控制）
    class SiteSettingsServiceStub:
        db_flag = False

        def __init__(self, db):
            pass

        async def is_subagent_fanout_enabled(self) -> bool:
            return type(self).db_flag

    monkeypatch.setattr(
        "cygnusx.application.services.site_settings_service.SiteSettingsService",
        SiteSettingsServiceStub,
    )
    return SimpleNamespace(
        settings=settings, bridge=bridge, tmp_path=tmp_path, site=SiteSettingsServiceStub
    )


def _patch_provider(monkeypatch, handler):
    """handler(messages, kwargs) 为异步生成器函数，按 messages 首条内容路由子任务行为。"""
    seen: dict[str, object] = {"tools": []}

    async def fake_stream(*, config, messages, system_prompt=None, **kwargs):
        seen["tools"].append(kwargs.get("tools"))
        async for chunk in handler(messages, kwargs):
            yield chunk

    monkeypatch.setattr(pss, "provider_manager", SimpleNamespace(chat_stream=fake_stream))
    return seen


# --- 测试 -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_fanout_parallel_success_and_tool_filtering(env, monkeypatch) -> None:
    contexts = {
        "agent-a": _ctx(
            "agent-a",
            tools=[
                {"function": {"name": "parallel_subagents"}},  # C2 必须被剥离
                {"function": {"name": "transfer_to_agent"}},  # C3 必须被剥离
                {"function": {"name": "danger_tool"}},  # C4 必须被剥离
                {"function": {"name": "long_task"}},  # analysis_flow 必须被剥离
                {"function": {"name": "workspace_read"}},  # 唯一保留
                {"function": {"name": "some_mcp_tool"}},  # 桥外工具必须被剥离
            ],
        ),
        "agent-b": _ctx("agent-b"),
    }
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    async def slow_text(messages, kwargs):
        await asyncio.sleep(0.1)
        first = messages[0]["content"]
        yield ChatChunk(type="text", content=f"结论：{'A' if 'task-a' in first else 'B'}")

    seen = _patch_provider(monkeypatch, slow_text)

    started = time.monotonic()
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="agent-general",
        parent_session_id="sess-1",
        context_summary="共享背景",
        tasks=[
            {"agent_id": "agent-a", "task": "task-a 内容"},
            {"agent_id": "agent-b", "task": "task-b 内容"},
        ],
        db=SimpleNamespace(),
    )
    elapsed = time.monotonic() - started

    assert result["success"] is True
    assert result["llm_payload"]["summary"].startswith("2/2 个子任务成功")
    statuses = [item["status"] for item in result["llm_payload"]["results"]]
    assert statuses == ["ok", "ok"]
    # 并行成立：两个各睡 0.1s 的子任务总墙钟应明显小于串行 0.2s
    assert elapsed < 0.19, f"fan-out 未并行执行，elapsed={elapsed:.3f}s"
    # 防递归/控制工具剥离：任何子循环都见不到被禁工具；agent-a 只保留 workspace_read
    forbidden = {
        "parallel_subagents",
        "transfer_to_agent",
        "long_task",
        "some_mcp_tool",
    }
    name_sets = [
        {(t.get("function") or {}).get("name") for t in (tools or [])} for tools in seen["tools"]
    ]
    assert all(names.isdisjoint(forbidden) for names in name_sets)
    assert any("workspace_read" in names for names in name_sets)


@pytest.mark.asyncio
async def test_fanout_preserves_long_stage_output_for_downstream_agents(env, monkeypatch) -> None:
    contexts = {"agent-general": _ctx("agent-general")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))
    marker = "LONG_PLAN_FINAL_CONTRACT"
    long_plan = "研究步骤与数据契约。" * 300 + marker

    async def handler(_messages, _kwargs):
        yield ChatChunk(type="text", content=long_plan)

    _patch_provider(monkeypatch, handler)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-1",
        context_summary="研究背景",
        tasks=[{"agent_id": "agent-general", "task": "形成完整研究计划"}],
        db=SimpleNamespace(),
    )

    answer = result["llm_payload"]["results"][0]["answer"]
    assert marker in answer
    assert len(answer) > 1200


@pytest.mark.asyncio
async def test_fanout_accumulates_text_across_tool_rounds(env, monkeypatch) -> None:
    contexts = {"agent-code": _ctx("agent-code", tools=[{"function": {"name": "workspace_read"}}])}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    async def fake_execute(*_args, **_kwargs):
        return {"success": True, "result": {"content": "upstream"}}

    monkeypatch.setattr(pss, "execute_studio_tool", fake_execute)

    async def handler(messages, _kwargs):
        if len(messages) == 1:
            yield ChatChunk(type="text", content="第一阶段完整设计。")
            yield ChatChunk(
                type="tool_calls",
                metadata={
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "function": {
                                "name": "workspace_read",
                                "arguments": '{"path":"output/upstream.md"}',
                            },
                        }
                    ]
                },
            )
        else:
            yield ChatChunk(type="text", content="第二阶段完整代码与交付说明。")

    _patch_provider(monkeypatch, handler)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-1",
        context_summary="",
        tasks=[{"agent_id": "agent-code", "task": "生成完整代码", "workspace_access": True}],
        db=SimpleNamespace(),
    )

    answer = result["llm_payload"]["results"][0]["answer"]
    assert "第一阶段完整设计" in answer
    assert "第二阶段完整代码与交付说明" in answer


@pytest.mark.asyncio
async def test_fanout_emits_correlated_tool_reinjection_events(env, monkeypatch) -> None:
    contexts = {"agent-code": _ctx("agent-code", tools=[{"function": {"name": "workspace_read"}}])}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))
    events: list[dict] = []

    async def fake_execute(*_args, **_kwargs):
        return {"success": True, "result": {"content": "upstream"}}

    monkeypatch.setattr(pss, "execute_studio_tool", fake_execute)

    async def handler(messages, _kwargs):
        if len(messages) == 1:
            yield ChatChunk(
                type="tool_calls",
                metadata={
                    "tool_calls": [{
                        "id": "call-1",
                        "function": {"name": "workspace_read", "arguments": '{"path":"output/upstream.md"}'},
                    }],
                },
            )
        else:
            yield ChatChunk(type="text", content="已基于文件完成分析。")

    _patch_provider(monkeypatch, handler)
    await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-1",
        context_summary="",
        tasks=[{"agent_id": "agent-code", "task": "读取文件并分析", "workspace_access": True}],
        db=SimpleNamespace(),
        on_event=events.append,
    )

    event_types = [event["type"] for event in events]
    assert event_types.index("worker_tool_call") < event_types.index("worker_tool_started")
    assert event_types.index("worker_tool_started") < event_types.index("worker_tool_result")
    assert event_types.index("worker_tool_result") < event_types.index("agent_context_reinjected")
    assert event_types.index("agent_context_reinjected") < event_types.index("agent_turn_continued")
    tool_events = [event for event in events if event["type"] in {"worker_tool_call", "worker_tool_started", "worker_tool_result", "agent_context_reinjected"}]
    assert {event["tool_call_id"] for event in tool_events} == {"call-1"}
    assert {event["execution_path"] for event in tool_events} == {"agentteams_worker_react"}
    assert all(event["timestamp"].endswith("+00:00") for event in events if "timestamp" in event)


@pytest.mark.asyncio
async def test_worker_loop_guard_stops_duplicate_tool_calls(env, monkeypatch) -> None:
    # 生产阈值为 100，测试用小阈值快速触发保护逻辑。
    monkeypatch.setattr(pss, "_MAX_DUPLICATE_TOOL_CALLS", 2)
    contexts = {"agent-code": _ctx("agent-code", tools=[{"function": {"name": "workspace_read"}}])}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))
    events: list[dict] = []

    async def fake_execute(*_args, **_kwargs):
        return {"success": True, "result": {"content": "same result"}}

    monkeypatch.setattr(pss, "execute_studio_tool", fake_execute)

    async def handler(_messages, _kwargs):
        yield ChatChunk(
            type="tool_calls",
            metadata={
                "tool_calls": [{
                    "id": "duplicate-call",
                    "function": {"name": "workspace_read", "arguments": '{"path":"same.csv"}'},
                }],
            },
        )

    _patch_provider(monkeypatch, handler)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-1",
        context_summary="",
        tasks=[{"agent_id": "agent-code", "task": "读取文件", "workspace_access": True}],
        db=SimpleNamespace(),
        on_event=events.append,
        max_rounds=5,
    )

    guard_events = [
        event for event in events if event["type"] == "agent_loop_guard_triggered"
    ]
    assert len(guard_events) == 1
    assert guard_events[0]["reason"] == "duplicate_tool_call"
    assert result["llm_payload"]["results"][0]["status"] == "guarded"
    assert "重复调用工具" in result["llm_payload"]["results"][0]["error"]


@pytest.mark.asyncio
async def test_worker_no_progress_is_reported_as_partial_success(env, monkeypatch) -> None:
    contexts = {"agent-code": _ctx("agent-code", tools=[{"function": {"name": "workspace_read"}}])}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))
    events: list[dict] = []

    async def fake_execute(*_args, **_kwargs):
        return {"success": True, "result": {"content": "same result"}}

    monkeypatch.setattr(pss, "execute_studio_tool", fake_execute)

    async def handler(messages, _kwargs):
        call_number = len(messages)
        yield ChatChunk(
            type="tool_calls",
            metadata={
                "tool_calls": [{
                    "id": f"call-{call_number}",
                    "function": {
                        "name": "workspace_read",
                        "arguments": json.dumps({"path": f"same-{call_number}.csv"}),
                    },
                }],
            },
        )

    _patch_provider(monkeypatch, handler)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-1",
        context_summary="",
        tasks=[{"agent_id": "agent-code", "task": "读取文件", "workspace_access": True}],
        db=SimpleNamespace(),
        on_event=events.append,
        max_rounds=5,
    )

    guard_events = [event for event in events if event["type"] == "agent_loop_guard_triggered"]
    assert guard_events[0]["reason"] == "no_progress"
    assert result["llm_payload"]["results"][0]["status"] == "ok"
    assert result["llm_payload"]["results"][0]["partial"] is True
    assert result["llm_payload"]["results"][0]["guard_triggered"] is True
    assert result["llm_payload"]["results"][0].get("error") is None
    assert "已停止重复调用" in result["llm_payload"]["results"][0]["answer"]
    envelope = json.loads(result["llm_payload"]["results"][0]["answer"])
    assert envelope["risks"] == ["工具连续返回相同结果，未继续执行重复调用。"]


@pytest.mark.asyncio
async def test_fanout_continues_after_model_output_length_limit(env, monkeypatch) -> None:
    contexts = {"agent-scrna": _ctx("agent-scrna")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))
    calls = 0

    async def handler(messages, _kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            yield ChatChunk(type="text", content="第一部分单细胞方案。")
            yield ChatChunk(type="done", metadata={"finish_reason": "length"})
            return
        assert "从中断处继续" in messages[-1]["content"]
        yield ChatChunk(type="text", content="第二部分免疫耐受机制与交付项。")
        yield ChatChunk(type="done", metadata={"finish_reason": "stop"})

    _patch_provider(monkeypatch, handler)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-1",
        context_summary="",
        tasks=[{"agent_id": "agent-scrna", "task": "写完整方案"}],
        db=SimpleNamespace(),
    )

    answer = result["llm_payload"]["results"][0]["answer"]
    assert calls == 2
    assert "第一部分单细胞方案" in answer
    assert "第二部分免疫耐受机制与交付项" in answer


@pytest.mark.asyncio
async def test_fanout_retries_when_model_returns_empty_content(env, monkeypatch) -> None:
    """模型偶发空响应（finish_reason=stop 且无正文）时追问重试，不向上返回空答复。"""
    contexts = {"agent-scrna": _ctx("agent-scrna")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))
    calls = 0

    async def handler(messages, _kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            yield ChatChunk(type="done", metadata={"finish_reason": "stop"})
            return
        assert "没有包含任何正文内容" in messages[-1]["content"]
        yield ChatChunk(type="text", content="正常答复。")
        yield ChatChunk(type="done", metadata={"finish_reason": "stop"})

    _patch_provider(monkeypatch, handler)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-1",
        context_summary="",
        tasks=[{"agent_id": "agent-scrna", "task": "你的职责是什么"}],
        db=SimpleNamespace(),
    )

    assert calls == 2
    assert "正常答复。" in result["llm_payload"]["results"][0]["answer"]


@pytest.mark.asyncio
async def test_fanout_fails_explicitly_after_repeated_empty_content(env, monkeypatch) -> None:
    """连续空响应超过重试上限后返回显式失败，而不是空答案。"""
    contexts = {"agent-scrna": _ctx("agent-scrna")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))
    calls = 0

    async def handler(messages, _kwargs):
        nonlocal calls
        calls += 1
        yield ChatChunk(type="done", metadata={"finish_reason": "stop"})

    _patch_provider(monkeypatch, handler)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-1",
        context_summary="",
        tasks=[{"agent_id": "agent-scrna", "task": "你的职责是什么"}],
        db=SimpleNamespace(),
    )

    first = result["llm_payload"]["results"][0]
    assert calls == 1 + pss._MAX_EMPTY_RESPONSE_RETRIES
    assert first["answer"] in (None, "")
    assert "空内容" in (first["error"] or "")


@pytest.mark.asyncio
async def test_fanout_merges_token_usage_across_rounds_and_children(env, monkeypatch) -> None:
    """done chunk 的 usage 跨轮累加，并经 run() 合并各子任务用量后透出。"""
    contexts = {"agent-a": _ctx("agent-a"), "agent-b": _ctx("agent-b")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    async def handler(messages, _kwargs):
        first = messages[0]["content"]
        # task-a 首轮以 length 中断触发续写；续写轮 messages 已扩展，按长度区分轮次
        if "task-a" in first and len(messages) == 1:
            yield ChatChunk(type="text", content="上半段。")
            yield ChatChunk(
                type="done",
                metadata={
                    "finish_reason": "length",
                    "usage": {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140},
                },
            )
            return
        yield ChatChunk(type="text", content=f"结论：{'A' if 'task-a' in first else 'B'}")
        yield ChatChunk(
            type="done",
            metadata={
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 160, "completion_tokens": 50, "total_tokens": 210},
            },
        )

    _patch_provider(monkeypatch, handler)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-1",
        context_summary="",
        tasks=[
            {"agent_id": "agent-a", "task": "task-a 内容"},
            {"agent_id": "agent-b", "task": "task-b 内容"},
        ],
        db=SimpleNamespace(),
    )

    # agent-a 两轮 140+210，agent-b 一轮 210，合计 350/260/90；merged usage 恒带 cached_tokens
    assert result["usage"] == {
        "prompt_tokens": 260 + 160,
        "completion_tokens": 90 + 50,
        "total_tokens": 350 + 210,
        "cached_tokens": 0,
    }


@pytest.mark.asyncio
async def test_fanout_separates_reasoning_from_worker_answer(env, monkeypatch) -> None:
    contexts = {"agent-general": _ctx("agent-general")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))
    events: list[dict] = []

    async def handler(_messages, _kwargs):
        yield ChatChunk(
            type="text",
            content="INTERNAL_REASONING",
            metadata={"is_reasoning": True},
        )
        yield ChatChunk(type="text", content="FINAL_ANSWER")

    _patch_provider(monkeypatch, handler)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-1",
        context_summary="",
        tasks=[{"agent_id": "agent-general", "task": "形成方案"}],
        db=SimpleNamespace(),
        on_event=events.append,
    )

    worker = result["llm_payload"]["results"][0]
    assert worker["answer"] == "FINAL_ANSWER"
    assert worker["thought"] == "INTERNAL_REASONING"
    assert any(event["type"] == "worker_reasoning_delta" for event in events)


def test_child_tools_include_research_tools_and_bound_mcp() -> None:
    ctx = _ctx("agent-general", tools=[{"function": {"name": "remote_lookup"}}])
    ctx.features["web_search"] = {"mode": "required_for_freshness"}
    ctx.mcp_servers = [SimpleNamespace(tools=[SimpleNamespace(tool_name="remote_lookup")])]

    tools = pss.ParallelSubAgentService._prepare_child_tools(ctx)
    names = {(tool.get("function") or {}).get("name") for tool in tools}

    assert {"ask_user", "knowledge_search", "web_search", "remote_lookup"} <= names


def test_child_tools_respect_explicit_web_search_disable() -> None:
    ctx = _ctx("agent-general")
    ctx.features["web_search"] = {"mode": "off"}

    names = {
        (tool.get("function") or {}).get("name")
        for tool in pss.ParallelSubAgentService._prepare_child_tools(ctx)
    }

    assert "knowledge_search" in names
    assert "web_search" not in names


def test_child_tools_add_workspace_execution_only_after_explicit_access() -> None:
    ctx = _ctx("agent-code")

    default_names = {
        (tool.get("function") or {}).get("name")
        for tool in pss.ParallelSubAgentService._prepare_child_tools(ctx)
    }
    enabled_names = {
        (tool.get("function") or {}).get("name")
        for tool in pss.ParallelSubAgentService._prepare_child_tools(ctx, workspace_access=True)
    }

    assert "sandbox_execute" not in default_names
    assert {"workspace_read", "workspace_write", "sandbox_execute"}.issubset(enabled_names)


def test_child_tools_workspace_access_grants_full_workbench_except_update_plan() -> None:
    ctx = _ctx("agent-code")

    names = {
        (tool.get("function") or {}).get("name")
        for tool in pss.ParallelSubAgentService._prepare_child_tools(ctx, workspace_access=True)
    }

    # 对齐 AI 工作台全集（execute_studio_tool 可直接分发的平台联动工具）
    assert {
        "sandbox_execute",
        "workspace_write",
        "workspace_edit",
        "workspace_read",
        "workspace_list",
        "datahub_import",
        "platform_result_import",
        "artifact_register",
        "pipeline_query",
    }.issubset(names)
    # update_plan 是 Studio 计划 UI 工具，不授予子 Agent
    assert "update_plan" not in names


def test_goal_safe_child_tools_only_keep_read_only_capabilities(monkeypatch) -> None:
    readonly_schema = SimpleNamespace(
        invocation_mode="backend_sync",
        requires_confirm=False,
        annotations=SimpleNamespace(read_only_hint=True),
    )
    unsafe_schema = SimpleNamespace(
        invocation_mode="backend_sync",
        requires_confirm=False,
        annotations=SimpleNamespace(read_only_hint=False),
    )
    schemas = {"readonly_lookup": readonly_schema, "unsafe_mutation": unsafe_schema}
    monkeypatch.setattr(
        pss,
        "schema_loader",
        SimpleNamespace(get_tool=lambda name: schemas.get(name)),
    )
    ctx = _ctx(
        "agent-general",
        tools=[
            {"function": {"name": "readonly_lookup"}},
            {"function": {"name": "unsafe_mutation"}},
            {"function": {"name": "remote_lookup"}},
        ],
    )
    ctx.features["web_search"] = {"mode": "required_for_freshness"}
    ctx.mcp_servers = [SimpleNamespace(tools=[SimpleNamespace(tool_name="remote_lookup")])]

    tools = pss.ParallelSubAgentService._prepare_child_tools(
        ctx,
        workspace_access=True,
        safe_only=True,
    )
    names = {(tool.get("function") or {}).get("name") for tool in tools}

    assert {"ask_user", "knowledge_search", "web_search", "readonly_lookup"} <= names
    assert {"unsafe_mutation", "remote_lookup", "workspace_write", "sandbox_execute"}.isdisjoint(
        names
    )


def test_child_tools_safe_only_keeps_readonly_annotated_mcp_tools() -> None:
    """safe_only 只读会诊放行声明 readOnlyHint 的 MCP 工具（能力目录/房间状态查询）。"""
    readonly_tool = SimpleNamespace(
        tool_name="ability_catalog_query",
        annotations={"readOnlyHint": True, "destructiveHint": False},
    )
    unannotated_tool = SimpleNamespace(tool_name="remote_lookup", annotations={})
    legacy_tool = SimpleNamespace(tool_name="legacy_lookup")  # 无 annotations 属性
    destructive_tool = SimpleNamespace(
        tool_name="dangerous_mcp",
        annotations={"readOnlyHint": True, "destructiveHint": True},
    )
    ctx = _ctx(
        "agent-manager",
        tools=[
            {"function": {"name": "ability_catalog_query"}},
            {"function": {"name": "remote_lookup"}},
            {"function": {"name": "legacy_lookup"}},
            {"function": {"name": "dangerous_mcp"}},
        ],
    )
    ctx.mcp_servers = [
        SimpleNamespace(tools=[readonly_tool, unannotated_tool, legacy_tool, destructive_tool])
    ]

    tools = pss.ParallelSubAgentService._prepare_child_tools(ctx, safe_only=True)
    names = {(tool.get("function") or {}).get("name") for tool in tools}

    assert "ability_catalog_query" in names
    assert {"remote_lookup", "legacy_lookup", "dangerous_mcp"}.isdisjoint(names)


def test_manager_safe_only_keeps_explicit_memory_management_tools(monkeypatch) -> None:
    """Manager 可按用户明确指令管理本人记忆，普通只读工具仍受 safe_only 约束。"""
    schema = SimpleNamespace(
        invocation_mode="backend_sync",
        requires_confirm=False,
        annotations=SimpleNamespace(read_only_hint=False),
    )
    monkeypatch.setattr(
        pss,
        "schema_loader",
        SimpleNamespace(get_tool=lambda name: schema if name.startswith("cygnusx_") else None),
    )
    ctx = _ctx(
        "agentteams-manager",
        tools=[
            {"function": {"name": "cygnusx_save_memory"}},
            {"function": {"name": "cygnusx_update_memory"}},
            {"function": {"name": "cygnusx_forget_memory"}},
            {"function": {"name": "cygnusx_update_memory_block"}},
        ],
    )

    tools = pss.ParallelSubAgentService._prepare_child_tools(ctx, safe_only=True)
    names = {(tool.get("function") or {}).get("name") for tool in tools}

    assert {
        "cygnusx_save_memory",
        "cygnusx_update_memory",
        "cygnusx_forget_memory",
        "cygnusx_update_memory_block",
    } <= names


@pytest.mark.asyncio
async def test_child_workspace_tool_uses_parent_workspace_after_user_confirmation(
    env, monkeypatch
) -> None:
    calls: list[tuple[str, str, dict]] = []

    async def fake_execute(name, args, session_id, **_kwargs):
        calls.append((name, session_id, args))
        return {"success": True, "result": {"llm_payload": {"path": args.get("path")}}}

    monkeypatch.setattr(pss, "execute_studio_tool", fake_execute)
    result = await pss.ParallelSubAgentService._execute_child_tool(
        user_id="user-1",
        agent_id="agent-code",
        child_session_id="session:sub:run:1",
        parent_session_id="session-parent",
        tool_name="workspace_write",
        args={"path": "scripts/run.py", "content": "print('ok')"},
        workdir=env.tmp_path,
        run_id="run",
        ctx=_ctx("agent-code"),
        workspace_access=True,
    )

    assert result["success"] is True
    assert calls == [
        (
            "workspace_write",
            "session-parent",
            {"path": "scripts/run.py", "content": "print('ok')"},
        )
    ]


@pytest.mark.asyncio
async def test_child_executes_bound_mcp_tool_with_child_context(env, monkeypatch) -> None:
    calls: list[tuple[str, dict, str]] = []

    class FakeMCPClient:
        async def call_tool(self, server, tool_name, arguments, *, user_id, context):
            calls.append((tool_name, arguments, context.session_id))
            return {"success": True, "result": {"source": server.name}}

    monkeypatch.setattr("cygnusx.infrastructure.mcp.client.MCPClient", FakeMCPClient)
    server = SimpleNamespace(
        name="research-mcp",
        tools=[SimpleNamespace(tool_name="remote_lookup")],
    )
    ctx = _ctx("agent-general")
    ctx.mcp_servers = [server]

    result = await pss.ParallelSubAgentService._execute_child_tool(
        user_id="user-1",
        agent_id="agent-general",
        child_session_id="session:sub:run:1",
        tool_name="remote_lookup",
        args={"query": "TP53"},
        workdir=env.tmp_path,
        run_id="run",
        ctx=ctx,
    )

    assert result["success"] is True
    assert calls == [("remote_lookup", {"query": "TP53"}, "session:sub:run:1")]


@pytest.mark.asyncio
async def test_fanout_isolates_child_failure(env, monkeypatch) -> None:
    contexts = {"agent-a": _ctx("agent-a"), "agent-b": _ctx("agent-b")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    async def handler(messages, kwargs):
        if "task-a" in messages[0]["content"]:
            yield ChatChunk(type="text", content="A 正常完成")
        else:
            raise RuntimeError("模型端点故障")

    _patch_provider(monkeypatch, handler)

    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="agent-general",
        parent_session_id="sess-1",
        context_summary="",
        tasks=[
            {"agent_id": "agent-a", "task": "task-a"},
            {"agent_id": "agent-b", "task": "task-b"},
        ],
        db=SimpleNamespace(),
    )

    assert result["success"] is True  # 部分成功仍视为可用汇总
    assert result["llm_payload"]["summary"].startswith("1/2 个子任务成功")
    by_agent = {item["agent_id"]: item for item in result["llm_payload"]["results"]}
    assert by_agent["agent-a"]["status"] == "ok"
    assert by_agent["agent-b"]["status"] == "failed"
    assert "模型端点故障" in by_agent["agent-b"]["error"]


@pytest.mark.asyncio
async def test_fanout_disabled_flag(env, monkeypatch) -> None:
    env.settings.subagent_fanout_enabled = False
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="agent-general",
        parent_session_id="sess-1",
        context_summary="",
        tasks=[
            {"agent_id": "agent-a", "task": "x"},
            {"agent_id": "agent-b", "task": "y"},
        ],
        db=SimpleNamespace(),
    )
    assert result["success"] is False
    assert "未启用" in result["llm_payload"]["error"]


@pytest.mark.asyncio
async def test_fanout_enabled_by_db_flag_alone(env, monkeypatch) -> None:
    """env 关、管理端平台设置开 → 仍可 fan-out（运行时主开关语义）。"""
    env.settings.subagent_fanout_enabled = False
    env.site.db_flag = True
    contexts = {"agent-a": _ctx("agent-a"), "agent-b": _ctx("agent-b")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    async def text(messages, kwargs):
        yield ChatChunk(type="text", content="完成")

    _patch_provider(monkeypatch, text)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="agent-general",
        parent_session_id="sess-1",
        context_summary="",
        tasks=[
            {"agent_id": "agent-a", "task": "x"},
            {"agent_id": "agent-b", "task": "y"},
        ],
        db=SimpleNamespace(),
    )
    assert result["success"] is True
    assert result["llm_payload"]["summary"].startswith("2/2")


@pytest.mark.asyncio
async def test_fanout_rejects_non_spawnable(env, monkeypatch) -> None:
    contexts = {
        "agent-a": _ctx("agent-a", spawnable=False),
        "agent-b": _ctx("agent-b"),
    }
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="agent-general",
        parent_session_id="sess-1",
        context_summary="",
        tasks=[
            {"agent_id": "agent-a", "task": "x"},
            {"agent_id": "agent-b", "task": "y"},
        ],
        db=SimpleNamespace(),
    )
    assert result["success"] is False
    assert "subagents_spawnable" in result["llm_payload"]["error"]


@pytest.mark.asyncio
async def test_safe_single_consultation_allows_non_spawnable_target(env, monkeypatch) -> None:
    contexts = {"agent-manager": _ctx("agent-manager", spawnable=False)}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    async def text(messages, kwargs):
        yield ChatChunk(type="text", content='{"conclusion":"已接单"}')

    _patch_provider(monkeypatch, text)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="agent-general",
        parent_session_id="sess-1",
        context_summary="",
        tasks=[{"agent_id": "agent-manager", "task": "回复用户"}],
        db=SimpleNamespace(),
        safe_only=True,
        runtime_authorized=True,
        allow_non_spawnable_target=True,
    )

    assert result["success"] is True
    assert result["llm_payload"]["results"][0]["answer"] == '{"conclusion":"已接单"}'


@pytest.mark.asyncio
async def test_fanout_child_timeout(env, monkeypatch) -> None:
    env.settings.subagent_child_timeout_seconds = 1
    contexts = {"agent-a": _ctx("agent-a"), "agent-b": _ctx("agent-b")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    async def hang(messages, kwargs):
        await asyncio.sleep(5)
        yield ChatChunk(type="text", content="不该出现")

    _patch_provider(monkeypatch, hang)
    started = time.monotonic()
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="agent-general",
        parent_session_id="sess-1",
        context_summary="",
        tasks=[
            {"agent_id": "agent-a", "task": "x"},
            {"agent_id": "agent-b", "task": "y"},
        ],
        db=SimpleNamespace(),
    )
    elapsed = time.monotonic() - started
    assert result["success"] is False
    assert {item["status"] for item in result["llm_payload"]["results"]} == {"timeout"}
    assert elapsed < 4, f"超时未生效，elapsed={elapsed:.3f}s"


@pytest.mark.asyncio
async def test_fanout_child_tool_roundtrip_with_dedicated_session(env, monkeypatch) -> None:
    contexts = {
        "agent-a": _ctx("agent-a", tools=[{"function": {"name": "workspace_read"}}]),
        "agent-b": _ctx("agent-b"),
    }
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    call_counts: dict[str, int] = {}

    async def handler(messages, kwargs):
        first = messages[0]["content"]
        key = "a" if "task-a" in first else "b"
        call_counts[key] = call_counts.get(key, 0) + 1
        if key == "a" and call_counts[key] == 1:
            yield ChatChunk(
                type="tool_calls",
                metadata={
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {
                                "name": "workspace_read",
                                "arguments": '{"path": "x.txt"}',
                            },
                        }
                    ]
                },
            )
        else:
            yield ChatChunk(type="text", content=f"{key} 完成")

    _patch_provider(monkeypatch, handler)

    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="agent-general",
        parent_session_id="sess-1",
        context_summary="",
        tasks=[
            {"agent_id": "agent-a", "task": "task-a"},
            {"agent_id": "agent-b", "task": "task-b"},
        ],
        db=SimpleNamespace(),
    )

    assert result["success"] is True
    assert env.bridge.calls == [("workspace_read", {"path": "x.txt"})]
    # C1：子任务工具执行创建了独占 session
    assert FakeSession.created >= 1


@pytest.mark.asyncio
async def test_repeated_missing_input_tool_call_stops_promptly(env, monkeypatch) -> None:
    contexts = {
        "agent-a": _ctx("agent-a", tools=[{"function": {"name": "workspace_read"}}]),
    }
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))
    model_calls = 0

    async def handler(_messages, _kwargs):
        nonlocal model_calls
        model_calls += 1
        yield ChatChunk(type="text", content="请补充 treefile 文件后继续。")
        yield ChatChunk(
            type="tool_calls",
            metadata={
                "tool_calls": [
                    {
                        "id": f"call-{model_calls}",
                        "type": "function",
                        "function": {
                            "name": "workspace_read",
                            "arguments": '{"path": "input/treefile"}',
                        },
                    }
                ]
            },
        )

    _patch_provider(monkeypatch, handler)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="agent-general",
        parent_session_id="sess-1",
        context_summary="",
        tasks=[{"agent_id": "agent-a", "task": "读取树文件并继续处理"}],
        db=SimpleNamespace(),
    )

    child = result["llm_payload"]["results"][0]
    assert model_calls == 2
    assert result["success"] is True
    assert child["status"] == "awaiting_input"
    assert child["packet"]["needs_user_input"] is True
    assert child["packet"]["status"] == "awaiting_input"
    assert child["packet"]["error"] == ""


@pytest.mark.asyncio
async def test_fanout_escalates_confirm_tool_without_child_execution(env, monkeypatch) -> None:
    contexts = {
        "agent-a": _ctx("agent-a", tools=[{"function": {"name": "danger_tool"}}]),
    }
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    async def handler(_messages, _kwargs):
        yield ChatChunk(
            type="tool_calls",
            metadata={
                "tool_calls": [
                    {
                        "id": "call-confirm",
                        "type": "function",
                        "function": {"name": "danger_tool", "arguments": '{"sample": "S1"}'},
                    }
                ]
            },
        )

    _patch_provider(monkeypatch, handler)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="agent-general",
        parent_session_id="sess-1",
        context_summary="",
        tasks=[{"agent_id": "agent-a", "task": "submit"}],
        db=SimpleNamespace(),
    )

    child = result["llm_payload"]["results"][0]
    assert child["status"] == "approval_pending"
    assert child["packet"]["approval_requests"] == [
        {"tool_name": "danger_tool", "arguments": {"sample": "S1"}}
    ]
    assert env.bridge.calls == []


@pytest.mark.asyncio
async def test_fanout_validation_rules(env, monkeypatch) -> None:
    service = pss.ParallelSubAgentService()
    kwargs = dict(
        user_id="user-1",
        parent_agent_id="agent-general",
        parent_session_id="sess-1",
        context_summary="",
        db=SimpleNamespace(),
    )
    single = service._validate_tasks([{"agent_id": "a", "task": "x"}], max_parallel=4)
    assert single == [{"agent_id": "a", "task": "x"}]

    long_dependency_packet = "上游研究计划。" * 1000
    accepted = service._validate_tasks(
        [{"agent_id": "a", "task": long_dependency_packet}], max_parallel=4
    )
    assert accepted == [{"agent_id": "a", "task": long_dependency_packet}]

    too_many = await service.run(
        tasks=[{"agent_id": "a", "task": f"t{i}"} for i in range(5)], **kwargs
    )
    assert too_many["success"] is False and "最多" in too_many["llm_payload"]["error"]

    missing = await service.run(
        tasks=[{"agent_id": "a", "task": "x"}, {"agent_id": "", "task": "y"}], **kwargs
    )
    assert missing["success"] is False and "缺少" in missing["llm_payload"]["error"]


@pytest.mark.asyncio
async def test_prepare_rejects_without_side_effects(env, monkeypatch) -> None:
    """prepare 拒绝路径：纯信封返回（无 run_id）、不实例化 AgentService、无可执行计划。"""
    service_calls: list[str] = []

    class GuardedAgentService:
        def __init__(self, db):
            service_calls.append("init")

    monkeypatch.setattr(pss, "AgentService", GuardedAgentService)
    service = pss.ParallelSubAgentService()

    too_many = await service.prepare(
        user_id="user-1",
        context_summary="",
        tasks=[{"agent_id": "a", "task": f"t{i}"} for i in range(5)],
        db=SimpleNamespace(),
    )
    assert isinstance(too_many, dict)
    assert too_many["success"] is False
    assert too_many["llm_payload"]["code"] == "SUBAGENT_MAX_PARALLEL"
    assert not hasattr(too_many, "run_id")
    assert service_calls == []  # 校验先于任何预组装

    monkeypatch.setattr(env.settings, "subagent_fanout_enabled", False)
    disabled = await service.prepare(
        user_id="user-1",
        context_summary="",
        tasks=[{"agent_id": "a", "task": "x"}],
        db=SimpleNamespace(),
    )
    assert isinstance(disabled, dict)
    assert disabled["llm_payload"]["code"] == "SUBAGENT_DISABLED"
    assert service_calls == []


def test_parallel_subagents_schema_max_items_matches_settings_default() -> None:
    """契约守卫：LLM 工具 schema 的 maxItems 必须与 settings.subagent_max_parallel 默认值一致。"""
    from cygnusx.core.config import Settings
    from cygnusx.tools.schema_loader import schema_loader

    tool = schema_loader.get_tool("parallel_subagents")
    assert tool is not None
    max_items = tool.input_schema["properties"]["tasks"]["maxItems"]
    assert max_items == Settings.model_fields["subagent_max_parallel"].default


def test_subagent_child_event_metadata_maps_ui_phases() -> None:
    meta = pss.subagent_child_event_metadata(
        {"type": "worker_started", "index": 2, "agent_id": "agent-a", "agent_name": "A 专家"}
    )
    assert meta == {"phase": "child_started", "index": 2, "agent_id": "agent-a", "name": "A 专家"}

    done = pss.subagent_child_event_metadata(
        {
            "type": "worker_finished",
            "index": 1,
            "agent_id": "agent-b",
            "status": "failed",
            "elapsed_s": 3.5,
            "error": "boom",
        }
    )
    assert done is not None
    assert done["phase"] == "child_done" and done["status"] == "failed"
    assert done["elapsed_s"] == 3.5 and done["error"] == "boom"

    # heartbeat 等内部事件不透出
    assert pss.subagent_child_event_metadata({"type": "worker_heartbeat", "index": 1}) is None


def test_has_unfinished_json_fence_detects_truncated_envelope() -> None:
    assert pss._has_unfinished_json_fence('前文 ```json { "conclusion": "写到一半') is True


def test_has_unfinished_json_fence_ignores_closed_blocks_and_plain_text() -> None:
    assert pss._has_unfinished_json_fence('```json {"a": 1} ``` 后续说明') is False
    assert pss._has_unfinished_json_fence("普通文本结论") is False


@pytest.mark.asyncio
async def test_fanout_capability_missing_marks_child_blocked(env, monkeypatch) -> None:
    """R11：声明 python.execute 但执行上下文无执行器 → 子任务 spawn 前 blocked，不算成功。"""
    contexts = {"agent-code": _ctx("agent-code")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    async def handler(messages, _kwargs):
        yield ChatChunk(type="text", content="不应被执行到的正文")

    seen = _patch_provider(monkeypatch, handler)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-1",
        context_summary="",
        db=SimpleNamespace(),
        tasks=[
            {"agent_id": "agent-code", "task": "运行 Python 探针", "requires": ["python.execute"]},
            {"agent_id": "agent-code", "task": "查平台知识库", "requires": ["research.retrieve"]},
        ],
    )

    blocked_item, ok_item = result["llm_payload"]["results"]
    assert blocked_item["status"] == "blocked"
    assert blocked_item["outcome_status"] == "blocked"
    assert blocked_item["reason_code"] == "CAPABILITY_MISSING"
    assert "python.execute" in blocked_item["capabilities_required"]
    assert ok_item["outcome_status"] == "answered_unverified"
    # 被准入阻止的子任务不得产生 provider 调用：仅 1 路真正执行
    assert len(seen["tools"]) == 1
    # 汇总口径不得出现 "2/2 成功"
    summary = result["llm_payload"]["summary"]
    assert "2/2" not in summary
    assert "受阻" in summary and "未验证问答" in summary


@pytest.mark.asyncio
async def test_fanout_execution_contract_without_receipt_not_verified(env, monkeypatch) -> None:
    """R12：有能力但子循环只给文本、无执行回执 → execution=ok 而 outcome 必非 succeeded。"""
    contexts = {"agent-code": _ctx("agent-code")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    async def fake_studio(name, args, session_id, **_kwargs):
        return {"success": True, "result": {"stdout": "hello"}}

    monkeypatch.setattr(pss, "execute_studio_tool", fake_studio)

    async def handler(messages, _kwargs):
        yield ChatChunk(type="text", content="我认为可以这样写代码（未实际执行）")

    _patch_provider(monkeypatch, handler)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-1",
        context_summary="",
        db=SimpleNamespace(),
        tasks=[
            {
                "agent_id": "agent-code",
                "task": "运行代码并给出真实 stdout",
                "requires": ["python.execute"],
                "workspace_access": True,
            }
        ],
    )

    item = result["llm_payload"]["results"][0]
    assert item["status"] == "ok"  # 子循环正常结束
    assert item["outcome_status"] == "blocked"
    assert item["reason_code"] == "EXECUTION_NOT_VERIFIED"
    assert item["artifact_status"] == "not_created"
    assert result["llm_payload"]["summary"].startswith("0 已验证完成")


@pytest.mark.asyncio
async def test_fanout_execution_contract_with_receipt_verified(env, monkeypatch) -> None:
    """声明 python.execute 且产生真实执行回执 → outcome=succeeded，回执随结果透传。"""
    contexts = {"agent-code": _ctx("agent-code")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    studio_calls: list[str] = []

    async def fake_studio(name, args, session_id, **_kwargs):
        studio_calls.append(name)
        return {"success": True, "result": {"stdout": "hello\npython=3.11"}}

    monkeypatch.setattr(pss, "execute_studio_tool", fake_studio)

    async def handler(messages, _kwargs):
        if len(messages) == 1:
            yield ChatChunk(
                type="tool_calls",
                metadata={
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "function": {"name": "sandbox_execute", "arguments": "{}"},
                        }
                    ]
                },
            )
        else:
            yield ChatChunk(type="text", content="已真实执行，stdout 见回执")

    _patch_provider(monkeypatch, handler)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-1",
        context_summary="",
        db=SimpleNamespace(),
        tasks=[
            {
                "agent_id": "agent-code",
                "task": "运行 print('hello') 并汇报 stdout",
                "requires": ["python.execute"],
                "workspace_access": True,
            }
        ],
    )

    item = result["llm_payload"]["results"][0]
    assert item["status"] == "ok"
    assert item["outcome_status"] == "succeeded"
    assert item["reason_code"] == "EXECUTION_RECEIPT_VERIFIED"
    assert studio_calls == ["sandbox_execute"]
    receipts = item["tool_receipts"]
    assert receipts and receipts[0]["tool_name"] == "sandbox_execute"
    assert receipts[0]["success"] is True
    assert "1 已验证完成" in result["llm_payload"]["summary"]


@pytest.mark.asyncio
async def test_fanout_pure_qa_contract_answered_unverified(env, monkeypatch) -> None:
    """纯问答声明 research.retrieve 且无客观验收器 → answered_unverified，不冒充成功。"""
    contexts = {"agent-general": _ctx("agent-general")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    async def handler(messages, _kwargs):
        yield ChatChunk(type="text", content="数据入库字段契约如下：……")

    _patch_provider(monkeypatch, handler)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-1",
        context_summary="",
        db=SimpleNamespace(),
        tasks=[
            {
                "agent_id": "agent-general",
                "task": "说明数据入库字段契约",
                "requires": ["research.retrieve"],
            }
        ],
    )

    item = result["llm_payload"]["results"][0]
    assert item["status"] == "ok"
    assert item["outcome_status"] == "answered_unverified"
    assert item["reason_code"] == "ANSWER_WITHOUT_VERIFIER"
    assert item["artifact_status"] == "not_required"


@pytest.mark.asyncio
async def test_fanout_rejects_unknown_capability(env, monkeypatch) -> None:
    """未知能力名在校验阶段拒绝（SUBAGENT_INVALID_TASKS），不产生执行副作用。"""
    contexts = {"agent-code": _ctx("agent-code")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    async def handler(messages, _kwargs):
        yield ChatChunk(type="text", content="不应执行")

    seen = _patch_provider(monkeypatch, handler)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-1",
        context_summary="",
        db=SimpleNamespace(),
        tasks=[{"agent_id": "agent-code", "task": "干活", "requires": ["shell.exec"]}],
    )

    assert result["success"] is False
    assert result["llm_payload"]["code"] == "SUBAGENT_INVALID_TASKS"
    assert "未知能力" in result["llm_payload"]["error"]
    assert seen["tools"] == []


@pytest.mark.asyncio
async def test_fanout_undeclared_tasks_keep_legacy_summary(env, monkeypatch) -> None:
    """未声明 requires 的旧式任务保持原有汇总口径与字段（向后兼容）。"""
    contexts = {"agent-general": _ctx("agent-general")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    async def handler(messages, _kwargs):
        yield ChatChunk(type="text", content="结论 A")

    _patch_provider(monkeypatch, handler)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-1",
        context_summary="",
        db=SimpleNamespace(),
        tasks=[{"agent_id": "agent-general", "task": "旧式问答"}],
    )

    assert result["success"] is True
    assert result["llm_payload"]["summary"].startswith("1/1 个子任务成功")
    item = result["llm_payload"]["results"][0]
    assert item["status"] == "ok"
    assert "outcome_status" not in item
    assert "tool_receipts" not in item


@pytest.mark.asyncio
async def test_fanout_long_answer_persisted_as_detail_ref(env, monkeypatch) -> None:
    """R16：长正文落盘为 detail_ref，信封内保持完整答案（预算内不降级）。"""
    contexts = {"agent-general": _ctx("agent-general")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))
    marker = "DETAIL_REF_EOF_MARKER"
    long_answer = "长交付物正文。" * 300 + marker  # ~4200 字，超过落盘阈值

    async def handler(messages, _kwargs):
        yield ChatChunk(type="text", content=long_answer)

    _patch_provider(monkeypatch, handler)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-1",
        context_summary="",
        db=SimpleNamespace(),
        tasks=[{"agent_id": "agent-general", "task": "长文任务"}],
    )

    item = result["llm_payload"]["results"][0]
    detail_ref = item.get("detail_ref")
    assert detail_ref and detail_ref.endswith("result.json")
    # 预算内单路不降级：信封内仍是完整正文
    assert marker in item["answer"]
    assert "payload_truncated" not in item
    # 落盘文件含完整结果，供父/前端按 ref 读取
    record = json.loads((env.tmp_path / detail_ref).read_text(encoding="utf-8"))
    assert marker in record["answer"]
    assert record["status"] == "ok"


@pytest.mark.asyncio
async def test_fanout_payload_budget_compacts_longest_answer(env, monkeypatch) -> None:
    """R16：多路长正文超出父轮回灌预算时，最长路降级为摘要+detail_ref 并显式标记。"""
    contexts = {"agent-general": _ctx("agent-general")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    async def handler(messages, _kwargs):
        task = messages[0]["content"]
        if "task-a" in task:
            yield ChatChunk(type="text", content="甲" * 4000)
        elif "task-b" in task:
            yield ChatChunk(type="text", content="乙" * 4000)
        else:
            yield ChatChunk(type="text", content="丙" * 4000)

    _patch_provider(monkeypatch, handler)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-1",
        context_summary="",
        db=SimpleNamespace(),
        tasks=[
            {"agent_id": "agent-general", "task": "task-a 长文"},
            {"agent_id": "agent-general", "task": "task-b 长文"},
            {"agent_id": "agent-general", "task": "task-c 长文"},
        ],
    )

    # 预算内只保留必要降级：至少一路被压缩且带显式标记
    compacted = [
        item
        for item in result["llm_payload"]["results"]
        if item.get("payload_truncated") is True
    ]
    assert compacted, "超长正文应触发预算降级"
    for item in compacted:
        assert len(item["answer"]) < 4000
        assert item.get("detail_ref")
        assert "detail_ref" in item["answer"]
    # 降级后 llm_payload 必须回到预算内
    assert (
        len(json.dumps(result["llm_payload"], ensure_ascii=False))
        <= pss._LLM_PAYLOAD_BUDGET_CHARS
    )
    # 所有路的完整正文均已落盘
    for item in result["llm_payload"]["results"]:
        record = json.loads((env.tmp_path / item["detail_ref"]).read_text(encoding="utf-8"))
        assert len(record["answer"]) >= 4000


@pytest.mark.asyncio
async def test_fanout_ok_without_body_flagged_missing(env, monkeypatch) -> None:
    """R15：退化场景——子循环报 ok 却无正文时，聚合必须显式标记正文缺失。"""

    async def fake_child_loop(*_args, **_kwargs):
        return {"status": "ok", "answer": None, "error": None, "usage": None}

    monkeypatch.setattr(pss.ParallelSubAgentService, "_child_loop", fake_child_loop)
    contexts = {"agent-general": _ctx("agent-general")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-1",
        context_summary="",
        db=SimpleNamespace(),
        tasks=[{"agent_id": "agent-general", "task": "任意"}],
    )

    item = result["llm_payload"]["results"][0]
    assert item["status"] == "ok"
    assert item["body_missing"] is True
    assert "正文缺失" in result["llm_payload"]["summary"]


@pytest.mark.asyncio
async def test_fanout_replay_same_key_same_payload_returns_original(env, monkeypatch) -> None:
    """R04：相同 request_key + 相同 payload 重放返回原 run 结果，不重复执行。"""
    contexts = {"agent-general": _ctx("agent-general")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    async def handler(messages, _kwargs):
        yield ChatChunk(type="text", content="原始执行结果")

    seen = _patch_provider(monkeypatch, handler)
    base_kwargs = dict(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-replay",
        context_summary="共享背景",
        db=SimpleNamespace(),
        tasks=[{"agent_id": "agent-general", "task": "幂等任务"}],
    )
    first = await pss.ParallelSubAgentService().run(**base_kwargs, request_key="rk-r04")
    second = await pss.ParallelSubAgentService().run(**base_kwargs, request_key="rk-r04")

    assert first["success"] is True
    assert second["replayed"] is True
    assert second["ui_payload"]["replayed"] is True
    assert second["ui_payload"]["fanout_run_id"] == first["ui_payload"]["fanout_run_id"]
    # provider 仅被调用一次：重放不产生第二次执行与回执
    assert len(seen["tools"]) == 1


@pytest.mark.asyncio
async def test_fanout_same_key_different_payload_conflicts(env, monkeypatch) -> None:
    """R05：相同 request_key 携带不同 payload → 明确 conflict，不得静默重跑。"""
    contexts = {"agent-general": _ctx("agent-general")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    async def handler(messages, _kwargs):
        yield ChatChunk(type="text", content="结果")

    seen = _patch_provider(monkeypatch, handler)
    base_kwargs = dict(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-conflict",
        context_summary="",
        db=SimpleNamespace(),
    )
    first = await pss.ParallelSubAgentService().run(
        **base_kwargs,
        tasks=[{"agent_id": "agent-general", "task": "第一批任务"}],
        request_key="rk-r05",
    )
    assert first["success"] is True
    second = await pss.ParallelSubAgentService().run(
        **base_kwargs,
        tasks=[{"agent_id": "agent-general", "task": "不同的第二批任务"}],
        request_key="rk-r05",
    )
    assert second["success"] is False
    assert second["llm_payload"]["code"] == "SUBAGENT_REQUEST_CONFLICT"
    assert len(seen["tools"]) == 1


@pytest.mark.asyncio
async def test_fanout_without_key_same_payload_executes_again(env, monkeypatch) -> None:
    """无 request_key 的同 payload 调用视为新的业务请求（如用户要求再跑一次），不隐式重放。"""
    contexts = {"agent-general": _ctx("agent-general")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    async def handler(messages, _kwargs):
        yield ChatChunk(type="text", content="结果")

    seen = _patch_provider(monkeypatch, handler)
    base_kwargs = dict(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-nokey",
        context_summary="",
        db=SimpleNamespace(),
        tasks=[{"agent_id": "agent-general", "task": "同一任务再来一次"}],
    )
    first = await pss.ParallelSubAgentService().run(**base_kwargs)
    second = await pss.ParallelSubAgentService().run(**base_kwargs)
    assert first["success"] and second["success"] is True
    assert "replayed" not in second
    assert len(seen["tools"]) == 2


@pytest.mark.asyncio
async def test_fanout_invalid_request_key_rejected(env, monkeypatch) -> None:
    """超长/非法 request_key 在校验阶段拒绝，不产生执行副作用。"""
    contexts = {"agent-general": _ctx("agent-general")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    async def handler(messages, _kwargs):
        yield ChatChunk(type="text", content="结果")

    seen = _patch_provider(monkeypatch, handler)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-badkey",
        context_summary="",
        db=SimpleNamespace(),
        tasks=[{"agent_id": "agent-general", "task": "任意"}],
        request_key="k" * 129,
    )
    assert result["success"] is False
    assert result["llm_payload"]["code"] == "SUBAGENT_INVALID_REQUEST_KEY"
    assert seen["tools"] == []


# --- WP2 产物闭环 ---------------------------------------------------------


def _patch_storage(tmp_path, monkeypatch):
    """把 path_factory/storage_backend 指向临时目录。"""
    from cygnusx.infrastructure.config.storage_config import StorageConfig
    from cygnusx.infrastructure.storage.backend import LocalStorageBackend
    from cygnusx.infrastructure.storage.path_factory import StoragePathFactory

    pf = StoragePathFactory(StorageConfig(data_root=str(tmp_path), users_subdir="users"))
    backend = LocalStorageBackend(pf)
    monkeypatch.setattr("cygnusx.infrastructure.storage.get_path_factory", lambda: pf)
    monkeypatch.setattr("cygnusx.infrastructure.storage.get_storage_backend", lambda: backend)
    return pf, backend


@pytest.mark.asyncio
async def test_fanout_publishes_child_artifacts_to_parent_workspace(env, monkeypatch) -> None:
    """R22/R23/R25：子 workdir 产物实测 → 发布父 chat-output → 父回读 hash 一致。"""
    _patch_storage(env.tmp_path, monkeypatch)
    contexts = {"agent-code": _ctx("agent-code")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))
    png_bytes = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 8

    async def fake_child_loop(*_args, workdir, **_kwargs):
        (workdir / "figures").mkdir(parents=True, exist_ok=True)
        (workdir / "figures" / "scatter.png").write_bytes(png_bytes)
        (workdir / "hello_stdout.txt").write_text("hello\npython=3.11\n", encoding="utf-8")
        return {
            "status": "ok",
            "answer": "已完成绘图与执行。",
            "error": None,
            "tool_receipts": [
                {"tool_name": "sandbox_execute", "success": True, "summary": "ok", "duration_ms": 1},
                {"tool_name": "workspace_write", "success": True, "summary": "ok", "duration_ms": 1},
                {"tool_name": "artifact_register", "success": True, "summary": "ok", "duration_ms": 1},
            ],
            "usage": None,
        }

    monkeypatch.setattr(pss.ParallelSubAgentService, "_child_loop", fake_child_loop)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-1",
        context_summary="",
        db=SimpleNamespace(),
        tasks=[
            {
                "agent_id": "agent-code",
                "task": "绘图并写 stdout",
                "requires": ["python.execute", "artifact.write", "artifact.publish"],
                "workspace_access": True,
            }
        ],
    )

    item = result["llm_payload"]["results"][0]
    assert item["outcome_status"] == "succeeded"
    assert item["reason_code"] == "ARTIFACT_RECEIPT_VERIFIED"
    # 实测产物经父回读对账 → artifact_status 升级为 published
    assert item["artifact_status"] == "published"
    artifacts = result["ui_payload"]["artifacts"]
    assert len(artifacts) == 2
    for artifact in artifacts:
        assert artifact["published_ref"].startswith(
            "workspace/chat-output/sess-1/output/subagents/"
        )
        assert artifact["sha256"]
    # 每路明细带父回读对账结果
    for entry in item["artifacts"]:
        assert entry["parent_reopen_check"] == "passed"
        assert entry["lifecycle"] == "published"
    # 父空间重读：文件真实存在且 hash 一致
    for artifact in artifacts:
        host_copy = env.tmp_path / artifact["published_ref"]
        assert host_copy.is_file()
        import hashlib

        assert hashlib.sha256(host_copy.read_bytes()).hexdigest() == artifact["sha256"]
    # result.json 属于审计记录，不得作为产物发布
    assert all(a["path"] != "result.json" for a in artifacts)
    # run 级 manifest 落盘且带 hash
    run_id = result["ui_payload"]["fanout_run_id"]
    manifest = json.loads(
        (env.tmp_path / "subagents" / run_id / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["schema_version"] == 1
    entries = manifest["tasks"][0]["entries"]
    assert {e["path"] for e in entries} == {"figures/scatter.png", "hello_stdout.txt"}
    assert all(e["sha256"] for e in entries)
    assert all(e["parent_reopen_check"] == "passed" for e in entries)
    assert "产物 2 件已发布" in result["llm_payload"]["summary"]


@pytest.mark.asyncio
async def test_fanout_publish_reopen_mismatch_marks_failed(env, monkeypatch) -> None:
    """父空间回读 hash 不一致（文件被篡改/写入失败）→ publish_failed，不冒充交付。"""
    _pf, backend = _patch_storage(env.tmp_path, monkeypatch)
    service = pss.ParallelSubAgentService()
    workdir = env.tmp_path / "subagents" / "runx" / "1"
    workdir.mkdir(parents=True)
    (workdir / "out.txt").write_text("original", encoding="utf-8")
    results = [
        {
            "index": 1,
            "task_id": "t1",
            "agent_id": "agent-code",
            "status": "ok",
            "workdir": str(workdir),
            "answer": "done",
        }
    ]
    first = await service._collect_and_publish_artifacts(
        results=results,
        workdir_root=env.tmp_path / "subagents" / "runx",
        run_id="runx",
        user_id="user-1",
        parent_session_id="sess-1",
    )
    assert first and first[0]["published_ref"].endswith("out.txt")

    # 篡改父空间副本后再次发布（幂等重试场景）：不得覆盖、必须检出 hash 不一致
    published_path = env.tmp_path / first[0]["published_ref"]
    published_path.write_text("tampered", encoding="utf-8")
    second = await service._collect_and_publish_artifacts(
        results=results,
        workdir_root=env.tmp_path / "subagents" / "runx",
        run_id="runx",
        user_id="user-1",
        parent_session_id="sess-1",
    )
    assert second == [], "回读 hash 不一致的产物不得标记为已发布"
    manifest = json.loads(
        (env.tmp_path / "subagents" / "runx" / "manifest.json").read_text(encoding="utf-8")
    )
    entry = manifest["tasks"][0]["entries"][0]
    assert entry["lifecycle"] == "publish_failed"
    assert entry["parent_reopen_check"] == "failed"
    # 子产物原文件未被篡改动作影响
    assert (workdir / "out.txt").read_text(encoding="utf-8") == "original"


@pytest.mark.asyncio
async def test_fanout_contract_without_artifacts_stays_not_created(env, monkeypatch) -> None:
    """R24：无产物产出时不得推断"已交付"；契约任务保持 not_created 并 blocked。"""
    contexts = {"agent-code": _ctx("agent-code")}
    monkeypatch.setattr(pss, "AgentService", lambda db: AgentServiceStub(contexts))

    async def handler(messages, _kwargs):
        yield ChatChunk(type="text", content="只是文字回答，没有写任何文件")

    _patch_provider(monkeypatch, handler)
    result = await pss.ParallelSubAgentService().run(
        user_id="user-1",
        parent_agent_id="manager",
        parent_session_id="sess-1",
        context_summary="",
        db=SimpleNamespace(),
        tasks=[
            {
                "agent_id": "agent-code",
                "task": "声称写了文件但实际没写",
                "requires": ["artifact.write"],
                "workspace_access": True,
            }
        ],
    )

    item = result["llm_payload"]["results"][0]
    assert item["status"] == "ok"
    assert item["outcome_status"] == "blocked"
    assert item["reason_code"] == "ARTIFACT_NOT_VERIFIED"
    assert item["artifact_status"] == "not_created"
    assert "artifacts" not in item
    assert result["ui_payload"]["artifacts"] == []
