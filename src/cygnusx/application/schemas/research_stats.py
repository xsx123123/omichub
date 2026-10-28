"""Public aggregate views; never expose sessions, prompts, emails or login names."""

from datetime import datetime
from unicodedata import category

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResearchStatRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    name: str
    treasures: int = 0
    digs: int = 0
    chats: int = 0
    updated_at: datetime | None = None
    is_guest: bool = Field(default=False, alias="isGuest")
    week_treasures: int = Field(default=0, alias="weekTreasures")
    week_digs: int = Field(default=0, alias="weekDigs")
    week_chats: int = Field(default=0, alias="weekChats")


class ResearchLeaderboard(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    users: list[ResearchStatRow]
    guests: list[ResearchStatRow] = Field(default_factory=list)
    own_key: str = Field(alias="ownKey")
    nickname: str
    total_treasures: int = Field(alias="totalTreasures")
    week_treasures: int = Field(alias="weekTreasures")


class ResearchToolStat(BaseModel):
    name: str
    label: str
    count: int = 0
    errors: int = 0
    empties: int = 0


class ResearchUsageStats(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    chats: int = 0
    llm_calls: int = Field(default=0, alias="llmCalls")
    prompt_tokens: int = Field(default=0, alias="promptTokens")
    completion_tokens: int = Field(default=0, alias="completionTokens")
    total_tokens: int = Field(default=0, alias="totalTokens")
    tool_calls: int = Field(default=0, alias="toolCalls")
    tool_errors: int = Field(default=0, alias="toolErrors")
    actors: int = 0
    tools: list[ResearchToolStat] = Field(default_factory=list)
    since: datetime
    updated_at: datetime = Field(alias="updatedAt")
    usage_recorded_chats: int = Field(default=0, alias="usageRecordedChats")


class ResearchNicknameUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nickname: str = Field(min_length=1, max_length=16)

    @field_validator("nickname", mode="before")
    @classmethod
    def clean_nickname(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if any(category(char) in {"Cc", "Cs"} for char in value):
                raise ValueError("昵称不能包含控制字符")
        return value
