"""
企业级上下文模块

本模块提供企业级上下文组件：
- SystemContext: 永久的系统级上下文
- TaskContext: 具备生命周期的任务级上下文
- ConversationContext: 带滑动窗口的对话历史（核心优化）
- EnterpriseContextManager: 统一的上下文协调器
"""

from openakita.context.enterprise.config import ContextConfig
from openakita.context.enterprise.conversation_context import ConversationContext
from openakita.context.enterprise.manager import EnterpriseContextManager
from openakita.context.enterprise.system_context import SystemContext
from openakita.context.enterprise.task_context import TaskContext

__all__ = [
    "ContextConfig",
    "ConversationContext",
    "EnterpriseContextManager",
    "SystemContext",
    "TaskContext",
]
