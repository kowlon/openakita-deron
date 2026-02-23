"""
Task Context

Manages task-level context for context building. This is focused on
generating context for LLM prompts, distinct from the memory module's
TaskMemory which is focused on storage.

Reference:
- docs/context-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TaskContext:
    """
    Task Context - Task-level context for prompt building.

    Contains task definition, step summaries, and key variables.
    Used by EnterpriseContextManager to build the task layer of context.

    Lifecycle:
    - Created when task starts
    - Updated as steps complete
    - Destroyed when task ends

    Attributes:
        task_id: Unique task identifier
        tenant_id: Tenant ID for multi-tenant isolation
        task_type: Type of task (e.g., "search", "analysis")
        task_description: Brief description of task goal
        step_summaries: List of step completion summaries (max 20)
        key_variables: Key variables extracted during task (max 50)
        current_step: Current step number
        total_steps: Total expected steps (0 if unknown)
        created_at: Task creation timestamp
        updated_at: Last update timestamp
    """

    task_id: str
    tenant_id: str
    task_type: str
    task_description: str
    step_summaries: list[str] = field(default_factory=list)
    key_variables: dict[str, Any] = field(default_factory=dict)
    current_step: int = 0
    total_steps: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Constraints
    MAX_STEP_SUMMARIES = 20
    MAX_KEY_VARIABLES = 50
    MAX_TOKENS = 16000

    def add_step_summary(self, step_name: str, summary: str) -> None:
        """
        Add a step summary with sliding window limit.

        Args:
            step_name: Name of the step
            summary: Brief summary of what was accomplished
        """
        # Truncate summary to 100 chars
        truncated = summary[:100] if len(summary) > 100 else summary
        entry = f"[{step_name}] {truncated}"

        self.step_summaries.append(entry)

        # Enforce sliding window limit
        if len(self.step_summaries) > self.MAX_STEP_SUMMARIES:
            self.step_summaries = self.step_summaries[-self.MAX_STEP_SUMMARIES:]

        self.current_step += 1
        self.updated_at = datetime.now()

    def add_variable(self, key: str, value: Any) -> None:
        """
        Add a key variable.

        Args:
            key: Variable name
            value: Variable value
        """
        # If at limit and adding new key, remove oldest
        if (
            len(self.key_variables) >= self.MAX_KEY_VARIABLES
            and key not in self.key_variables
        ):
            first_key = next(iter(self.key_variables))
            del self.key_variables[first_key]

        self.key_variables[key] = value
        self.updated_at = datetime.now()

    def add_variables(self, variables: dict[str, Any]) -> None:
        """
        Add multiple variables.

        Args:
            variables: Dictionary of variables to add
        """
        for key, value in variables.items():
            self.add_variable(key, value)

    def to_prompt(self) -> str:
        """
        Generate task context prompt string.

        Returns:
            Formatted string for injection into system prompt.
        """
        parts = []

        # Task description
        parts.append(f"# Current Task\n{self.task_description}")

        # Progress indicator
        if self.total_steps > 0:
            parts.append(f"\nProgress: Step {self.current_step}/{self.total_steps}")
        elif self.current_step > 0:
            parts.append(f"\nProgress: Step {self.current_step}")

        # Step summaries
        if self.step_summaries:
            parts.append("\n# Completed Steps")
            for i, summary in enumerate(self.step_summaries, 1):
                parts.append(f"{i}. {summary}")

        # Key variables
        if self.key_variables:
            parts.append("\n# Key Variables")
            for key, value in self.key_variables.items():
                # Truncate long values
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:100] + "..."
                parts.append(f"- {key}: {value_str}")

        return "\n".join(parts)

    def estimate_tokens(self, chars_per_token: float = 4.0) -> int:
        """
        Estimate token count for task context.

        Args:
            chars_per_token: Average characters per token

        Returns:
            Estimated token count
        """
        return int(len(self.to_prompt()) / chars_per_token)

    def is_within_budget(self) -> bool:
        """
        Check if context is within token budget.

        Returns:
            True if estimated tokens <= MAX_TOKENS
        """
        return self.estimate_tokens() <= self.MAX_TOKENS

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about the task context.

        Returns:
            Dictionary with task statistics
        """
        return {
            "task_id": self.task_id,
            "tenant_id": self.tenant_id,
            "task_type": self.task_type,
            "step_count": len(self.step_summaries),
            "variable_count": len(self.key_variables),
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "estimated_tokens": self.estimate_tokens(),
            "within_budget": self.is_within_budget(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "tenant_id": self.tenant_id,
            "task_type": self.task_type,
            "task_description": self.task_description,
            "step_summaries": self.step_summaries,
            "key_variables": self.key_variables,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskContext":
        """Create from dictionary."""
        return cls(
            task_id=data["task_id"],
            tenant_id=data["tenant_id"],
            task_type=data["task_type"],
            task_description=data["task_description"],
            step_summaries=data.get("step_summaries", []),
            key_variables=data.get("key_variables", {}),
            current_step=data.get("current_step", 0),
            total_steps=data.get("total_steps", 0),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if "created_at" in data
                else datetime.now()
            ),
            updated_at=(
                datetime.fromisoformat(data["updated_at"])
                if "updated_at" in data
                else datetime.now()
            ),
        )

    def __str__(self) -> str:
        """String representation."""
        return f"TaskContext({self.task_id}, type={self.task_type}, steps={len(self.step_summaries)})"

    def __repr__(self) -> str:
        """Detailed representation."""
        return (
            f"TaskContext(task_id='{self.task_id}', tenant_id='{self.tenant_id}', "
            f"task_type='{self.task_type}', steps={len(self.step_summaries)}, "
            f"variables={len(self.key_variables)})"
        )
