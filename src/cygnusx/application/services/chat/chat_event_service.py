"""聊天 SSE 出口的事件序列校验。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace

from loguru import logger

from cygnusx.application.services.execution_events import (
    EventSequenceError,
    validate_event_sequence,
)
from cygnusx.core.config import Settings, get_settings
from cygnusx.infrastructure.ai_provider.openai_compatible import ChatChunk

# 同类违规警告的合并窗口（秒）：窗口内重复警告合并计数，窗口过期再输出一条汇总，
# 避免已知问题刷爆日志（历史上 reinjected 序列缺陷曾达 760 条/分钟）。
_VIOLATION_LOG_WINDOW_SECONDS = 60.0


@dataclass
class ChatEventService:
    """在 SSE 发送前验证单个聊天流的统一状态转移。"""

    enforcement: str
    _events: list[ChatChunk] = field(default_factory=list)
    _download_call_ids: set[str] = field(default_factory=set)
    _violation_log_state: dict[tuple[str, str], tuple[float, int]] = field(default_factory=dict)

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> ChatEventService:
        settings = settings or get_settings()
        return cls(enforcement=settings.chat_event_sequence_enforcement)

    def before_send(self, chunk: ChatChunk) -> ChatChunk:
        """在 SSE 输出前校验事件；生产告警模式不会中断用户流。"""
        from cygnusx.domain.download_security import (
            is_download_tool_name,
            redact_download_text,
            redact_download_tool_history,
        )

        call_id = chunk.metadata.get("tool_call_id") or chunk.metadata.get("id")
        named_download = any(
            is_download_tool_name(chunk.metadata.get(key)) for key in ("tool_name", "name")
        )
        if named_download and isinstance(call_id, str):
            self._download_call_ids.add(call_id)
        download_context = named_download or (
            isinstance(call_id, str) and call_id in self._download_call_ids
        )
        safe_metadata = redact_download_tool_history(
            chunk.metadata, download_context=download_context
        )
        assert isinstance(safe_metadata, dict)
        chunk = replace(
            chunk,
            metadata=safe_metadata,
            content=redact_download_text(chunk.content) if download_context else chunk.content,
        )
        self._events.append(chunk)
        try:
            validate_event_sequence(self._events, require_completion=False)
        except EventSequenceError as exc:
            self._events.pop()
            self._handle_violation(chunk.type, exc)
        return chunk

    def after_stream(self) -> None:
        """在生成器正常结束时确认执行生命周期已完成。"""
        try:
            validate_event_sequence(self._events, require_completion=True)
        except EventSequenceError as exc:
            self._handle_violation("stream_completed", exc)

    def _handle_violation(self, event_type: str, exc: EventSequenceError) -> None:
        if self.enforcement == "raise":
            raise exc
        if self.enforcement == "warn":
            key = (event_type, str(exc))
            now = time.monotonic()
            state = self._violation_log_state.get(key)
            if state is None:
                self._violation_log_state[key] = (now, 0)
                logger.warning("event_sequence_violation event_type={} reason={}", event_type, exc)
                return
            last_at, suppressed = state
            if now - last_at >= _VIOLATION_LOG_WINDOW_SECONDS:
                merged = f"（窗口期内抑制 {suppressed} 条同类警告）" if suppressed else ""
                self._violation_log_state[key] = (now, 0)
                logger.warning(
                    "event_sequence_violation{} event_type={} reason={}",
                    merged,
                    event_type,
                    exc,
                )
            else:
                self._violation_log_state[key] = (last_at, suppressed + 1)
