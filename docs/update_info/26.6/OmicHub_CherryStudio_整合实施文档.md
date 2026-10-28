# OmicHub AI助手 — Cherry Studio 架构整合实施文档

> **文档版本**：v1.0  
> **日期**：2025-06-27  
> **目标**：将 Cherry Studio 的 AI 架构（SSE流式输出、Provider管理、助手系统）完整整合到 OmicHub  
> **整合范围**：后端（FastAPI）+ 前端（Vue 3）+ 数据库 + 部署

---

## 快速开始（5步让AI跑起来）

### Step 0: 填API Key
在系统管理 → AI模型配置 → 编辑kimi → **填入你的阿里云API Key**

### Step 1: 安装依赖
```bash
# 后端
pip install httpx cryptography

# 前端
npm install markdown-it highlight.js dompurify @vicons/ionicons5 @vueuse/core
npm install -D @types/markdown-it @types/dompurify
```

### Step 2: 数据库迁移
```bash
alembic upgrade V009
```

### Step 3: 复制代码
- 后端代码 → 复制到 `app/` 对应目录
- 前端代码 → 复制到 `src/` 对应目录

### Step 4: 重启服务
```bash
docker-compose restart web
```

---

## 文档结构

| 部分 | 内容 | 文件路径 |
|------|------|----------|
| **第一部分** | 后端完整代码（FastAPI） | 本文件第1-6章 |
| **第二部分** | 前端完整代码（Vue 3） | 本文件第7-12章 |
| **第三部分** | 联调验证清单 | 本文件第13章 |

---



---

# 第一部分：后端代码（FastAPI）

# OmicHub AI助手整合Cherry Studio架构 — 后端完整代码

> 将 Cherry Studio 的 AI 架构（SSE 流式输出、Provider 管理、助手系统）整合到 OmicHub 的 FastAPI 后端。

---

## 目录

