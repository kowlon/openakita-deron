"""
上下文配置

EnterpriseContextManager 的配置。
"""

from dataclasses import dataclass


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
    """

    max_conversation_rounds: int = 20
    max_task_summaries: int = 20
    max_task_variables: int = 50
    max_system_tokens: int = 8000
    max_task_tokens: int = 16000
    max_conversation_tokens: int = 8000

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "max_conversation_rounds": self.max_conversation_rounds,
            "max_task_summaries": self.max_task_summaries,
            "max_task_variables": self.max_task_variables,
            "max_system_tokens": self.max_system_tokens,
            "max_task_tokens": self.max_task_tokens,
            "max_conversation_tokens": self.max_conversation_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ContextConfig":
        """从字典创建。"""
        return cls(
            max_conversation_rounds=data.get("max_conversation_rounds", 20),
            max_task_summaries=data.get("max_task_summaries", 20),
            max_task_variables=data.get("max_task_variables", 50),
            max_system_tokens=data.get("max_system_tokens", 8000),
            max_task_tokens=data.get("max_task_tokens", 16000),
            max_conversation_tokens=data.get("max_conversation_tokens", 8000),
        )
