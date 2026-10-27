"""Restricted system-agent adapter over the existing LangGraph execution runtime."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import aclosing
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from cygnusx.application.services.ai_provider_service import AIProviderConfigService
from cygnusx.application.services.welcome.validation import APPROVED_FACTS, Audience
from cygnusx.core.config import get_settings
from cygnusx.infrastructure.ai_provider.openai_compatible import (
    ChatChunk,
    merge_token_usage,
    provider_manager,
)
from cygnusx.infrastructure.config.agent_loader import load_system_agent_configs
from cygnusx.infrastructure.database.session import get_session_factory
from cygnusx.infrastructure.execution.langgraph_nodes import NodeDeps
from cygnusx.infrastructure.execution.langgraph_runtime import LangGraphRuntimeService


@dataclass
class AgentResult:
    text: str
    metadata: dict[str, Any]


class WelcomeAgentError(RuntimeError):
    def __init__(self, code: str, metadata: dict[str, Any]) -> None:
        super().__init__(code)
        self.metadata = metadata


class WelcomeAgentAdapter:
    def __init__(self) -> None:
        configs = load_system_agent_configs()
        self.config = next(c for c in configs if c["agent_id"] == "welcome_copywriter")
        if any(self.config.get(k) for k in ("tools", "mcp_ids", "skill_ids")):
            raise ValueError("Welcome agent must have no tools, MCP or skills")
        self.system = str(self.config["system_prompt"])
        self.prompt_version = str(self.config["features"]["prompt_version"])
        path = (
            Path(get_settings().site_content_yaml).parent
            / f"ai/prompts/welcome/user_batch.{self.prompt_version}.md"
        )
        self.user_template = path.read_text(encoding="utf-8")
        self.prompt_hash = hashlib.sha256(
            (
                self.system
                + self.user_template
                + json.dumps(APPROVED_FACTS, ensure_ascii=False, sort_keys=True)
            ).encode()
        ).hexdigest()

    async def generate(
        self,
        *,
        audience: Audience,
        target_week: date,
        count: int,
        recent: list[str],
        run_id: UUID,
        focus_round: int = 0,
    ) -> AgentResult:
        settings = get_settings()
        # Close the read transaction before inference. No user/knowledge/session assembly.
        async with get_session_factory()() as db:
            model = await AIProviderConfigService(db).get_active_default()
        if model is None:
            raise RuntimeError("welcome_provider_unavailable")
        prompt = self.user_template + json.dumps(
            {
                "week_start": target_week.isoformat(),
                "audience": audience,
                "locale": "zh-CN",
                "count": min(count, 8),
                "approved_platform_facts": APPROVED_FACTS,
                "creative_directions": self.config["creative_directions"][
                    focus_round % len(self.config["creative_directions"])
                ],
                "recent_examples": recent[-96:],
            },
            ensure_ascii=False,
        )
        attempts: list[dict[str, Any]] = []

        async def audited_stream(**kwargs: Any) -> AsyncIterator[ChatChunk]:
            async for chunk in provider_manager.chat_stream(
                **kwargs, on_attempt_usage=attempts.append
            ):
                yield chunk

        runtime = LangGraphRuntimeService(
            NodeDeps(
                model_config=model,
                system_prompt=self.system,
                temperature=float(self.config["temperature"]),
                max_tokens=min(int(self.config["max_tokens"]), settings.welcome_max_output_tokens),
                chat_stream=audited_stream,
                tools=None,
                tool_executor=None,
                prepare_messages=None,
                run_id=str(run_id),
                agent_id="welcome_copywriter",
                execution_path="welcome_system_langgraph",
                emit_execution_events=True,
            ),
            max_rounds=1,
        )
        content = ""
        error_code: str | None = None
        try:
            async with asyncio.timeout(settings.welcome_timeout_seconds):
                async with aclosing(
                    cast(
                        AsyncGenerator[ChatChunk, None],
                        runtime.stream([{"role": "user", "content": prompt}]),
                    )
                ) as chunks:
                    async for chunk in chunks:
                        if chunk.type in {"error", "tool_call", "tool_result"}:
                            error_code = "welcome_agent_execution_failed"
                        if chunk.type == "text" and not chunk.metadata.get("is_reasoning"):
                            if len(content) + len(chunk.content) > 20000:
                                error_code = "welcome_output_budget_exceeded"
                            else:
                                content += chunk.content
            if runtime.error or any(m.get("tool_calls") for m in runtime.last_messages):
                error_code = "welcome_agent_execution_failed"
        except Exception as exc:
            error_code = type(exc).__name__
        usage = runtime.last_usage
        if attempts:
            usage = None
            for attempt in attempts:
                usage = merge_token_usage(usage, attempt.get("usage"))
        price_in = model.input_price if model.input_price is not None else model.cost_per_1m_in
        price_out = model.output_price if model.output_price is not None else model.cost_per_1m_out
        cost = (
            (
                int(usage.get("prompt_tokens", 0)) * price_in
                + int(usage.get("completion_tokens", 0)) * price_out
            )
            / 1_000_000
            if usage is not None and price_in is not None and price_out is not None
            else None
        )
        metadata = {
            "agent_run_id": str(run_id),
            "prompt_version": self.prompt_version,
            "prompt_sha256": self.prompt_hash,
            "model_provider": model.provider_type.value,
            "model_id": model.model,
            "model_config_id": str(model.id),
            "usage": usage or {},
            "usage_complete": usage is not None and error_code != "TimeoutError",
            "provider_attempts": attempts,
            "estimated_cost_cny": cost,
            "request_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        }
        if error_code:
            raise WelcomeAgentError(error_code, metadata)
        return AgentResult(content, metadata)