1. [数据库模型（SQLAlchemy）](#1-数据库模型)
2. [Pydantic DTO 模型](#2-pydantic-dto-模型)
3. [LLM Provider 服务](#3-llm-provider-服务)
4. [Chat Service 业务逻辑](#4-chat-service-业务逻辑)
5. [FastAPI 路由](#5-fastapi-路由)
6. [数据库迁移脚本（Alembic）](#6-数据库迁移脚本)
7. [路由注册](#7-路由注册)
8. [依赖安装](#8-依赖安装)

---

## 1. 数据库模型

### 文件：`app/models/ai_chat.py`

```python
"""
AI 聊天系统数据库模型
对应 Cherry Studio 架构：Topic (Session) + Message + Assistant
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Float, Boolean, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from cryptography.fernet import Fernet
import os

# 加密密钥从环境变量读取
ENCRYPTION_KEY = os.environ.get("AI_CONFIG_ENCRYPTION_KEY", Fernet.generate_key())
fernet = Fernet(ENCRYPTION_KEY)


class ChatSession(Base):
    """聊天会话表（对应 Cherry Studio 的 Topic）"""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(50), unique=True, nullable=False, index=True)  # UUID
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    assistant_id = Column(String(50), ForeignKey("chat_assistants.assistant_id"), nullable=True)
    title = Column(String(200), default="新对话")
    model_id = Column(Integer, ForeignKey("ai_model_configs.id"), nullable=False)

    # 统计
    message_count = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)

    # 状态
    status = Column(String(20), default="active")  # active / archived / deleted

    # 时间
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_message_at = Column(DateTime, nullable=True)

    # 关联
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at"
    )
    assistant = relationship("ChatAssistant", back_populates="sessions")

    __table_args__ = (
        Index('idx_chat_sessions_user_updated', 'user_id', 'updated_at'),
    )


class ChatMessage(Base):
    """聊天消息表"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    message_id = Column(String(50), unique=True, nullable=False, index=True)  # UUID
    session_id = Column(String(50), ForeignKey("chat_sessions.session_id"), nullable=False, index=True)

    # 消息内容
    role = Column(String(20), nullable=False)  # user / assistant / system
    content = Column(Text, default="")
    content_type = Column(String(20), default="text")  # text / markdown / code / tool_call / tool_result / error

    # 元数据（JSONB 存储）
    metadata_json = Column(JSON, default=dict)  # tokens, model, tool_calls, etc.

    # 状态
    status = Column(String(20), default="complete")  # streaming / complete / error / stopped

    # 时间
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联
    session = relationship("ChatSession", back_populates="messages")

    __table_args__ = (
        Index('idx_chat_messages_session_created', 'session_id', 'created_at'),
    )


class ChatAssistant(Base):
    """AI 助手表（对应 Cherry Studio 的 Assistant）"""
    __tablename__ = "chat_assistants"

    id = Column(Integer, primary_key=True)
    assistant_id = Column(String(50), unique=True, nullable=False)  # 如 rna_seq_analyst

    # 基本信息
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    system_prompt = Column(Text, nullable=False)

    # 默认配置
    default_model_id = Column(Integer, ForeignKey("ai_model_configs.id"), nullable=True)
    default_temperature = Column(Float, default=0.3)
    default_max_tokens = Column(Integer, default=4096)

    # 显示
    icon = Column(String(10), default="\U0001F916")  # 🤖
    color = Column(String(20), default="#4f8ef7")

    # 分类
    category = Column(String(50), default="general")  # analysis / visualization / literature / code

    # 是否内置（预设）
    is_builtin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # 创建者（null 表示系统预设）
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    sessions = relationship("ChatSession", back_populates="assistant")

    __table_args__ = (
        Index('idx_chat_assistants_category', 'category', 'is_active'),
    )
```

### User 模型补充（`app/models/user.py` 追加）

```python
# 在 User 类中添加反向关联
class User(Base):
    # ... 已有字段 ...

    chat_sessions = relationship(
        "ChatSession",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="desc(ChatSession.updated_at)"
    )
```

---

## 2. Pydantic DTO 模型

### 文件：`app/schemas/chat.py`

```python
"""
聊天系统 Pydantic DTO 模型
请求验证 + 响应序列化
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class ChatStreamRequest(BaseModel):
    """流式聊天请求"""
    messages: List[Dict[str, str]] = Field(..., description="消息列表 [{role, content}]")
    model_id: int = Field(..., description="使用的模型 ID")
    session_id: Optional[str] = Field(None, description="会话 ID，新建则传 null")
    assistant_id: Optional[str] = Field(None, description="助手 ID")
    system_prompt: Optional[str] = Field(None, description="自定义系统提示词")


class ChatMessageResponse(BaseModel):
    """消息响应"""
    model_config = ConfigDict(from_attributes=True)

    message_id: str
    role: str
    content: str
    content_type: str = "text"
    status: str
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ChatSessionResponse(BaseModel):
    """会话响应"""
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    title: str
    assistant_id: Optional[str] = None
    model_id: int
    model_name: Optional[str] = None
    message_count: int
    status: str
    created_at: datetime
    updated_at: datetime
    last_message_at: Optional[datetime] = None


class ChatAssistantResponse(BaseModel):
    """助手响应"""
    model_config = ConfigDict(from_attributes=True)

    assistant_id: str
    name: str
    description: str
    system_prompt: str
    default_model_id: Optional[int] = None
    default_temperature: float
    default_max_tokens: int
    icon: str
    color: str
    category: str
    is_builtin: bool
    is_active: bool
    created_at: datetime


class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    title: Optional[str] = "新对话"
    assistant_id: Optional[str] = None
    model_id: int


class MessageFeedbackRequest(BaseModel):
    """消息反馈请求"""
    message_id: str
    feedback: str = Field(..., pattern="^(up|down)$")
    comment: Optional[str] = None
```

---

## 3. LLM Provider 服务

### 文件：`app/services/llm_provider.py`

```python
"""
LLM Provider 管理服务 -- 借鉴 Cherry Studio 的 ProviderManager 架构
统一管理多个 AI 模型 Provider 的调用

支持的 Provider 类型：
- OpenAI 兼容格式（DeepSeek / Kimi / Qwen / 通义千问 / 智谱 / ChatGLM 等）
- 未来可扩展：Anthropic Claude / Azure OpenAI / Google Gemini
"""

import httpx
import json
import os
from typing import AsyncIterable, Dict, Any, Optional, List
from dataclasses import dataclass, field
from app.models.ai_config import AIModelConfig


@dataclass
class ChatChunk:
    """流式输出数据块 -- SSE 事件的统一抽象"""
    type: str  # "text" | "tool_call" | "error" | "done"
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class LLMProvider:
    """
    LLM Provider 抽象基类
    所有 Provider 必须实现此接口
    """

    def __init__(self, config: AIModelConfig):
        self.config = config
        self.name = config.name
        self.model = config.model
        self.base_url = config.base_url.rstrip("/")  # 去掉尾部斜杠
        # API Key 通过 property 解密获取（假设 config.api_key 已解密）
        self._api_key = config.api_key

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> AsyncIterable[ChatChunk]:
        """流式聊天 -- 子类必须实现"""
        raise NotImplementedError

    async def chat_complete(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> ChatChunk:
        """非流式完整聊天 -- 默认实现，可覆盖"""
        full_content = ""
        async for chunk in self.chat_stream(messages, system_prompt, temperature, max_tokens):
            if chunk.type == "text":
                full_content += chunk.content
            elif chunk.type == "done":
                return ChatChunk(type="done", content=full_content)
            elif chunk.type == "error":
                return chunk
        return ChatChunk(type="done", content=full_content)

    async def validate(self) -> bool:
        """验证配置是否可用（API Key 和连接）"""
        raise NotImplementedError


class OpenAICompatibleProvider(LLMProvider):
    """
    OpenAI 兼容 Provider
    适用于绝大多数国产模型（Kimi / DeepSeek / Qwen / 通义千问 / 智谱等）
    所有接口遵循 OpenAI Chat Completions API 规范
    """

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> AsyncIterable[ChatChunk]:
        """
        SSE 流式输出 -- 对接 OpenAI /chat/completions 接口

        SSE 格式：
            data: {"choices":[{"delta":{"content":"你好"}}]}
            data: {"choices":[{"delta":{"content":"世界"}}]}
            data: [DONE]
        """

        # 构建消息列表（system prompt 放最前面）
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        api_messages.extend(messages)

        # 构建请求体
        payload = {
            "model": self.model,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True  # 关键：启用流式
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }

        timeout = self.config.timeout if hasattr(self.config, 'timeout') and self.config.timeout else 120

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout, connect=10),
                verify=True,
                follow_redirects=True
            ) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:

                    # ---- HTTP 错误处理 ----
                    if response.status_code == 401:
                        yield ChatChunk(
                            type="error",
                            content=f"API Key 无效或已过期，请检查模型 '{self.name}' 的配置"
                        )
                        return
                    elif response.status_code == 403:
                        yield ChatChunk(
                            type="error",
                            content=f"API 访问被拒绝，请检查模型 '{self.name}' 的权限设置"
                        )
                        return
                    elif response.status_code == 429:
                        yield ChatChunk(
                            type="error",
                            content=f"请求频率过高（模型: {self.name}），请稍后重试"
                        )
                        return
                    elif response.status_code == 404:
                        yield ChatChunk(
                            type="error",
                            content=f"模型 '{self.model}' 不存在，请检查模型名称是否正确"
                        )
                        return
                    elif response.status_code >= 500:
                        body = await response.aread()
                        error_detail = body.decode()[:200] if body else "未知服务器错误"
                        yield ChatChunk(
                            type="error",
                            content=f"模型服务暂时不可用（模型: {self.name}, HTTP {response.status_code}）: {error_detail}"
                        )
                        return
                    elif response.status_code != 200:
                        body = await response.aread()
                        error_detail = body.decode()[:500] if body else f"HTTP {response.status_code}"
                        yield ChatChunk(
                            type="error",
                            content=f"请求失败（模型: {self.name}）: {error_detail}"
                        )
                        return

                    # ---- 解析 SSE 流 ----
                    buffer = ""
                    async for chunk in response.aiter_text():
                        buffer += chunk
                        lines = buffer.split("\n")
                        # 保留未完成的行
                        buffer = lines.pop() if not buffer.endswith("\n") else ""

                        for line in lines:
                            line = line.strip()
                            if not line or not line.startswith("data: "):
                                continue

                            data = line[6:]  # 去掉 "data: " 前缀

                            if data == "[DONE]":
                                yield ChatChunk(type="done")
                                return

                            try:
                                parsed = json.loads(data)

                                # 检查顶层错误
                                if "error" in parsed:
                                    error_msg = parsed["error"].get("message", "未知错误")
                                    error_code = parsed["error"].get("code", "")
                                    yield ChatChunk(
                                        type="error",
                                        content=f"模型错误（{self.name}, code={error_code}）: {error_msg}"
                                    )
                                    return

                                # 提取增量内容（choices 可能为空）
                                choices = parsed.get("choices", [])
                                if not choices:
                                    continue

                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")

                                if content:
                                    yield ChatChunk(
                                        type="text",
                                        content=content,
                                        metadata={
                                            "model": self.model,
                                            **({"usage": parsed.get("usage")} if parsed.get("usage") else {})
                                        }
                                    )

                                # 检查工具调用（如果 provider 支持 function calling）
                                tool_calls = delta.get("tool_calls")
                                if tool_calls:
                                    yield ChatChunk(
                                        type="tool_call",
                                        content="",
                                        metadata={"tool_calls": tool_calls}
                                    )

                                # 检查 finish_reason
                                finish_reason = choices[0].get("finish_reason")
                                if finish_reason and finish_reason != "null":
                                    if finish_reason == "length":
                                        yield ChatChunk(
                                            type="text",
                                            content="",
                                            metadata={"warning": "输出因达到 max_tokens 限制而被截断"}
                                        )
                                    elif finish_reason == "content_filter":
                                        yield ChatChunk(
                                            type="error",
                                            content="输出被内容安全过滤器拦截"
                                        )
                                        return

                            except json.JSONDecodeError:
                                # 忽略解析失败的行（部分 provider 会输出非 JSON 内容）
                                continue
                            except (KeyError, IndexError):
                                # 忽略结构不匹配的 chunk
                                continue

                    # 流结束但未收到 [DONE]
                    yield ChatChunk(type="done")

        except httpx.TimeoutException:
            yield ChatChunk(
                type="error",
                content=f"请求超时（{timeout}秒），请检查网络连接或增加 Timeout 设置（模型: {self.name}）"
            )
        except httpx.ConnectError:
            yield ChatChunk(
                type="error",
                content=f"无法连接到模型服务（{self.base_url}），请检查 Base URL 是否正确（模型: {self.name}）"
            )
        except httpx.HTTPStatusError as e:
            yield ChatChunk(
                type="error",
                content=f"HTTP 错误（模型: {self.name}）: {e.response.status_code} - {str(e)[:200]}"
            )
        except Exception as e:
            yield ChatChunk(
                type="error",
                content=f"调用模型时发生未预期错误（模型: {self.name}）: {str(e)}"
            )

    async def validate(self) -> bool:
        """验证 API Key 和连接是否正常 -- 通过获取模型列表验证"""
        try:
            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json"
            }
            async with httpx.AsyncClient(timeout=10, verify=True) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=headers
                )
                return response.status_code == 200
        except Exception:
            return False


class DeepSeekProvider(OpenAICompatibleProvider):
    """DeepSeek 专用 Provider -- 支持推理过程输出"""

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> AsyncIterable[ChatChunk]:
        """DeepSeek 流式输出，支持 reasoning_content 字段"""

        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        api_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }

        timeout = self.config.timeout if hasattr(self.config, 'timeout') and self.config.timeout else 120

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout, connect=10),
                verify=True,
                follow_redirects=True
            ) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:

                    if response.status_code != 200:
                        body = await response.aread()
                        yield ChatChunk(
                            type="error",
                            content=f"DeepSeek 请求失败 (HTTP {response.status_code}): {body.decode()[:200]}"
                        )
                        return

                    buffer = ""
                    async for chunk in response.aiter_text():
                        buffer += chunk
                        lines = buffer.split("\n")
                        buffer = lines.pop() if not buffer.endswith("\n") else ""

                        for line in lines:
                            line = line.strip()
                            if not line or not line.startswith("data: "):
                                continue

                            data = line[6:]
                            if data == "[DONE]":
                                yield ChatChunk(type="done")
                                return

                            try:
                                parsed = json.loads(data)
                                if "error" in parsed:
                                    error_msg = parsed["error"].get("message", "未知错误")
                                    yield ChatChunk(type="error", content=f"DeepSeek 错误: {error_msg}")
                                    return

                                choices = parsed.get("choices", [])
                                if not choices:
                                    continue

                                delta = choices[0].get("delta", {})

                                # DeepSeek 特有: reasoning_content（思考过程）
                                reasoning = delta.get("reasoning_content", "")
                                if reasoning:
                                    yield ChatChunk(
                                        type="text",
                                        content=reasoning,
                                        metadata={"is_reasoning": True}
                                    )

                                # 普通内容
                                content = delta.get("content", "")
                                if content:
                                    yield ChatChunk(
                                        type="text",
                                        content=content,
                                        metadata={"is_reasoning": False}
                                    )

                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue

                    yield ChatChunk(type="done")

        except httpx.TimeoutException:
            yield ChatChunk(type="error", content=f"DeepSeek 请求超时（{timeout}秒）")
        except httpx.ConnectError:
            yield ChatChunk(type="error", content=f"无法连接到 DeepSeek ({self.base_url})")
        except Exception as e:
            yield ChatChunk(type="error", content=f"DeepSeek 调用错误: {str(e)}")


class ProviderManager:
    """
    Provider 管理器 -- 借鉴 Cherry Studio 的 ProviderRegistry
    单例模式，统一管理所有 LLM Provider 的创建、缓存和调用

    使用方式：
        manager = ProviderManager()
        async for chunk in manager.chat_stream(config, messages, system_prompt):
            print(chunk.content)
    """

    _instance = None
    _providers: Dict[int, LLMProvider] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_or_create_provider(self, model_config: AIModelConfig) -> LLMProvider:
        """
        获取或创建 Provider（带缓存）

        缓存策略：以 model_config.id 为 key
        当模型配置变更时，需要调用 clear_cache 清除缓存
        """
        cache_key = model_config.id

        if cache_key in self._providers:
            return self._providers[cache_key]

        # 根据 Provider 类型创建对应实例
        provider_type = (model_config.provider or "").lower()

        if provider_type in ["deepseek"]:
            provider = DeepSeekProvider(model_config)
        elif provider_type in ["openai_compatible", "openai", ""]:
            provider = OpenAICompatibleProvider(model_config)
        # 未来扩展：
        # elif provider_type == "anthropic":
        #     provider = AnthropicProvider(model_config)
        # elif provider_type == "azure":
        #     provider = AzureOpenAIProvider(model_config)
        # elif provider_type == "google":
        #     provider = GoogleGeminiProvider(model_config)
        else:
            # 默认使用 OpenAI 兼容格式（兼容性最好）
            provider = OpenAICompatibleProvider(model_config)

        self._providers[cache_key] = provider
        return provider

    def clear_cache(self, model_id: Optional[int] = None):
        """
        清除 Provider 缓存

        Args:
            model_id: 指定 model_id 清除单个缓存；为 None 时清除全部
        """
        if model_id:
            self._providers.pop(model_id, None)
        else:
            self._providers.clear()

    async def chat_stream(
        self,
        model_config: AIModelConfig,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncIterable[ChatChunk]:
        """
        统一入口：流式聊天

        Args:
            model_config: 模型配置对象
            messages: 消息列表
            system_prompt: 系统提示词
            **kwargs: 额外参数（temperature, max_tokens 等）

        Yields:
            ChatChunk: 流式数据块
        """
        provider = self.get_or_create_provider(model_config)
        async for chunk in provider.chat_stream(messages, system_prompt, **kwargs):
            yield chunk

    async def chat_complete(
        self,
        model_config: AIModelConfig,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> ChatChunk:
        """
        统一入口：非流式完整聊天

        Returns:
            ChatChunk: 完整响应（type="done", content=全部内容）
        """
        provider = self.get_or_create_provider(model_config)
        return await provider.chat_complete(messages, system_prompt, **kwargs)

    async def validate_provider(self, model_config: AIModelConfig) -> bool:
        """
        验证 Provider 配置是否可用

        Returns:
            bool: 配置是否有效
        """
        provider = self.get_or_create_provider(model_config)
        return await provider.validate()


# ---- 全局 Provider 管理器实例 ----
provider_manager = ProviderManager()
```

---

## 4. Chat Service 业务逻辑

### 文件：`app/services/chat_service.py`

```python
"""
聊天业务服务 -- 处理会话管理、消息存储、流式调用

核心职责：
1. 会话 CRUD（创建、查询、更新、软删除）
2. 消息持久化（用户消息 + AI 消息）
3. 流式聊天编排（调用 LLM + 实时更新数据库）
4. 内置助手管理（初始化预设助手）
"""

import uuid
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException

from app.models.ai_chat import ChatSession, ChatMessage, ChatAssistant
from app.models.ai_config import AIModelConfig
from app.services.llm_provider import provider_manager, ChatChunk


class ChatService:
    """聊天业务服务"""

    def __init__(self, db: Session):
        self.db = db

    # ============================================================
    # 会话管理
    # ============================================================

    def create_session(
        self,
        user_id: int,
        model_id: int,
        title: str = "新对话",
        assistant_id: Optional[str] = None
    ) -> ChatSession:
        """创建新会话"""
        session = ChatSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            model_id=model_id,
            title=title,
            assistant_id=assistant_id,
            status="active"
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: str, user_id: int) -> Optional[ChatSession]:
        """获取会话（带权限校验：只能查看自己的会话）"""
        return self.db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.status == "active"
        ).first()

    def get_session_by_id(self, session_id: str) -> Optional[ChatSession]:
        """根据 session_id 获取会话（不校验用户，内部使用）"""
        return self.db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()

    def list_sessions(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[List[ChatSession], int]:
        """
        获取会话列表（按更新时间倒序）

        Returns:
            (sessions, total): 会话列表和总数
        """
        query = self.db.query(ChatSession).filter(
            ChatSession.user_id == user_id,
            ChatSession.status == "active"
        ).order_by(desc(ChatSession.updated_at))

        total = query.count()
        sessions = query.offset((page - 1) * page_size).limit(page_size).all()
        return sessions, total

    def update_session_title(self, session_id: str, user_id: int, title: str) -> ChatSession:
        """更新会话标题"""
        session = self.get_session(session_id, user_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在或无权访问")
        session.title = title
        session.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)
        return session

    def update_session_model(self, session_id: str, user_id: int, model_id: int) -> ChatSession:
        """更新会话使用的模型"""
        session = self.get_session(session_id, user_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在或无权访问")
        session.model_id = model_id
        session.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)
        return session

    def delete_session(self, session_id: str, user_id: int):
        """删除会话（软删除）"""
        session = self.get_session(session_id, user_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在或无权访问")
        session.status = "deleted"
        session.updated_at = datetime.utcnow()
        self.db.commit()

    def archive_session(self, session_id: str, user_id: int):
        """归档会话"""
        session = self.get_session(session_id, user_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在或无权访问")
        session.status = "archived"
        session.updated_at = datetime.utcnow()
        self.db.commit()

    # ============================================================
    # 消息管理
    # ============================================================

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str = "",
        content_type: str = "text",
        status: str = "complete",
        metadata: Optional[Dict] = None
    ) -> ChatMessage:
        """
        添加消息到数据库

        同时自动更新会话的 message_count 和 last_message_at
        """
        message = ChatMessage(
            message_id=str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            content_type=content_type,
            status=status,
            metadata_json=metadata or {}
        )
        self.db.add(message)

        # 更新会话统计信息
        session = self.db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()
        if session:
            session.message_count += 1
            session.last_message_at = datetime.utcnow()
            session.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(message)
        return message

    def update_message_content(
        self,
        message_id: str,
        content: str,
        status: str = "complete",
        metadata: Optional[Dict] = None
    ) -> Optional[ChatMessage]:
        """更新消息内容（流式输出时实时更新）"""
        message = self.db.query(ChatMessage).filter(
            ChatMessage.message_id == message_id
        ).first()
        if message:
            message.content = content
            message.status = status
            if metadata:
                message.metadata_json = {**(message.metadata_json or {}), **metadata}
            self.db.commit()
            self.db.refresh(message)
        return message

    def update_message_metadata(self, message_id: str, metadata: Dict) -> Optional[ChatMessage]:
        """更新消息元数据（如 token 用量）"""
        message = self.db.query(ChatMessage).filter(
            ChatMessage.message_id == message_id
        ).first()
        if message:
            current = message.metadata_json or {}
            current.update(metadata)
            message.metadata_json = current
            self.db.commit()
            self.db.refresh(message)
        return message

    def get_message(self, message_id: str) -> Optional[ChatMessage]:
        """根据 message_id 获取单条消息"""
        return self.db.query(ChatMessage).filter(
            ChatMessage.message_id == message_id
        ).first()

    def get_messages(
        self,
        session_id: str,
        page: int = 1,
        page_size: int = 50
    ) -> List[ChatMessage]:
        """
        获取会话消息列表（按时间正序）

        Args:
            session_id: 会话 ID
            page: 页码（从 1 开始）
            page_size: 每页条数

        Returns:
            消息列表
        """
        return self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at).offset(
            (page - 1) * page_size
        ).limit(page_size).all()

    def get_recent_messages(
        self,
        session_id: str,
        limit: int = 20
    ) -> List[ChatMessage]:
        """获取最近的 N 条消息（用于构建上下文）"""
        return self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(desc(ChatMessage.created_at)).limit(limit).all()[::-1]  # 反转回正序

    # ============================================================
    # 流式聊天（核心方法）
    # ============================================================

    async def stream_chat(
        self,
        user_id: int,
        messages: List[Dict[str, str]],
        model_id: int,
        session_id: Optional[str] = None,
        assistant_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ):
        """
        流式聊天 -- 核心方法

        流程：
        1. 验证模型配置（存在性、可用性、API Key）
        2. 获取或创建会话
        3. 确定系统提示词（自定义 > 助手默认 > 全局默认）
        4. 保存用户消息到数据库
        5. 创建空的 AI 消息记录（streaming 状态）
        6. 调用 LLM 流式输出，实时更新 AI 消息内容
        7. 最终更新 AI 消息状态为 complete / error

        Yields:
            ChatChunk: 流式数据块（text / error / done）
        """

        # ---- 1. 获取并验证模型配置 ----
        model_config = self.db.query(AIModelConfig).filter(
            AIModelConfig.id == model_id,
            AIModelConfig.is_active == True
        ).first()

        if not model_config:
            yield ChatChunk(type="error", content="指定的模型不存在或未启用，请在系统管理中添加模型配置")
            return

        if not model_config.api_key:
            yield ChatChunk(
                type="error",
                content=f"模型 '{model_config.name}' 的 API Key 未配置，请联系管理员在 [系统管理 > AI 模型配置] 中设置"
            )
            return

        # ---- 2. 获取或创建会话 ----
        if session_id:
            session = self.get_session(session_id, user_id)
            if not session:
                yield ChatChunk(type="error", content="会话不存在或已被删除，请创建新会话")
                return
            current_session_id = session_id
        else:
            # 从助手获取默认标题
            title = "新对话"
            if assistant_id:
                assistant = self.db.query(ChatAssistant).filter(
                    ChatAssistant.assistant_id == assistant_id
                ).first()
                if assistant:
                    title = f"与 {assistant.name} 的对话"

            session = self.create_session(user_id, model_id, title, assistant_id)
            current_session_id = session.session_id

        # ---- 3. 确定系统提示词（优先级：自定义 > 助手默认 > 全局默认） ----
        final_system_prompt = system_prompt  # 用户自定义最高优先级

        if not final_system_prompt and assistant_id:
            assistant = self.db.query(ChatAssistant).filter(
                ChatAssistant.assistant_id == assistant_id
            ).first()
            if assistant:
                final_system_prompt = assistant.system_prompt

        if not final_system_prompt:
            final_system_prompt = (
                "你是 OmicHub AI 助手，一个专业的多组学数据分析助手。"
                "你精通 RNA-seq、单细胞转录组、蛋白质组学、代谢组学等领域的数据分析。"
                "请使用中文回答，保持专业性和准确性。"
            )

        # ---- 4. 保存用户消息 ----
        user_content = messages[-1].get("content", "") if messages else ""
        self.add_message(
            session_id=current_session_id,
            role="user",
            content=user_content,
            content_type="text",
            status="complete"
        )

        # ---- 5. 创建 AI 消息记录（初始 streaming 状态） ----
        ai_message = self.add_message(
            session_id=current_session_id,
            role="assistant",
            content="",
            content_type="text",
            status="streaming",
            metadata={
                "model": model_config.name,
                "model_id": model_id,
                "provider": model_config.provider
            }
        )

        # ---- 6. 调用 LLM 流式输出 ----
        full_content = ""
        update_counter = 0
        DB_UPDATE_INTERVAL = 5  # 每 5 个 chunk 更新一次数据库（减少 DB 压力）

        try:
            # 参数优先级：传入参数 > 模型配置参数 > 默认值
            final_temperature = temperature if temperature is not None else (
                model_config.parameters.get("temperature", 0.7)
                if hasattr(model_config, "parameters") and model_config.parameters
                else 0.7
            )
            final_max_tokens = max_tokens if max_tokens is not None else (
                model_config.parameters.get("max_tokens", 4096)
                if hasattr(model_config, "parameters") and model_config.parameters
                else 4096
            )

            async for chunk in provider_manager.chat_stream(
                model_config=model_config,
                messages=messages,
                system_prompt=final_system_prompt,
                temperature=final_temperature,
                max_tokens=final_max_tokens
            ):
                if chunk.type == "text":
                    full_content += chunk.content
                    update_counter += 1

                    # 定期更新数据库内容
                    if update_counter % DB_UPDATE_INTERVAL == 0:
                        self.update_message_content(
                            ai_message.message_id,
                            full_content,
                            status="streaming"
                        )

                    # 将 session_id 附加到第一个 chunk
                    if update_counter == 1:
                        chunk.metadata["session_id"] = current_session_id
                        chunk.metadata["message_id"] = ai_message.message_id

                elif chunk.type == "error":
                    # LLM 返回错误
                    self.update_message_content(
                        ai_message.message_id,
                        full_content or f"生成失败: {chunk.content}",
                        status="error",
                        metadata={"error": chunk.content}
                    )
                    yield chunk
                    return

                elif chunk.type == "done":
                    # 流结束，更新最终状态
                    self.update_message_content(
                        ai_message.message_id,
                        full_content,
                        status="complete"
                    )
                    # 附加 metadata
                    chunk.metadata["session_id"] = current_session_id
                    chunk.metadata["message_id"] = ai_message.message_id
                    yield chunk
                    return

                elif chunk.type == "tool_call":
                    # 工具调用（暂不处理，透传给前端）
                    pass

                yield chunk

        except Exception as e:
            # ---- 7. 异常处理：更新消息为错误状态 ----
            error_message = f"生成失败: {str(e)}"
            self.update_message_content(
                ai_message.message_id,
                full_content or error_message,
                status="error",
                metadata={"error": str(e), "error_type": type(e).__name__}
            )
            yield ChatChunk(
                type="error",
                content=error_message,
                metadata={"session_id": current_session_id, "message_id": ai_message.message_id}
            )

    async def chat_complete(
        self,
        user_id: int,
        messages: List[Dict[str, str]],
        model_id: int,
        session_id: Optional[str] = None,
        assistant_id: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        非流式完整聊天 -- 返回完整响应字符串

        适用于不需要实时展示的场景（如后台任务、自动摘要等）
        """
        full_content = ""
        async for chunk in self.stream_chat(
            user_id=user_id,
            messages=messages,
            model_id=model_id,
            session_id=session_id,
            assistant_id=assistant_id,
            system_prompt=system_prompt
        ):
            if chunk.type == "text":
                full_content += chunk.content
            elif chunk.type == "error":
                raise HTTPException(status_code=500, detail=chunk.content)
        return full_content

    # ============================================================
    # 助手管理
    # ============================================================

    def get_assistant(self, assistant_id: str) -> Optional[ChatAssistant]:
        """根据 assistant_id 获取助手"""
        return self.db.query(ChatAssistant).filter(
            ChatAssistant.assistant_id == assistant_id
        ).first()

    def init_builtin_assistants(self):
        """
        初始化内置助手（仅在表为空时执行）

        内置助手列表：
        - RNA-seq 分析师
        - 单细胞分析师
        - 代码助手
        - 文献助手
        - 通用助手
        """
        count = self.db.query(ChatAssistant).filter(
            ChatAssistant.is_builtin == True
        ).count()
        if count > 0:
            return  # 已初始化，跳过

        builtin_assistants = [
            ChatAssistant(
                assistant_id="rna_seq_analyst",
                name="RNA-seq 分析师",
                description="专注于 RNA-seq 差异表达分析、通路富集、可视化",
                system_prompt="""你是 OmicHub 的 RNA-seq 分析专家，精通差异表达分析全流程。

你可以帮助用户：
1. 设计 RNA-seq 分析流程（DESeq2 / edgeR / limma）
2. 解读差异表达结果（MA 图、火山图、热图）
3. 进行 GO / KEGG / GSEA 富集分析
4. 生成高质量的可视化图表
5. 解释生物学意义和实验设计

请使用专业但易懂的语言回答。在提供分析建议时，请给出具体的代码示例和参数解释。
注意：涉及统计检验时，请提醒用户注意多重检验校正（FDR）。""",
                default_temperature=0.3,
                default_max_tokens=4096,
                icon="\U0001F9EC",  # 🧬
                color="#4f8ef7",
                category="analysis",
                is_builtin=True
            ),
            ChatAssistant(
                assistant_id="scrna_analyst",
                name="单细胞分析师",
                description="专注于单细胞转录组分析、降维聚类、细胞注释",
                system_prompt="""你是 OmicHub 的单细胞转录组分析专家，精通 Scanpy 和 Seurat 分析流程。

你可以帮助用户：
1. 质控和过滤细胞（QC 指标解读：n_genes, n_counts, percent.mt 等）
2. 降维（PCA）和聚类分析（Louvain / Leiden）
3. 细胞类型自动注释和手动注释
4. 绘制 UMAP / t-SNE 图、小提琴图、气泡图
5. 伪时间分析和轨迹推断（Monocle / PAGA）
6. 细胞通讯分析（CellPhoneDB / CellChat）

请提供具体的代码示例和参数建议。推荐使用 Scanpy（Python）进行交互式分析。""",
                default_temperature=0.3,
                default_max_tokens=4096,
                icon="\U0001F52C",  # 🔬
                color="#e74c3c",
                category="analysis",
                is_builtin=True
            ),
            ChatAssistant(
                assistant_id="code_helper",
                name="代码助手",
                description="帮助编写和调试生信分析代码（Python / R）",
                system_prompt="""你是 OmicHub 的编程助手，精通生物信息学相关的 Python 和 R 代码。

你可以帮助用户：
1. 编写数据分析脚本（Scanpy / anndata / Bioconductor / tidyverse）
2. 调试代码错误（解释错误原因并提供修复方案）
3. 优化代码性能（向量化、并行计算、内存管理）
4. 解释代码逻辑（逐行注释和流程说明）

请提供完整可运行的代码，并添加详细的中文注释。
代码规范：
- 变量使用有意义的命名
- 关键步骤添加注释
- 提供示例数据和预期输出
- 标注 Python/R 版本要求""",
                default_temperature=0.2,
                default_max_tokens=4096,
                icon="\U0001F4BB",  # 💻
                color="#f39c12",
                category="code",
                is_builtin=True
            ),
            ChatAssistant(
                assistant_id="paper_reader",
                name="文献助手",
                description="帮助解读生物信息学文献和实验方法",
                system_prompt="""你是 OmicHub 的文献解读专家，精通生物信息学和基因组学领域的学术论文。

你可以帮助用户：
1. 总结文献核心内容（背景 / 方法 / 结果 / 结论）
2. 解释实验方法和分析流程（技术细节和参数设置）
3. 分析图表的含义和数据解读
4. 评估研究的创新性和局限性
5. 推荐相关文献和后续研究方向

请用中文回答，保持学术严谨性。
在分析时请：
- 指出研究的亮点和不足
- 对比同类研究的异同
- 评估结论的可靠性（样本量、统计方法等）
- 如果涉及方法学，解释其原理和适用范围""",
                default_temperature=0.5,
                default_max_tokens=4096,
                icon="\U0001F4C4",  # 📄
                color="#9b59b6",
                category="literature",
                is_builtin=True
            ),
            ChatAssistant(
                assistant_id="visualization",
                name="可视化助手",
                description="帮助创建和优化科研图表",
                system_prompt="""你是 OmicHub 的数据可视化专家，精通科研图表的制作和优化。

你可以帮助用户：
1. 推荐适合数据类型的图表类型
2. 优化图表的配色、布局和标注
3. 使用 matplotlib / seaborn / plotly 绘制图表
4. 遵循期刊投稿的图表规范
5. 提供 ggplot2 和 ComplexHeatmap 的 R 代码

图表规范：
- 使用期刊友好的配色方案
- 确保字体大小适中（一般 >= 8pt）
- 添加清晰的轴标签和图例
- 提供高分辨率导出方案（PDF / SVG / 300dpi PNG）""",
                default_temperature=0.3,
                default_max_tokens=4096,
                icon="\U0001F4CA",  # 📊
                color="#27ae60",
                category="visualization",
                is_builtin=True
            ),
            ChatAssistant(
                assistant_id="general",
                name="通用助手",
                description="OmicHub 通用 AI 助手，回答各类问题",
                system_prompt="""你是 OmicHub AI 助手，一个专业的多组学数据分析平台助手。

OmicHub 是一个专注于多组学数据分析的综合平台，支持：
- RNA-seq、单细胞、蛋白质组学、代谢组学等数据分析
- 差异表达分析、富集分析、聚类分析等
- 高质量科研图表生成
- 工作流管理和数据共享

你可以帮助用户：
1. 解答平台使用问题（功能介绍、操作指南）
2. 推荐合适的分析流程（根据数据类型和研究目的）
3. 解释生信概念和术语（用通俗语言）
4. 协助数据管理和项目规划

请友好、专业地回答用户的问题。如果不确定，请坦诚说明。""",
                default_temperature=0.7,
                default_max_tokens=2048,
                icon="\U0001F916",  # 🤖
                color="#4f8ef7",
                category="general",
                is_builtin=True
            )
        ]

        for assistant in builtin_assistants:
            self.db.add(assistant)

        self.db.commit()

    def list_assistants(
        self,
        user_id: int,
        category: Optional[str] = None
    ) -> List[ChatAssistant]:
        """
        获取助手列表

        Args:
            user_id: 当前用户 ID（用于过滤用户创建的助手）
            category: 分类筛选（analysis / visualization / literature / code / general）

        Returns:
            助手列表
        """
        query = self.db.query(ChatAssistant).filter(
            ChatAssistant.is_active == True
        )
        if category:
            query = query.filter(ChatAssistant.category == category)
        return query.order_by(ChatAssistant.created_at).all()

    def create_custom_assistant(
        self,
        user_id: int,
        assistant_id: str,
        name: str,
        description: str,
        system_prompt: str,
        default_model_id: Optional[int] = None,
        default_temperature: float = 0.3,
        default_max_tokens: int = 4096,
        icon: str = "\U0001F916",
        color: str = "#4f8ef7",
        category: str = "general"
    ) -> ChatAssistant:
        """创建自定义助手"""
        # 检查 assistant_id 是否已存在
        existing = self.db.query(ChatAssistant).filter(
            ChatAssistant.assistant_id == assistant_id
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"助手 ID '{assistant_id}' 已存在")

        assistant = ChatAssistant(
            assistant_id=assistant_id,
            name=name,
            description=description,
            system_prompt=system_prompt,
            default_model_id=default_model_id,
            default_temperature=default_temperature,
            default_max_tokens=default_max_tokens,
            icon=icon,
            color=color,
            category=category,
            is_builtin=False,
            is_active=True,
            created_by=user_id
        )
        self.db.add(assistant)
        self.db.commit()
        self.db.refresh(assistant)
        return assistant

    def delete_custom_assistant(self, assistant_id: str, user_id: int):
        """删除自定义助手（只能删除自己创建的）"""
        assistant = self.db.query(ChatAssistant).filter(
            ChatAssistant.assistant_id == assistant_id,
            ChatAssistant.is_builtin == False,
            ChatAssistant.created_by == user_id
        ).first()
        if not assistant:
            raise HTTPException(status_code=404, detail="助手不存在或无权删除")
        assistant.is_active = False
        self.db.commit()
```

---

## 5. FastAPI 路由

### 文件：`app/api/v1/chat.py`

```python
"""
聊天 API 路由
SSE 流式聊天 + 会话管理 + 助手管理 + 消息反馈

API 前缀：/api/v1/chat

接口列表：
- POST   /api/v1/chat/stream              SSE 流式聊天（核心接口）
- POST   /api/v1/chat/sessions            创建会话
- GET    /api/v1/chat/sessions            获取会话列表
- GET    /api/v1/chat/sessions/{id}/msgs  获取会话消息
- PUT    /api/v1/chat/sessions/{id}/title 更新会话标题
- DELETE /api/v1/chat/sessions/{id}       删除会话
- GET    /api/v1/chat/assistants          获取助手列表
- POST   /api/v1/chat/assistants          创建自定义助手
- POST   /api/v1/chat/feedback            消息反馈
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List
import json

from app.database import get_db
from app.auth import get_current_user, User
from app.schemas.chat import (
    ChatStreamRequest,
    ChatSessionResponse,
    ChatMessageResponse,
    CreateSessionRequest,
    MessageFeedbackRequest,
    ChatAssistantResponse
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["AI 聊天"])


# ============================================================
# SSE 流式聊天（核心接口）
# ============================================================

@router.post("/stream")
async def chat_stream(
    request: ChatStreamRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    SSE 流式聊天接口 -- 核心

    请求体示例：
    ```json
    {
        "messages": [
            {"role": "user", "content": "请帮我分析 RNA-seq 数据"}
        ],
        "model_id": 1,
        "session_id": null,
        "assistant_id": "rna_seq_analyst",
        "system_prompt": null
    }
    ```

    SSE 响应格式：
    ```
    data: {"type": "text", "content": "当", "session_id": "uuid", "message_id": "uuid"}\n\n
    data: {"type": "text", "content": "然"}\n\n
    data: {"type": "text", "content": "可"}\n\n
    data: {"type": "text", "content": "以"}\n\n
    data: {"type": "done", "session_id": "uuid", "message_id": "uuid"}\n\n
    ```

    错误响应：
    ```
    data: {"type": "error", "content": "模型配置错误..."}\n\n
    ```
    """
    chat_service = ChatService(db)

    async def generate_sse():
        """SSE 事件生成器"""
        first_chunk = True
        session_id_sent = None

        async for chunk in chat_service.stream_chat(
            user_id=current_user.id,
            messages=request.messages,
            model_id=request.model_id,
            session_id=request.session_id,
            assistant_id=request.assistant_id,
            system_prompt=request.system_prompt
        ):
            data = {
                "type": chunk.type,
                "content": chunk.content
            }

            # 将 session_id 和 message_id 附加到关键 chunk
            if chunk.metadata:
                if "session_id" in chunk.metadata:
                    data["session_id"] = chunk.metadata["session_id"]
                    session_id_sent = chunk.metadata["session_id"]
                if "message_id" in chunk.metadata:
                    data["message_id"] = chunk.metadata["message_id"]
                # 透传其他 metadata
                for key, value in chunk.metadata.items():
                    if key not in ("session_id", "message_id", "model") and value:
                        data[key] = value

            # 第一个 text chunk 必须包含 session_id（前端需要知道新会话 ID）
            if first_chunk and chunk.type == "text" and session_id_sent:
                first_chunk = False

            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

            if chunk.type == "done":
                break

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲，确保 SSE 实时推送
            "Content-Type": "text/event-stream"
        }
    )


# ============================================================
# 会话管理
# ============================================================

@router.post("/sessions", response_model=ChatSessionResponse)
def create_session(
    request: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建新会话"""
    chat_service = ChatService(db)
    session = chat_service.create_session(
        user_id=current_user.id,
        model_id=request.model_id,
        title=request.title,
        assistant_id=request.assistant_id
    )
    return session


@router.get("/sessions", response_model=List[ChatSessionResponse])
def list_sessions(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取会话列表（按更新时间倒序）"""
    chat_service = ChatService(db)
    sessions, total = chat_service.list_sessions(current_user.id, page, page_size)
    return sessions


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
def get_messages(
    session_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取会话消息列表

    权限校验：只能查看自己的会话消息
    """
    chat_service = ChatService(db)

    # 校验会话归属权
    session = chat_service.get_session(session_id, current_user.id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")

    return chat_service.get_messages(session_id, page, page_size)


@router.put("/sessions/{session_id}/title")
def update_session_title(
    session_id: str,
    title: str = Query(..., min_length=1, max_length=200, description="新标题"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新会话标题"""
    chat_service = ChatService(db)
    chat_service.update_session_title(session_id, current_user.id, title)
    return {"success": True, "message": "标题已更新"}


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除会话（软删除）"""
    chat_service = ChatService(db)
    chat_service.delete_session(session_id, current_user.id)
    return {"success": True, "message": "会话已删除"}


# ============================================================
# 助手管理
# ============================================================

@router.get("/assistants", response_model=List[ChatAssistantResponse])
def list_assistants(
    category: Optional[str] = Query(None, description="分类筛选：analysis / visualization / literature / code / general"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取助手列表

    首次调用时会自动初始化内置助手。
    可按分类筛选：analysis（分析）、visualization（可视化）、literature（文献）、code（代码）、general（通用）
    """
    chat_service = ChatService(db)
    # 首次调用时初始化内置助手（幂等操作）
    chat_service.init_builtin_assistants()
    return chat_service.list_assistants(current_user.id, category)


@router.get("/assistants/{assistant_id}", response_model=ChatAssistantResponse)
def get_assistant(
    assistant_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取单个助手详情"""
    chat_service = ChatService(db)
    chat_service.init_builtin_assistants()
    assistant = chat_service.get_assistant(assistant_id)
    if not assistant:
        raise HTTPException(status_code=404, detail="助手不存在")
    return assistant


@router.post("/assistants", response_model=ChatAssistantResponse)
def create_custom_assistant(
    request: dict,  # 使用 dict 简化，实际项目应定义专用 schema
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    创建自定义助手

    请求体：
    ```json
    {
        "assistant_id": "my_custom_bot",
        "name": "我的定制助手",
        "description": "描述",
        "system_prompt": "系统提示词...",
        "icon": "\U0001F916",
        "color": "#4f8ef7",
        "category": "general",
        "default_temperature": 0.3,
        "default_max_tokens": 4096
    }
    ```
    """
    chat_service = ChatService(db)
    assistant = chat_service.create_custom_assistant(
        user_id=current_user.id,
        assistant_id=request["assistant_id"],
        name=request["name"],
        description=request.get("description", ""),
        system_prompt=request["system_prompt"],
        default_model_id=request.get("default_model_id"),
        default_temperature=request.get("default_temperature", 0.3),
        default_max_tokens=request.get("default_max_tokens", 4096),
        icon=request.get("icon", "\U0001F916"),
        color=request.get("color", "#4f8ef7"),
        category=request.get("category", "general")
    )
    return assistant


# ============================================================
# 消息反馈
# ============================================================

@router.post("/feedback")
def message_feedback(
    request: MessageFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    消息反馈（点赞/点踩）

    用于收集用户反馈，后续可用于模型评估和优化。
    feedback 值："up" 表示点赞，"down" 表示点踩
    """
    # TODO: 实现反馈持久化存储（可存入新表 chat_message_feedback）
    # 示例实现：
    # from app.models.ai_chat import MessageFeedback
    # feedback = MessageFeedback(
    #     message_id=request.message_id,
    #     user_id=current_user.id,
    #     feedback=request.feedback,
    #     comment=request.comment
    # )
    # db.add(feedback)
    # db.commit()
    return {"success": True, "message": "反馈已记录"}
```

---

## 6. 数据库迁移脚本

### 文件：`migration/versions/V009__add_chat_system.py`

```python
"""
新增聊天系统表：chat_sessions, chat_messages, chat_assistants

对应 Cherry Studio 架构：
- chat_sessions  -> Topic（会话/话题）
- chat_messages  -> Message（消息）
- chat_assistants -> Assistant（助手）
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = 'V009'
down_revision = 'V008'  # 上一个迁移版本号
depends_on = None


def upgrade():
    # ============================================================
    # 1. chat_sessions 表 -- 聊天会话
    # ============================================================
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(50), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('assistant_id', sa.String(50), nullable=True),
        sa.Column('title', sa.String(200), server_default='\u65b0\u5bf9\u8bdd'),
        sa.Column('model_id', sa.Integer(), nullable=False),
        sa.Column('message_count', sa.Integer(), server_default='0'),
        sa.Column('total_tokens', sa.Integer(), server_default='0'),
        sa.Column('status', sa.String(20), server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id', name='pk_chat_sessions'),
        sa.UniqueConstraint('session_id', name='uq_chat_sessions_session_id')
    )
    op.create_index('idx_chat_sessions_user', 'chat_sessions', ['user_id'])
    op.create_index('idx_chat_sessions_assistant', 'chat_sessions', ['assistant_id'])
    op.create_index('idx_chat_sessions_user_updated', 'chat_sessions', ['user_id', 'updated_at'])
    op.create_index('idx_chat_sessions_status', 'chat_sessions', ['status'])

    # 外键约束（可选：根据项目实际情况决定是否添加）
    op.create_foreign_key(
        'fk_chat_sessions_user', 'chat_sessions', 'users',
        ['user_id'], ['id'], ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_chat_sessions_model', 'chat_sessions', 'ai_model_configs',
        ['model_id'], ['id'], ondelete='RESTRICT'
    )

    # ============================================================
    # 2. chat_messages 表 -- 聊天消息
    # ============================================================
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.String(50), nullable=False),
        sa.Column('session_id', sa.String(50), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), server_default=''),
        sa.Column('content_type', sa.String(20), server_default='text'),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('status', sa.String(20), server_default='complete'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id', name='pk_chat_messages'),
        sa.UniqueConstraint('message_id', name='uq_chat_messages_message_id')
    )
    op.create_index('idx_chat_messages_session', 'chat_messages', ['session_id'])
    op.create_index('idx_chat_messages_session_created', 'chat_messages', ['session_id', 'created_at'])
    op.create_index('idx_chat_messages_role', 'chat_messages', ['role'])
    op.create_index('idx_chat_messages_status', 'chat_messages', ['status'])

    op.create_foreign_key(
        'fk_chat_messages_session', 'chat_messages', 'chat_sessions',
        ['session_id'], ['session_id'], ondelete='CASCADE'
    )

    # ============================================================
    # 3. chat_assistants 表 -- AI 助手
    # ============================================================
    op.create_table(
        'chat_assistants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assistant_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('default_model_id', sa.Integer(), nullable=True),
        sa.Column('default_temperature', sa.Float(), server_default='0.3'),
        sa.Column('default_max_tokens', sa.Integer(), server_default='4096'),
        sa.Column('icon', sa.String(10), server_default='\U0001F916'),
        sa.Column('color', sa.String(20), server_default='#4f8ef7'),
        sa.Column('category', sa.String(50), server_default='general'),
        sa.Column('is_builtin', sa.Boolean(), server_default='false'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id', name='pk_chat_assistants'),
        sa.UniqueConstraint('assistant_id', name='uq_chat_assistants_assistant_id')
    )
    op.create_index('idx_chat_assistants_category', 'chat_assistants', ['category', 'is_active'])
    op.create_index('idx_chat_assistants_builtin', 'chat_assistants', ['is_builtin'])
    op.create_index('idx_chat_assistants_active', 'chat_assistants', ['is_active'])



def downgrade():
    """回滚迁移 -- 删除所有聊天系统表"""
    op.drop_index('idx_chat_assistants_active', table_name='chat_assistants')
    op.drop_index('idx_chat_assistants_builtin', table_name='chat_assistants')
    op.drop_index('idx_chat_assistants_category', table_name='chat_assistants')
    op.drop_table('chat_assistants')

    op.drop_index('idx_chat_messages_status', table_name='chat_messages')
    op.drop_index('idx_chat_messages_role', table_name='chat_messages')
    op.drop_index('idx_chat_messages_session_created', table_name='chat_messages')
    op.drop_index('idx_chat_messages_session', table_name='chat_messages')
    op.drop_table('chat_messages')

    op.drop_index('idx_chat_sessions_status', table_name='chat_sessions')
    op.drop_index('idx_chat_sessions_user_updated', table_name='chat_sessions')
    op.drop_index('idx_chat_sessions_assistant', table_name='chat_sessions')
    op.drop_index('idx_chat_sessions_user', table_name='chat_sessions')
    op.drop_table('chat_sessions')
```

---

## 7. 路由注册

### 文件：`app/main.py`（在现有路由注册处添加）

```python
from app.api.v1 import chat as chat_router

# ... 已有路由注册 ...

app.include_router(chat_router.router, prefix="/api/v1")
```

---

## 8. 依赖安装

在 `requirements.txt` 中确保包含以下依赖：

```txt
# 已有依赖
fastapi>=0.100.0
pydantic>=2.0.0
sqlalchemy>=2.0.0
alembic>=1.12.0
psycopg2-binary>=2.9.0
redis>=5.0.0
celery>=5.3.0

# 新增依赖
httpx>=0.25.0          # 异步 HTTP 客户端（替代 requests）
cryptography>=41.0.0   # API Key 加密
```

安装命令：

```bash
pip install httpx cryptography
```

---

## 9. 环境变量配置

在 `.env` 文件中添加：

```bash
# AI 配置加密密钥（生产环境必须设置，否则每次重启会重新生成）
AI_CONFIG_ENCRYPTION_KEY=your-32-byte-base64-encoded-key-here=

# 可选：默认模型配置
DEFAULT_CHAT_MODEL_ID=1
```

> **安全提示**：`AI_CONFIG_ENCRYPTION_KEY` 用于加密存储在数据库中的 API Key。生产环境必须在首次部署时设置固定值，否则每次服务重启都会重新生成密钥，导致已存储的加密 API Key 无法解密。

---

## 10. API 接口速查表

| 方法 | 路径 | 描述 |
|------|------|------|
| `POST` | `/api/v1/chat/stream` | SSE 流式聊天（核心） |
| `POST` | `/api/v1/chat/sessions` | 创建会话 |
| `GET` | `/api/v1/chat/sessions` | 获取会话列表 |
| `GET` | `/api/v1/chat/sessions/{id}/messages` | 获取会话消息 |
| `PUT` | `/api/v1/chat/sessions/{id}/title` | 更新会话标题 |
| `DELETE` | `/api/v1/chat/sessions/{id}` | 删除会话 |
| `GET` | `/api/v1/chat/assistants` | 获取助手列表 |
| `GET` | `/api/v1/chat/assistants/{id}` | 获取助手详情 |
| `POST` | `/api/v1/chat/assistants` | 创建自定义助手 |
| `POST` | `/api/v1/chat/feedback` | 消息反馈 |

---

## 11. 架构说明

```
+-------------------------------------------------+
|                  前端 (Vue 3)                    |
|  EventSource -> /api/v1/chat/stream (SSE)       |
+-------------------------------------------------+
                          |
+-------------------------------------------------+
|              FastAPI 后端                         |
|  +-------------------+  +---------------------+  |
|  | chat.py (Router)  |->| ChatService         |  |
|  | - /stream         |  | - stream_chat()     |  |
|  | - /sessions       |  | - session CRUD      |  |
|  | - /assistants     |  | - assistant manage  |  |
|  +-------------------+  +---------------------+  |
|                                   |               |
|                          +----------------+       |
|                          | ProviderManager |      |
|                          | (Singleton)     |      |
|                          +----------------+       |
|                                   |               |
|                    +--------------+               |
|                    |                              |
|  +------------------------+------------------+   |
|  | OpenAICompatibleProvider | DeepSeekProvider |  |
|  | - SSE parse             | - reasoning      |  |
|  | - error handling        | - DeepSeek API   |  |
|  +------------------------+------------------+   |
|                    |                              |
|  +-----------------+-------------------------+    |
|  | httpx.AsyncClient (async HTTP)           |    |
|  +------------------------------------------+    |
+-------------------------------------------------+
                          |
+-------------------------------------------------+
|            PostgreSQL + SQLAlchemy                |
|  chat_sessions | chat_messages | chat_assistants  |
+-------------------------------------------------+
```

### 核心设计决策

1. **SSE 流式输出**：使用 `StreamingResponse` + `text/event-stream` 实现真正的实时推送，前端通过 `EventSource` 接收
2. **Provider 管理器单例**：借鉴 Cherry Studio 的 ProviderRegistry，统一管理所有 LLM Provider，支持缓存和热更新
3. **OpenAI 兼容格式**：支持绝大多数国产模型（DeepSeek、Kimi、Qwen 等），只需配置 base_url 和 api_key
4. **内置助手系统**：5 个预设助手覆盖常见分析场景，支持用户创建自定义助手
5. **软删除机制**：会话使用 `status` 字段标记状态，保留数据可追溯性
6. **数据库索引优化**：针对高频查询场景（用户会话列表、会话消息）建立复合索引


---

# 第二部分：前端代码（Vue 3）

# OmicHub AI助手 — 前端完整代码（整合Cherry Studio架构）

> 将Cherry Studio的AI架构（流式输出、Provider管理、助手系统）整合到OmicHub的Vue 3前端。

---

## 文件清单

| 序号 | 文件 | 说明 |
|------|------|------|
| 1 | `composables/useChatStream.ts` | 聊天流式输出Composable（核心） |
| 2 | `components/MarkdownRenderer.vue` | Markdown渲染组件 |
| 3 | `components/ChatMessageItem.vue` | 聊天消息项组件 |
| 4 | `stores/llmModel.ts` | 模型管理Store |
| 5 | `stores/chatAssistant.ts` | 助手管理Store |

---

## 1. useChatStream Composable（核心！替代WebSocket方案）

**文件路径：** `src/composables/useChatStream.ts`

```typescript
// composables/useChatStream.ts
/**
 * 聊天流式输出 Composable - 借鉴Cherry Studio的流式架构
 * 使用EventSource(SSE)替代WebSocket，更适合AI流式输出场景
 */

import { ref, computed } from 'vue'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  status: 'pending' | 'streaming' | 'complete' | 'error' | 'stopped'
  contentType?: 'text' | 'markdown' | 'code' | 'tool_call' | 'error'
  metadata?: {
    model?: string
    tokens?: number
    toolCalls?: any[]
  }
  createdAt: Date
}

export interface StreamChunk {
  type: 'text' | 'tool_call' | 'error' | 'done'
  content: string
  metadata?: Record<string, any>
}

export function useChatStream() {
  // ==================== State ====================
  const messages = ref<ChatMessage[]>([])
  const status = ref<'idle' | 'submitting' | 'streaming' | 'error'>('idle')
  const error = ref<string | null>(null)
  const currentSessionId = ref<string | null>(null)
  const abortController = ref<AbortController | null>(null)

  // ==================== Getters ====================
  const isLoading = computed(() => status.value === 'submitting' || status.value === 'streaming')
  const isStreaming = computed(() => status.value === 'streaming')
  const canSend = computed(() => status.value === 'idle' || status.value === 'error')

  // 当前流式消息（正在生成的AI回复）
  const streamingMessage = computed(() => {
    const lastMsg = messages.value[messages.value.length - 1]
    return lastMsg?.status === 'streaming' ? lastMsg : null
  })

  // ==================== Actions ====================

  /**
   * 发送消息 - 核心方法
   * 借鉴Cherry Studio的Optimistic Update模式：
   * 1. 立即显示用户消息（不等待API）
   * 2. 立即显示空AI消息（streaming状态）
   * 3. 发起SSE请求
   * 4. 逐字接收并更新AI消息
   */
  async function sendMessage(
    content: string,
    options: {
      modelId: number
      assistantId?: string
      systemPrompt?: string
    }
  ) {
    if (!content.trim() || isLoading.value) return

    error.value = null

    // 1. 添加用户消息（Optimistic Update）
    const userMessage: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: content.trim(),
      status: 'complete',
      createdAt: new Date()
    }
    messages.value.push(userMessage)

    // 2. 添加AI消息（初始为空，streaming状态）
    const assistantMessage: ChatMessage = {
      id: generateId(),
      role: 'assistant',
      content: '',
      status: 'streaming',
      contentType: 'markdown',
      createdAt: new Date()
    }
    messages.value.push(assistantMessage)
    status.value = 'streaming'

    // 3. 构建消息历史（用于API上下文）
    const historyMessages = messages.value
      .filter(m => m.status === 'complete' || m.status === 'streaming')
      .map(m => ({ role: m.role, content: m.content }))

    // 4. 发起SSE请求
    abortController.value = new AbortController()

    try {
      const response = await fetch('/api/v1/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          messages: historyMessages,
          model_id: options.modelId,
          session_id: currentSessionId.value,
          assistant_id: options.assistantId,
          system_prompt: options.systemPrompt
        }),
        signal: abortController.value.signal
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }))
        throw new Error(errorData.detail || `请求失败: ${response.status}`)
      }

      // 5. 读取SSE流
      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      // 滚动到底部
      scrollToBottom()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue

          const dataStr = trimmed.slice(6)
          if (dataStr === '[DONE]') continue

          try {
            const data: StreamChunk = JSON.parse(dataStr)

            switch (data.type) {
              case 'text':
                // 追加内容
                assistantMessage.content += data.content
                assistantMessage.metadata = {
                  ...assistantMessage.metadata,
                  ...data.metadata
                }
                // 滚动跟随
                scrollToBottom()
                break

              case 'tool_call':
                assistantMessage.contentType = 'tool_call'
                assistantMessage.metadata = {
                  ...assistantMessage.metadata,
                  toolCalls: data.metadata?.tool_calls
                }
                break

              case 'error':
                assistantMessage.status = 'error'
                assistantMessage.contentType = 'error'
                assistantMessage.content = data.content
                status.value = 'error'
                error.value = data.content
                break

              case 'done':
                assistantMessage.status = 'complete'
                status.value = 'idle'
                // 保存会话ID（如果是新会话）
                if (data.metadata?.session_id) {
                  currentSessionId.value = data.metadata.session_id
                }
                break
            }
          } catch (e) {
            // 忽略解析错误（可能是心跳或空白行）
          }
        }
      }

      // 确保消息标记为完成（流正常结束但未收到done事件时兜底）
      if (assistantMessage.status === 'streaming') {
        assistantMessage.status = 'complete'
      }
      status.value = 'idle'

    } catch (err: any) {
      if (err.name === 'AbortError') {
        // 用户主动停止
        assistantMessage.status = 'stopped'
        assistantMessage.content += '\n\n*[已停止生成]*'
        status.value = 'idle'
      } else {
        // 真正的错误
        assistantMessage.status = 'error'
        assistantMessage.contentType = 'error'
        assistantMessage.content = `\u274c ${err.message}`
        status.value = 'error'
        error.value = err.message
      }
    } finally {
      abortController.value = null
    }
  }

  /**
   * 停止生成
   */
  function stopGeneration() {
    abortController.value?.abort()
  }

  /**
   * 加载会话历史
   */
  async function loadSession(sessionId: string) {
    try {
      const response = await fetch(`/api/v1/chat/sessions/${sessionId}/messages`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      })
      const data = await response.json()

      messages.value = data.map((m: any) => ({
        id: m.message_id,
        role: m.role,
        content: m.content,
        status: m.status,
        contentType: m.content_type,
        metadata: m.metadata_json,
        createdAt: new Date(m.created_at)
      }))

      currentSessionId.value = sessionId
    } catch (err: any) {
      error.value = `加载会话失败: ${err.message}`
    }
  }

  /**
   * 新建会话
   */
  function newSession() {
    messages.value = []
    currentSessionId.value = null
    status.value = 'idle'
    error.value = null
  }

  /**
   * 滚动到底部
   */
  function scrollToBottom() {
    setTimeout(() => {
      const container = document.querySelector('.message-list-container')
      if (container) {
        container.scrollTop = container.scrollHeight
      }
    }, 10)
  }

  // ==================== Return ====================
  return {
    // State
    messages,
    status,
    error,
    currentSessionId,
    // Getters
    isLoading,
    isStreaming,
    canSend,
    streamingMessage,
    // Actions
    sendMessage,
    stopGeneration,
    loadSession,
    newSession
  }
}

// ==================== 工具函数 ====================

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).substr(2)
}
```

### 依赖安装

```bash
npm install markdown-it highlight.js dompurify
npm install -D @types/markdown-it @types/dompurify
```

### 使用示例

```vue
<!-- views/AIChat.vue 中的使用方式 -->
<script setup lang="ts">
import { useChatStream } from '@/composables/useChatStream'
import { useLLMModelStore } from '@/stores/llmModel'
import { useChatAssistantStore } from '@/stores/chatAssistant'
import ChatMessageItem from '@/components/ChatMessageItem.vue'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'
import { storeToRefs } from 'pinia'
import { onMounted } from 'vue'

// ===== Composables & Stores =====
const chat = useChatStream()
const modelStore = useLLMModelStore()
const assistantStore = useChatAssistantStore()

const { currentModel } = storeToRefs(modelStore)
const { currentAssistant } = storeToRefs(assistantStore)

// ===== 发送消息 =====
const inputMessage = ref('')

async function handleSend() {
  if (!inputMessage.value.trim()) return
  if (!currentModel.value) {
    chat.error.value = '请先在模型设置中选择一个可用的AI模型'
    return
  }

  const content = inputMessage.value
  inputMessage.value = ''

  await chat.sendMessage(content, {
    modelId: currentModel.value.id,
    assistantId: currentAssistant.value?.assistantId,
    systemPrompt: currentAssistant.value?.systemPrompt
  })
}

// ===== 停止生成 =====
function handleStop() {
  chat.stopGeneration()
}

// ===== 初始化 =====
onMounted(() => {
  modelStore.init()
  assistantStore.fetchAssistants()
})
</script>
```

---

## 2. Markdown渲染组件

**文件路径：** `src/components/MarkdownRenderer.vue`

```vue
<!-- components/MarkdownRenderer.vue -->
<template>
  <div ref="container" class="markdown-body" v-html="renderedHtml" />
</template>

<script setup lang="ts">
import { computed, ref, onMounted, nextTick, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import DOMPurify from 'dompurify'
import 'highlight.js/styles/github-dark.css'

const props = defineProps<{
  content: string
}>()

const container = ref<HTMLDivElement>()

// ==================== Markdown渲染器配置 ====================
const md = new MarkdownIt({
  html: false,        // 安全：禁用HTML
  breaks: true,       // 换行转为<br>
  linkify: true,      // 自动链接
  typographer: true,  // 排版优化
  highlight: (code: string, lang: string) => {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<div class="code-block-wrapper">
          <div class="code-header">
            <span class="code-lang">${lang}</span>
            <button class="copy-btn" data-code="${encodeURIComponent(code)}">复制</button>
          </div>
          <pre class="hljs"><code>${hljs.highlight(code, { language: lang }).value}</code></pre>
        </div>`
      } catch (e) {
        // 高亮失败时回退
      }
    }
    return `<pre class="hljs"><code>${hljs.highlightAuto(code).value}</code></pre>`
  }
})

// ==================== 渲染 + XSS过滤 ====================
const rawHtml = computed(() => md.render(props.content || ''))
const renderedHtml = computed(() => {
  return DOMPurify.sanitize(rawHtml.value, {
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'em', 'del', 's', 'code', 'pre',
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'ul', 'ol', 'li', 'blockquote',
      'a', 'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
      'span', 'div', 'hr',
      'sup', 'sub', 'thead', 'tbody'
    ],
    ALLOWED_ATTR: [
      'href', 'src', 'alt', 'title', 'class', 'target',
      'data-code',  // 用于代码复制
      'rel'       // 用于链接安全
    ]
  })
})

// ==================== 绑定复制按钮事件 ====================
function bindCopyButtons() {
  if (!container.value) return

  const buttons = container.value.querySelectorAll('.copy-btn')
  buttons.forEach(btn => {
    // 避免重复绑定
    if (btn.hasAttribute('data-bound')) return
    btn.setAttribute('data-bound', 'true')

    btn.addEventListener('click', async () => {
      const code = decodeURIComponent(btn.getAttribute('data-code') || '')
      try {
        await navigator.clipboard.writeText(code)
        const originalText = btn.textContent || '复制'
        btn.textContent = '已复制!'
        btn.classList.add('copied')
        setTimeout(() => {
          btn.textContent = originalText
          btn.classList.remove('copied')
        }, 2000)
      } catch (err) {
        console.error('复制失败:', err)
      }
    })
  })
}

// 初始挂载 + content变化时重新绑定
onMounted(() => {
  nextTick(bindCopyButtons)
})

watch(() => props.content, () => {
  nextTick(bindCopyButtons)
})
</script>

<style scoped>
/* ==================== Markdown 正文样式 ==================== */
.markdown-body :deep(p) {
  margin: 8px 0;
  line-height: 1.75;
  color: var(--chat-text-primary, #e0e0e0);
}

.markdown-body :deep(pre) {
  margin: 12px 0;
  border-radius: 8px;
  overflow-x: auto;
}

.markdown-body :deep(code) {
  font-family: 'Fira Code', 'SF Mono', 'Courier New', monospace;
  font-size: 0.9em;
}

/* 行内代码 */
.markdown-body :deep(:not(pre) > code) {
  background: rgba(255, 255, 255, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
  color: #ff6b6b;
  word-break: break-word;
}

/* ==================== 代码块样式 ==================== */
.markdown-body :deep(.code-block-wrapper) {
  background: #1e1e2e;
  border-radius: 8px;
  overflow: hidden;
  margin: 12px 0;
  border: 1px solid #2a2a3c;
}

.markdown-body :deep(.code-header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: #2a2a3c;
  border-bottom: 1px solid #333;
}

.markdown-body :deep(.code-lang) {
  font-size: 12px;
  color: #888;
  text-transform: uppercase;
  font-weight: 500;
}

.markdown-body :deep(.copy-btn) {
  background: transparent;
  border: 1px solid #555;
  color: #aaa;
  padding: 2px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s ease;
}

.markdown-body :deep(.copy-btn:hover) {
  border-color: #4f8ef7;
  color: #4f8ef7;
  background: rgba(79, 142, 247, 0.1);
}

.markdown-body :deep(.copy-btn.copied) {
  border-color: #52c41a;
  color: #52c41a;
}

.markdown-body :deep(pre code) {
  display: block;
  padding: 16px;
  overflow-x: auto;
  line-height: 1.6;
  background: #1e1e2e !important;
}

/* ==================== 标题样式 ==================== */
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  margin: 20px 0 12px;
  color: var(--chat-text-primary, #e0e0e0);
  font-weight: 600;
  line-height: 1.4;
}

.markdown-body :deep(h1) { font-size: 1.6em; border-bottom: 1px solid #333; padding-bottom: 8px; }
.markdown-body :deep(h2) { font-size: 1.4em; border-bottom: 1px solid #333; padding-bottom: 6px; }
.markdown-body :deep(h3) { font-size: 1.2em; }
.markdown-body :deep(h4) { font-size: 1.1em; }

/* ==================== 链接样式 ==================== */
.markdown-body :deep(a) {
  color: #4f8ef7;
  text-decoration: none;
  transition: opacity 0.2s;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
  opacity: 0.9;
}

/* ==================== 列表样式 ==================== */
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 24px;
  margin: 8px 0;
}

.markdown-body :deep(li) {
  margin: 4px 0;
  line-height: 1.6;
}

.markdown-body :deep(ul) { list-style-type: disc; }
.markdown-body :deep(ol) { list-style-type: decimal; }

.markdown-body :deep(li > ul),
.markdown-body :deep(li > ol) {
  margin: 2px 0;
}

/* ==================== 引用块 ==================== */
.markdown-body :deep(blockquote) {
  border-left: 3px solid #4f8ef7;
  padding-left: 16px;
  margin: 12px 0;
  color: #aaa;
  background: rgba(79, 142, 247, 0.05);
  padding: 12px 16px;
  border-radius: 0 6px 6px 0;
}

/* ==================== 表格样式 ==================== */
.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  border-radius: 6px;
  overflow: hidden;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #333;
  padding: 8px 12px;
  text-align: left;
}

.markdown-body :deep(th) {
  background: #2a2a3c;
  font-weight: 600;
  color: #ccc;
}

.markdown-body :deep(tr:nth-child(even)) {
  background: rgba(255, 255, 255, 0.02);
}

/* ==================== 分隔线 ==================== */
.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid #333;
  margin: 16px 0;
}

/* ==================== 图片 ==================== */
.markdown-body :deep(img) {
  max-width: 100%;
  border-radius: 6px;
  margin: 8px 0;
}

/* ==================== 水平线 ==================== */
.markdown-body :deep(del),
.markdown-body :deep(s) {
  color: #888;
}

/* ==================== 公式相关 ==================== */
.markdown-body :deep(sup),
.markdown-body :deep(sub) {
  font-size: 0.75em;
}
</style>
```

### 依赖安装

```bash
npm install markdown-it highlight.js dompurify
npm install -D @types/markdown-it @types/dompurify
```

---

## 3. 聊天消息项组件

**文件路径：** `src/components/ChatMessageItem.vue`

```vue
<!-- components/ChatMessageItem.vue -->
<template>
  <div class="message-item" :class="message.role">
    <!-- ====== AI消息头部 ====== -->
    <div v-if="message.role === 'assistant'" class="ai-header">
      <img src="/omic-logo.svg" class="ai-avatar" alt="AI" />
      <span class="ai-name">OmicHub AI</span>
      <span v-if="message.metadata?.model" class="ai-model-tag">
        {{ message.metadata.model }}
      </span>
    </div>

    <!-- ====== 消息内容区域 ====== -->
    <div class="message-bubble" :class="message.role">
      <!-- 加载中动画 -->
      <div v-if="message.status === 'pending'" class="typing-indicator">
        <span class="dot"></span>
        <span class="dot"></span>
        <span class="dot"></span>
      </div>

      <!-- 错误消息 -->
      <n-alert
        v-else-if="message.contentType === 'error' || message.status === 'error'"
        type="error"
        :bordered="false"
        class="error-alert"
      >
        {{ message.content }}
      </n-alert>

      <!-- Tool Call展示 -->
      <div v-else-if="message.contentType === 'tool_call'" class="tool-call-display">
        <div class="tool-call-header">
          <n-icon size="16"><BuildOutline /></n-icon>
          <span>正在调用工具...</span>
        </div>
        <pre v-if="message.metadata?.toolCalls" class="tool-call-detail">{{
          JSON.stringify(message.metadata.toolCalls, null, 2)
        }}</pre>
      </div>

      <!-- Markdown内容（AI消息默认使用Markdown） -->
      <div v-else-if="message.role === 'assistant' && message.content">
        <MarkdownRenderer :content="message.content" />
      </div>

      <!-- 纯文本（用户消息） -->
      <div v-else class="text-content">{{ message.content }}</div>
    </div>

    <!-- ====== 流式生成中的光标闪烁 ====== -->
    <div
      v-if="message.status === 'streaming'"
      class="streaming-cursor"
    >
      <span class="cursor-blink">|</span>
    </div>

    <!-- ====== 消息操作栏（仅AI已完成的完整消息） ====== -->
    <div
      v-if="message.role === 'assistant' && message.status === 'complete'"
      class="message-actions"
    >
      <n-button text size="tiny" @click="handleCopy(message.content)">
        <template #icon><n-icon size="14"><CopyOutline /></n-icon></template>
        复制
      </n-button>
      <n-button text size="tiny" @click="$emit('feedback', message.id, 'up')">
        <template #icon><n-icon size="14"><ThumbsUpOutline /></n-icon></template>
      </n-button>
      <n-button text size="tiny" @click="$emit('feedback', message.id, 'down')">
        <template #icon><n-icon size="14"><ThumbsDownOutline /></n-icon></template>
      </n-button>
      <n-button text size="tiny" @click="$emit('regenerate')">
        <template #icon><n-icon size="14"><RefreshOutline /></n-icon></template>
        重新生成
      </n-button>
    </div>

    <!-- ====== 已停止提示 ====== -->
    <div v-if="message.status === 'stopped'" class="stopped-notice">
      <n-icon size="12"><StopCircleOutline /></n-icon>
      <span>生成已停止</span>
    </div>

    <!-- ====== 用户消息时间戳 ====== -->
    <div v-if="message.role === 'user'" class="message-timestamp">
      {{ formatTime(message.createdAt) }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { CopyOutline, ThumbsUpOutline, ThumbsDownOutline, RefreshOutline, BuildOutline, StopCircleOutline } from '@vicons/ionicons5'
import { useMessage } from 'naive-ui'
import MarkdownRenderer from './MarkdownRenderer.vue'
import type { ChatMessage } from '@/composables/useChatStream'

// ===== 类型定义 =====
const props = defineProps<{
  message: ChatMessage
}>()

const emit = defineEmits<{
  copy: [content: string]
  feedback: [messageId: string, type: 'up' | 'down']
  regenerate: []
}>()

// ===== Naive UI 消息提示 =====
const naiveMessage = useMessage()

// ===== 复制功能 =====
async function handleCopy(content: string) {
  try {
    await navigator.clipboard.writeText(content)
    naiveMessage.success('已复制到剪贴板')
  } catch (err) {
    naiveMessage.error('复制失败')
    console.error('复制失败:', err)
  }
}

// ===== 时间格式化 =====
function formatTime(date: Date): string {
  const now = new Date()
  const d = new Date(date)
  const isToday = d.toDateString() === now.toDateString()

  const pad = (n: number) => n.toString().padStart(2, '0')
  const time = `${pad(d.getHours())}:${pad(d.getMinutes())}`

  if (isToday) return time
  return `${d.getMonth() + 1}/${d.getDate()} ${time}`
}
</script>

<style scoped>
/* ==================== 消息项基础 ==================== */
.message-item {
  padding: 12px 20px;
  animation: messageSlideIn 0.3s ease-out;
  position: relative;
}

@keyframes messageSlideIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ==================== AI消息 ==================== */
.message-item.assistant {
  background: transparent;
}

/* AI消息头部 */
.ai-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  padding-left: 36px;
}

.ai-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  position: absolute;
  left: 20px;
  top: 14px;
  background: #1a1a2e;
  border: 1px solid #2a2a3c;
}

.ai-name {
  font-size: 13px;
  font-weight: 500;
  color: #4f8ef7;
}

.ai-model-tag {
  font-size: 11px;
  color: #888;
  background: #1e1e2e;
  padding: 1px 8px;
  border-radius: 10px;
  border: 1px solid #2a2a3c;
  margin-left: 4px;
}

/* ==================== 用户消息 ==================== */
.message-item.user {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.message-bubble.user {
  background: #2a2a3c;
  padding: 10px 16px;
  border-radius: 12px 12px 2px 12px;
  max-width: 80%;
  color: #e0e0e0;
  line-height: 1.75;
  word-break: break-word;
  white-space: pre-wrap;
}

/* ==================== AI消息气泡 ==================== */
.message-bubble.assistant {
  padding-left: 36px;  /* 给头像留空间 */
  color: #e0e0e0;
}

/* ==================== 纯文本内容 ==================== */
.text-content {
  white-space: pre-wrap;
  word-break: break-word;
  color: #e0e0e0;
  line-height: 1.75;
}

/* ==================== 打字机动画 ==================== */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 8px 0;
  align-items: center;
}

.typing-indicator .dot {
  width: 8px;
  height: 8px;
  background: #4f8ef7;
  border-radius: 50%;
  animation: typingBounce 1.4s infinite ease-in-out both;
}

.typing-indicator .dot:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator .dot:nth-child(2) { animation-delay: -0.16s; }
.typing-indicator .dot:nth-child(3) { animation-delay: 0s; }

@keyframes typingBounce {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

/* ==================== 流式光标闪烁 ==================== */
.streaming-cursor {
  padding-left: 36px;
  margin-top: -4px;
}

.cursor-blink {
  color: #4f8ef7;
  font-weight: 300;
  animation: blink 0.8s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* ==================== 消息操作栏 ==================== */
.message-actions {
  display: flex;
  gap: 4px;
  margin-top: 8px;
  padding-left: 36px;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.message-item:hover .message-actions {
  opacity: 1;
}

/* ==================== 错误提示 ==================== */
.error-alert {
  max-width: 80%;
  border-radius: 8px;
}

/* ==================== Tool Call 展示 ==================== */
.tool-call-display {
  padding-left: 36px;
}

.tool-call-header {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #4f8ef7;
  font-size: 13px;
  margin-bottom: 8px;
}

.tool-call-detail {
  background: #1e1e2e;
  border: 1px solid #2a2a3c;
  border-radius: 6px;
  padding: 10px 12px;
  font-size: 12px;
  color: #aaa;
  overflow-x: auto;
  max-height: 200px;
}

/* ==================== 已停止提示 ==================== */
.stopped-notice {
  display: flex;
  align-items: center;
  gap: 4px;
  padding-left: 36px;
  margin-top: 8px;
  font-size: 12px;
  color: #888;
}

/* ==================== 时间戳 ==================== */
.message-timestamp {
  font-size: 11px;
  color: #666;
  margin-top: 4px;
  margin-right: 4px;
}

/* ==================== 响应式适配 ==================== */
@media (max-width: 768px) {
  .message-bubble.user {
    max-width: 90%;
  }

  .message-actions {
    opacity: 1;  /* 移动端始终显示操作按钮 */
  }

  .message-item {
    padding: 10px 12px;
  }
}
</style>
```

---

## 4. 模型管理Store

**文件路径：** `src/stores/llmModel.ts`

```typescript
// stores/llmModel.ts
/**
 * LLM模型管理Store - 借鉴Cherry Studio的Provider管理
 * 统一管理所有AI模型配置，替代写死的"K2.6快速"
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

// ==================== 类型定义 ====================

export type ProviderType = 'openai_compatible' | 'anthropic' | 'azure' | 'google' | 'cohere' | 'deepseek' | 'moonshot'

export interface LLMModelConfig {
  id: number
  name: string              // 显示名（如"Kimi"、"GPT-4"）
  provider: ProviderType    // Provider类型
  model: string             // 模型ID（如"moonshot-v1-128k"）
  baseUrl: string           // API基础URL
  apiKey?: string           // API密钥（前端不存储，仅用于展示）
  isActive: boolean         // 是否启用
  isDefault: boolean        // 是否为默认模型
  description?: string      // 模型描述
  tags?: string[]           // 标签（如 ["128K", "多模态"]）
  parameters: {
    temperature: number
    maxTokens: number
    topP: number
    timeout: number          // 超时时间（秒）
  }
  createdAt?: string
  updatedAt?: string
}

export interface CreateModelPayload {
  name: string
  provider: ProviderType
  model: string
  base_url: string
  api_key: string
  description?: string
  parameters?: {
    temperature?: number
    max_tokens?: number
    top_p?: number
    timeout?: number
  }
  is_default?: boolean
}

// ==================== Store ====================

export const useLLMModelStore = defineStore('llmModel', () => {

  // ==================== State ====================
  const models = ref<LLMModelConfig[]>([])
  const currentModelId = ref<number | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // ==================== Getters ====================

  /** 当前选中的模型 */
  const currentModel = computed(() => {
    return models.value.find(m => m.id === currentModelId.value)
  })

  /** 所有启用的模型 */
  const activeModels = computed(() => {
    return models.value.filter(m => m.isActive)
  })

  /** Naive UI dropdown 选项格式 */
  const dropdownOptions = computed(() => {
    return activeModels.value.map(m => ({
      label: m.name,
      key: m.id,
      disabled: !m.isActive,
      modelId: m.model,
      isDefault: m.isDefault,
      description: m.description,
      tags: m.tags || []
    }))
  })

  /** 模型选择器渲染选项 */
  const selectOptions = computed(() => {
    return activeModels.value.map(m => ({
      label: m.name,
      value: m.id,
      disabled: !m.isActive
    }))
  })

  /** 默认模型 */
  const defaultModel = computed(() => {
    return models.value.find(m => m.isDefault && m.isActive) || activeModels.value[0]
  })

  /** 按Provider分组 */
  const modelsByProvider = computed(() => {
    const groups: Record<string, LLMModelConfig[]> = {}
    activeModels.value.forEach(m => {
      const key = m.provider
      if (!groups[key]) groups[key] = []
      groups[key].push(m)
    })
    return groups
  })

  // ==================== Actions ====================

  /**
   * 获取模型列表
   */
  async function fetchModels() {
    loading.value = true
    error.value = null
    try {
      const response = await fetch('/api/v1/ai/models', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      })

      if (!response.ok) {
        throw new Error(`获取模型列表失败: ${response.status}`)
      }

      const data = await response.json()
      models.value = data.data || []

      // 恢复上次选择的模型，或选择默认模型
      const saved = localStorage.getItem('omic_current_model')
      if (saved) {
        const savedId = Number(saved)
        const exists = models.value.find(m => m.id === savedId && m.isActive)
        if (exists) {
          currentModelId.value = savedId
        } else {
          currentModelId.value = defaultModel.value?.id || null
        }
      } else {
        currentModelId.value = defaultModel.value?.id || null
      }
    } catch (err: any) {
      error.value = err.message
      console.error('获取模型列表失败:', err)
      // 加载失败时使用默认数据（仅展示用）
      models.value = getDefaultModels()
      currentModelId.value = models.value[0]?.id || null
    } finally {
      loading.value = false
    }
  }

  /**
   * 创建新模型
   */
  async function createModel(payload: CreateModelPayload) {
    loading.value = true
    error.value = null
    try {
      const response = await fetch('/api/v1/ai/models', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(payload)
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }))
        throw new Error(errorData.detail || '创建模型失败')
      }

      const data = await response.json()
      // 重新拉取列表
      await fetchModels()
      return data
    } catch (err: any) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 更新模型
   */
  async function updateModel(modelId: number, payload: Partial<CreateModelPayload>) {
    loading.value = true
    error.value = null
    try {
      const response = await fetch(`/api/v1/ai/models/${modelId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(payload)
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }))
        throw new Error(errorData.detail || '更新模型失败')
      }

      await fetchModels()
    } catch (err: any) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 删除模型
   */
  async function deleteModel(modelId: number) {
    loading.value = true
    error.value = null
    try {
      const response = await fetch(`/api/v1/ai/models/${modelId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      })

      if (!response.ok) {
        throw new Error(`删除模型失败: ${response.status}`)
      }

      // 如果删除的是当前选中的模型，清除选择
      if (currentModelId.value === modelId) {
        currentModelId.value = defaultModel.value?.id || null
      }

      await fetchModels()
    } catch (err: any) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 切换当前模型
   */
  function switchModel(modelId: number) {
    currentModelId.value = modelId
    localStorage.setItem('omic_current_model', String(modelId))
  }

  /**
   * 测试模型连接
   */
  async function testModel(modelId: number): Promise<{ success: boolean; latency: number; message?: string }> {
    try {
      const startTime = Date.now()
      const response = await fetch(`/api/v1/ai/models/${modelId}/test`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      })

      const latency = Date.now() - startTime

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        return {
          success: false,
          latency,
          message: errorData.detail || '连接测试失败'
        }
      }

      return {
        success: true,
        latency,
        message: `连接成功，延迟 ${latency}ms`
      }
    } catch (err: any) {
      return {
        success: false,
        latency: -1,
        message: err.message || '网络错误'
      }
    }
  }

  /**
   * 初始化
   */
  function init() {
    fetchModels()
  }

  /**
   * 清除错误
   */
  function clearError() {
    error.value = null
  }

  // ==================== Return ====================
  return {
    // State
    models,
    currentModelId,
    loading,
    error,
    // Getters
    currentModel,
    activeModels,
    dropdownOptions,
    selectOptions,
    defaultModel,
    modelsByProvider,
    // Actions
    fetchModels,
    createModel,
    updateModel,
    deleteModel,
    switchModel,
    testModel,
    init,
    clearError
  }
})

