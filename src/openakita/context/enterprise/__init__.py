"""
Enterprise Context Module

This module provides enterprise-grade context components:
- SystemContext: Permanent system-level context
- TaskContext: Task-level context with lifecycle
- ConversationContext: Conversation history with sliding window
"""

from openakita.context.enterprise.system_context import SystemContext

__all__ = [
    "SystemContext",
]
