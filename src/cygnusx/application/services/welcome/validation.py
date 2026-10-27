"""Strict structured output and conservative public-copy quality policy."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, timedelta
from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Audience = Literal["admin", "general"]
Topic = Literal["research", "workflow", "evidence", "discovery", "general"]
APPROVED_FACTS = {
    "version": "v1",
    "facts": ["CygnusX BioOps 提供版本化的组学分析流程", "平台支持结果追溯与可复现分析"],
}
FALLBACK_TEXT = "欢迎回来，愿每一次科研探索都有清晰的线索与证据。"
# Welcome copy need not advertise capabilities. Reject concrete claims rather than infer facts.
_FORBIDDEN = re.compile(
    r"root|omichub|https?[:/]|www\.|[<>`\[\]{}/\\@#]|\d|"
    r"早上|上午|中午|下午|晚上|凌晨|今天|明天|昨日|昨天|星期|周[一二三四五六日天]|天气|节日|"
    r"保证|百分之|绝对|最强|全球|秒级|免费|无限|诊断|治疗|患者|账号|密码|密钥|"
    r"实现|拥有|确保|包办|全能|稳赚|完美|信仰|宗教|政治|种族|处方|用药|治愈|疗效|"
    r"已经|已为|已帮|已完成|您的[\u4e00-\u9fff]{0,6}(项目|样本|数据)|"
    r"支持|提供|具备|能够|可以|自动|一键|加速|准确率|预测|识别|检测|生成|计算|下载|上传|"
    r"营销|口号|遥遥领先|颠覆|赋能",
    re.IGNORECASE,
)


class CopyMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(min_length=14, max_length=48)
    tone: Literal["warm", "professional", "playful"]
    topic: Topic


class CopyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["1.0"]
    messages: list[CopyMessage] = Field(min_length=1, max_length=8)


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def normalized(text: str) -> str:
    return "".join(c.lower() for c in unicodedata.normalize("NFKC", text) if c.isalnum())


def content_hash(text: str) -> str:
    return hashlib.sha256(normalized(text).encode()).hexdigest()


def similarity(left: str, right: str) -> float:
    def grams(value: str) -> set[str]:
        value = normalized(value)
        return {value[i : i + 2] for i in range(len(value) - 1)}

    a, b = grams(left), grams(right)
    return len(a & b) / max(1, len(a | b))


def reject_reason(text: str, previous: list[str]) -> str | None:
    if not 14 <= len(text) <= 48 or text != text.strip():
        return "length_or_whitespace"
    if any(unicodedata.category(c).startswith("C") for c in text):
        return "control_character"
    plain = unicodedata.normalize("NFKC", text)
    if _FORBIDDEN.search(plain):
        return "content_policy"
    # Latin text is limited to the approved brand; arbitrary product/ability names fail closed.
    if re.search(r"[a-zA-Z]", plain.replace("CygnusX BioOps", "").replace("CygnusX", "")):
        return "unapproved_fact"
    if sum(ord(c) >= 0x1F000 or 0x2600 <= ord(c) <= 0x27BF for c in text) > 1:
        return "emoji_limit"
    if any(
        content_hash(text) == content_hash(old)
        or similarity(text, old) >= 0.42
        or SequenceMatcher(None, normalized(text), normalized(old)).ratio() >= 0.8
        for old in previous
    ):
        return "duplicate"
    return None


_TOPIC_WORDS: dict[str, str] = {
    "research": "科学|问题|假设|思考|研究|实验|认知|疑问",
    "workflow": "流程|步骤|任务|组织|规划|衔接|计划|整理",
    "evidence": "证据|记录|核对|复现|追溯|审查|复核|质量|依据|可靠|检验|验证|可信",
    "discovery": "好奇|灵感|观察|发现|探索|线索|意外|新知|未知|边界|洞见",
    "general": "专注|耐心|从容|协作|休息|伙伴|轻松|热情|互助|默契|安心|珍惜|信任|交流|团队",
}


def topic_matches(message: CopyMessage) -> bool:
    """A conservative lexical check prevents four arbitrary topic labels passing QA."""
    return bool(re.search(_TOPIC_WORDS[message.topic], message.text))