// ==================== 默认模型（加载失败时备用） ====================
function getDefaultModels(): LLMModelConfig[] {
  return [
    {
      id: 1,
      name: 'Kimi K2',
      provider: 'moonshot',
      model: 'moonshot-v1-128k',
      baseUrl: 'https://api.moonshot.cn/v1',
      isActive: true,
      isDefault: true,
      description: 'Moonshot Kimi 大模型',
      tags: ['128K'],
      parameters: {
        temperature: 0.7,
        maxTokens: 4096,
        topP: 1.0,
        timeout: 60
      }
    },
    {
      id: 2,
      name: 'GPT-4o',
      provider: 'openai_compatible',
      model: 'gpt-4o',
      baseUrl: 'https://api.openai.com/v1',
      isActive: true,
      isDefault: false,
      description: 'OpenAI GPT-4o',
      tags: ['128K', '多模态'],
      parameters: {
        temperature: 0.7,
        maxTokens: 4096,
        topP: 1.0,
        timeout: 60
      }
    }
  ]
}
```

---

## 5. 助手管理Store

**文件路径：** `src/stores/chatAssistant.ts`

```typescript
// stores/chatAssistant.ts
/**
 * AI助手管理Store - 借鉴Cherry Studio的助手系统
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

// ==================== 类型定义 ====================

export interface ChatAssistant {
  assistantId: string
  name: string
  description: string
  systemPrompt: string
  defaultModelId: number | null
  defaultTemperature: number
  defaultMaxTokens: number
  icon: string           // Lucide/ionicons5 图标名
  color: string          // 主题色（hex）
  category: string       // 分类（如"通用"、"学术"、"编程"）
  isBuiltin: boolean     // 是否为内置助手
  isActive: boolean
  sortOrder?: number     // 排序
  createdAt?: string
  updatedAt?: string
}

export interface CreateAssistantPayload {
  name: string
  description: string
  system_prompt: string
  default_model_id?: number
  default_temperature?: number
  default_max_tokens?: number
  icon?: string
  color?: string
  category?: string
}

// ==================== 内置助手配置 ====================

const BUILTIN_ASSISTANTS: ChatAssistant[] = [
  {
    assistantId: 'general',
    name: '通用助手',
    description: '全能型AI助手，适用于日常对话、问答、写作等多种场景',
    systemPrompt: 'You are a helpful AI assistant. Answer questions accurately and concisely. If you are unsure about something, say so.',
    defaultModelId: null,
    defaultTemperature: 0.7,
    defaultMaxTokens: 4096,
    icon: 'ChatbubblesOutline',
    color: '#4f8ef7',
    category: '通用',
    isBuiltin: true,
    isActive: true,
    sortOrder: 0
  },
  {
    assistantId: 'code_expert',
    name: '代码专家',
    description: '专注于编程、代码审查、算法设计和调试的AI助手',
    systemPrompt: 'You are an expert programmer and software engineer. Provide clean, well-documented code with explanations. Follow best practices and consider edge cases. Use markdown code blocks for all code.',
    defaultModelId: null,
    defaultTemperature: 0.3,
    defaultMaxTokens: 8192,
    icon: 'CodeSlashOutline',
    color: '#52c41a',
    category: '编程',
    isBuiltin: true,
    isActive: true,
    sortOrder: 0
  },
  {
    assistantId: 'academic',
    name: '学术研究',
    description: '帮助文献阅读、论文写作、研究方法论和学术翻译',
    systemPrompt: 'You are an academic research assistant. Help with literature review, paper writing, research methodology, and academic translation. Use formal academic language and provide references when possible. Always cite sources when referencing specific research.',
    defaultModelId: null,
    defaultTemperature: 0.5,
    defaultMaxTokens: 4096,
    icon: 'SchoolOutline',
    color: '#722ed1',
    category: '学术',
    isBuiltin: true,
    isActive: true,
    sortOrder: 0
  },
  {
    assistantId: 'translator',
    name: '翻译专家',
    description: '专业翻译助手，支持中英互译和多语言翻译',
    systemPrompt: 'You are a professional translator. Provide accurate and natural translations. Preserve the original meaning and tone. For technical terms, provide both the translation and the original term in parentheses.',
    defaultModelId: null,
    defaultTemperature: 0.3,
    defaultMaxTokens: 4096,
    icon: 'LanguageOutline',
    color: '#faad14',
    category: '工具',
    isBuiltin: true,
    isActive: true,
    sortOrder: 1
  },
  {
    assistantId: 'data_analyst',
    name: '数据分析师',
    description: '数据分析、可视化、统计方法和Python/R代码生成',
    systemPrompt: 'You are a data analysis expert. Help with data cleaning, visualization, statistical analysis, and generating Python/R code. Explain your analysis approach clearly and provide actionable insights. Use pandas, matplotlib, seaborn, or plotly for Python examples.',
    defaultModelId: null,
    defaultTemperature: 0.3,
    defaultMaxTokens: 4096,
    icon: 'BarChartOutline',
    color: '#eb2f96',
    category: '数据分析',
    isBuiltin: true,
    isActive: true,
    sortOrder: 0
  },
  {
    assistantId: 'creative_writer',
    name: '创意写作',
    description: '故事创作、文案撰写、诗歌和创意内容生成',
    systemPrompt: 'You are a creative writing assistant. Help with storytelling, copywriting, poetry, and content generation. Be imaginative, use vivid language, and adapt to different styles and genres as requested.',
    defaultModelId: null,
    defaultTemperature: 0.9,
    defaultMaxTokens: 4096,
    icon: 'ColorWandOutline',
    color: '#ff4d4f',
    category: '创作',
    isBuiltin: true,
    isActive: true,
    sortOrder: 0
  },
  {
    assistantId: 'bioinformatics',
    name: '生信分析',
    description: '生物信息学专用助手，支持基因组学、转录组学和蛋白质组学分析',
    systemPrompt: 'You are a bioinformatics expert specializing in genomics, transcriptomics, and proteomics. Help with sequence analysis, differential expression, pathway enrichment, and R/Python code for bioinformatics pipelines. Use Bioconductor tools (DESeq2, edgeR, limma) for R, and scanpy/biopython for Python examples.',
    defaultModelId: null,
    defaultTemperature: 0.3,
    defaultMaxTokens: 8192,
    icon: 'FlaskOutline',
    color: '#13c2c2',
    category: '学术',
    isBuiltin: true,
    isActive: true,
    sortOrder: 1
  }
]

// ==================== Store ====================

export const useChatAssistantStore = defineStore('chatAssistant', () => {

  // ==================== State ====================
  const assistants = ref<ChatAssistant[]>([...BUILTIN_ASSISTANTS])
  const currentAssistantId = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // ==================== Getters ====================

  /** 当前选中的助手 */
  const currentAssistant = computed(() => {
    return assistants.value.find(a => a.assistantId === currentAssistantId.value)
  })

  /** 按分类分组的助手 */
  const groupedAssistants = computed(() => {
    const groups: Record<string, ChatAssistant[]> = {}
    assistants.value
      .filter(a => a.isActive)
      .sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0))
      .forEach(a => {
        if (!groups[a.category]) groups[a.category] = []
        groups[a.category].push(a)
      })
    return groups
  })

  /** 分类列表（有序） */
  const categories = computed(() => {
    const seen = new Set<string>()
    assistants.value
      .filter(a => a.isActive)
      .forEach(a => seen.add(a.category))
    return Array.from(seen)
  })

  /** 获取助手名称（用于展示） */
  const getAssistantName = computed(() => {
    return (assistantId: string) => {
      const a = assistants.value.find(item => item.assistantId === assistantId)
      return a?.name || '通用助手'
    }
  })

  /** 获取助手图标和颜色 */
  const getAssistantStyle = computed(() => {
    return (assistantId: string) => {
      const a = assistants.value.find(item => item.assistantId === assistantId)
      return {
        icon: a?.icon || 'ChatbubblesOutline',
        color: a?.color || '#4f8ef7'
      }
    }
  })

  // ==================== Actions ====================

  /**
   * 获取助手列表（从API + 合并内置）
   */
  async function fetchAssistants() {
    loading.value = true
    error.value = null
    try {
      const response = await fetch('/api/v1/chat/assistants', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      })

      if (!response.ok) {
        throw new Error(`获取助手列表失败: ${response.status}`)
      }

      const data = await response.json()
      const apiAssistants: ChatAssistant[] = (data.data || []).map((a: any) => ({
        ...a,
        isBuiltin: false
      }))

      // 合并内置助手和API助手（API助手可覆盖内置）
      const builtinIds = new Set(BUILTIN_ASSISTANTS.map(a => a.assistantId))
      const uniqueApiAssistants = apiAssistants.filter((a: ChatAssistant) => !builtinIds.has(a.assistantId))

      assistants.value = [...BUILTIN_ASSISTANTS, ...uniqueApiAssistants]

      // 恢复上次选择，或默认选择通用助手
      const saved = localStorage.getItem('omic_current_assistant')
      if (saved) {
        const exists = assistants.value.find(a => a.assistantId === saved && a.isActive)
        if (exists) {
          currentAssistantId.value = saved
          return
        }
      }

      const general = assistants.value.find(a => a.assistantId === 'general')
      currentAssistantId.value = general?.assistantId || assistants.value[0]?.assistantId || null

    } catch (err: any) {
      error.value = err.message
      console.error('获取助手列表失败，使用内置助手:', err)
      // API失败时使用内置助手
      assistants.value = [...BUILTIN_ASSISTANTS]
      currentAssistantId.value = 'general'
    } finally {
      loading.value = false
    }
  }

  /**
   * 选择助手
   */
  function selectAssistant(assistantId: string) {
    const assistant = assistants.value.find(a => a.assistantId === assistantId && a.isActive)
    if (!assistant) {
      console.warn(`助手不存在或未启用: ${assistantId}`)
      return
    }
    currentAssistantId.value = assistantId
    localStorage.setItem('omic_current_assistant', assistantId)
  }

  /**
   * 创建自定义助手
   */
  async function createAssistant(payload: CreateAssistantPayload) {
    loading.value = true
    error.value = null
    try {
      const response = await fetch('/api/v1/chat/assistants', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(payload)
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }))
        throw new Error(errorData.detail || '创建助手失败')
      }

      const data = await response.json()
      // 添加到列表
      assistants.value.push({
        ...data,
        isBuiltin: false,
        isActive: true
      })

      return data
    } catch (err: any) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 更新助手
   */
  async function updateAssistant(assistantId: string, payload: Partial<CreateAssistantPayload>) {
    loading.value = true
    error.value = null
    try {
      const response = await fetch(`/api/v1/chat/assistants/${assistantId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(payload)
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }))
        throw new Error(errorData.detail || '更新助手失败')
      }

      // 更新本地数据
      const index = assistants.value.findIndex(a => a.assistantId === assistantId)
      if (index !== -1) {
        assistants.value[index] = {
          ...assistants.value[index],
          ...payload
        }
      }
    } catch (err: any) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 删除助手（仅自定义助手可删除）
   */
  async function deleteAssistant(assistantId: string) {
    const assistant = assistants.value.find(a => a.assistantId === assistantId)
    if (assistant?.isBuiltin) {
      throw new Error('内置助手不能删除')
    }

    loading.value = true
    error.value = null
    try {
      const response = await fetch(`/api/v1/chat/assistants/${assistantId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      })

      if (!response.ok) {
        throw new Error(`删除助手失败: ${response.status}`)
      }

      // 如果删除的是当前选中的，切换到通用助手
      if (currentAssistantId.value === assistantId) {
        selectAssistant('general')
      }

      assistants.value = assistants.value.filter(a => a.assistantId !== assistantId)
    } catch (err: any) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 重置为通用助手
   */
  function resetToGeneral() {
    selectAssistant('general')
  }

  /**
   * 清除错误
   */
  function clearError() {
    error.value = null
  }

  // ==================== Return ====================
  return {
    // State
    assistants,
    currentAssistantId,
    loading,
    error,
    // Getters
    currentAssistant,
    groupedAssistants,
    categories,
    getAssistantName,
    getAssistantStyle,
    // Actions
    fetchAssistants,
    selectAssistant,
    createAssistant,
    updateAssistant,
    deleteAssistant,
    resetToGeneral,
    clearError
  }
})
```

---

## 6. 完整集成页面示例（AIChat.vue）

**文件路径：** `src/views/AIChat.vue`

```vue
<!-- views/AIChat.vue -->
<template>
  <div class="ai-chat-page">
    <!-- ===== 顶部导航栏 ===== -->
    <div class="chat-header">
      <div class="header-left">
        <n-dropdown
          :options="modelStore.dropdownOptions"
          @select="handleModelChange"
          trigger="click"
        >
          <n-button ghost size="small" class="model-selector">
            <template #icon>
              <n-icon size="16"><FlashOutline /></n-icon>
            </template>
            {{ currentModelLabel }}
            <n-icon size="14" style="margin-left: 4px;"><ChevronDownOutline /></n-icon>
          </n-button>
        </n-dropdown>

        <n-dropdown
          :options="assistantDropdownOptions"
          @select="handleAssistantChange"
          trigger="click"
        >
          <n-button text size="small" class="assistant-selector">
            <n-icon size="16" :color="assistantIconColor" style="margin-right: 4px;">
              <component :is="assistantIconComponent" />
            </n-icon>
            {{ currentAssistantLabel }}
            <n-icon size="14" style="margin-left: 4px;"><ChevronDownOutline /></n-icon>
          </n-button>
        </n-dropdown>
      </div>

      <div class="header-right">
        <n-tooltip>
          <template #trigger>
            <n-button text circle size="small" @click="handleNewSession">
              <template #icon><n-icon size="16"><AddOutline /></n-icon></template>
            </n-button>
          </template>
          新建会话
        </n-tooltip>

        <n-tooltip>
          <template #trigger>
            <n-button text circle size="small" @click="showHistory = true">
              <template #icon><n-icon size="16"><TimeOutline /></n-icon></template>
            </n-button>
          </template>
          历史记录
        </n-tooltip>

        <n-tooltip>
          <template #trigger>
            <n-button text circle size="small" @click="showSettings = true">
              <template #icon><n-icon size="16"><SettingsOutline /></n-icon></template>
            </n-button>
          </template>
          设置
        </n-tooltip>
      </div>
    </div>

    <!-- ===== 错误提示 ===== -->
    <n-alert
      v-if="chat.error"
      type="error"
      closable
      @close="chat.error = null"
      class="global-error"
    >
      {{ chat.error }}
    </n-alert>

    <!-- ===== 消息列表 ===== -->
    <div class="message-list-container" ref="messageContainer">
      <!-- 空状态 -->
      <div v-if="chat.messages.length === 0" class="empty-state">
        <img src="/omic-logo.svg" class="empty-logo" alt="OmicHub" />
        <h2>OmicHub AI</h2>
        <p class="empty-desc">我可以帮你写作、编程、翻译、数据分析等</p>
        <div class="quick-prompts">
          <n-button
            v-for="prompt in quickPrompts"
            :key="prompt"
            text
            class="quick-prompt"
            @click="inputMessage = prompt; handleSend()"
          >
            {{ prompt }}
          </n-button>
        </div>
      </div>

      <!-- 消息列表 -->
      <template v-else>
        <ChatMessageItem
          v-for="message in chat.messages"
          :key="message.id"
          :message="message"
          @copy="handleCopy"
          @feedback="handleFeedback"
          @regenerate="handleRegenerate"
        />
      </template>
    </div>

    <!-- ===== 底部输入区域 ===== -->
    <div class="input-area">
      <div class="input-wrapper">
        <n-input
          v-model:value="inputMessage"
          type="textarea"
          placeholder="输入消息... (Shift + Enter 换行)"
          :autosize="{ minRows: 1, maxRows: 6 }"
          class="chat-input"
          @keydown="handleKeydown"
        />

        <div class="input-actions">
          <n-tooltip v-if="chat.isStreaming">
            <template #trigger>
              <n-button
                type="error"
                ghost
                size="small"
                @click="chat.stopGeneration()"
                class="stop-btn"
              >
                <template #icon><n-icon size="16"><SquareOutline /></n-icon></template>
                停止
              </n-button>
            </template>
            停止生成
          </n-tooltip>

          <n-button
            v-else
            type="primary"
            size="small"
            :disabled="!inputMessage.trim() || !chat.canSend || !modelStore.currentModel"
            @click="handleSend"
            class="send-btn"
          >
            <template #icon><n-icon size="16"><SendOutline /></n-icon></template>
            发送
          </n-button>
        </div>
      </div>

      <div class="input-footer">
        <span class="model-hint">
          {{ modelStore.currentModel?.description || 'AI 生成的内容可能不准确' }}
        </span>
        <n-button
          v-if="chat.isStreaming"
          text
          size="tiny"
          type="error"
          @click="chat.stopGeneration()"
        >
          <template #icon><n-icon size="12"><SquareOutline /></n-icon></template>
          停止生成
        </n-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue'
