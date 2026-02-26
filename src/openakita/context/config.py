"""
上下文配置

EnterpriseContextManager 的配置。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TokenBudget:
    """
    Token 预算配置

    定义各层上下文的 Token 预算分配。

    属性：
        total: 总 Token 预算
        system_reserve: 系统层预留
        task_reserve: 任务层预留
        conversation_reserve: 会话层预留
        response_reserve: 响应预留
        buffer: 缓冲区
    """

    total: int = 128000              # 总预算 (Claude 3.5 Sonnet)
    system_reserve: int = 16000      # 系统层预留
    task_reserve: int = 4000         # 任务层预留
    conversation_reserve: int = 80000  # 会话层预留
    response_reserve: int = 16000    # 响应预留
    buffer: int = 12000               # 缓冲区

    @property
    def available_for_context(self) -> int:
        """可用于上下文的 Token 数"""
        return self.total - self.response_reserve - self.buffer

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "total": self.total,
            "system_reserve": self.system_reserve,
            "task_reserve": self.task_reserve,
            "conversation_reserve": self.conversation_reserve,
            "response_reserve": self.response_reserve,
            "buffer": self.buffer,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TokenBudget":
        """从字典创建"""
        return cls(
            total=data.get("total", 128000),
            system_reserve=data.get("system_reserve", 16000),
            task_reserve=data.get("task_reserve", 4000),
            conversation_reserve=data.get("conversation_reserve", 80000),
            response_reserve=data.get("response_reserve", 16000),
            buffer=data.get("buffer", 12000),
        )


@dataclass
class ContextConfig:
    """
    EnterpriseContextManager 的配置。

    属性：
        max_conversation_rounds: 保留的最大对话轮数
        max_task_summaries: 每个任务的最大步骤摘要数
        max_task_variables: 每个任务的最大关键变量数
        max_system_tokens: 系统上下文的 token 预算
        max_task_tokens: 任务上下文的 token 预算
        max_conversation_tokens: 对话上下文的 token 预算
        token_budget: Token 预算配置
    """

    max_conversation_rounds: int = 20
    max_task_summaries: int = 20
    max_task_variables: int = 50
    max_system_tokens: int = 8000
    max_task_tokens: int = 16000
    max_conversation_tokens: int = 8000
    token_budget: TokenBudget = field(default_factory=TokenBudget)

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "max_conversation_rounds": self.max_conversation_rounds,
            "max_task_summaries": self.max_task_summaries,
            "max_task_variables": self.max_task_variables,
            "max_system_tokens": self.max_system_tokens,
            "max_task_tokens": self.max_task_tokens,
            "max_conversation_tokens": self.max_conversation_tokens,
            "token_budget": self.token_budget.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ContextConfig":
        """从字典创建。"""
        token_budget_data = data.get("token_budget", {})
        return cls(
            max_conversation_rounds=data.get("max_conversation_rounds", 20),
            max_task_summaries=data.get("max_task_summaries", 20),
            max_task_variables=data.get("max_task_variables", 50),
            max_system_tokens=data.get("max_system_tokens", 8000),
            max_task_tokens=data.get("max_task_tokens", 16000),
            max_conversation_tokens=data.get("max_conversation_tokens", 8000),
            token_budget=TokenBudget.from_dict(token_budget_data) if token_budget_data else TokenBudget(),
        )
