"""对话内并行子 Agent fan-out 运行时。

设计文档：ARCHITECTURE_DESIGN/CygnusX_multi_agent_fanout.md §4。

父 Agent 一次工具调用提交相互独立的子任务列表，本服务在请求内并行运行
受限子 ReAct 循环（可调用 builtin 工具），失败隔离后结构化汇总回父上下文。

关键正确性约束（对应设计文档 §4.4 C1–C7）：
- C1 每个子循环的工具执行独占 AsyncSession（并发共享父 session 必崩）；
- C2 子 Agent 工具表剥离 parallel_subagents 自身（防递归，深度恒为 1）；
- C3 剥离 handoff 等会话控制工具；ask_user 作为结构化中断升级回 Manager；
- C4 requires_confirm 工具不在子循环执行，而是形成审批请求升级回 Manager；
- C5 单工具回灌截断 + 子循环总轮数上限；
- C6 子任务产物写入各自隔离子目录（经 ToolInvocationContext.extra 透出）；
- C7 fan-out 对父循环只计一次 tool_call。
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import itertools
import json
import logging
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from cygnusx.application.schemas.tool_invocation import ToolInvocationContext
from cygnusx.application.services.agent_service import AgentService
from cygnusx.application.services.agentteams_turn_recorder import AgentTeamsTurnRecorder
from cygnusx.application.services.execution_events import execution_metadata
from cygnusx.application.services.studio_tools import (
    ASK_USER_TOOL_SCHEMA,
    STUDIO_TOOL_SCHEMAS,
    _knowledge_search,
    execute_studio_tool,
)
from cygnusx.core.agentteams_context import agentteams_ctx_var
from cygnusx.core.config import get_settings
from cygnusx.domain.skill.services import (
    SKILL_TOOL_NAMES,
    USE_SKILL_TOOL_NAME,
)
from cygnusx.infrastructure.ai_provider.openai_compatible import (
    merge_token_usage,
    provider_manager,
)
from cygnusx.infrastructure.database.session import get_session_factory
from cygnusx.tools.schema_loader import schema_loader

logger = logging.getLogger(__name__)

PARALLEL_SUBAGENTS_TOOL_NAME = "parallel_subagents"

# 子循环内必须剥离的控制类工具（C2/C3）
_CONTROL_TOOL_NAMES = frozenset(
    {
        PARALLEL_SUBAGENTS_TOOL_NAME,  # C2 防递归 fan-out
        "skill_route",  # Skill scout 不得递归启动另一个 scout
        "transfer_to_agent",  # C3 子任务不能切换父会话
        "create_agentteams_case",  # 子任务不得创建跨会话交付 Case
        "cygnusx_save_memory",  # 子任务是临时工，不写长期记忆
        "cygnusx_update_memory",  # 26.8.4：子任务同样不得改写主用户记忆
        "cygnusx_forget_memory",  # 26.8.4：子任务不得删除主用户记忆
        # 保留 cygnusx_search_memory：只读检索对子任务有用且无副作用
    }
)

# Manager 的会诊仍禁止分析写入，但允许用户明确要求的记忆管理操作。
# 这些工具只修改当前用户自己的记忆，并由 Manager 提示词约束触发条件；
# 子 Agent 仍完全禁止写记忆。
_MANAGER_MEMORY_WRITE_TOOL_NAMES = frozenset(
    {
        "cygnusx_save_memory",
        "cygnusx_update_memory",
        "cygnusx_forget_memory",
        "cygnusx_update_memory_block",
    }
)

# 超频专家的工作台工具集合（对齐 AI 工作台）：沙盒/工作区读写 + 平台联动工具。
# datahub_import / platform_result_import / artifact_register / pipeline_query 均可由
# execute_studio_tool(name, args, session_id, user_id, db) 直接执行；
# update_plan 是 Studio 计划 UI 工具，不授予子 Agent。
_OVERDRIVE_WORKSPACE_TOOL_NAMES = frozenset(
    {
        "sandbox_execute",
        "workspace_write",
        "workspace_edit",
        "workspace_read",
        "workspace_list",
        "datahub_import",
        "platform_result_import",
        "artifact_register",
        "pipeline_query",
    }
)

# --- 任务能力契约（优化方案 §3.1）---
# 子任务可声明 requires（能力名单），prepare 阶段按装配后的有效工具求交；
# 缺失能力在 spawn 前即 blocked/CAPABILITY_MISSING，严禁静默成功。
CAPABILITY_RESEARCH_RETRIEVE = "research.retrieve"
CAPABILITY_WORKSPACE_READ = "workspace.read"
CAPABILITY_PYTHON_EXECUTE = "python.execute"
CAPABILITY_ARTIFACT_WRITE = "artifact.write"
CAPABILITY_ARTIFACT_PUBLISH = "artifact.publish"
CAPABILITY_APPROVAL_REQUEST = "approval.request"

_KNOWN_CAPABILITIES = frozenset(
    {
        CAPABILITY_RESEARCH_RETRIEVE,
        CAPABILITY_WORKSPACE_READ,
        CAPABILITY_PYTHON_EXECUTE,
        CAPABILITY_ARTIFACT_WRITE,
        CAPABILITY_ARTIFACT_PUBLISH,
        CAPABILITY_APPROVAL_REQUEST,
    }
)

# capability → 满足该能力所需的有效工具（任一命中即视为授予）
_CAPABILITY_SATISFY_TOOLS: dict[str, frozenset[str]] = {
    CAPABILITY_RESEARCH_RETRIEVE: frozenset({"knowledge_search", "web_search"}),
    CAPABILITY_WORKSPACE_READ: frozenset({"workspace_read", "workspace_list"}),
    CAPABILITY_PYTHON_EXECUTE: frozenset({"sandbox_execute"}),
    CAPABILITY_ARTIFACT_WRITE: frozenset({"workspace_write", "workspace_edit"}),
    CAPABILITY_ARTIFACT_PUBLISH: frozenset({"artifact_register"}),
    CAPABILITY_APPROVAL_REQUEST: frozenset({"ask_user"}),
}
# outcome evaluator 判定"真实执行/产物"的收据工具族
_EXECUTION_RECEIPT_TOOLS = frozenset({"sandbox_execute"})
_ARTIFACT_WRITE_RECEIPT_TOOLS = frozenset({"workspace_write", "workspace_edit"})
_ARTIFACT_PUBLISH_RECEIPT_TOOLS = frozenset({"artifact_register"})

# 子任务正式产物会落盘，不能再用 8,000 字截断代码、研究计划等长交付物。
# 20K tokens 的英文/代码输出可能超过 40K 字符，保留足够空间让 Agent 配置生效。
_ANSWER_CAP_CHARS = 100_000
_MAX_LENGTH_CONTINUATIONS = 2
# 父轮回灌 llm_payload 的预算（chat_service 对 fan-out 结果有 12,000 字护栏，
# 预留骨架余量）：超出预算的长正文降级为「短摘要 + detail_ref 引用」。
_LLM_PAYLOAD_BUDGET_CHARS = 10_000
# 降级后随父上下文回灌的单路摘要长度
_DETAIL_SUMMARY_CHARS = 500
# 单路子结果落盘为 detail_ref 的最小正文长度（低于此直接随信封携带）
_DETAIL_PERSIST_MIN_CHARS = 2_000
# 幂等重放缓存：R04 相同 request_key+payload 重放返回原 run 结果；R05 同 key 异 payload 报冲突。
# 进程内实现（多 worker 部署需共享存储，见 docs/subagents/01_current_runtime_audit.md §6）。
_REPLAY_CACHE_MAX_ENTRIES = 128
_REPLAY_CACHE_TTL_SECONDS = 1_800.0
_REQUEST_KEY_MAX_CHARS = 128
# 单子任务发布到父工作区的产物文件数上限（超出保留在子 workdir，manifest 记 truncated）
_PUBLISH_MAX_FILES_PER_CHILD = 50


class _FanoutReplayCache:
    """fan-out 结果重放缓存：(scope, key) → (payload_digest, envelope, stored_at)。"""

    def __init__(self, *, max_entries: int, ttl_seconds: float) -> None:
        self._max_entries = max_entries
        self._ttl = ttl_seconds
        self._entries: OrderedDict[tuple[str, str], tuple[str, dict[str, Any], float]] = (
            OrderedDict()
        )

    def lookup(self, scope: str, key: str) -> tuple[str, dict[str, Any]] | None:
        entry = self._entries.get((scope, key))
        if entry is None:
            return None
        _digest, envelope, stored_at = entry
        if time.monotonic() - stored_at > self._ttl:
            del self._entries[(scope, key)]
            return None
        self._entries.move_to_end((scope, key))
        return _digest, envelope

    def store(self, scope: str, key: str, digest: str, envelope: dict[str, Any]) -> None:
        self._entries[(scope, key)] = (digest, envelope, time.monotonic())
        self._entries.move_to_end((scope, key))
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)


_replay_cache = _FanoutReplayCache(
    max_entries=_REPLAY_CACHE_MAX_ENTRIES, ttl_seconds=_REPLAY_CACHE_TTL_SECONDS
)


def _canonical_payload_digest(prepared: FanoutPrepared, context_summary: str) -> str:
    """fan-out 请求规范化 digest：context + 全部子任务字段，任意差异即不同 payload。"""
    canonical = {
        "context_summary": (context_summary or "").strip(),
        "tasks": [
            {
                key: child.item.get(key)
                for key in (
                    "agent_id",
                    "task",
                    "requires",
                    "model_id",
                    "workspace_access",
                    "timeout_seconds",
                    "deep_thinking",
                    "task_id",
                )
                if child.item.get(key) is not None
            }
            for child in prepared.children
        ],
    }
    blob = json.dumps(canonical, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _has_unfinished_json_fence(text: str) -> bool:
    """判断文本是否结束在一个未闭合的 ```json 围栏内（用于长度截断续写的提示词选择）。"""
    if text.count("```") % 2 == 0:
        return False
    tail = text[text.rfind("```") + 3 :].lstrip()
    if tail[:4].lower() == "json":
        tail = tail[4:].lstrip()
    return tail.startswith("{")
# 模型偶发返回空内容（finish_reason=stop 且无任何正文）时的重试上限，
# 避免把空答复当作正常结果向上层返回。
_MAX_EMPTY_RESPONSE_RETRIES = 2
# 单条工具结果回灌子上下文的字符上限（C5）
_TOOL_RESULT_CAP_CHARS = 8000
# 可视化任务可能同时携带研究计划和代码阶段两个上游产物。
_TASK_INSTRUCTION_MAX_CHARS = 20000
_CONTEXT_SUMMARY_MAX_CHARS = 12000
# 连续相同（工具名+参数完全一致）工具调用的循环保护阈值。
# 取较大值避免误伤正常的重复只读查询（如能力目录/房间消息读取），
# 真正的死循环仍会被 max_rounds 兜底终止。
_MAX_DUPLICATE_TOOL_CALLS = 100
_MAX_REPEATED_TOOL_RESULTS = 2
# 单子任务随结果透出的工具回执上限（超出保留最近 N 条）
_MAX_TOOL_RECEIPTS = 20

