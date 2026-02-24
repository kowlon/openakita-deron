"""
LLM 统一调用层

提供统一的 LLM 调用接口，支持：
- Anthropic 和 OpenAI 两种 API 格式
- 多模态（图片、视频）
- 工具调用
- 思考模式 (thinking)
- 自动故障切换
- 能力分流

Brain: LLMClient 的高级封装，负责：
1. 维护对话上下文 (Context)
2. 集成记忆系统
3. 处理思考过程
4. 管理 Token 预算
"""

from .adapter import LegacyContext, LegacyResponse, LLMAdapter, think
from .brain import Brain, Context, Response
from .client import LLMClient, chat, get_default_client
from .config import get_default_config_path, load_endpoints_config
from .types import (
    ContentBlock,
    EndpointConfig,
    ImageContent,
    LLMRequest,
    LLMResponse,
    Message,
    StopReason,
    TextBlock,
    Tool,
    ToolResultBlock,
    ToolUseBlock,
    Usage,
    VideoContent,
)

__all__ = [
    # Types
    "LLMRequest",
    "LLMResponse",
    "EndpointConfig",
    "ContentBlock",
    "TextBlock",
    "ToolUseBlock",
    "ToolResultBlock",
    "ImageContent",
    "VideoContent",
    "Message",
    "Tool",
    "Usage",
    "StopReason",
    # Client
    "LLMClient",
    "get_default_client",
    "chat",
    # Config
    "load_endpoints_config",
    "get_default_config_path",
    # Adapter (backward compatibility)
    "LLMAdapter",
    "LegacyResponse",
    "LegacyContext",
    "think",
    # Brain (backward compatibility layer)
    "Brain",
    "Context",
    "Response",
]