import {
  FlashOutline, ChevronDownOutline, AddOutline, TimeOutline, SettingsOutline,
  SendOutline, SquareOutline,
  ChatbubblesOutline, CodeSlashOutline, SchoolOutline, LanguageOutline,
  BarChartOutline, ColorWandOutline, FlaskOutline
} from '@vicons/ionicons5'
import { useMessage } from 'naive-ui'
import { useChatStream } from '@/composables/useChatStream'
import { useLLMModelStore } from '@/stores/llmModel'
import { useChatAssistantStore } from '@/stores/chatAssistant'
import ChatMessageItem from '@/components/ChatMessageItem.vue'
import { storeToRefs } from 'pinia'

// ===== 图标组件映射 =====
const iconMap: Record<string, any> = {
  ChatbubblesOutline,
  CodeSlashOutline,
  SchoolOutline,
  LanguageOutline,
  BarChartOutline,
  ColorWandOutline,
  FlaskOutline
}

// ===== Stores & Composables =====
const chat = useChatStream()
const modelStore = useLLMModelStore()
const assistantStore = useChatAssistantStore()
const naiveMessage = useMessage()

const { currentModel } = storeToRefs(modelStore)
const { currentAssistant } = storeToRefs(assistantStore)

// ===== State =====
const inputMessage = ref('')
const showHistory = ref(false)
const showSettings = ref(false)
const messageContainer = ref<HTMLDivElement>()

