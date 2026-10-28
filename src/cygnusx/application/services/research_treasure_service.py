"""平台身份边界内的科研寻宝鼠适配服务。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, ClassVar, cast

import httpx
from loguru import logger
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cygnusx.application.schemas.chat import ChatMessageDTO, ChatSessionDTO
from cygnusx.application.schemas.research_agent import DiscoveryProposal, ResearchAgentCapabilities
from cygnusx.application.services.chat.session_service import SessionService
from cygnusx.core.config import Settings, get_settings
from cygnusx.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    CygnusXError,
    DependencyUnavailableError,
    NotFoundError,
)
from cygnusx.infrastructure.database.models.ai_provider import AIProviderConfigModel
from cygnusx.infrastructure.database.models.chat import (
    ChatMessageEventModel,
    ChatMessageModel,
    ChatSessionModel,
)
from cygnusx.infrastructure.database.models.project import ProjectModel
from cygnusx.infrastructure.database.models.user import UserModel
from cygnusx.infrastructure.database.session import get_session_factory

RESEARCH_AGENT_MARKER = "research-treasure-mouse"
ACCESSION_RE = re.compile(
    r"^(?:GSE|GSM|GPL|SRP|SRA|SRR|ERR|DRR|PRJ(?:NA|EB|DB|CA)|PMID)\d+[A-Z0-9.-]*$",
    re.I,
)


def _source_link(accession: str | None) -> str | None:
    """Only create links for known accession families; never trust an upstream URL."""
    if not accession or not ACCESSION_RE.fullmatch(accession.strip()):
        return None
    value = accession.strip().upper()
    if value.startswith(("GSE", "GSM", "GPL", "SRP", "SRA", "SRR", "ERR", "DRR", "PRJ")):
        return f"https://www.ncbi.nlm.nih.gov/bioproject/?term={value}"
    if value.startswith("PMID"):
        return f"https://pubmed.ncbi.nlm.nih.gov/{value[4:]}"
    return None


def card_to_proposal(
    card: dict[str, Any], *, session_id: str, project_id: str | None
) -> DiscoveryProposal:
    """Map the legacy DatasetCard without upgrading it into a platform asset."""
    accession = str(card.get("accession") or "").strip() or None
    raw_meta = card.get("meta")
    meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
    link = _source_link(accession)
    proposal_id = f"{session_id}:{accession or uuid.uuid4().hex}"
    return DiscoveryProposal(
        proposal_id=proposal_id,
        source=str(card.get("tool") or "unknown")[:64],
        accession=accession,
        title=str(card.get("title") or "")[:1000],
        summary=str(card.get("summary") or "")[:5000],
        organism=str(meta.get("organism"))[:256] if meta.get("organism") else None,
        assay_type=str(meta.get("assay"))[:256] if meta.get("assay") else None,
        sample_count=(
            int(meta["sample_count"])
            if str(meta.get("sample_count", "")).isdigit()
            else None
        ),
        metadata_status="unverified",
        source_links=[link] if link else [],
        evidence_refs=[accession] if accession else [],
        retrieved_at=datetime.now(UTC),
        project_id=project_id,
        conversation_id=session_id,
        provenance={
            "agent": RESEARCH_AGENT_MARKER,
            "tool_name": str(card.get("tool") or "")[:128] or None,
            "verification_level": "source_not_verified",
        },
    )


def merge_discovery_cards(
    previous: list[dict[str, Any]], incoming: list[Any],
) -> list[dict[str, Any]]:
    """Keep source metadata while collapsing cards repeated in the terminal snapshot."""
    result: dict[str, dict[str, Any]] = {}
    for card in [*previous, *incoming]:
        if not isinstance(card, dict):
            continue
        raw_meta = card.get("meta")
        meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
        key = json.dumps([meta.get("source"), meta.get("literature_source"),
                          card.get("accession") or meta.get("doi") or meta.get("pmid")
                          or card.get("title") or json.dumps(card, sort_keys=True, default=str)], default=str)
        old = result.get(key, {})
        result[key] = {**old, **card, "meta": {**old.get("meta", {}), **meta}}
    return list(result.values())


class TreasureAgentAdapter:
    """Server-to-server bridge to the existing Node/TS agent runtime."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def literature(self, *, kind: str, identifier: str, principal_id: str) -> dict[str, Any]:
        if not self._settings.treasure_agent_url or not self._settings.treasure_agent_internal_token:
            raise DependencyUnavailableError("科研寻宝鼠受信 Agent 未配置")
        try:
            async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                response = await client.post(
                    self._settings.treasure_agent_url.rstrip("/") + "/cygnusx/discovery",
                    headers={
                        "X-CygnusX-Internal-Token": self._settings.treasure_agent_internal_token,
                        "X-CygnusX-Principal": principal_id,
                    },
                    json={"action": "literature", "kind": kind, "id": identifier},
                )
                response.raise_for_status()
                result = response.json()
                if not isinstance(result, dict) or result.get("status") not in {"ok", "not_found"}:
                    raise ValueError("invalid literature response")
                return cast(dict[str, Any], result)
        except (httpx.HTTPError, ValueError) as exc:
            raise DependencyUnavailableError("文献详情服务暂不可用") from exc

    async def stream(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        lang: str,
        cancel_event: asyncio.Event,
        principal_id: str,
        project_id: str | None,
        session_id: str,
        platform_tools: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        url = self._settings.treasure_agent_url.rstrip("/") + "/cygnusx/discovery"
        if (
            not self._settings.treasure_agent_url
            or not self._settings.treasure_agent_internal_token
        ):
            raise DependencyUnavailableError("科研寻宝鼠受信 Agent 未配置")
        headers = {
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "X-CygnusX-Internal-Token": self._settings.treasure_agent_internal_token,
            "X-CygnusX-Principal": principal_id,
            "X-CygnusX-Project": project_id or "",
            "X-CygnusX-Session": session_id,
        }
        payload = {"messages": messages[-16:], "model": model, "stream": True, "lang": lang}
        if platform_tools:
            payload["platform_tools"] = platform_tools
        try:
            async with (
                httpx.AsyncClient(
                    timeout=httpx.Timeout(self._settings.treasure_agent_timeout_seconds),
                    trust_env=False,
                ) as client,
                client.stream("POST", url, headers=headers, json=payload) as response,
            ):
                    if response.status_code >= 400:
                        raise DependencyUnavailableError(
                            f"科研寻宝鼠 Agent 返回 HTTP {response.status_code}"
                        )
                    async for line in response.aiter_lines():
                        if cancel_event.is_set():
                            return
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            return
                        try:
                            parsed = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(parsed, dict):
                            yield parsed
        except httpx.HTTPError as exc:
            raise DependencyUnavailableError("科研寻宝鼠 Agent 连接失败") from exc


class ResearchTreasureService:
    _active_cancels: ClassVar[dict[str, set[asyncio.Event]]] = {}
    _generation_tasks: ClassVar[dict[tuple[str, uuid.UUID], asyncio.Task[None]]] = {}
    _generation_ready: ClassVar[dict[tuple[str, uuid.UUID], asyncio.Event]] = {}

    def __init__(self, db: AsyncSession, *, adapter: TreasureAgentAdapter | None = None) -> None:
        self._db = db
        self._sessions = SessionService(db)
        self._adapter = adapter or TreasureAgentAdapter()

    @staticmethod
    def ensure_enabled() -> None:
        if not get_settings().treasure_native_ui_enabled:
            raise AuthorizationError("科研寻宝鼠原生入口尚未在当前环境启用", code="FEATURE_DISABLED")

    @staticmethod
    def _request_fingerprint(content: str, model_id: uuid.UUID | None, lang: str) -> str:
        canonical = json.dumps(
            {"content": content, "model_id": str(model_id) if model_id else None, "lang": lang},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _ensure_same_request(
        user_message: ChatMessageModel | None, fingerprint: str,
    ) -> None:
        if user_message is not None and user_message.metadata_json.get(
            "research_request_fingerprint"
        ) != fingerprint:
            raise ConflictError(
                "请求 ID 已绑定到其他科研发现请求",
                code="IDEMPOTENCY_KEY_REUSED",
            )

    async def _current_user(self, user_id: str) -> UserModel:
        # Re-read even in a long-lived SQLAlchemy identity map after access revocation.
        user = await self._db.get(UserModel, uuid.UUID(user_id), populate_existing=True)
        if user is None or user.status != "active":
            raise AuthenticationError("用户不存在或已被禁用")
        return user

    async def capabilities(self, user_id: str) -> ResearchAgentCapabilities:
        user = await self._current_user(user_id)
        denied = set(user.disabled_modules or []) if user.role != "admin" else set()
        settings = get_settings()
        allowed = "treasure-mouse" not in denied
        enabled = allowed and settings.treasure_native_ui_enabled
        discovery = enabled and bool(
            settings.treasure_agent_url and settings.treasure_agent_internal_token
        )
        prepare = enabled and settings.tool_gateway_read_enabled
        dataset = prepare and settings.dataset_discovery_readonly and "files" not in denied
        reason = (
            "MODULE_LOCKED" if not allowed else
            "FEATURE_DISABLED" if not enabled else
            "NODE_NOT_CONFIGURED" if not discovery else None
        )
        return ResearchAgentCapabilities(
            native_ui_enabled=settings.treasure_native_ui_enabled,
            enabled=enabled,
            read_sessions=enabled,
            read_discovery=discovery,
            prepare_import=dataset and "downloads" not in denied,
            prepare_analysis=dataset and "flows" not in denied,
            reason_code=reason,
        )

    async def ensure_access(self, user_id: str) -> None:
        user = await self._current_user(user_id)
        if user.role != "admin" and "treasure-mouse" in (user.disabled_modules or []):
            raise AuthorizationError("寻宝鼠模块未开通，请联系管理员", code="MODULE_LOCKED")
        self.ensure_enabled()

    async def _owned_project(self, user_id: str, project_id: str | None) -> None:
        if not project_id:
            return
        try:
            project_uuid = uuid.UUID(project_id)
        except ValueError as exc:
            raise NotFoundError("项目不存在") from exc
        result = await self._db.execute(
            select(ProjectModel.id).where(
                ProjectModel.id == project_uuid,
                ProjectModel.user_id == uuid.UUID(user_id),
            )
        )
        if result.scalar_one_or_none() is None:
            raise AuthorizationError("无权访问该项目", code="PROJECT_FORBIDDEN")

    async def _provider(self, model_id: uuid.UUID | None) -> AIProviderConfigModel:
        query = select(AIProviderConfigModel).where(AIProviderConfigModel.is_active.is_(True))
        if model_id:
            query = query.where(AIProviderConfigModel.id == model_id)
        else:
            query = query.order_by(
                desc(AIProviderConfigModel.is_default),
                desc(AIProviderConfigModel.updated_at),
            )
        result = await self._db.execute(query.limit(1))
        provider = result.scalar_one_or_none()
        if provider is None:
            raise DependencyUnavailableError("平台没有可用的 AI 模型配置", code="PROVIDER_UNAVAILABLE")
        return provider

    async def create_session(
        self, user_id: str, project_id: str | None, title: str, model_id: uuid.UUID | None
    ) -> Any:
        await self.ensure_access(user_id)
        await self._owned_project(user_id, project_id)
        provider = await self._provider(model_id)
        # Research discovery explicitly permits a global read-only session. Do not
        # inherit Chat's convenience default-project behavior for this surface.
        session = ChatSessionModel(
            id=uuid.uuid4(),
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            model_id=provider.id,
            title=title.strip() or "新对话",
            status="active",
            mode="chat",
            sandbox_meta={
                "research_agent": RESEARCH_AGENT_MARKER,
                "legacy_history": "not_migrated",
            },
            project_id=project_id,
        )
        # Unlike normal Chat, a global discovery session must never create or
        # inherit a default project as a side effect.
        self._db.add(session)
        await self._db.flush()
        return ChatSessionDTO.model_validate(session)

    async def list_sessions(self, user_id: str, project_id: str | None) -> list[Any]:
        await self.ensure_access(user_id)
        await self._owned_project(user_id, project_id)
        query = select(ChatSessionModel).where(
            ChatSessionModel.user_id == user_id,
            ChatSessionModel.status == "active",
            ChatSessionModel.sandbox_meta["research_agent"].as_string() == RESEARCH_AGENT_MARKER,
        ).order_by(desc(ChatSessionModel.updated_at)).limit(200)
        if project_id:
            query = query.where(ChatSessionModel.project_id == project_id)
        else:
            query = query.where(ChatSessionModel.project_id.is_(None))
        result = await self._db.execute(query)
        return [ChatSessionDTO.model_validate(session) for session in result.scalars().all()]

    async def _owned_session(self, user_id: str, session_id: str) -> ChatSessionModel:
        await self.ensure_access(user_id)
        result = await self._db.execute(select(ChatSessionModel).where(
            ChatSessionModel.session_id == session_id,
            ChatSessionModel.user_id == user_id,
            ChatSessionModel.status == "active",
            ChatSessionModel.sandbox_meta["research_agent"].as_string() == RESEARCH_AGENT_MARKER,
        ))
        session = result.scalar_one_or_none()
        if session is None:
            raise NotFoundError("科研发现会话不存在或无权访问")
        await self._owned_project(user_id, session.project_id)
        return session

    async def messages(self, user_id: str, session_id: str) -> list[Any]:
        await self._owned_session(user_id, session_id)
        rows = cast(list[ChatMessageModel], await self._sessions.get_messages(session_id))
        return [ChatMessageDTO.model_validate(row) for row in rows]

    async def update_session(
        self, user_id: str, session_id: str, *, title: str | None, status: str | None,
    ) -> Any:
        session = await self._owned_session(user_id, session_id)
        if title is not None:
            session.title = title.strip() or session.title
            session.title_locked = True
        if status == "archived":
            session.status = "archived"
        await self._db.flush()
        return ChatSessionDTO.model_validate(session)

    async def literature(
        self, user_id: str, session_id: str, kind: str, identifier: str,
    ) -> dict[str, Any]:
        await self._owned_session(user_id, session_id)
        return await self._adapter.literature(
            kind=kind, identifier=identifier, principal_id=user_id,
        )

    async def _generation_messages(
        self, session_id: str, request_id: uuid.UUID,
    ) -> tuple[ChatMessageModel | None, ChatMessageModel | None]:
        result = await self._db.execute(
            select(ChatMessageModel).where(
                ChatMessageModel.session_id == session_id,
                ChatMessageModel.metadata_json["research_request_id"].as_string() == str(request_id),
            )
        )
        rows = list(result.scalars().all())
        user_message = next((row for row in rows if row.role == "user"), None)
        assistant_message = next((row for row in rows if row.role == "assistant"), None)
        return user_message, assistant_message

    async def check_stream_access(
        self, user_id: str, session_id: str, model_id: uuid.UUID | None,
        request_id: uuid.UUID, content: str, lang: str,
    ) -> None:
        session = await self._owned_session(user_id, session_id)
        user_message, assistant = await self._generation_messages(session_id, request_id)
        if assistant is None:
            await self._provider(model_id or session.model_id)
        else:
            self._ensure_same_request(
                user_message, self._request_fingerprint(content, model_id, lang)
            )

    async def ensure_generation_running(
        self,
        user_id: str,
        session_id: str,
        content: str,
        model_id: uuid.UUID | None,
        lang: str,
        request_id: uuid.UUID,
    ) -> None:
        """Start a durable producer outside the SSE response's cancellation scope."""
        session = await self._owned_session(user_id, session_id)
        fingerprint = self._request_fingerprint(content, model_id, lang)
        user_message, assistant_message = await self._generation_messages(session_id, request_id)
        if assistant_message is not None:
            self._ensure_same_request(user_message, fingerprint)
            if assistant_message.status != "streaming":
                return
        else:
            await self._provider(model_id or session.model_id)

        key = (session_id, request_id)
        task = self._generation_tasks.get(key)
        ready = self._generation_ready.get(key)
        if task is not None and not task.done():
            if ready is not None:
                await asyncio.wait_for(ready.wait(), timeout=10)
            return
        if assistant_message is not None:
            # Another web process owns this already-persisted generation.
            return

        ready = asyncio.Event()
        failures: list[Exception] = []

        async def produce() -> None:
            try:
                factory = get_session_factory()
                async with factory() as worker_db:
                    worker = ResearchTreasureService(worker_db, adapter=self._adapter)
                    async for _ in worker.stream_message(
                        user_id,
                        session_id,
                        content,
                        model_id,
                        lang,
                        request_id,
                        ready_event=ready,
                    ):
                        pass
            except Exception as exc:
                failures.append(exc)
                logger.warning("Research generation producer failed: {}", type(exc).__name__)
            finally:
                ready.set()
                self._generation_ready.pop(key, None)
                self._generation_tasks.pop(key, None)

        self._generation_ready[key] = ready
        # The request session has only performed access/read checks here.
        await self._db.rollback()
        task = asyncio.create_task(produce(), name=f"research-generation-{request_id}")
        self._generation_tasks[key] = task
        try:
            await asyncio.wait_for(ready.wait(), timeout=10)
        except TimeoutError as exc:
            raise DependencyUnavailableError(
                "科研发现任务未能及时建立持久会话", code="RESEARCH_STREAM_START_TIMEOUT"
            ) from exc
        if failures:
            raise DependencyUnavailableError(
                "科研发现任务无法启动", code="RESEARCH_STREAM_START_FAILED"
            ) from failures[0]
        _, assistant_message = await self._generation_messages(session_id, request_id)
        if assistant_message is None:
            raise DependencyUnavailableError(
                "科研发现任务未建立持久会话", code="RESEARCH_STREAM_START_FAILED"
            )

    async def cancel(self, user_id: str, session_id: str) -> str:
        await self._owned_session(user_id, session_id)
        events = self._active_cancels.get(session_id)
        if events:
            for event in events:
                event.set()
            return "accepted"

        # Persist the request so a producer owned by another web process can see
        # it on its next event.  A missing row remains unknown; no status is
        # changed here because the producer must publish the terminal event.
        result = await self._db.execute(
            select(ChatMessageModel)
            .where(
                ChatMessageModel.session_id == session_id,
                ChatMessageModel.role == "assistant",
                ChatMessageModel.status == "streaming",
            )
            .order_by(desc(ChatMessageModel.created_at))
            .limit(1)
        )
        assistant = result.scalar_one_or_none()
        if assistant is None:
            return "unknown"
        metadata = dict(assistant.metadata_json or {})
        metadata["cancel_requested"] = True
        metadata["cancel_requested_at"] = datetime.now(UTC).isoformat()
        assistant.metadata_json = metadata
        await self._db.commit()
        return "accepted"

    async def stream_message(
        self,
        user_id: str,
        session_id: str,
        content: str,
        model_id: uuid.UUID | None,
        lang: str,
        request_id: uuid.UUID,
        cursor: int = 0,
        ready_event: asyncio.Event | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        session = await self._owned_session(user_id, session_id)
        fingerprint = self._request_fingerprint(content, model_id, lang)
        user_message, assistant_message = await self._generation_messages(session_id, request_id)
        if assistant_message is not None:
            self._ensure_same_request(user_message, fingerprint)
            if ready_event is not None:
                ready_event.set()
            async for event in self._replay_generation(assistant_message, cursor):
                yield event
            return

        provider = await self._provider(model_id or session.model_id)
        request_metadata = {
            "source": RESEARCH_AGENT_MARKER,
            "research_request_id": str(request_id),
            "research_request_fingerprint": fingerprint,
        }
        try:
            await self._sessions.add_message(
                session_id=session_id, role="user", content=content,
                content_type="text", status="complete", metadata=request_metadata,
            )
            assistant_message = await self._sessions.add_message(
                session_id=session_id, role="assistant", content="",
                content_type="text", status="streaming", metadata=request_metadata,
            )
            await self._db.commit()
            if ready_event is not None:
                ready_event.set()
        except IntegrityError:
            await self._db.rollback()
            user_message, assistant_message = await self._generation_messages(session_id, request_id)
            if assistant_message is None:
                raise
            self._ensure_same_request(user_message, fingerprint)
            if ready_event is not None:
                ready_event.set()
            async for event in self._replay_generation(assistant_message, cursor):
                yield event
            return

        history = cast(list[ChatMessageModel], await self._sessions.get_messages(session_id))
        messages = [
            {"role": row.role, "content": row.content}
            for row in history
            if row.role in {"user", "assistant"} and row.message_id != assistant_message.message_id
        ]
        cancel_event = asyncio.Event()
        self._active_cancels.setdefault(session_id, set()).add(cancel_event)
        assistant_text = ""
        cards: list[dict[str, Any]] = []
        tools: list[dict[str, Any]] = []
        grounding: dict[str, Any] | None = None
        polariseq: dict[str, Any] | None = None
        terminal = "interrupted"
        sequence = 0
        terminal_event_saved = False
        next_cancel_check = 0.0
        usage: dict[str, int] | None = None
        llm_calls = 0

        def snapshot_metadata() -> dict[str, Any]:
            return {
                **request_metadata,
                **({"usage": usage} if usage is not None else {}),
                "llm_calls": llm_calls,
                "events": {
                    "cards": cards,
                    "tools": tools,
                    "grounding": grounding,
                    "polariseq": polariseq,
                },
                "proposals": [
                    card_to_proposal(
                        card, session_id=session_id, project_id=session.project_id
                    ).model_dump(mode="json")
                    for card in cards
                ],
            }

        async def persist_event(
            payload: dict[str, Any], *, terminal_snapshot: bool = False,
        ) -> dict[str, Any]:
            nonlocal sequence
            sequence += 1
            normalized = json.loads(json.dumps(payload, ensure_ascii=False, default=str))
            self._db.add(ChatMessageEventModel(
                message_id=assistant_message.message_id,
                seq=sequence,
                event_type=str(normalized.get("event") or normalized.get("type") or "delta"),
                payload=normalized,
            ))
            if terminal_snapshot:
                assistant_message.content = assistant_text
                assistant_message.status = terminal
                assistant_message.metadata_json = snapshot_metadata()
            await self._db.commit()
            return {**normalized, "_sse_id": sequence}

        async def cancellation_requested() -> bool:
            nonlocal next_cancel_check
            if cancel_event.is_set():
                return True
            now = asyncio.get_running_loop().time()
            if now < next_cancel_check:
                return False
            next_cancel_check = now + 0.15
            result = await self._db.execute(
                select(ChatMessageModel.metadata_json).where(
                    ChatMessageModel.message_id == assistant_message.message_id
                )
            )
            metadata = result.scalar_one_or_none()
            return bool(isinstance(metadata, dict) and metadata.get("cancel_requested"))

        try:
            # Even with the gateway disabled, tell the trusted runtime why it has
            # no platform tools. Absence must not look like a standalone install.
            platform_tools: dict[str, Any] = {
                "catalog": [],
                "project_selected": bool(session.project_id),
            }
            if get_settings().tool_gateway_read_enabled:
                from cygnusx.application.services.agent_tool_delegation import issue_delegation
                from cygnusx.application.services.agent_tool_gateway import AgentToolGateway

                gateway = AgentToolGateway(self._db)
                context = await gateway.context(user_id, session_id,
                                                expected_agent="research_treasure_mouse")
                platform_tools.update({"catalog": gateway.catalog(context),
                                       "delegation": await issue_delegation(context)})
            async for event in self._adapter.stream(
                messages=messages,
                model=provider.model,
                lang=lang,
                cancel_event=cancel_event,
                principal_id=user_id,
                project_id=session.project_id,
                session_id=session_id,
                platform_tools=platform_tools,
            ):
                if event.get("event"):
                    event_name = str(event["event"])
                elif "delta" in event:
                    event_name = "delta"
                else:
                    event_name = str(event.get("type") or "")
                if isinstance(event.get("delta"), str):
                    assistant_text += event["delta"]
                if event_name == "usage":
                    raw_usage = event.get("usage")
                    if isinstance(raw_usage, dict):
                        usage = {
                            key: max(0, value) if isinstance(value, int)
                            and not isinstance(value, bool) else 0
                            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                            for value in [raw_usage.get(key)]
                        }
                    raw_calls = event.get("llm_calls")
                    if isinstance(raw_calls, int) and not isinstance(raw_calls, bool):
                        llm_calls = max(llm_calls, raw_calls)
                if isinstance(event.get("cards"), list):
                    cards = merge_discovery_cards(cards, event["cards"])
                if event_name == "end" and isinstance(event.get("tools"), list) and event["tools"]:
                    tools = [item for item in event["tools"] if isinstance(item, dict)]
                if event_name == "polariseq":
                    accession = event.get("accession")
                    polariseq = {"accession": accession if isinstance(accession, str) else None}
                if event_name == "tool":
                    tools.append(dict(event))
                if event_name == "grounding":
                    grounding = dict(event)
                if event_name == "cancel":
                    terminal = "cancel"
                if await cancellation_requested():
                    terminal = "cancel"
                    outgoing = await persist_event(
                        {"event": "cancel"}, terminal_snapshot=True,
                    )
                    terminal_event_saved = True
                    yield outgoing
                    break
                if event.get("error") or event_name == "error":
                    terminal = "error"
                    outgoing = await persist_event({
                        "event": "error", "code": "NODE_UNAVAILABLE",
                        "error": "科研发现服务暂不可用，请稍后重试。",
                    }, terminal_snapshot=True)
                    terminal_event_saved = True
                    yield outgoing
                    break
                if event_name == "end":
                    terminal = "end"
                    outgoing = await persist_event(event, terminal_snapshot=True)
                    terminal_event_saved = True
                    yield outgoing
                    break
                if event_name == "cancel":
                    terminal = "cancel"
                    outgoing = await persist_event(event, terminal_snapshot=True)
                    terminal_event_saved = True
                    yield outgoing
                    break
                yield await persist_event(event)
        except asyncio.CancelledError:
            terminal = "cancel"
            raise
        except Exception as exc:
            terminal = "error"
            logger.warning("Research discovery stream failed: {}", type(exc).__name__)
            code = exc.code if isinstance(exc, CygnusXError) and exc.code else "NODE_UNAVAILABLE"
            outgoing = await persist_event({
                "event": "error", "code": code,
                "error": "科研发现服务暂不可用，请稍后重试。",
            }, terminal_snapshot=True)
            terminal_event_saved = True
            yield outgoing
        finally:
            active = self._active_cancels.get(session_id)
            if active is not None:
                active.discard(cancel_event)
                if not active:
                    self._active_cancels.pop(session_id, None)
            if not terminal_event_saved:
                event_name = "cancel" if terminal == "cancel" else "interrupted"
                await persist_event({"event": event_name}, terminal_snapshot=True)

    async def _replay_generation(
        self, assistant: ChatMessageModel, cursor: int,
    ) -> AsyncIterator[dict[str, Any]]:
        last_sequence = cursor
        while True:
            result = await self._db.execute(
                select(ChatMessageEventModel).where(
                    ChatMessageEventModel.message_id == assistant.message_id,
                    ChatMessageEventModel.seq > last_sequence,
                ).order_by(ChatMessageEventModel.seq)
            )
            rows = list(result.scalars().all())
            await self._db.commit()
            for row in rows:
                last_sequence = row.seq
                yield {**row.payload, "_sse_id": row.seq}
            await self._db.refresh(assistant)
            if assistant.status != "streaming":
                return
            await self._db.commit()
            await asyncio.sleep(0.15)
