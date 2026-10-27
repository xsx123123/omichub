"""Policy, registration and first-session contracts for offline welcome content."""

from collections.abc import AsyncIterator
from datetime import date
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cygnusx.application.services.auth_service import AuthService
from cygnusx.application.services.welcome.agent import WelcomeAgentAdapter
from cygnusx.application.services.welcome.validation import (
    CopyResponse,
    content_hash,
    reject_reason,
    week_start,
)
from cygnusx.core.security import create_access_token, create_refresh_token, decode_token
from cygnusx.domain.user.entities import User
from cygnusx.infrastructure.config.agent_loader import load_agent_configs, load_system_agent_configs

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "text",
    [
        "晚上好，root，欢迎使用我们的科研平台。",
        "欢迎回来，OmicHub 助您科研顺利。",
        "欢迎回来，平台支持全自动疾病诊断分析。",
        "平台保证所有分析准确率百分之百。",
        "欢迎回来，您的项目已经完成全部分析。",
        "欢迎回来，点击 https://example.com 查看报告。",
        "<script>alert('hello')</script>",
        "欢迎回来，星期一的探索也要有据可循。",
        "欢迎回来，科研\n探索与证据始终相伴同行。",
        "欢迎回来，探索🧪🔬背后的证据与科学线索。",
    ],
)
def test_reject_unsafe_copy(text: str) -> None:
    assert reject_reason(text, []) is not None


def test_strict_schema_and_dedup() -> None:
    valid = "从数据走向发现，让每一步分析都有迹可循。"
    assert reject_reason(valid, []) is None
    assert reject_reason(valid.replace("，", "！"), [valid]) == "duplicate"
    assert content_hash(valid) == content_hash(valid.replace("，", " "))
    with pytest.raises(ValidationError):
        CopyResponse.model_validate_json('{"schema_version":"1.0","messages":[],"extra":true}')
    with pytest.raises(ValidationError):
        CopyResponse.model_validate_json("```json\n{}\n```")


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2027, 1, 1), date(2026, 12, 28)),
        (date(2026, 11, 1), date(2026, 10, 26)),
        (date(2026, 11, 2), date(2026, 11, 2)),
    ],
)
def test_local_week_boundary(day: date, expected: date) -> None:
    assert week_start(day) == expected


def test_internal_agent_is_registered_without_public_tools_or_sandbox_prompt() -> None:
    configs = load_system_agent_configs()
    assert [c["agent_id"] for c in configs] == ["welcome_copywriter"]
    assert "welcome_copywriter" not in [c["agent_id"] for c in load_agent_configs()]
    agent = WelcomeAgentAdapter()
    assert (
        not agent.config["tools"] and not agent.config["mcp_ids"] and not agent.config["skill_ids"]
    )
    assert "共享沙盒协议" not in agent.system
    assert len(agent.prompt_hash) == 64


async def test_signed_onboarding_session_survives_refresh() -> None:
    user = User(
        username="welcome-test", email="welcome-test@example.test", hashed_password="unused"
    )
    repo = AsyncMock()
    repo.get_by_id.return_value = user
    refresh = create_refresh_token(
        str(user.id), token_version=user.token_version, onboarding_session=True
    )
    service = AuthService(repo, AsyncMock())
    access, renewed = await service.refresh_token(refresh)
    assert (decode_token(access) or {})["onboarding_session"] is True
    assert (decode_token(renewed) or {})["onboarding_session"] is True
    ordinary = decode_token(create_access_token(str(uuid4()), token_version=0)) or {}
    assert not ordinary.get("onboarding_session")


async def test_provider_reports_usage_for_empty_retry_and_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cygnusx.infrastructure.ai_provider.openai_compatible import (
        ChatChunk,
        OpenAICompatibleProvider,
    )
    from cygnusx.infrastructure.database.models.ai_provider import AIProviderConfigModel

    config = AIProviderConfigModel(
        id=uuid4(), name="usage-test", model="test", base_url="https://example.test", api_key="test"
    )
    provider = OpenAICompatibleProvider(config)
    count = 0

    async def once(*args: Any) -> AsyncIterator[ChatChunk]:
        nonlocal count
        count += 1
        if count == 2:
            yield ChatChunk(type="text", content="valid")
        yield ChatChunk(
            type="done",
            metadata={"usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}},
        )

    monkeypatch.setattr(provider, "_stream_once", once)
    attempts = []
    chunks = [
        c
        async for c in provider.chat_stream(
            [{"role": "user", "content": "public"}], on_attempt_usage=attempts.append
        )
    ]
    assert count == 2 and len(attempts) == 2
    assert sum(a["usage"]["total_tokens"] for a in attempts) == 60
    assert chunks[-1].type == "done"


def test_real_chinese_near_duplicates_and_topic_mismatch_fail_qa() -> None:
    from cygnusx.application.services.welcome.validation import CopyMessage, topic_matches

    assert reject_reason("欢迎回来，ＲＯＯＴ，让科研探索更从容。", []) == "content_policy"

    assert (
        reject_reason(
            "欢迎回来，愿版本化流程让维护更从容。", ["欢迎回来，愿版本化流程守住每次维护的质量。"]
        )
        == "duplicate"
    )
    assert not topic_matches(
        CopyMessage(text="欢迎回来，愿版本化流程让维护更从容。", tone="warm", topic="discovery")
    )
    assert topic_matches(
        CopyMessage(
            text="给那些出乎意料的观察，留一点继续探索的空间。", tone="warm", topic="discovery"
        )
    )