// ===== 快捷提示词 =====
const quickPrompts = [
  '帮我写一段Python代码，实现快速排序算法',
  '解释什么是RNA-seq数据分析的流程',
  '将以下英文翻译成中文',
  '帮我分析这个数据集的特点'
]

// ===== 计算属性 =====
const currentModelLabel = computed(() => {
  return modelStore.currentModel?.name || '选择模型'
})

const currentAssistantLabel = computed(() => {
  return assistantStore.currentAssistant?.name || '通用助手'
})

const assistantIconColor = computed(() => {
  return assistantStore.currentAssistant?.color || '#4f8ef7'
})

const assistantIconComponent = computed(() => {
  const iconName = assistantStore.currentAssistant?.icon || 'ChatbubblesOutline'
  return iconMap[iconName] || ChatbubblesOutline
})

// 助手下拉菜单选项
const assistantDropdownOptions = computed(() => {
  const groups = assistantStore.groupedAssistants
  const options: any[] = []

  Object.entries(groups).forEach(([category, assistants]) => {
    options.push({
      type: 'group',
      label: category,
      key: `group-${category}`,
      children: assistants.map(a => ({
        label: a.name,
        key: a.assistantId,
        description: a.description
      }))
    })
  })

  return options
})

// ===== 事件处理 =====

