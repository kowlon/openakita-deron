"""
会话管理模块

提供统一的会话管理能力:
- Session: 会话对象，包含上下文和配置
- SessionManager: 会话生命周期管理

注意：跨平台用户管理功能已移除（消费者端功能）
"""

from .manager import SessionManager
from .session import Session, SessionConfig, SessionContext, SessionState

__all__ = [
    "Session",
    "SessionState",
    "SessionContext",
    "SessionConfig",
    "SessionManager",
]
