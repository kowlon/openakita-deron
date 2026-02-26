"""
上下文模块。

该模块为 Agent 系统提供分层上下文管理能力：

- SystemContext: 永久层（身份、规则、能力清单）
- TaskContext: 任务层（目标、进度、变量）
- ConversationContext: 会话层（滑动窗口、Token预算）

使用方式：
    from openakita.context import (
        ContextBackend,
        create_context_backend,
        TokenBudget,
        ContextConfig,
        ContextError,
        TokenBudgetExceeded,
    )
"""
from __future__ import annotations

import logging
from typing import Any

from openakita.context.config import ContextConfig as EnterpriseContextConfig
from openakita.context.config import TokenBudget, ContextConfig
from openakita.context.exceptions import (
    CheckpointNotFoundError,
    CompressionError,
    ContextError,
    ContextNotFoundError,
    SessionContextNotFoundError,
    TaskContextNotFoundError,
    TokenBudgetExceeded,
)
from openakita.context.interfaces import (
    CompressionStrategy,
    ContextPriority,
    ICompressor,
    IContext,
    IContextOrchestrator,
    IConversationContext,
    ISystemContext,
    ITaskContext,
)
from openakita.context.manager import EnterpriseContextManager
from openakita.context.protocol import ContextBackend

logger = logging.getLogger(__name__)


def create_context_backend(
    config: Any | None = None,
    brain: Any = None,
    cancel_event: Any = None,
) -> ContextBackend:
    if config is None:
        enterprise_config = EnterpriseContextConfig()
    else:
        enterprise_config = EnterpriseContextConfig(
            max_conversation_rounds=config.max_conversation_rounds,
            max_task_summaries=config.max_task_summaries,
            max_task_variables=config.max_task_variables,
        )

    backend = EnterpriseContextManager(enterprise_config)
    logger.info("[ContextBackend] Created EnterpriseContextManager")
    return backend


__all__ = [
    # Factory
    "create_context_backend",
    # Protocol
    "ContextBackend",
    # Config
    "TokenBudget",
    "ContextConfig",
    # Interfaces
    "IContext",
    "ISystemContext",
    "ITaskContext",
    "IConversationContext",
    "ICompressor",
    "IContextOrchestrator",
    # Enums
    "ContextPriority",
    "CompressionStrategy",
    # Exceptions
    "ContextError",
    "TokenBudgetExceeded",
    "ContextNotFoundError",
    "TaskContextNotFoundError",
    "SessionContextNotFoundError",
    "CheckpointNotFoundError",
    "CompressionError",
]
