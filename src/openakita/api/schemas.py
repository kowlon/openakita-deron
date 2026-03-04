"""HTTP API 的 Pydantic 请求/响应模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """聊天请求体。"""

    message: str = Field("", description="User message text")
    conversation_id: str | None = Field(None, description="Conversation ID for context")
    plan_mode: bool = Field(False, description="Force Plan mode")
    endpoint: str | None = Field(None, description="Specific endpoint name (null=auto)")
    attachments: list[AttachmentInfo] | None = Field(None, description="Attached files/images")
    thinking_mode: str | None = Field(
        None,
        description="Thinking mode override: 'auto'(system decides), 'on'(force enable), 'off'(force disable). null=use system default.",
    )
    thinking_depth: str | None = Field(
        None,
        description="Thinking depth: 'low', 'medium', 'high'. Only effective when thinking is enabled.",
    )


class AttachmentInfo(BaseModel):
    """附件元数据。"""

    type: str = Field(..., description="image | file | voice")
    name: str = Field(..., description="Filename")
    url: str | None = Field(None, description="URL or data URI")
    mime_type: str | None = Field(None, description="MIME type")


# 修复前向引用
ChatRequest.model_rebuild()


class ChatAnswerRequest(BaseModel):
    """对 ask_user 事件的回答。"""

    conversation_id: str | None = None
    answer: str = ""


class ChatControlRequest(BaseModel):
    """聊天控制操作（取消/跳过/插入）的请求体。"""

    conversation_id: str | None = Field(None, description="Conversation ID")
    reason: str = Field("", description="Reason for the control action")
    message: str = Field("", description="User message (only for insert)")


class HealthCheckRequest(BaseModel):
    """健康检查请求。"""

    endpoint_name: str | None = None
    channel: str | None = None


class HealthResult(BaseModel):
    """单个端点健康结果。"""

    name: str
    status: str  # 健康 | 降级 | 不健康 | 未知
    latency_ms: float | None = None
    error: str | None = None
    error_category: str | None = None
    consecutive_failures: int = 0
    cooldown_remaining: float = 0
    is_extended_cooldown: bool = False
    last_checked_at: str | None = None


class ModelInfo(BaseModel):
    """可用模型/端点信息。"""

    name: str
    provider: str
    model: str
    status: str = "unknown"
    has_api_key: bool = False


class SkillInfoResponse(BaseModel):
    """API 的技能信息。"""

    name: str
    description: str
    system: bool = False
    enabled: bool = True
    category: str | None = None
    config: list[dict[str, Any]] | None = None
