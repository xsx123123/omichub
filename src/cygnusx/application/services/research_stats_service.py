"""Compute platform statistics from durable research message snapshots.

No browser supplied counters, no extra ledger and no replay-sensitive increments.
Historical provider usage is unknown unless actually recorded; never estimate it.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import String, cast, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from cygnusx.application.schemas.research_stats import (
    ResearchLeaderboard,
    ResearchStatRow,
    ResearchToolStat,
    ResearchUsageStats,
)
from cygnusx.application.services.research_treasure_service import (
    RESEARCH_AGENT_MARKER,
    ResearchTreasureService,
    merge_discovery_cards,
)
from cygnusx.core.config import get_settings
from cygnusx.infrastructure.database.models.chat import ChatMessageModel, ChatSessionModel
from cygnusx.infrastructure.database.models.user import UserModel

NICKNAME_KEY = "treasure_mouse_nickname"
_NON_SEARCH_TOOLS = {"intent_plan", "grounding_check"}
_LEADERBOARD_LIMIT = 100
_SNAPSHOT_BATCH_SIZE = 500


def public_key(user_id: str) -> str:
    return "u:" + hashlib.sha256(user_id.encode()).hexdigest()[:24]


def display_name(user: UserModel) -> str:
    nickname = (user.preferences or {}).get(NICKNAME_KEY)
    return str(nickname or user.nickname or f"寻宝鼠 {public_key(str(user.id))[-6:]}")[:16]


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _count(value: object) -> int:
    return max(0, value) if isinstance(value, int) and not isinstance(value, bool) else 0


def completed_tools(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    events = metadata.get("events")
    raw = events.get("tools", []) if isinstance(events, dict) else []
    if not isinstance(raw, list):
        return []
    return [
        item for item in raw if isinstance(item, dict)
        and item.get("name") not in _NON_SEARCH_TOOLS
        and (isinstance(item.get("ok"), bool) or item.get("status") in {"done", "error"})
    ]


class ResearchStatsService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _snapshot(
        self,
    ) -> tuple[dict[str, ResearchStatRow], ResearchUsageStats]:
        now = datetime.now(UTC)
        local = now.astimezone(ZoneInfo(get_settings().treasure_stats_timezone))
        monday = (local - timedelta(days=local.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0,
        ).astimezone(UTC)
        stats = ResearchUsageStats(since=now, updated_at=now)
        users: dict[str, ResearchStatRow] = {}
        tools: dict[str, ResearchToolStat] = {}
        # Select no content or project/session identifiers. Stream bounded batches
        # rather than materializing the complete message history in memory.
        query = (
            select(UserModel, ChatMessageModel.metadata_json, ChatMessageModel.created_at)
            .select_from(ChatMessageModel)
            .join(ChatSessionModel, ChatSessionModel.session_id == ChatMessageModel.session_id)
            .join(UserModel, cast(UserModel.id, String) == ChatSessionModel.user_id)
            .where(
                UserModel.status == "active",
                ChatSessionModel.sandbox_meta["research_agent"].as_string()
                == RESEARCH_AGENT_MARKER,
                ChatMessageModel.role == "assistant",
                ChatMessageModel.status.in_(
                    ["end", "complete", "completed", "error", "cancel", "interrupted"],
                ),
            )
            .options(load_only(UserModel.id, UserModel.nickname, UserModel.preferences))
            .execution_options(yield_per=_SNAPSHOT_BATCH_SIZE)
        )
        result = await self._db.stream(query)
        async for user, metadata, created_at in result:
            key = public_key(str(user.id))
            row = users.setdefault(key, ResearchStatRow(key=key, name=display_name(user)))
            created = _utc(created_at)
            stats.since = min(stats.since, created)
            row.updated_at = max(row.updated_at or created, created)
            metadata = metadata if isinstance(metadata, dict) else {}
            events = metadata.get("events")
            cards = events.get("cards", []) if isinstance(events, dict) else []
            treasures = len(merge_discovery_cards([], cards if isinstance(cards, list) else []))
            calls = completed_tools(metadata)
            row.chats += 1
            row.treasures += treasures
            row.digs += len(calls)
            if created >= monday:
                row.week_chats += 1
                row.week_treasures += treasures
                row.week_digs += len(calls)
            for item in calls:
                name = str(item.get("name") or "unknown")[:128]
                tool = tools.setdefault(
                    name, ResearchToolStat(name=name, label=str(item.get("label") or name)[:128]),
                )
                tool.count += 1
                tool.errors += int(item.get("ok") is False or item.get("status") == "error")
                tool.empties += int(item.get("empty") is True)
            usage = metadata.get("usage")
            if isinstance(usage, dict):
                stats.usage_recorded_chats += 1
                stats.prompt_tokens += _count(usage.get("prompt_tokens"))
                stats.completion_tokens += _count(usage.get("completion_tokens"))
                stats.total_tokens += _count(usage.get("total_tokens"))
            stats.llm_calls += _count(metadata.get("llm_calls"))
        stats.chats = sum(row.chats for row in users.values())
        stats.actors = len(users)
        stats.tools = sorted(tools.values(), key=lambda tool: (-tool.count, tool.name))
        stats.tool_calls = sum(tool.count for tool in stats.tools)
        stats.tool_errors = sum(tool.errors for tool in stats.tools)
        return users, stats

    async def leaderboard(
        self, user_id: str, period: Literal["all", "week"] = "all",
    ) -> ResearchLeaderboard:
        access = ResearchTreasureService(self._db)
        await access.ensure_access(user_id)
        own_user = await access._current_user(user_id)
        users, _stats = await self._snapshot()
        ranked = sorted(
            [row for row in users.values() if period == "all" or row.week_chats > 0],
            key=lambda row: (
                -(row.week_treasures if period == "week" else row.treasures),
                -(row.week_chats if period == "week" else row.chats),
                -(row.week_digs if period == "week" else row.digs), row.key,
            ),
        )
        return ResearchLeaderboard(
            users=ranked[:_LEADERBOARD_LIMIT],
            own_key=public_key(user_id), nickname=display_name(own_user),
            total_treasures=sum(row.treasures for row in users.values()),
            week_treasures=sum(row.week_treasures for row in users.values()),
        )

    async def usage(self, user_id: str) -> ResearchUsageStats:
        await ResearchTreasureService(self._db).ensure_access(user_id)
        _users, stats = await self._snapshot()
        return stats

    async def set_nickname(self, user_id: str, nickname: str) -> dict[str, object]:
        access = ResearchTreasureService(self._db)
        await access.ensure_access(user_id)
        user = await access._current_user(user_id)
        # Lock the user row so parallel preference updates cannot lose this value.
        await self._db.refresh(user, with_for_update=True)
        user.preferences = {**(user.preferences or {}), NICKNAME_KEY: nickname}
        await self._db.flush()
        return {"ok": True, "nickname": nickname}
