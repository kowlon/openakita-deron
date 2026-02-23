"""
Enterprise Context Module

This module provides enterprise-grade context components:
- SystemContext: Permanent system-level context
- TaskContext: Task-level context with lifecycle
- ConversationContext: Conversation history with sliding window (CORE OPTIMIZATION)
"""

from openakita.context.enterprise.conversation_context import ConversationContext
from openakita.context.enterprise.system_context import SystemContext
from openakita.context.enterprise.task_context import TaskContext

__all__ = [
    "ConversationContext",
    "SystemContext",
    "TaskContext",
]