async function handleSend() {
  if (!inputMessage.value.trim()) return
  if (!modelStore.currentModel) {
    naiveMessage.warning('请先在模型设置中选择一个可用的AI模型')
    return
  }

  const content = inputMessage.value
  inputMessage.value = ''

  await chat.sendMessage(content, {
    modelId: modelStore.currentModel.id,
    assistantId: assistantStore.currentAssistant?.assistantId,
    systemPrompt: assistantStore.currentAssistant?.systemPrompt
  })
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function handleModelChange(modelId: number) {
  modelStore.switchModel(modelId)
  naiveMessage.success(`已切换到: ${modelStore.currentModel?.name}`)
}

function handleAssistantChange(assistantId: string) {
  assistantStore.selectAssistant(assistantId)
}

function handleNewSession() {
  chat.newSession()
  naiveMessage.info('已新建会话')
}

function handleCopy(content: string) {
  navigator.clipboard.writeText(content)
  naiveMessage.success('已复制')
}

function handleFeedback(messageId: string, type: 'up' | 'down') {
  naiveMessage.success(type === 'up' ? '感谢你的反馈!' : '我们会继续改进')
  // TODO: 调用API提交反馈
}

async function handleRegenerate() {
  if (!modelStore.currentModel) return
  // 找到最后一条用户消息
  const lastUserMsg = [...chat.messages].reverse().find(m => m.role === 'user')
  if (!lastUserMsg) {
    naiveMessage.warning('没有可以重新生成的消息')
    return
  }

  // 移除最后一条AI回复
  const lastAiMsg = chat.messages[chat.messages.length - 1]
  if (lastAiMsg?.role === 'assistant') {
    chat.messages.pop()
  }

  // 重新发送
  await chat.sendMessage(lastUserMsg.content, {
    modelId: modelStore.currentModel.id,
    assistantId: assistantStore.currentAssistant?.assistantId,
    systemPrompt: assistantStore.currentAssistant?.systemPrompt
  })
}

// ===== 生命周期 =====
onMounted(() => {
  modelStore.init()
  assistantStore.fetchAssistants()
})
</script>

<style scoped>
.ai-chat-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0d0d1a;
  color: #e0e0e0;
}

