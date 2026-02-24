"""
OpenAkita 记忆系统

实现三层记忆架构:
1. 短期记忆 (Short-term): 当前会话上下文
2. 工作记忆 (Working): MEMORY.md 中的任务进度
3. 长期记忆 (Long-term): 持久化的经验和模式

注意：消费者端的 AI 提取和每日归纳功能已移除。
企业级实现请使用 memory.enterprise 模块。
"""

from .consolidator import MemoryConsolidator
from .manager import MemoryManager
from .types import (
    ConversationTurn,
    Memory,
    MemoryPriority,
    MemoryType,
    SessionSummary,
)

__all__ = [
    "MemoryManager",
    "MemoryConsolidator",
    "Memory",
    "MemoryType",
    "MemoryPriority",
    "ConversationTurn",
    "SessionSummary",
]
