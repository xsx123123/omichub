"""ChatEventService 违规警告合并抑制的单元测试。"""

import time
from typing import Any

import pytest

from cygnusx.application.services.chat import chat_event_service
from cygnusx.application.services.chat.chat_event_service import ChatEventService
from cygnusx.application.services.execution_events import EventSequenceError


class _WarningRecorder:
    """替代 loguru logger，记录 warning 调用（caplog 捕不到 loguru）。"""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def warning(self, template: str, *args: Any, **kwargs: Any) -> None:
        self.messages.append(template.format(*args, **kwargs))


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> _WarningRecorder:
    rec = _WarningRecorder()
    monkeypatch.setattr(chat_event_service, "logger", rec)
    return rec


def _service() -> ChatEventService:
    return ChatEventService(enforcement="warn")


@pytest.mark.unit
def test_violation_warning_throttled_within_window(recorder: _WarningRecorder) -> None:
    service = _service()
    exc = EventSequenceError("agent_context_reinjected 后必须紧接 agent_turn_continued")
    for _ in range(10):
        service._handle_violation("text", exc)
    assert len(recorder.messages) == 1
    assert "合并" not in recorder.messages[0]


@pytest.mark.unit
def test_violation_warning_resumes_after_window(
    recorder: _WarningRecorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service()
    exc = EventSequenceError("boom")
    now = time.monotonic()
    service._handle_violation("text", exc)
    # 窗口内继续刷：被抑制、仅计数
    for _ in range(5):
        service._handle_violation("text", exc)
    monkeypatch.setattr(time, "monotonic", lambda: now + 120.0)
    # 越过 60s 窗口：汇总输出一条（含抑制计数）
    service._handle_violation("text", exc)
    assert len(recorder.messages) == 2
    assert "抑制 5 条" in recorder.messages[1]


@pytest.mark.unit
def test_violation_warning_dedupes_by_reason(recorder: _WarningRecorder) -> None:
    service = _service()
    service._handle_violation("text", EventSequenceError("reason-a"))
    service._handle_violation("text", EventSequenceError("reason-b"))
    assert len(recorder.messages) == 2


@pytest.mark.unit
def test_violation_raise_mode_bypasses_throttle(recorder: _WarningRecorder) -> None:
    service = ChatEventService(enforcement="raise")
    with pytest.raises(EventSequenceError):
        service._handle_violation("text", EventSequenceError("boom"))
    assert recorder.messages == []
