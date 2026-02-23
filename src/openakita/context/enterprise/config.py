"""
Context Configuration

Configuration for EnterpriseContextManager.
"""

from dataclasses import dataclass


@dataclass
class ContextConfig:
    """
    Configuration for EnterpriseContextManager.

    Attributes:
        max_conversation_rounds: Maximum conversation rounds to keep
        max_task_summaries: Maximum step summaries per task
        max_task_variables: Maximum key variables per task
        max_system_tokens: Token budget for system context
        max_task_tokens: Token budget for task context
        max_conversation_tokens: Token budget for conversation context
    """

    max_conversation_rounds: int = 20
    max_task_summaries: int = 20
    max_task_variables: int = 50
    max_system_tokens: int = 8000
    max_task_tokens: int = 16000
    max_conversation_tokens: int = 8000

    def to_dict(self) -> dict:
        """Convert to dictionary."""
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
        """Create from dictionary."""
        return cls(
            max_conversation_rounds=data.get("max_conversation_rounds", 20),
            max_task_summaries=data.get("max_task_summaries", 20),
            max_task_variables=data.get("max_task_variables", 50),
            max_system_tokens=data.get("max_system_tokens", 8000),
            max_task_tokens=data.get("max_task_tokens", 16000),
            max_conversation_tokens=data.get("max_conversation_tokens", 8000),
        )