/* ===== 顶部导航栏 ===== */
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  border-bottom: 1px solid #1a1a2e;
  background: #111122;
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

.model-selector {
  color: #4f8ef7;
  border-color: #2a2a3c;
}

.model-selector:hover {
  border-color: #4f8ef7;
  background: rgba(79, 142, 247, 0.1);
}

.assistant-selector {
  color: #aaa;
}

/* ===== 全局错误提示 ===== */
.global-error {
  margin: 8px 16px 0;
  border-radius: 8px;
}

/* ===== 消息列表 ===== */
.message-list-container {
  flex: 1;
  overflow-y: auto;
  padding: 0;
  scroll-behavior: smooth;
}

/* 自定义滚动条 */
.message-list-container::-webkit-scrollbar {
  width: 4px;
}

.message-list-container::-webkit-scrollbar-track {
  background: transparent;
}

.message-list-container::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 2px;
}

.message-list-container::-webkit-scrollbar-thumb:hover {
  background: #555;
}

/* ===== 空状态 ===== */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 40px;
  text-align: center;
}

.empty-logo {
  width: 64px;
  height: 64px;
  margin-bottom: 20px;
  opacity: 0.8;
}

.empty-state h2 {
  font-size: 24px;
  font-weight: 600;
  color: #e0e0e0;
  margin-bottom: 8px;
}