_WEB_SEARCH_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "联网搜索公开资料，用于补充最新研究背景、文献线索与外部事实。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_n": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
}

_KNOWLEDGE_SEARCH_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "knowledge_search",
        "description": (
            "检索 CygnusX 已发布的知识库文档。专业问题必须先检索知识库；"
            "结果不足时再使用 web_search 补充公开资料。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 8},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}

_SUBAGENT_RESEARCH_PROMPT_SUFFIX = (
    "\n\n## 检索证据协议\n"
    "遇到专业原理、方法或流程问题时，先调用 `knowledge_search` 检索平台知识库。"
    "若结果为空、弱相关或不足以覆盖问题，再调用 `web_search` 补充公开资料。"
    "最终结论须区分实际检索证据与通用知识；不要虚构检索、文献或来源。"
)


class SubagentControlError(Exception):
    """Cooperative stop raised by a durable runtime at an explicit safe point."""

    def __init__(self, action: str) -> None:
        if action not in {"paused", "terminated"}:
            raise ValueError(f"unsupported subagent control action: {action}")
        self.action = action
        super().__init__(action)


def _collaboration_packet(*, answer: str | None, error: str | None, status: str) -> dict[str, Any]:
    """Worker 对 Manager 的稳定协作契约，避免把内部过程作为汇总输入。"""
    user_text = (answer or "").strip()
    compact = user_text.replace(" ", "")
    needs_user_input = any(
        marker in compact for marker in ("请补充", "请告诉我", "请回答", "需要明确", "等待你的")
    )
    return {
        "status": status,
        "final_answer": "" if needs_user_input else user_text,
        "needs_user_input": needs_user_input,
        "user_request": user_text if needs_user_input else "",
        "approval_requests": [],
        "error": error or "",
    }


def subagent_child_event_metadata(event: dict[str, Any]) -> dict[str, Any] | None:
    """把子循环 worker 事件映射为 chat SSE `subagents` chunk 的 metadata。

    仅透出有 UI 语义的相位（queued/started/retrying/finished）；heartbeat 等高频或
    内部事件返回 None，由调用方丢弃。seq 为 run 内单调序号，供前端乱序/重复去重。
    """
    event_type = str(event.get("type") or "")
    base: dict[str, Any] = {
        "index": int(event.get("index") or 0),
        "agent_id": str(event.get("agent_id") or ""),
        "name": str(event.get("agent_name") or event.get("agent_id") or ""),
        "seq": int(event.get("seq") or 0),
    }
    if event_type == "worker_queued":
        return {"phase": "child_queued", **base}
    if event_type == "worker_started":
        return {"phase": "child_started", **base}
    if event_type == "worker_retrying":
        return {"phase": "child_retrying", **base, "attempt": int(event.get("attempt") or 0)}
    if event_type == "worker_finished":
        return {
            "phase": "child_done",
            **base,
            "status": str(event.get("status") or ""),
            "elapsed_s": float(event.get("elapsed_s") or 0.0),
            "error": str(event.get("error") or "")[:200],
        }
    return None


SUBAGENT_SYSTEM_SUFFIX = (
    "\n\n## 子任务模式\n"
    "你正在执行由上级 Agent 并行分派的子任务。约束：\n"
    "1. 只专注完成本子任务，不要暴露内部推理、工具可用性或会话交接；\n"
    "2. 生成的一切中文内容不使用破折号\"——\"，需要解释或补充时改用逗号、冒号或括号；\n"
    "3. 优先只读操作，谨慎执行写文件或提交计算任务；\n"
    f"4. 完成后直接输出自包含、可核验的精简结论（控制在 {_ANSWER_CAP_CHARS} 字以内），"
    "包含关键证据与产物路径（如有）。若缺少用户必须提供的信息，只用一段简短、直接的"
    "补充请求说明缺什么；不要解释 ask_user 等工具是否可用，也不要重复上级 Agent 的分工说明。\n"
    "5. 正式结论末尾必须增加 `## 执行摘要`，用不超过 1,500 字概括结论、关键证据、"
    "限制和产物路径，供下游 Agent 与折叠卡片直接读取。"
)


@dataclass
class FanoutPreparedChild:
    """单个子任务的预组装结果（校验通过、尚未执行）。"""

    item: dict[str, Any]
    ctx: Any
    child_tools: list[dict[str, Any]]
    requires: tuple[str, ...] = ()
    capabilities_granted: tuple[str, ...] = ()
    blocked_capabilities: tuple[str, ...] = ()


@dataclass
class FanoutPrepared:
    """prepare() 通过的 fan-out 执行计划。

    prepare 阶段只读库与校验，不创建子运行、不占用配额、不发 started 事件；
    只有调用方确认接受（execute）后才产生执行副作用。
    """

    run_id: str
    workdir_root: Path
    context_summary: str
    children: list[FanoutPreparedChild]


class ParallelSubAgentService:
    """将独立子任务列表 fan-out 给已注册 Agent 并行执行，失败隔离并汇总。"""

    async def prepare(
        self,
        *,
        user_id: str,
        context_summary: str,
        tasks: list[dict[str, Any]],
        db: AsyncSession,
        safe_only: bool = False,
        runtime_authorized: bool = False,
        allow_non_spawnable_target: bool = False,
        workdir_root: Path | None = None,
    ) -> FanoutPrepared | dict[str, Any]:
        """仅做准入校验与预组装，不产生任何执行副作用（validate 先于 reserve）。

        返回 FanoutPrepared 表示校验通过可进入 execute()；返回 dict 即为拒绝信封
        （含 code/reason），调用方不得据此占用任何配额或发出 started 事件。
        """
        settings = get_settings()
        # env 开关与管理端平台设置（DB）任一为真即启用；管理端为运行时主开关
        from cygnusx.application.services.site_settings_service import SiteSettingsService

        db_enabled = await SiteSettingsService(db).is_subagent_fanout_enabled()
        if not (runtime_authorized or settings.subagent_fanout_enabled or db_enabled):
            return self._error(
                "子 Agent 并行分派未启用（管理端「设置 → 平台设置」开关"
                "或环境变量 SUBAGENT_FANOUT_ENABLED=true 任一启用即可）",
                code="SUBAGENT_DISABLED",
            )

        normalized = self._validate_tasks(tasks, settings.subagent_max_parallel)
        if isinstance(normalized, dict):  # 校验失败信封
            return normalized
        context_summary = (context_summary or "").strip()[:_CONTEXT_SUMMARY_MAX_CHARS]

        # 顺序预组装：单线程复用父 session 读库，满足 C1（并发阶段不再碰父 session）
        agent_service = AgentService(db)
        prepared: list[FanoutPreparedChild] = []
        for index, item in enumerate(normalized, start=1):
            assemble = agent_service.assemble_context
            parameters = inspect.signature(assemble).parameters
            assemble_kwargs: dict[str, Any] = {}
            if "user_id" in parameters:
                assemble_kwargs["user_id"] = user_id
            if "model_id" in parameters and item.get("model_id"):
                assemble_kwargs["model_id"] = item["model_id"]
            ctx = await assemble(item["agent_id"], **assemble_kwargs)
            if ctx is None or ctx.model_config is None:
                return self._error(
                    f"子任务 #{index} 的目标 Agent {item['agent_id']} 不存在或未绑定可用模型",
                    code="SUBAGENT_AGENT_UNKNOWN",
                )
            if not bool((ctx.features or {}).get("subagents_spawnable")) and not (
                allow_non_spawnable_target and safe_only and len(normalized) == 1
            ):
                return self._error(
                    f"Agent {item['agent_id']} 未标记为可派生子 Agent"
                    "（需在 Agent YAML 的 features 增加 subagents_spawnable: true）",
                    code="SUBAGENT_NOT_SPAWNABLE",
                )
            child_tools = self._prepare_child_tools(
                ctx,
                workspace_access=bool(item.get("workspace_access")) and not safe_only,
                safe_only=safe_only,
            )
            tool_names = {
                str((tool.get("function") or {}).get("name") or "")
                for tool in child_tools
                if isinstance(tool, dict)
            }
            requires = tuple(item.get("requires") or ())
            granted = tuple(
                capability
                for capability, satisfy in _CAPABILITY_SATISFY_TOOLS.items()
                if tool_names & satisfy
            )
            prepared.append(
                FanoutPreparedChild(
                    item=item,
                    ctx=ctx,
                    child_tools=child_tools,
                    requires=requires,
                    capabilities_granted=granted,
                    blocked_capabilities=tuple(
                        capability for capability in requires if capability not in granted
                    ),
                )
            )

        run_id = uuid4().hex[:12]
        return FanoutPrepared(
            run_id=run_id,
            workdir_root=workdir_root or Path(get_settings().storage_path) / "subagents" / run_id,
            context_summary=context_summary,
            children=prepared,
        )

    async def execute(
        self,
        prepared: FanoutPrepared,
        *,
        user_id: str,
        parent_agent_id: str,
        parent_session_id: str,
        on_event: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
        approved_tool_calls: list[dict[str, Any]] | None = None,
        control_check: Callable[[], Awaitable[str | None] | str | None] | None = None,
        max_rounds: int | None = None,
        request_key: str | None = None,
    ) -> dict[str, Any]:
        """执行已通过 prepare() 校验的 fan-out，返回统一信封 {success, llm_payload, ui_payload}。"""
        settings = get_settings()
        run_id = prepared.run_id
        workdir_root = prepared.workdir_root
        children = prepared.children
        if request_key is not None:
            if (
                not isinstance(request_key, str)
                or not request_key.strip()
                or len(request_key) > _REQUEST_KEY_MAX_CHARS
            ):
                return self._error(
                    "request_key 必须是非空字符串且不超过 128 字符",
                    code="SUBAGENT_INVALID_REQUEST_KEY",
                )
            request_key = request_key.strip()
        payload_digest = _canonical_payload_digest(prepared, prepared.context_summary)
        replay_scope = f"{user_id}:{parent_session_id}"
        # 幂等契约只在显式提供 request_key 时生效：无键的同 payload 调用视为新的业务请求
        #（用户在会话中"再跑一次"合法），不做隐式重放。
        replay_lookup_key = request_key
        cached = _replay_cache.lookup(replay_scope, replay_lookup_key) if replay_lookup_key else None
        if cached is not None:
            cached_digest, cached_envelope = cached
            if cached_digest != payload_digest:
                # R05：相同 request_key 携带不同 payload → 明确冲突，不得静默重跑
                return self._error(
                    "相同 request_key 已受理过不同内容的 fan-out 请求（SUBAGENT_REQUEST_CONFLICT）",
                    code="SUBAGENT_REQUEST_CONFLICT",
                )
            import copy

            replayed = copy.deepcopy(cached_envelope)
            replayed["replayed"] = True
            replayed.setdefault("ui_payload", {})["replayed"] = True
            logger.info(
                "subagent fan-out 幂等重放命中: scope=%s key=%s run_id=%s",
                replay_scope,
                (replay_lookup_key or "")[:16],
                (replayed.get("ui_payload") or {}).get("fanout_run_id"),
            )
            return replayed
        semaphore = asyncio.Semaphore(max(1, settings.subagent_max_concurrent))
        started = time.monotonic()
        logger.info(
            "subagent fan-out 启动: run_id=%s parent_agent=%s parent_session=%s tasks=%d",
            run_id,
            parent_agent_id,
            parent_session_id,
            len(children),
        )
        gathered = await asyncio.gather(
            *(
                self._run_child(
                    index=index,
                    task_id=str(child.item.get("task_id") or ""),
                    agent_id=child.item["agent_id"],
                    task=child.item["task"],
                    context_summary=prepared.context_summary,
                    ctx=child.ctx,
                    child_tools=child.child_tools,
                    requires=child.requires,
                    capabilities_granted=child.capabilities_granted,
                    blocked_capabilities=child.blocked_capabilities,
                    workspace_access=bool(child.item.get("workspace_access")),
                    user_id=user_id,
                    parent_session_id=parent_session_id,
                    run_id=run_id,
                    workdir=workdir_root if len(children) == 1 else workdir_root / str(index),
                    timeout_seconds=int(
                        child.item.get("timeout_seconds") or settings.subagent_child_timeout_seconds
                    ),
                    retry=child.item.get("retry") or {},
                    # 缺省保持普通聊天 fan-out 的轮数上限；超频专家经 max_rounds 显式放宽
                    max_rounds=max_rounds or settings.subagent_max_rounds_per_child,
                    deep_thinking=bool(child.item.get("deep_thinking")),
                    semaphore=semaphore,
                    on_event=on_event,
                    approved_tool_calls=approved_tool_calls or [],
                    control_check=control_check,
                )
                for index, child in enumerate(children, start=1)
            ),
            return_exceptions=True,
        )
        results: list[dict[str, Any]] = []
        for index, item in enumerate(gathered, start=1):
            if isinstance(item, BaseException):
                prepared_item = children[index - 1].item
                results.append(
                    {
                        "index": index,
                        "task_id": prepared_item.get("task_id") or f"agentteams:{run_id}:{index}",
                        "agent_id": prepared_item["agent_id"],
                        "status": "failed",
                        "answer": None,
                        "thought": None,
                        "error": str(item)[:500],
                        "packet": _collaboration_packet(
                            answer=None, error=str(item)[:500], status="failed"
                        ),
                        "elapsed_s": round(time.monotonic() - started, 1),
                    }
                )
            else:
                results.append(item)
        # WP2 产物闭环：子 workdir 实测（stat/sha256）→ 发布父工作区 → 父回读对账
        try:
            published_artifacts = await self._collect_and_publish_artifacts(
                results=results,
                workdir_root=workdir_root,
                run_id=run_id,
                user_id=user_id,
                parent_session_id=parent_session_id,
            )
        except Exception as exc:  # noqa: BLE001 — 产物闭环失败不颠覆已完成的子任务
            logger.warning("subagent 产物发布异常 run_id=%s: %s", run_id, exc)
            published_artifacts = []
        elapsed = round(time.monotonic() - started, 1)
        ok_count = sum(1 for item in results if item["status"] == "ok")
        interrupted_count = sum(
            1 for item in results if item["status"] in {"awaiting_input", "approval_pending"}
        )
        merged_usage: dict[str, Any] | None = None
        for item in results:
            merged_usage = merge_token_usage(merged_usage, item.get("usage"))
        total = len(results)
        views = [self._llm_view(item) for item in results]
        # R15 退化检测：子循环正常结束却没有任何正文时显式标记，禁止静默丢失
        for view in views:
            if view.get("status") == "ok" and not (view.get("answer") or "").strip():
                view["body_missing"] = True
        body_missing_count = sum(1 for view in views if view.get("body_missing"))
        missing_suffix = "（部分子任务正文缺失，见明细）" if body_missing_count else ""
        contract_evaluated = any("outcome_status" in item for item in results)
        if contract_evaluated:
            # 契约化任务：按验收口径汇总，"成功"只代表已验证完成
            verified_count = sum(1 for item in results if item.get("outcome_status") == "succeeded")
            blocked_count = sum(1 for item in results if item.get("outcome_status") == "blocked")
            unverified_count = sum(
                1 for item in results if item.get("outcome_status") == "answered_unverified"
            )
            partial_count = sum(1 for item in results if item.get("outcome_status") == "partial")
            failed_count = total - verified_count - blocked_count - unverified_count - partial_count
            parts = [f"{verified_count} 已验证完成"]
            if blocked_count:
                parts.append(f"{blocked_count} 受阻")
            if unverified_count:
                parts.append(f"{unverified_count} 未验证问答")
            if partial_count:
                parts.append(f"{partial_count} 部分完成")
            if failed_count:
                parts.append(f"{failed_count} 失败/超时")
            summary = "，".join(parts) + f"；总墙钟 {elapsed}s{missing_suffix}"
        else:
            summary = (
                f"{ok_count}/{total} 个子任务成功，总墙钟 {elapsed}s{missing_suffix}"
                if ok_count == total
                else f"{interrupted_count}/{total} 个子任务等待用户处理，总墙钟 {elapsed}s{missing_suffix}"
                if interrupted_count and ok_count + interrupted_count == total
                else f"{ok_count}/{total} 个子任务成功，总墙钟 {elapsed}s（含失败/超时项，见明细）{missing_suffix}"
            )
        if published_artifacts:
            summary = (
                f"{summary}；产物 {len(published_artifacts)} 件已发布到"
                f"父工作区 subagents/{run_id}/"
            )
        llm_payload: dict[str, Any] = {"summary": summary, "results": views}
        # R16：父轮回灌预算内逐路降级，长正文走 detail_ref，杜绝父轮 12k 静默截断
        if len(json.dumps(llm_payload, ensure_ascii=False, default=str)) > _LLM_PAYLOAD_BUDGET_CHARS:
            order = sorted(
                range(len(views)),
                key=lambda i: len(views[i].get("answer") or ""),
                reverse=True,
            )
            for i in order:
                if (
                    len(json.dumps(llm_payload, ensure_ascii=False, default=str))
                    <= _LLM_PAYLOAD_BUDGET_CHARS
                ):
                    break
                views[i] = self._compact_view_for_budget(views[i])
                llm_payload["results"][i] = views[i]
        envelope: dict[str, Any] = {
            "success": ok_count + interrupted_count > 0,
            "usage": merged_usage,
            "llm_payload": llm_payload,
            "ui_payload": {
                "fanout_run_id": run_id,
                "elapsed_s": elapsed,
                "artifacts": published_artifacts,
                "progress": [
                    {
                        "index": item["index"],
                        "agent_id": item["agent_id"],
                        "status": item["status"],
                        "outcome_status": item.get("outcome_status"),
                        "reason_code": item.get("reason_code"),
                        "elapsed_s": item["elapsed_s"],
                        **(
                            {
                                "answer_summary": (item.get("answer") or "")[:200],
                                "detail_ref": item.get("detail_ref"),
                                "payload_truncated": item.get("payload_truncated", False),
                                "body_missing": item.get("body_missing", False),
                            }
                            if isinstance(item.get("answer"), str)
                            or item.get("detail_ref")
                            or item.get("body_missing")
                            else {}
                        ),
                    }
                    for item in views
                ],
            },
        }
        if replay_lookup_key:
            _replay_cache.store(replay_scope, replay_lookup_key, payload_digest, envelope)
        return envelope

    @staticmethod
    def _compact_view_for_budget(view: dict[str, Any]) -> dict[str, Any]:
        """把单路 view 的长正文降级为「短摘要 + detail_ref 引用」，并显式标记截断。"""
        answer = str(view.get("answer") or "")
        compacted = dict(view)
        detail_ref = view.get("detail_ref")
        if detail_ref:
            compacted["answer"] = (
                answer[:_DETAIL_SUMMARY_CHARS]
                + f"\n\n[完整结果已持久化，请按 detail_ref 读取: {detail_ref}]"
            )
        else:
            compacted["answer"] = answer[:_DETAIL_SUMMARY_CHARS]
        packet = view.get("packet")
        if isinstance(packet, dict) and len(str(packet.get("final_answer") or "")) > len(
            compacted["answer"]
        ):
            compacted["packet"] = {
                **packet,
                "final_answer": str(packet.get("final_answer") or "")[:_DETAIL_SUMMARY_CHARS],
            }
        compacted["payload_truncated"] = True
        return compacted

    async def run(
        self,
        *,
        user_id: str,
        parent_agent_id: str,
        parent_session_id: str,
        context_summary: str,
        tasks: list[dict[str, Any]],
        db: AsyncSession,
        on_event: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
        safe_only: bool = False,
        runtime_authorized: bool = False,
        allow_non_spawnable_target: bool = False,
        workdir_root: Path | None = None,
        approved_tool_calls: list[dict[str, Any]] | None = None,
        control_check: Callable[[], Awaitable[str | None] | str | None] | None = None,
        max_rounds: int | None = None,
        request_key: str | None = None,
    ) -> dict[str, Any]:
        """prepare + execute 的组合便捷入口（供超频/会诊/scout/Goal 等既有调用方使用）。"""
        prepared = await self.prepare(
            user_id=user_id,
            context_summary=context_summary,
            tasks=tasks,
            db=db,
            safe_only=safe_only,
            runtime_authorized=runtime_authorized,
            allow_non_spawnable_target=allow_non_spawnable_target,
            workdir_root=workdir_root,
        )
        if isinstance(prepared, dict):  # 校验拒绝信封
            return prepared
        return await self.execute(
            prepared,
            user_id=user_id,
            parent_agent_id=parent_agent_id,
            parent_session_id=parent_session_id,
            on_event=on_event,
            approved_tool_calls=approved_tool_calls,
            control_check=control_check,
            max_rounds=max_rounds,
            request_key=request_key,
        )

    # --- 校验 ---

    @staticmethod
    def _validate_tasks(tasks: Any, max_parallel: int) -> list[dict[str, Any]] | dict[str, Any]:
        if not isinstance(tasks, list) or not tasks:
            return ParallelSubAgentService._error(
                "tasks 必须为非空列表", code="SUBAGENT_INVALID_TASKS"
            )
        if len(tasks) > max_parallel:
            return ParallelSubAgentService._error(
                f"单次 fan-out 最多 {max_parallel} 个子任务（SUBAGENT_MAX_PARALLEL）",
                code="SUBAGENT_MAX_PARALLEL",
            )
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(tasks, start=1):
            if not isinstance(item, dict):
                return ParallelSubAgentService._error(
                    f"子任务 #{index} 必须是对象", code="SUBAGENT_INVALID_TASKS"
                )
            agent_id = str(item.get("agent_id") or "").strip()
            task = str(item.get("task") or "").strip()
            if not agent_id or not task:
                return ParallelSubAgentService._error(
                    f"子任务 #{index} 缺少 agent_id 或 task", code="SUBAGENT_INVALID_TASKS"
                )
            if len(task) > _TASK_INSTRUCTION_MAX_CHARS:
                return ParallelSubAgentService._error(
                    f"子任务 #{index} 的指令超过 {_TASK_INSTRUCTION_MAX_CHARS} 字",
                    code="SUBAGENT_INVALID_TASKS",
                )
            normalized_item: dict[str, Any] = {"agent_id": agent_id, "task": task}
            raw_requires = item.get("requires")
            if raw_requires is not None:
                if not isinstance(raw_requires, list) or not all(
                    isinstance(cap, str) for cap in raw_requires
                ):
                    return ParallelSubAgentService._error(
                        f"子任务 #{index} 的 requires 必须是字符串数组",
                        code="SUBAGENT_INVALID_TASKS",
                    )
                unknown = [cap for cap in raw_requires if cap not in _KNOWN_CAPABILITIES]
                if unknown:
                    return ParallelSubAgentService._error(
                        f"子任务 #{index} 声明了未知能力：{'、'.join(unknown)}",
                        code="SUBAGENT_INVALID_TASKS",
                    )
                normalized_item["requires"] = list(dict.fromkeys(raw_requires))
            if item.get("model_id"):
                normalized_item["model_id"] = item["model_id"]
            if item.get("deep_thinking") is not None:
                normalized_item["deep_thinking"] = bool(item["deep_thinking"])
            if item.get("task_id"):
                normalized_item["task_id"] = str(item["task_id"]).strip()
            if item.get("timeout_seconds"):
                normalized_item["timeout_seconds"] = max(1, int(item["timeout_seconds"]))
            if isinstance(item.get("retry"), dict) and item["retry"]:
                normalized_item["retry"] = item["retry"]
            if item.get("workspace_access"):
                normalized_item["workspace_access"] = True
            normalized.append(normalized_item)
        return normalized

    # --- 工具过滤（C2/C3/C4）---

    @staticmethod
    def _prepare_child_tools(
        ctx: Any, *, workspace_access: bool = False, safe_only: bool = False
    ) -> list[dict[str, Any]]:
        """透传 Agent 已绑定能力，同时剥离递归与长任务控制工具。"""
        context_agent_id = str(
            getattr(getattr(ctx, "agent", None), "agent_id", "") or ""
        )
        tools = list(getattr(ctx, "tools", []) or [])
        room_id = str((agentteams_ctx_var.get() or {}).get("room_id") or "").strip()
        if room_id:
            room_tool_names = {"room_messages_read", "room_facts_query"}
            known_names = {
                str((tool.get("function") or {}).get("name") or "")
                for tool in tools
                if isinstance(tool, dict)
            }
            tools.extend(
                tool
                for tool in schema_loader.to_openai_tools()
                if str((tool.get("function") or {}).get("name") or "") in room_tool_names
                and str((tool.get("function") or {}).get("name") or "") not in known_names
            )
        names = {
            str((tool.get("function") or {}).get("name") or "")
            for tool in tools
            if isinstance(tool, dict)
        }
        if "ask_user" not in names:
            tools.append(ASK_USER_TOOL_SCHEMA)
            names.add("ask_user")
        if "knowledge_search" not in names:
            tools.append(_KNOWLEDGE_SEARCH_TOOL_SCHEMA)
            names.add("knowledge_search")
        web_policy = (getattr(ctx, "features", {}) or {}).get("web_search")
        web_disabled = web_policy is False or (
            isinstance(web_policy, dict)
            and str(web_policy.get("mode") or "").lower() in {"off", "disabled"}
        )
        if not web_disabled and "web_search" not in names:
            tools.append(_WEB_SEARCH_TOOL_SCHEMA)

        mcp_tool_names = {
            str(tool.tool_name)
            for server in (getattr(ctx, "mcp_servers", []) or [])
            for tool in (getattr(server, "tools", []) or [])
        }
        # 声明了 readOnlyHint 的 MCP 工具（如协作室能力目录/房间状态查询）在
        # safe_only 只读会诊中放行；无注解声明的外部 MCP 工具维持原样剥离。
        readonly_mcp_tool_names = {
            str(tool.tool_name)
            for server in (getattr(ctx, "mcp_servers", []) or [])
            for tool in (getattr(server, "tools", []) or [])
            if (getattr(tool, "annotations", None) or {}).get("readOnlyHint") is True
            and (getattr(tool, "annotations", None) or {}).get("destructiveHint") is not True
        }
        kept: list[dict[str, Any]] = []
        for tool in tools:
            name = str((tool.get("function") or {}).get("name") or "")
            manager_memory_write = (
                context_agent_id == "agentteams-manager"
                and name in _MANAGER_MEMORY_WRITE_TOOL_NAMES
            )
            if not name or (name in _CONTROL_TOOL_NAMES and not manager_memory_write):
                continue
            schema = schema_loader.get_tool(name)
            if schema is not None and schema.invocation_mode != "backend_sync":
                continue  # analysis_flow 长耗时管道应走 MAS
            if (
                schema is None
                and name not in mcp_tool_names
                and name not in SKILL_TOOL_NAMES
                and name not in {"ask_user", "knowledge_search", "web_search"}
            ):
                continue
            if (
                safe_only
                and name not in {"ask_user", "knowledge_search", "web_search", *SKILL_TOOL_NAMES}
                and name not in readonly_mcp_tool_names
                and not manager_memory_write
                and (
                    schema is None
                    or not schema.annotations.read_only_hint
                    or schema.requires_confirm
                )
            ):
                continue
            kept.append(tool)
        if workspace_access and not safe_only:
            existing_names = {str((tool.get("function") or {}).get("name") or "") for tool in kept}
            kept.extend(
                tool
                for tool in STUDIO_TOOL_SCHEMAS
                if str((tool.get("function") or {}).get("name") or "")
                in _OVERDRIVE_WORKSPACE_TOOL_NAMES
                and str((tool.get("function") or {}).get("name") or "") not in existing_names
            )
        return kept

    @staticmethod
    def _filter_child_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        """兼容旧测试/调用：仅按 builtin 安全约束过滤。"""
        ctx = type(
            "ChildToolContext", (), {"tools": tools or [], "features": {}, "mcp_servers": []}
        )()
        return ParallelSubAgentService._prepare_child_tools(ctx)

    # --- 子循环执行 ---

    async def _run_child(
        self,
        *,
        index: int,
        task_id: str,
        agent_id: str,
        task: str,
        context_summary: str,
        ctx: Any,
        child_tools: list[dict[str, Any]],
        requires: tuple[str, ...] = (),
        capabilities_granted: tuple[str, ...] = (),
        blocked_capabilities: tuple[str, ...] = (),
        workspace_access: bool,
        user_id: str,
        parent_session_id: str,
        run_id: str,
        workdir: Path,
        timeout_seconds: int,
        retry: dict[str, Any],
        max_rounds: int,
        deep_thinking: bool,
        semaphore: asyncio.Semaphore,
        on_event: Callable[[dict[str, Any]], Awaitable[None] | None] | None,
        control_check: Callable[[], Awaitable[str | None] | str | None] | None,
        approved_tool_calls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        started = time.monotonic()
        base = {
            "index": index,
            "agent_id": agent_id,
            "agent_name": str(getattr(getattr(ctx, "agent", None), "name", agent_id)),
        }
        try:
            workdir.mkdir(parents=True, exist_ok=True)  # noqa: ASYNC240
        except OSError as exc:  # 存储不可写不致命：路径仍透出给工具自选
            logger.warning("子任务工作目录创建失败 %s: %s", workdir, exc)
        max_attempts = max(1, min(5, int(retry.get("max_attempts") or 1)))
        backoff_seconds = max(0, min(300, int(retry.get("backoff_seconds") or 0)))
        outcome: dict[str, Any] = {}
        if blocked_capabilities:
            # 能力预检在 spawn 前阻断：子循环不启动、不占 provider 调用，
            # 以 blocked/CAPABILITY_MISSING 明示缺失，杜绝静默成功。
            await self._emit_event(on_event, {"type": "worker_started", **base})
            missing = "、".join(blocked_capabilities)
            outcome = {
                "status": "blocked",
                "answer": None,
                "error": (
                    f"缺少必需能力：{missing}（当前执行上下文未授予，"
                    "子任务未启动；请改派具备该能力的 Agent 或改用受权工作台模式）"
                ),
                "tool_receipts": [],
            }
        else:
            # 排队观测：semaphore acquire 之前即发 queued（R17/R30 需要可见的排队期），
            # 同一进程 monotonic 钟，timing 可直接比较。
            queued_monotonic = time.monotonic()
            await self._emit_event(on_event, {"type": "worker_queued", **base})
            async with semaphore:
                started_monotonic = time.monotonic()
                await self._emit_event(on_event, {"type": "worker_started", **base})
                for attempt in range(1, max_attempts + 1):
                    await self._emit_event(
                        on_event, {"type": "worker_heartbeat", "attempt": attempt, **base}
                    )
                    try:
                        await self._check_control(control_check)
                        async with asyncio.timeout(float(max(1, timeout_seconds))):
                            outcome = await self._child_loop(
                                agent_id=agent_id,
                                task=task,
                                context_summary=context_summary,
                                ctx=ctx,
                                child_tools=child_tools,
                                workspace_access=workspace_access,
                                user_id=user_id,
                                parent_session_id=parent_session_id,
                                run_id=run_id,
                                index=index,
                                workdir=workdir,
                                max_rounds=max_rounds,
                                on_event=on_event,
                                control_check=control_check,
                                approved_tool_calls=approved_tool_calls,
                                deep_thinking=deep_thinking,
                            )
                        await self._check_control(control_check)
                    except SubagentControlError as exc:
                        outcome = {
                            "status": exc.action,
                            "answer": None,
                            "error": None,
                        }
                    except TimeoutError:
                        outcome = {"status": "timeout", "answer": None, "error": "子任务超时"}
                    except Exception as exc:  # noqa: BLE001 — 失败隔离，不影响兄弟子任务
                        logger.warning("子任务 #%d (%s) 执行异常: %s", index, agent_id, exc)
                        outcome = {"status": "failed", "answer": None, "error": str(exc)[:500]}
                    if outcome.get("status") not in {"timeout", "failed"}:
                        break
                    error = str(outcome.get("error") or "").lower()
                    transient = outcome.get("status") == "timeout" or any(
                        marker in error
                        for marker in ("timeout", "timed out", "502", "503", "504", "5xx")
                    )
                    if not transient or attempt >= max_attempts:
                        break
                    await self._emit_event(
                        on_event,
                        {
                            "type": "worker_retrying",
                            "attempt": attempt + 1,
                            "backoff_seconds": backoff_seconds * (2 ** (attempt - 1)),
                            **base,
                        },
                    )
                    await asyncio.sleep(backoff_seconds * (2 ** (attempt - 1)))
        packet = outcome.get("packet") or _collaboration_packet(
            answer=outcome.get("answer"), error=outcome.get("error"), status=outcome["status"]
        )
        effective_status = str(outcome["status"])
        if packet.get("needs_user_input"):
            effective_status = "awaiting_input"
            packet = {**packet, "status": effective_status, "error": ""}
        result = {
            **base,
            "task_id": task_id or f"agentteams:{run_id}:{index}",
            "status": effective_status,
            "answer": outcome.get("answer"),
            "thought": outcome.get("thought"),
            "error": None if effective_status == "awaiting_input" else outcome.get("error"),
            "packet": packet,
            "verified_evidence_refs": outcome.get("verified_evidence_refs") or [],
            "workdir": str(workdir),
            "elapsed_s": round(time.monotonic() - started, 1),
            "usage": outcome.get("usage"),
        }
        if outcome.get("partial"):
            result["partial"] = True
        if outcome.get("guard_triggered"):
            result["guard_triggered"] = True
        if requires:
            # 契约化任务：附 outcome/artifact 判定与回执，供汇总诚实口径与父 Agent 审计
            evaluated = self._evaluate_outcome(
                requires=requires,
                status=effective_status,
                receipts=outcome.get("tool_receipts") or [],
                blocked_capabilities=blocked_capabilities,
            )
            result["outcome_status"] = evaluated["outcome_status"]
            result["reason_code"] = evaluated["reason_code"]
            result["artifact_status"] = evaluated["artifact_status"]
            result["capabilities_required"] = list(requires)
            result["capabilities_granted"] = list(capabilities_granted)
            result["tool_receipts"] = list(outcome.get("tool_receipts") or [])[-_MAX_TOOL_RECEIPTS:]
        detail_ref = self._persist_child_detail(result=result, workdir=workdir)
        if detail_ref:
            result["detail_ref"] = detail_ref
        await self._emit_event(on_event, {"type": "worker_finished", **result})
        return result

    @staticmethod
    def _persist_child_detail(*, result: dict[str, Any], workdir: Path) -> str | None:
        """把单路子结果完整正文落盘为 detail_ref，父/前端按引用读取。

        返回相对 storage 的引用（subagents/{run_id}/{index}/result.json）；
        正文过短（随信封携带即可）或落盘失败时返回 None，不影响主流程。
        """
        answer = str(result.get("answer") or "")
        if len(answer) < _DETAIL_PERSIST_MIN_CHARS:
            return None
        record = {
            key: result.get(key)
            for key in (
                "task_id",
                "agent_id",
                "agent_name",
                "status",
                "answer",
                "thought",
                "error",
                "outcome_status",
                "reason_code",
                "artifact_status",
                "tool_receipts",
                "usage",
                "elapsed_s",
            )
            if key in result
        }
        try:
            workdir.mkdir(parents=True, exist_ok=True)  # noqa: ASYNC240
            (workdir / "result.json").write_text(
                json.dumps(record, ensure_ascii=False, default=str), encoding="utf-8"
            )
        except OSError as exc:
            logger.warning("子任务结果落盘失败 %s: %s", workdir, exc)
            return None
        try:
            relative = workdir.relative_to(Path(get_settings().storage_path))
        except ValueError:
            relative = workdir
        return str(relative / "result.json")

    async def _collect_and_publish_artifacts(
        self,
        *,
        results: list[dict[str, Any]],
        workdir_root: Path,
        run_id: str,
        user_id: str,
        parent_session_id: str,
    ) -> list[dict[str, Any]]:
        """子任务产物闭环：Produced（子 workdir 实测）→ Verified（size/sha256）→
        Published（复制到父 chat-output 并父回读对账）→ 登记 file_records。

        返回已发布产物扁平清单（供 ui_payload.artifacts）；单文件失败只降级该项，
        不影响兄弟产物与主流程。run 级 manifest 落盘 workdir_root/manifest.json。
        """
        from cygnusx.infrastructure.storage import get_path_factory, get_storage_backend

        path_factory = get_path_factory()
        backend = get_storage_backend()
        published: list[dict[str, Any]] = []
        manifest_tasks: list[dict[str, Any]] = []
        for item in results:
            index = item.get("index")
            task_label = str(item.get("task_id") or f"task-{index}")
            # 发布路径安全化：仅保留字母数字与 -_:，防 ../ 与特殊字符逃逸
            safe_label = "".join(
                char if (char.isalnum() or char in "-_:") else "-" for char in task_label
            )[:80]
            workdir = Path(str(item.get("workdir") or ""))
            dir_exists, files = await asyncio.to_thread(self._scan_workdir, workdir)
            if not dir_exists:
                continue
            if not files:
                continue
            files_truncated = len(files) > _PUBLISH_MAX_FILES_PER_CHILD
            from cygnusx.application.services.artifact_manifest import build_manifest

            entries = build_manifest(workdir, files[:_PUBLISH_MAX_FILES_PER_CHILD])
            dest_dir_rel = (
                f"workspace/chat-output/{parent_session_id}/output"
                f"/subagents/{run_id}/{safe_label}"
            )
            await backend.ensure_dir(dest_dir_rel)
            task_entries: list[dict[str, Any]] = []
            for entry in entries:
                record: dict[str, Any] = {
                    **entry,
                    "index": index,
                    "agent_id": item.get("agent_id"),
                    "task_id": item.get("task_id"),
                    "lifecycle": "produced",
                    "published_ref": None,
                    "parent_reopen_check": "not_run",
                }
                sha256 = entry.get("sha256")
                if sha256:
                    dst_rel = f"{dest_dir_rel}/{entry['path']}"
                    src_rel = path_factory.relative_to_root(workdir / str(entry["path"]))
                    try:
                        # R26 幂等/重名：已存在不覆盖（run_id 命名空间内仅同 run 重试可能命中）
                        if not await backend.exists(dst_rel):
                            await backend.copy(src_rel, dst_rel)
                        reopened_sha = hashlib.sha256(await backend.read(dst_rel)).hexdigest()
                        if reopened_sha == sha256:
                            record["lifecycle"] = "published"
                            record["published_ref"] = dst_rel
                            record["parent_reopen_check"] = "passed"
                        else:
                            record["lifecycle"] = "publish_failed"
                            record["parent_reopen_check"] = "failed"
                            record["error"] = "父空间回读 hash 与产物不一致"
                    except Exception as exc:  # noqa: BLE001 — 单文件失败不颠覆整批
                        record["lifecycle"] = "publish_failed"
                        record["error"] = f"{type(exc).__name__}: {exc}"[:200]
                task_entries.append(record)
                if record["lifecycle"] == "published":
                    published.append(
                        {
                            "index": index,
                            "agent_id": item.get("agent_id"),
                            "task_id": item.get("task_id"),
                            "path": entry["path"],
                            "size": entry.get("size"),
                            "sha256": entry.get("sha256"),
                            "published_ref": record["published_ref"],
                        }
                    )
            published_count = sum(1 for e in task_entries if e.get("lifecycle") == "published")
            verified_count = sum(1 for e in task_entries if e.get("sha256"))
            if "artifact_status" in item:
                # 契约任务：用实测产物刷新产物状态（outcome 仍由回执判定）
                if published_count:
                    item["artifact_status"] = "published"
                elif verified_count:
                    item["artifact_status"] = "verified"
            item["artifacts"] = task_entries
            manifest_tasks.append(
                {
                    "index": index,
                    "agent_id": item.get("agent_id"),
                    "task_id": item.get("task_id"),
                    "status": item.get("status"),
                    "files_truncated": files_truncated,
                    "entries": task_entries,
                }
            )
            await self._register_artifact_records(
                path_factory=path_factory,
                user_id=user_id,
                directory=dest_dir_rel,
                records=[
                    entry for entry in task_entries if entry.get("lifecycle") == "published"
                ],
            )
        if manifest_tasks:
            try:
                (workdir_root / "manifest.json").write_text(
                    json.dumps(
                        {
                            "schema_version": 1,
                            "run_id": run_id,
                            "parent_session_id": parent_session_id,
                            "tasks": manifest_tasks,
                        },
                        ensure_ascii=False,
                        default=str,
                    ),
                    encoding="utf-8",
                )
            except OSError as exc:
                logger.warning("subagent manifest 落盘失败 run_id=%s: %s", run_id, exc)
        return published

    @staticmethod
    def _scan_workdir(workdir: Path) -> tuple[bool, list[Path]]:
        """同步扫描子任务产物目录（含符号链接排除），供 to_thread 调用。"""
        try:
            if not workdir.is_dir():
                return False, []
            return True, sorted(
                path
                for path in workdir.rglob("*")
                if path.is_file() and not path.is_symlink() and path.name != "result.json"
            )
        except OSError as exc:
            logger.warning("子任务产物目录扫描失败 %s: %s", workdir, exc)
            return False, []

    @staticmethod
    async def _register_artifact_records(
        *,
        path_factory: Any,
        user_id: str,
        directory: str,
        records: list[dict[str, Any]],
    ) -> None:
        """已发布产物登记 file_records（source=CHAT_SANDBOX），供文件中心/下载端点发现。"""
        if not records:
            return
        from uuid import UUID

        from cygnusx.domain.file.value_objects import FileSource
        from cygnusx.infrastructure.storage.file_registry import FileRegistry

        workspace_root = path_factory.workspace_dir(str(user_id))
        try:
            async with get_session_factory()() as session:
                registry = FileRegistry(session)
                for record in records:
                    try:
                        abs_path = (
                            workspace_root
                            / directory.removeprefix("workspace/")
                            / str(record["path"])
                        )
                        await registry.register(
                            UUID(str(user_id)),
                            abs_path,
                            source=FileSource.CHAT_SANDBOX,
                            directory=directory,
                            checksum=record.get("sha256"),
                        )
                    except Exception as exc:  # noqa: BLE001 — 单条登记失败不阻断
                        logger.warning("子任务产物登记失败 %s: %s", record.get("path"), exc)
        except Exception as exc:  # noqa: BLE001 — 登记失败不颠覆发布结果
            logger.warning("子任务产物登记会话失败: %s", exc)

    async def _child_loop(
        self,
        *,
        agent_id: str,
        task: str,
        context_summary: str,
        ctx: Any,
        child_tools: list[dict[str, Any]],
        workspace_access: bool,
        user_id: str,
        parent_session_id: str,
        run_id: str,
        index: int,
        workdir: Path,
        max_rounds: int,
        on_event: Callable[[dict[str, Any]], Awaitable[None] | None] | None,
        control_check: Callable[[], Awaitable[str | None] | str | None] | None,
        approved_tool_calls: list[dict[str, Any]],
        deep_thinking: bool = False,
    ) -> dict[str, Any]:
        """受限 ReAct 循环：chat_service legacy 工具循环的最小克隆。"""
        instruction = f"{context_summary}\n\n{task}".strip() if context_summary else task
        system_prompt = (
            f"{ctx.system_prompt or ''}{_SUBAGENT_RESEARCH_PROMPT_SUFFIX}{SUBAGENT_SYSTEM_SUFFIX}"
        )
        messages: list[dict[str, Any]] = [{"role": "user", "content": instruction}]
        child_session_id = f"{parent_session_id}:child:{run_id}:{index}"
        last_text = ""
        answer_parts: list[str] = []
        reasoning_text = ""
        verified_evidence_refs: list[str] = []
        successful_tool_calls = 0
        tool_call_signatures: list[str] = []
        result_signatures: list[str] = []
        tool_receipts: list[dict[str, Any]] = []
        length_continuations = 0
        empty_response_retries = 0
        usage: dict[str, Any] | None = None
        for _round in range(max(1, max_rounds)):
            round_number = _round + 1
            agentteams_context = agentteams_ctx_var.get()
            agentteams_token = None
            if agentteams_context is not None:
                agentteams_context = {
                    **agentteams_context,
                    "round_number": round_number,
                    "agent_id": agent_id,
                    "call_seq": 1,
                }
                agentteams_token = agentteams_ctx_var.set(agentteams_context)
            await self._check_control(control_check)
            await self._emit_event(
                on_event,
                execution_metadata(
                    "agent_turn_started",
                    session_id=child_session_id,
                    run_id=run_id,
                    agent_id=agent_id,
                    round_number=round_number,
                    execution_path="agentteams_worker_react",
                    index=index,
                )
                | {"type": "agent_turn_started", "index": index},
            )
            text = ""
            round_reasoning_text = ""
            tool_calls: list[dict[str, Any]] = []
            finish_reason = ""
            turn_started = time.monotonic()
            async def recorded_stream():
                try:
                    async for stream_chunk in provider_manager.chat_stream(
                        config=ctx.model_config,
                        messages=messages,
                        system_prompt=system_prompt,
                        temperature=0.3,
                        max_tokens=min(
                            int(getattr(ctx, "max_tokens", 0) or 0)
                            or int(getattr(ctx.model_config, "max_tokens", 0) or 20_000),
                            262_144,
                        ),
                        tools=child_tools or None,
                        deep_thinking=deep_thinking,
                    ):
                        yield stream_chunk
                except Exception as exc:
                    self._record_agentteams_turn(
                        ctx=ctx,
                        child_session_id=child_session_id,
                        messages=messages,
                        system_prompt=system_prompt,
                        output_text=text,
                        reasoning_text=round_reasoning_text,
                        tool_calls=tool_calls,
                        usage=usage,
                        duration_ms=round((time.monotonic() - turn_started) * 1000),
                        finish_reason=finish_reason,
                        status="error",
                        error=str(exc)[:500],
                        deep_thinking=deep_thinking,
                    )
                    if agentteams_token is not None:
                        agentteams_ctx_var.reset(agentteams_token)
                    raise

            async for chunk in recorded_stream():
                if chunk.type == "text":
                    if chunk.metadata.get("is_reasoning"):
                        reasoning_text += chunk.content
                        round_reasoning_text += chunk.content
                        await self._emit_event(
                            on_event,
                            execution_metadata(
                                "agent_reasoning_delta",
                                session_id=child_session_id,
                                run_id=run_id,
                                agent_id=agent_id,
                                round_number=round_number,
                                execution_path="agentteams_worker_react",
                                index=index,
                            )
                            | {
                                "type": "worker_reasoning_delta",
                                "index": index,
                                "content": chunk.content,
                            },
                        )
                        continue
                    text += chunk.content
                    await self._emit_event(
                        on_event,
                        {
                            "type": "worker_text_delta",
                            "index": index,
                            "agent_id": agent_id,
                            "content": chunk.content,
                        },
                    )
                elif chunk.type == "tool_calls":
                    tool_calls = list(chunk.metadata.get("tool_calls", []))
                    for tool_call in tool_calls:
                        function = tool_call.get("function", {}) or {}
                        await self._emit_event(
                            on_event,
                            execution_metadata(
                                "agent_tool_call",
                                session_id=child_session_id,
                                run_id=run_id,
                                agent_id=agent_id,
                                round_number=round_number,
                                execution_path="agentteams_worker_react",
                                index=index,
                                tool_call_id=str(tool_call.get("id") or ""),
                                tool_name=str(function.get("name") or "工具"),
                                args_summary=str(function.get("arguments") or "")[:2_000],
                            )
                            | {"type": "worker_tool_call", "index": index},
                        )
                elif chunk.type == "done":
                    finish_reason = str(chunk.metadata.get("finish_reason") or "").lower()
                    usage = merge_token_usage(usage, chunk.metadata.get("usage"))
                elif chunk.type == "error":
                    self._record_agentteams_turn(
                        ctx=ctx,
                        child_session_id=child_session_id,
                        messages=messages,
                        system_prompt=system_prompt,
                        output_text=text,
                        reasoning_text=round_reasoning_text,
                        tool_calls=tool_calls,
                        usage=usage,
                        duration_ms=round((time.monotonic() - turn_started) * 1000),
                        finish_reason=finish_reason,
                        status="error",
                        error=str(chunk.content or "模型调用失败")[:500],
                    )
                    await self._emit_event(
                        on_event,
                        execution_metadata(
                            "agent_turn_failed",
                            session_id=child_session_id,
                            run_id=run_id,
                            agent_id=agent_id,
                            round_number=round_number,
                            execution_path="agentteams_worker_react",
                            index=index,
                            error=str(chunk.content or "模型调用失败")[:500],
                        )
                        | {"type": "agent_turn_failed", "index": index},
                    )
                    if agentteams_token is not None:
                        agentteams_ctx_var.reset(agentteams_token)
                    return {
                        "status": "failed",
                        "answer": None,
                        "error": str(chunk.content or "模型调用失败")[:500],
                        "tool_receipts": tool_receipts,
                        "usage": usage,
                    }
            self._record_agentteams_turn(
                ctx=ctx,
                child_session_id=child_session_id,
                messages=messages,
                system_prompt=system_prompt,
                output_text=text,
                reasoning_text=round_reasoning_text,
                tool_calls=tool_calls,
                usage=usage,
                duration_ms=round((time.monotonic() - turn_started) * 1000),
                finish_reason=finish_reason,
                status="ok",
                error=None,
                deep_thinking=deep_thinking,
            )
            if agentteams_token is not None:
                agentteams_ctx_var.reset(agentteams_token)
            last_text = text.strip()
            if last_text and (not answer_parts or answer_parts[-1] != last_text):
                answer_parts.append(last_text)
            if not tool_calls:
                if (
                    not last_text
                    and not answer_parts
                    and finish_reason not in {"length", "max_tokens"}
                ):
                    # 模型偶发空响应（仅 reasoning、无正文）：追问重试，兜底报显式失败，
                    # 不让空答复以"成功"姿态进入会诊信封解析。
                    if empty_response_retries < _MAX_EMPTY_RESPONSE_RETRIES:
                        empty_response_retries += 1
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "你的上一段回复没有包含任何正文内容。"
                                    "请直接输出对任务的文字答复，不要留空。"
                                ),
                            }
                        )
                        continue
                    return {
                        "status": "failed",
                        "answer": None,
                        "error": "模型连续返回空内容，请稍后重试",
                        "tool_receipts": tool_receipts,
                        "usage": usage,
                    }
                if (
                    finish_reason in {"length", "max_tokens"}
                    and length_continuations < _MAX_LENGTH_CONTINUATIONS
                ):
                    length_continuations += 1
                    if _has_unfinished_json_fence("\n\n".join(answer_parts)):
                        # 截断发生在 JSON 围栏内：要求只续写 JSON 残片，避免模型
                        # 重开一个新信封导致围栏跨块错配、整段解析降级。
                        continuation_prompt = (
                            "上一段回复因输出长度上限在 JSON 代码块内被截断。"
                            "请从截断处精确续写剩余的 JSON：不要重新开始、不要重复"
                            "已输出内容、不要输出任何解释或额外的标记，只输出 JSON 的"
                            "后续片段，并在结束时补全闭合的 ```。"
                        )
                    else:
                        continuation_prompt = (
                            "上一段因输出长度达到上限而中断。请从中断处继续，"
                            "不要重复已输出内容；保持相同的结构，直到完成当前任务。"
                        )
                    messages.extend(
                        [
                            {"role": "assistant", "content": text},
                            {
                                "role": "user",
                                "content": continuation_prompt,
                            },
                        ]
                    )
                    continue
                final_answer = "\n\n".join(answer_parts).strip()
                await self._emit_event(
                    on_event,
                    execution_metadata(
                        "agent_final_result",
                        session_id=child_session_id,
                        run_id=run_id,
                        agent_id=agent_id,
                        round_number=round_number,
                        execution_path="agentteams_worker_react",
                        index=index,
                        status="completed",
                        tool_call_count=successful_tool_calls,
                    )
                    | {"type": "agent_final_result", "index": index},
                )
                return {
                    "status": "ok",
                    "answer": final_answer[:_ANSWER_CAP_CHARS],
                    "thought": reasoning_text.strip() or None,
                    "error": None,
                    "verified_evidence_refs": verified_evidence_refs,
                    "tool_call_count": successful_tool_calls,
                    "tool_receipts": tool_receipts,
                    "usage": usage,
                }

            messages.append(
                {"role": "assistant", "content": text or None, "tool_calls": tool_calls}
            )
            for tc in tool_calls:
                await self._check_control(control_check)
                fn = tc.get("function", {}) or {}
                tool_name = str(fn.get("name") or "")
                tool_call_id = str(tc.get("id") or "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                args = args if isinstance(args, dict) else {}
                tool_signature = json.dumps(
                    {"tool": tool_name, "args": args},
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
                tool_call_signatures.append(tool_signature)
                if len(tool_call_signatures) >= _MAX_DUPLICATE_TOOL_CALLS and all(
                    signature == tool_call_signatures[-1]
                    for signature in tool_call_signatures[-_MAX_DUPLICATE_TOOL_CALLS :]
                ):
                    reason = "duplicate_tool_call"
                    await self._emit_event(
                        on_event,
                        execution_metadata(
                            "agent_loop_guard_triggered",
                            session_id=child_session_id,
                            run_id=run_id,
                            agent_id=agent_id,
                            round_number=round_number,
                            execution_path="agentteams_worker_react",
                            index=index,
                            reason=reason,
                            tool_name=tool_name,
                            tool_call_id=tool_call_id,
                        )
                        | {"type": "agent_loop_guard_triggered", "index": index},
                    )
                    return {
                        "status": "guarded",
                        "answer": "\n\n".join(answer_parts).strip()[:_ANSWER_CAP_CHARS] or None,
                        "thought": reasoning_text.strip() or None,
                        "error": f"重复调用工具 {tool_name}，已触发运行保护",
                        "verified_evidence_refs": verified_evidence_refs,
                        "tool_call_count": successful_tool_calls,
                        "tool_receipts": tool_receipts,
                        "usage": usage,
                    }
                schema = schema_loader.get_tool(tool_name)
                if tool_name == "ask_user":
                    questions = args.get("questions")
                    if not isinstance(questions, list):
                        questions = [
                            {
                                "question": str(args.get("question") or "请补充必要信息"),
                                "options": args.get("options") or [],
                            }
                        ]
                    return {
                        "status": "awaiting_input",
                        "answer": str(questions[0].get("question") or "请补充必要信息"),
                        "error": None,
                        "tool_receipts": tool_receipts,
                        "usage": usage,
                        "packet": {
                            "status": "awaiting_input",
                            "final_answer": "",
                            "needs_user_input": True,
                            "user_request": str(questions[0].get("question") or "请补充必要信息"),
                            "questions": questions,
                            "approval_requests": [],
                            "error": "",
                        },
                    }
                if schema is not None and schema.requires_confirm:
                    approved = any(
                        isinstance(item, dict)
                        and item.get("tool_name") == tool_name
                        and item.get("arguments") == args
                        for item in approved_tool_calls
                    )
                    if approved:
                        args = {**args, "_confirmed": True}
                    else:
                        return {
                            "status": "approval_pending",
                            "answer": f"需要你批准后才能执行 {tool_name}。",
                            "error": None,
                            "tool_receipts": tool_receipts,
                            "usage": usage,
                            "packet": {
                                "status": "approval_pending",
                                "final_answer": "",
                                "needs_user_input": False,
                                "user_request": "",
                                "questions": [],
                                "approval_requests": [{"tool_name": tool_name, "arguments": args}],
                                "error": "",
                            },
                        }
                tool_started = time.monotonic()
                await self._emit_event(
                    on_event,
                    execution_metadata(
                        "agent_tool_started",
                        session_id=child_session_id,
                        run_id=run_id,
                        agent_id=agent_id,
                        round_number=round_number,
                        execution_path="agentteams_worker_react",
                        index=index,
                        tool_call_id=tool_call_id,
                        tool_name=tool_name,
                    )
                    | {"type": "worker_tool_started", "index": index},
                )
                tool_envelope = await self._execute_child_tool(
                    user_id=user_id,
                    agent_id=agent_id,
                    child_session_id=child_session_id,
                    parent_session_id=parent_session_id,
                    tool_name=tool_name,
                    args=args,
                    workdir=workdir,
                    run_id=run_id,
                    ctx=ctx,
                    workspace_access=workspace_access,
                )
                result_signature = json.dumps(
                    tool_envelope, ensure_ascii=False, sort_keys=True, default=str
                )
                result_signatures.append(result_signature)
                tool_receipts.append(
                    {
                        "tool_name": tool_name,
                        "success": tool_envelope.get("success") is True,
                        "summary": self._tool_result_summary(tool_envelope),
                        "duration_ms": round((time.monotonic() - tool_started) * 1000),
                    }
                )
                await self._emit_event(
                    on_event,
                    execution_metadata(
                        "agent_tool_result",
                        session_id=child_session_id,
                        run_id=run_id,
                        agent_id=agent_id,
                        round_number=round_number,
                        execution_path="agentteams_worker_react",
                        index=index,
                        tool_call_id=tool_call_id,
                        tool_name=tool_name,
                        success=tool_envelope.get("success") is True,
                        duration_ms=round((time.monotonic() - tool_started) * 1000),
                        result_summary=self._tool_result_summary(tool_envelope),
                    )
                    | {"type": "worker_tool_result", "index": index},
                )
                if len(result_signatures) >= _MAX_REPEATED_TOOL_RESULTS and all(
                    signature == result_signatures[-1]
                    for signature in result_signatures[-_MAX_REPEATED_TOOL_RESULTS :]
                ):
                    reason = "no_progress"
                    await self._emit_event(
                        on_event,
                        execution_metadata(
                            "agent_loop_guard_triggered",
                            session_id=child_session_id,
                            run_id=run_id,
                            agent_id=agent_id,
                            round_number=round_number,
                            execution_path="agentteams_worker_react",
                            index=index,
                            reason=reason,
                            tool_name=tool_name,
                            tool_call_id=tool_call_id,
                        )
                        | {"type": "agent_loop_guard_triggered", "index": index},
                    )
                    return {
                        # 保护触发只能表示阶段性结果，不能伪装成可交付完成。
                        "status": "ok",
                        "partial": True,
                        "guard_triggered": True,
                        "answer": (
                            json.dumps(
                                {
                                    "conclusion": (
                                        "\n\n".join(answer_parts).strip()[:_ANSWER_CAP_CHARS]
                                        or f"已获得 {tool_name} 的重复结果，结果未继续变化；"
                                        "已停止重复调用，以下结论基于最近一次工具结果。"
                                    ),
                                    "recommendations": ["基于最近一次工具结果继续分析，不再重复调用。"],
                                    "evidence_refs": [],
                                    "risks": ["工具连续返回相同结果，未继续执行重复调用。"],
                                },
                                ensure_ascii=False,
                            )
                        ),
                        "thought": reasoning_text.strip() or None,
                        "error": None,
                        "verified_evidence_refs": verified_evidence_refs,
                        "tool_call_count": successful_tool_calls,
                        "tool_receipts": tool_receipts,
                        "usage": usage,
                    }
                if tool_envelope.get("success") is True:
                    successful_tool_calls += 1
                    verified_evidence_refs.extend(self._tool_evidence_refs(tool_name, args))
                    verified_evidence_refs = list(dict.fromkeys(verified_evidence_refs))
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(tc.get("id") or ""),
                        "content": json.dumps(tool_envelope, ensure_ascii=False, default=str)[
                            :_TOOL_RESULT_CAP_CHARS
                        ],
                    }
                )
                await self._emit_event(
                    on_event,
                    execution_metadata(
                        "agent_context_reinjected",
                        session_id=child_session_id,
                        run_id=run_id,
                        agent_id=agent_id,
                        round_number=round_number,
                        execution_path="agentteams_worker_react",
                        index=index,
                        tool_call_id=tool_call_id,
                        tool_name=tool_name,
                    )
                    | {"type": "agent_context_reinjected", "index": index},
                )
            await self._emit_event(
                on_event,
                execution_metadata(
                    "agent_turn_continued",
                    session_id=child_session_id,
                    run_id=run_id,
                    agent_id=agent_id,
                    round_number=round_number + 1,
                    execution_path="agentteams_worker_react",
                    index=index,
                    reason="tool_results_reinjected",
                    previous_round=round_number,
                )
                | {"type": "agent_turn_continued", "index": index},
            )
        # 预算耗尽：把最后一段文本作为部分结论返回
        await self._emit_event(
            on_event,
            execution_metadata(
                "agent_loop_guard_triggered",
                session_id=child_session_id,
                run_id=run_id,
                agent_id=agent_id,
                round_number=max(1, max_rounds),
                execution_path="agentteams_worker_react",
                index=index,
                reason="max_rounds",
                max_rounds=max_rounds,
            )
            | {"type": "agent_loop_guard_triggered", "index": index},
        )
        return {
            "status": "budget_exhausted",
            "answer": "\n\n".join(answer_parts).strip()[:_ANSWER_CAP_CHARS] or None,
            "thought": reasoning_text.strip() or None,
            "error": f"子循环超过 {max_rounds} 轮工具上限，返回阶段性结论",
            "verified_evidence_refs": verified_evidence_refs,
            "tool_call_count": successful_tool_calls,
            "tool_receipts": tool_receipts,
            "usage": usage,
        }

    @staticmethod
    def _record_agentteams_turn(
        *,
        ctx: Any,
        child_session_id: str,
        messages: list[dict[str, Any]],
        system_prompt: str,
        output_text: str,
        reasoning_text: str,
        tool_calls: list[dict[str, Any]],
        usage: dict[str, Any] | None,
        duration_ms: int,
        finish_reason: str,
        status: str,
        error: str | None,
        deep_thinking: bool = False,
    ) -> None:
        """Queue AgentTeams-only audit capture; storage errors stay off the model path."""
        uri = AgentTeamsTurnRecorder.schedule(
            messages=[{"role": "system", "content": system_prompt}, *messages],
            output_text=output_text,
            reasoning_text=reasoning_text,
            tool_calls=tool_calls,
            usage=usage,
            duration_ms=duration_ms,
            finish_reason=finish_reason,
            status=status,
            error=error,
            child_session_id=child_session_id,
            provider=str(getattr(ctx.model_config, "name", "")),
            model=str(getattr(ctx.model_config, "model", "")),
            sampling={
                "temperature": 0.3,
                "max_tokens": min(int(getattr(ctx, "max_tokens", 20_000) or 20_000), 20_000),
                "deep_thinking": deep_thinking,
            },
        )
        if not uri:
            return
        try:
            from opentelemetry import trace

            trace.get_current_span().set_attribute("agentteams.turn_record_uri", uri)
        except Exception:  # noqa: BLE001 - tracing must not affect model execution
            return

    @staticmethod
    def _tool_result_summary(tool_envelope: dict[str, Any]) -> str:
        """Return bounded debug context instead of the full raw tool envelope."""
        if tool_envelope.get("success") is not True:
            return str(tool_envelope.get("error") or "工具执行失败")[:500]
        result = tool_envelope.get("result")
        if isinstance(result, dict):
            for key in ("summary", "message", "content", "stdout"):
                value = result.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()[:500]
            return "工具执行成功"
        if isinstance(result, str) and result.strip():
            return result.strip()[:500]
        return "工具执行成功"

    @staticmethod
    def _evaluate_outcome(
        *,
        requires: tuple[str, ...],
        status: str,
        receipts: list[dict[str, Any]],
        blocked_capabilities: tuple[str, ...] = (),
    ) -> dict[str, str | None]:
        """按任务契约与真实工具回执判定业务结果（不靠 LLM 自评）。

        只在任务声明 requires 时调用；返回 outcome_status/reason_code/artifact_status。
        """
        if blocked_capabilities:
            return {
                "outcome_status": "blocked",
                "reason_code": "CAPABILITY_MISSING",
                "artifact_status": "not_created",
            }
        if status in {"failed", "timeout", "paused", "terminated"}:
            reason = {
                "failed": "EXECUTION_FAILED",
                "timeout": "TOOL_TIMEOUT",
            }.get(status, "EXECUTION_CANCELLED")
            return {
                "outcome_status": "failed",
                "reason_code": reason,
                "artifact_status": "not_created",
            }
        if status in {"awaiting_input", "approval_pending"}:
            return {
                "outcome_status": "blocked",
                "reason_code": "AWAITING_USER",
                "artifact_status": "not_created",
            }
        required = set(requires)
        exec_ok = any(
            receipt.get("success") and receipt.get("tool_name") in _EXECUTION_RECEIPT_TOOLS
            for receipt in receipts
        )
        write_ok = any(
            receipt.get("success") and receipt.get("tool_name") in _ARTIFACT_WRITE_RECEIPT_TOOLS
            for receipt in receipts
        )
        publish_ok = any(
            receipt.get("success") and receipt.get("tool_name") in _ARTIFACT_PUBLISH_RECEIPT_TOOLS
            for receipt in receipts
        )
        if CAPABILITY_PYTHON_EXECUTE in required and not exec_ok:
            return {
                "outcome_status": "blocked",
                "reason_code": "EXECUTION_NOT_VERIFIED",
                "artifact_status": "not_created",
            }
        artifact_required = required & {CAPABILITY_ARTIFACT_WRITE, CAPABILITY_ARTIFACT_PUBLISH}
        if artifact_required:
            if not write_ok:
                return {
                    "outcome_status": "blocked",
                    "reason_code": "ARTIFACT_NOT_VERIFIED",
                    "artifact_status": "not_created",
                }
            if CAPABILITY_ARTIFACT_PUBLISH in required and not publish_ok:
                return {
                    "outcome_status": "partial",
                    "reason_code": "ARTIFACT_NOT_PUBLISHED",
                    "artifact_status": "produced",
                }
            return {
                "outcome_status": "succeeded",
                "reason_code": "ARTIFACT_RECEIPT_VERIFIED",
                "artifact_status": "produced",
            }
        if exec_ok:
            return {
                "outcome_status": "succeeded",
                "reason_code": "EXECUTION_RECEIPT_VERIFIED",
                "artifact_status": "not_required",
            }
        if status == "ok":
            return {
                "outcome_status": "answered_unverified",
                "reason_code": "ANSWER_WITHOUT_VERIFIER",
                "artifact_status": "not_required",
            }
        # budget_exhausted / guarded 等阶段性收尾
        return {
            "outcome_status": "partial",
            "reason_code": "RESULT_PARTIAL",
            "artifact_status": "not_required",
        }

    @staticmethod
    def _tool_evidence_refs(tool_name: str, args: dict[str, Any]) -> list[str]:
        if tool_name == "task_result_summary":
            task_id = str(args.get("task_id") or "").strip()
            return [f"task:{task_id}"] if task_id else []
        if tool_name == "task_file_preview":
            task_id = str(args.get("task_id") or "").strip()
            path = str(args.get("path") or "").strip()
            return [
                ref
                for ref in (f"task:{task_id}" if task_id else "", f"file:{path}" if path else "")
                if ref
            ]
        if tool_name == "workspace_file_preview":
            path = str(args.get("path") or "").strip()
            return [f"file:{path}"] if path else []
        if tool_name == "task_compare_metrics":
            return [
                f"task:{task_id}"
                for value in (args.get("task_ids") or [])
                if (task_id := str(value).strip())
            ]
        if tool_name == "rule_threshold_lookup":
            flow_id = str(args.get("flow_id") or "").strip()
            metric = str(args.get("metric_name") or "").strip()
            return [f"rule:{flow_id}:{metric}"] if flow_id and metric else []
        return []

    @staticmethod
    async def _check_control(
        callback: Callable[[], Awaitable[str | None] | str | None] | None,
    ) -> None:
        if callback is None:
            return
        value = callback()
        if hasattr(value, "__await__"):
            value = await value
        if value in {"paused", "terminated"}:
            raise SubagentControlError(str(value))

    @staticmethod
    async def _emit_event(
        callback: Callable[[dict[str, Any]], Awaitable[None] | None] | None,
        event: dict[str, Any],
    ) -> None:
        if callback is None:
            return
        result = callback(event)
        if hasattr(result, "__await__"):
            await result

    @staticmethod
    async def _execute_child_tool(
        *,
        user_id: str,
        agent_id: str,
        child_session_id: str,
        tool_name: str,
        args: dict[str, Any],
        workdir: Path,
        run_id: str,
        ctx: Any,
        parent_session_id: str | None = None,
        workspace_access: bool = False,
    ) -> dict[str, Any]:
        """C1：每次工具执行独占会话；builtin、MCP、搜索和技能统一分发。"""
        from cygnusx.application.services.artifact_manifest import normalize_tool_artifact_payload
        from cygnusx.application.services.tool_bridge_service import get_tool_bridge_service
        from cygnusx.infrastructure.mcp.client import MCPClient
        from cygnusx.infrastructure.skills import skill_store

        async with get_session_factory()() as session:
            try:
                if workspace_access and tool_name in _OVERDRIVE_WORKSPACE_TOOL_NAMES:
                    # Gap 3 挂载断裂修复：沙盒类工具进入 Studio 会话沙盒前，
                    # 把分配的宿主 workdir 注册进容器挂载（/workspace/workdir），
                    # 使提示词承诺的工作目录在容器内真实可见、可写。
                    # 必须在首次 ensure_running 之前注册（mount 创建后不可变，
                    # 旧容器缺挂载时由 manager 复用校验触发重建）。
                    from cygnusx.infrastructure.studio.manager import studio_sandbox_manager

                    studio_sandbox_manager.register_workdir_mount(
                        parent_session_id or child_session_id, workdir
                    )
                    return await execute_studio_tool(
                        tool_name,
                        args,
                        parent_session_id or child_session_id,
                        user_id=user_id,
                        db=session,
                    )
                tool_context = ToolInvocationContext(
                    user_id=user_id,
                    agent_id=agent_id,
                    session_id=child_session_id,
                    db=session,
                    extra={
                        "subagent_workdir": str(workdir),
                        "fanout_run_id": run_id,
                        "subagent_depth": 1,
                        "room_id": str((agentteams_ctx_var.get() or {}).get("room_id") or ""),
                    },
                )
                if tool_name == "knowledge_search":
                    result = await _knowledge_search(
                        args,
                        session,
                        project_id=getattr(getattr(ctx, "agent", None), "project_id", None),
                    )
                elif tool_name == "web_search":
                    from cygnusx.application.services.search_provider_service import (
                        SearchProviderService,
                    )

                    query = str(args.get("query") or "").strip()
                    top_n = max(1, min(int(args.get("top_n") or 5), 20))
                    if not query:
                        result = {"success": False, "error": "缺少搜索关键词"}
                    else:
                        rows = await SearchProviderService(session).search_default(query, top_n)
                        result = {"success": True, "result": {"query": query, "results": rows}}
                elif tool_name in SKILL_TOOL_NAMES:
                    skill_key = str(args.get("skill_id") or args.get("name") or "").strip()
                    skills = list(getattr(ctx, "skills", []) or [])
                    skill = next(
                        (
                            item
                            for item in skills
                            if item.skill_id == skill_key or item.name == skill_key
                        ),
                        None,
                    )
                    if skill is None:
                        result = {"success": False, "error": f"技能 '{skill_key}' 未挂载到该 Agent"}
                    elif tool_name == USE_SKILL_TOOL_NAME:
                        body = skill_store.read_skill_body(skill.skill_id) or (skill.prompt or "")
                        result = {
                            "success": bool(body.strip()),
                            "result": {
                                "skill_id": skill.skill_id,
                                "name": skill.name,
                                "instructions": body,
                                "resources": skill_store.list_skill_files(skill.skill_id) or None,
                            },
                        }
                    else:
                        path = str(args.get("path") or "").strip()
                        ok, message, content = skill_store.read_skill_resource(skill.skill_id, path)
                        result = (
                            {
                                "success": True,
                                "result": {"path": path, "content": content.decode("utf-8")},
                            }
                            if ok and content is not None
                            else {"success": False, "error": message}
                        )
                else:
                    server = next(
                        (
                            candidate
                            for candidate in (getattr(ctx, "mcp_servers", []) or [])
                            if any(
                                str(tool.tool_name) == tool_name
                                for tool in (getattr(candidate, "tools", []) or [])
                            )
                        ),
                        None,
                    )
                    if server is not None:
                        result = await MCPClient().call_tool(
                            server, tool_name, args, user_id=user_id, context=tool_context
                        )
                    else:
                        result = await get_tool_bridge_service().execute(
                            user_id=user_id,
                            tool_name=tool_name,
                            arguments=args,
                            context=tool_context,
                        )
                # Worker tools share the same artifact contract as foreground
                # chat tools; normalize before the result is reinjected into the
                # child model so no Agent has a private output shape.
                tool_output = result.get("result") if isinstance(result, dict) else result
                if isinstance(tool_output, dict) and (
                    "llm_payload" in tool_output or "ui_payload" in tool_output
                ):
                    llm_payload = tool_output.get("llm_payload", tool_output)
                    ui_payload = tool_output.get("ui_payload")
                else:
                    llm_payload = tool_output if isinstance(tool_output, dict) else {"result": tool_output}
                    ui_payload = None
                normalized_llm, normalized_ui = normalize_tool_artifact_payload(
                    llm_payload,
                    ui_payload,
                    tool_name=tool_name,
                )
                if isinstance(result, dict):
                    result["result"] = {
                        "llm_payload": normalized_llm,
                        "ui_payload": normalized_ui,
                    }
                await session.commit()
                return result
            except Exception as exc:  # noqa: BLE001 — 工具失败回灌模型自行决策
                await session.rollback()
                return {"success": False, "error": f"工具 {tool_name} 执行失败：{exc}"}

    # --- 视图与信封 ---

    @staticmethod
    def _llm_view(item: dict[str, Any]) -> dict[str, Any]:
        view: dict[str, Any] = {
            "index": item["index"],
            "task_id": item.get("task_id", ""),
            "agent_id": item["agent_id"],
            "status": item["status"],
            "answer": item.get("answer"),
            "thought": item.get("thought"),
            "elapsed_s": item["elapsed_s"],
            "packet": item.get("packet") or {},
            "verified_evidence_refs": item.get("verified_evidence_refs") or [],
        }
        # 契约化任务（声明 requires）附带的验收判定与工具回执，随旧字段一并透传；
        # detail_ref 为正文落盘引用（长正文才有）
        for key in (
            "outcome_status",
            "reason_code",
            "artifact_status",
            "capabilities_required",
            "capabilities_granted",
            "tool_receipts",
            "detail_ref",
            "artifacts",
        ):
            if key in item:
                view[key] = item[key]
        if item.get("partial"):
            view["partial"] = True
        if item.get("guard_triggered"):
            view["guard_triggered"] = True
        if item.get("error"):
            view["error"] = item["error"]
        if item.get("workdir"):
            view["workdir"] = item["workdir"]
        return view

    @staticmethod
    def _error(message: str, *, code: str = "SUBAGENT_ERROR") -> dict[str, Any]:
        return {
            "success": False,
            "llm_payload": {"success": False, "error": message, "code": code},
            "ui_payload": {"error": message, "code": code},
        }
