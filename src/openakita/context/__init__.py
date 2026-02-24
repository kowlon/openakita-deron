"""
上下文模块。

该模块为 Agent 系统提供上下文管理能力。
"""
from __future__ import annotations

import logging
from typing import Any

from openakita.context.config import ContextConfig as EnterpriseContextConfig
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


__all__ = ["ContextBackend", "create_context_backend"]
