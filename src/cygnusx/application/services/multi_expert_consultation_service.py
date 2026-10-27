"""受开关控制的只读多专家并行会诊。"""

from __future__ import annotations

import asyncio
from typing import Any

from cygnusx.application.services.agent_context_builder import AgentContextBuilder
from cygnusx.infrastructure.ai_provider.openai_compatible import provider_manager


class MultiExpertConsultationService:
    """并行收集专家意见；任一专家失败不影响其余意见或主链路回答。"""

    def __init__(
        self,
        agent_service: Any,
        context_builder: AgentContextBuilder | None = None,
    ) -> None:
        self._agent_service = agent_service
        # 显式注入的 builder（测试桩等）原样使用；生产默认 None，
        # collect 时为每位专家开独立 DB 会话装配（见 collect 注释）。
        self._explicit_builder = context_builder

    async def collect(
        self, agent_ids: list[str], user_text: str, user_id: str | None = None
    ) -> list[dict[str, str]]:
        if self._explicit_builder is not None:
            return await self._collect_with_builder(
                self._explicit_builder, agent_ids, user_text, user_id
            )

        # 每位专家使用独立 DB 会话：assemble 内部走 AgentService.assemble_context，
        # 多专家共享同一 AsyncSession 并发查询会被 SQLAlchemy 拒绝
        # （InvalidRequestError: concurrent operations are not permitted），
        # 异常又被 return_exceptions 静默丢弃，导致会诊意见悄悄缺失。
        from cygnusx.application.services.agent_service import AgentService
        from cygnusx.infrastructure.database.session import get_session_factory

        async def _run_one(agent_id: str) -> dict[str, str] | None:
            async with get_session_factory()() as session:
                builder = AgentContextBuilder(session, AgentService(session))
                context = await builder.assemble(
                    agent_id,
                    user_id or "",
                    user_message=user_text,
                    mode="consultation",
                )
                if context is None:
                    return None
                return await self._collect_one(context, user_text)

        results = await asyncio.gather(
            *(_run_one(agent_id) for agent_id in agent_ids),
            return_exceptions=True,
        )
        return [result for result in results if isinstance(result, dict)]

    async def _collect_with_builder(
        self,
        builder: AgentContextBuilder,
        agent_ids: list[str],
        user_text: str,
        user_id: str | None,
    ) -> list[dict[str, str]]:
        contexts = await asyncio.gather(
            *(
                builder.assemble(
                    agent_id,
                    user_id or "",
                    user_message=user_text,
                    mode="consultation",
                )
                for agent_id in agent_ids
            ),
            return_exceptions=True,
        )
        tasks = [
            self._collect_one(context, user_text)
            for context in contexts
            if not isinstance(context, Exception) and context is not None
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [result for result in results if isinstance(result, dict)]

    @staticmethod
    async def _collect_one(context: Any, user_text: str) -> dict[str, str] | None:
        model_config = getattr(context, "model_config", None)
        agent = getattr(context, "agent", None)
        if model_config is None or agent is None:
            return None
        text = ""
        try:
            async for chunk in provider_manager.chat_stream(
                config=model_config,
                messages=[{"role": "user", "content": user_text}],
                system_prompt=(
                    f"{getattr(context, 'system_prompt', '')}\n\n"
                    "你正在参与多专家会诊。仅从自己的专业角度给主助手一份简洁、"
                    "可核验的建议；不要调用工具、不要向用户承诺执行任务，控制在 300 字内。"
                ),
                temperature=0.2,
                max_tokens=400,
                tools=None,
                deep_thinking=False,
            ):
                if chunk.type == "text":
                    text += chunk.content
        except Exception:
            return None
        text = text.strip()
        if not text:
            return None
        return {
            "agent_id": str(getattr(agent, "agent_id", "")),
            "name": str(getattr(agent, "name", "专家")),
            "opinion": text[:1200],
        }

    @staticmethod
    def render_prompt_context(opinions: list[dict[str, str]]) -> str:
        if not opinions:
            return ""
        lines = ["## 多专家会诊意见（仅供综合，需自行核验）"]
        lines.extend(f"- {item['name']}：{item['opinion']}" for item in opinions)
        return "\n".join(lines)

    @staticmethod
    def summarize(opinions: list[dict[str, str]]) -> str:
        """Return a conclusion-only handoff summary safe to prefill into a Case."""
        if not opinions:
            return ""
        lines = ["会诊纪要（仅含专家结论，不含原始工具轨迹）："]
        lines.extend(f"- {item['name']}：{item['opinion'][:360]}" for item in opinions)
        return "\n".join(lines)[:1800]