.empty-desc {
  font-size: 14px;
  color: #888;
  margin-bottom: 24px;
}

.quick-prompts {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 500px;
}

.quick-prompt {
  justify-content: flex-start;
  padding: 8px 16px;
  background: #1a1a2e;
  border: 1px solid #2a2a3c;
  border-radius: 8px;
  color: #aaa;
  transition: all 0.2s;
}

.quick-prompt:hover {
  background: #222244;
  border-color: #4f8ef7;
  color: #e0e0e0;
}

/* ===== 底部输入区域 ===== */
.input-area {
  padding: 12px 16px;
  border-top: 1px solid #1a1a2e;
  background: #111122;
}

.input-wrapper {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  background: #1a1a2e;
  border: 1px solid #2a2a3c;
  border-radius: 12px;
  padding: 8px 12px;
}

.chat-input {
  flex: 1;
  background: transparent !important;
  border: none !important;
  color: #e0e0e0 !important;
  font-size: 14px;
  line-height: 1.6;
}

.chat-input :deep(.n-input__textarea-el) {
  background: transparent;
  color: #e0e0e0;
  resize: none;
}

.chat-input :deep(.n-input__border) {
  display: none;
}

.chat-input :deep(.n-input__state-border) {
  display: none;
}

.input-actions {
  display: flex;
  align-items: center;
  padding-bottom: 4px;
}

.send-btn {
  background: #4f8ef7;
  border: none;
}

.send-btn:hover {
  background: #3a7ce8;
}

.send-btn:disabled {
  background: #2a2a3c;
  color: #666;
}

.stop-btn {
  color: #ff4d4f;
  border-color: #ff4d4f;
}

.stop-btn:hover {
  background: rgba(255, 77, 79, 0.1);
}

.input-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 6px;
  padding: 0 4px;
}

.model-hint {
  font-size: 11px;
  color: #666;
}

/* ===== 响应式 ===== */
@media (max-width: 768px) {
  .chat-header {
    padding: 8px 12px;
  }

  .input-area {
    padding: 8px 12px;
  }

  .assistant-selector {
    display: none;
  }
}
</style>
```

---

## 技术要点总结

### 架构设计

| 特性 | 实现方式 | 来源 |
|------|---------|------|
| **流式输出** | `fetch` + `ReadableStream` + `SSE` 逐字追加 | Cherry Studio |
| **Optimistic Update** | 立即显示用户消息+空AI消息，再发起请求 | Cherry Studio |
| **消息管理** | `useChatStream` Composable 管理状态 | 自定义 |
| **模型管理** | Pinia Store + API + localStorage持久化 | Cherry Studio Provider |
| **助手系统** | 内置助手 + API助手合并，分类分组 | Cherry Studio |
| **Markdown渲染** | `markdown-it` + `highlight.js` + `DOMPurify` | 业界标准 |
| **错误处理** | 全局错误展示 + 消息级错误状态 | 自定义 |
| **停止生成** | `AbortController` 中断流 | 原生API |

### API 接口约定

```
POST /api/v1/chat/stream     # SSE流式聊天
GET  /api/v1/chat/sessions/:id/messages  # 获取会话历史
GET  /api/v1/ai/models       # 获取模型列表
POST /api/v1/ai/models       # 创建模型
PUT  /api/v1/ai/models/:id   # 更新模型
DELETE /api/v1/ai/models/:id # 删除模型
GET  /api/v1/chat/assistants # 获取助手列表
POST /api/v1/chat/assistants # 创建助手
```

### SSE 数据格式

```json
{"type": "text", "content": "你好"}
{"type": "tool_call", "metadata": {"tool_calls": [...]}}
{"type": "error", "content": "错误信息"}
{"type": "done", "metadata": {"session_id": "xxx", "tokens": 100}}
data: [DONE]
```


---

# 第三部分：联调验证清单

## 验证步骤（按顺序执行）

### 1. 后端接口测试

```bash
# 1.1 获取助手列表
curl -H "Authorization: Bearer $TOKEN"   http://localhost:8000/api/v1/chat/assistants

# 期望：返回5个内置助手

# 1.2 创建会话
curl -X POST -H "Authorization: Bearer $TOKEN"   -H "Content-Type: application/json"   -d '{"title": "测试会话", "model_id": 1}'   http://localhost:8000/api/v1/chat/sessions

# 1.3 SSE流式聊天（命令行测试）
curl -X POST -H "Authorization: Bearer $TOKEN"   -H "Content-Type: application/json"   -d '{
    "messages": [{"role": "user", "content": "hi"}],
    "model_id": 1,
    "assistant_id": "general"
  }'   http://localhost:8000/api/v1/chat/stream

# 期望：看到 data: {"type":"text","content":"你"} 等流式输出
```

### 2. 前端界面测试

| # | 操作 | 期望结果 |
|---|------|----------|
| 1 | 打开AI助手页面 | 界面铺满全屏，无白色空隙 |
| 2 | 查看模型选择下拉 | 显示配置的所有模型（非"K2.6快速"） |
| 3 | 输入"hi"发送 | AI逐字回复内容（不是空的） |
| 4 | 发送"写一段Python代码" | 代码块有语法高亮+复制按钮 |
| 5 | 快速发送多条消息 | 虚拟滚动正常工作 |
| 6 | 点击停止按钮 | 生成立即停止 |
| 7 | 切换助手（RNA-seq分析师） | 后续对话使用新的system prompt |
| 8 | 新建会话 | 清空历史，开始新对话 |
| 9 | 查看历史会话 | 左侧显示历史列表 |
| 10 | API Key为空时发送 | 显示友好错误"API Key未配置" |

### 3. 常见问题排查

| 问题 | 排查方法 |
|------|----------|
| AI不回复 | 检查API Key是否填写 → 检查后端日志 → 测试SSE接口 |
| 流式不工作 | 检查Nginx是否开启`proxy_buffering off` |
| 代码不高亮 | 检查highlight.js主题CSS是否导入 |
| 模型不显示 | 检查GET /api/v1/ai/models是否返回数据 |
| 底部有白边 | 检查CSS `height: 100vh` 和 `flex: 1` |

---

## 文件清单（共10个新文件）

### 后端（6个文件）
```
app/
├── models/
│   └── ai_chat.py              # ChatSession, ChatMessage, ChatAssistant
├── schemas/
│   └── chat.py                 # 所有Pydantic DTO
├── services/
│   ├── llm_provider.py         # LLMProvider, ProviderManager
│   └── chat_service.py         # ChatService业务逻辑
├── api/v1/
│   └── chat.py                 # FastAPI路由
└── database/
    └── migrations/
        └── V009__add_chat_system.py  # 数据库迁移
```

### 前端（4个文件）
```
src/
├── composables/
│   └── useChatStream.ts        # 流式聊天核心逻辑
├── components/
│   ├── MarkdownRenderer.vue    # Markdown安全渲染
│   └── ChatMessageItem.vue     # 消息项组件
├── stores/
│   ├── llmModel.ts             # 模型管理Store
│   └── chatAssistant.ts        # 助手管理Store
└── views/
    └── AIChat.vue              # AI助手页面（整合版）
```

---

## 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 流式协议 | SSE（Server-Sent Events） | 比WebSocket更简单，单向流式完美适配AI输出 |
| Provider管理 | 统一接口 + 缓存 | 借鉴Cherry Studio，支持50+模型 |
| 助手系统 | Assistant → Topic 双层 | 角色设定与对话分离，灵活复用 |
| 渲染安全 | DOMPurify + Shadow DOM | 防止XSS，AI输出不可信 |
| 状态管理 | Pinia + localStorage | 持久化用户选择（模型/助手） |
| 数据库 | PostgreSQL JSONB | 灵活存储消息元数据 |
| API Key存储 | Fernet加密 | 安全存储，不明文存数据库 |

