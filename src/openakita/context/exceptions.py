"""
上下文模块异常定义
"""
from __future__ import annotations


class ContextError(Exception):
    """上下文模块基础异常"""

    def __init__(self, message: str = "Context error"):
        self.message = message
        super().__init__(self.message)


class TokenBudgetExceeded(ContextError):
    """Token 预算超限异常

    当上下文构建超出预设的 Token 预算时抛出。
    """

    def __init__(
        self,
        current_tokens: int,
        budget: int,
        context_type: str = "unknown"
    ):
        self.current_tokens = current_tokens
        self.budget = budget
        self.context_type = context_type
        message = (
            f"Token budget exceeded for {context_type}: "
            f"{current_tokens} > {budget}"
        )
        super().__init__(message)


class ContextNotFoundError(ContextError):
    """上下文未找到异常

    当请求的上下文（任务/会话）不存在时抛出。
    """

    def __init__(self, context_type: str, context_id: str):
        self.context_type = context_type
        self.context_id = context_id
        message = f"{context_type} context not found: {context_id}"
        super().__init__(message)


class TaskContextNotFoundError(ContextNotFoundError):
    """任务上下文未找到"""

    def __init__(self, task_id: str):
        super().__init__("Task", task_id)


class SessionContextNotFoundError(ContextNotFoundError):
    """会话上下文未找到"""

    def __init__(self, session_id: str):
        super().__init__("Session", session_id)


class CheckpointNotFoundError(ContextError):
    """检查点未找到异常"""

    def __init__(self, checkpoint_id: str, task_id: str | None = None):
        self.checkpoint_id = checkpoint_id
        self.task_id = task_id
        message = f"Checkpoint not found: {checkpoint_id}"
        if task_id:
            message += f" (task: {task_id})"
        super().__init__(message)


class CompressionError(ContextError):
    """上下文压缩异常"""

    def __init__(self, reason: str, original_size: int | None = None):
        self.reason = reason
        self.original_size = original_size
        message = f"Context compression failed: {reason}"
        if original_size:
            message += f" (original size: {original_size})"
        super().__init__(message)