"""
Task Context Store

Manages task-level context storage with step summaries, key variables,
and error records. Supports multi-tenant isolation.

Reference:
- docs/memory-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ErrorEntry:
    """
    Error record entry.

    Records errors encountered during task execution for debugging
    and error tracking purposes.

    Attributes:
        step_id: ID of the step where error occurred
        error_type: Type of error (e.g., "NetworkError", "TimeoutError")
        error_message: Detailed error message
        retry_count: Number of retry attempts
        resolution: How the error was resolved (None if unresolved)
        timestamp: When the error occurred
    """

    step_id: str
    error_type: str
    error_message: str
    retry_count: int = 0
    resolution: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "step_id": self.step_id,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "resolution": self.resolution,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ErrorEntry":
        """Create from dictionary"""
        return cls(
            step_id=data["step_id"],
            error_type=data["error_type"],
            error_message=data["error_message"],
            retry_count=data.get("retry_count", 0),
            resolution=data.get("resolution"),
            timestamp=(
                datetime.fromisoformat(data["timestamp"])
                if "timestamp" in data
                else datetime.now()
            ),
        )


@dataclass
class TaskMemory:
    """
    Task memory context.

    Stores task-level information including step summaries, key variables,
    and error records. Task memory is ephemeral - it should be cleared
    when the task ends.

    Attributes:
        task_id: Unique task identifier
        tenant_id: Tenant ID for multi-tenant isolation
        task_type: Type of task (e.g., "search", "analysis")
        task_description: Brief description of the task goal
        step_summaries: List of step completion summaries (max 20)
        key_variables: Key variables extracted during task (max 50)
        errors: List of error records
        created_at: Task creation timestamp
        updated_at: Last update timestamp
    """

    task_id: str
    tenant_id: str
    task_type: str
    task_description: str
    step_summaries: list[str] = field(default_factory=list)
    key_variables: dict[str, Any] = field(default_factory=dict)
    errors: list[ErrorEntry] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Limits
    MAX_STEP_SUMMARIES = 20
    MAX_KEY_VARIABLES = 50

    def add_step_summary(self, step_name: str, summary: str) -> None:
        """
        Add a step summary with sliding window limit.

        If exceeding MAX_STEP_SUMMARIES, removes oldest entries.
        """
        entry = f"{step_name}: {summary}"
        self.step_summaries.append(entry)

        # Enforce limit using sliding window
        if len(self.step_summaries) > self.MAX_STEP_SUMMARIES:
            self.step_summaries = self.step_summaries[-self.MAX_STEP_SUMMARIES :]

        self.updated_at = datetime.now()

    def add_variable(self, key: str, value: Any) -> None:
        """
        Add a key variable.

        If exceeding MAX_KEY_VARIABLES, removes oldest entry.
        """
        # If at limit and adding new key, remove oldest
        if len(self.key_variables) >= self.MAX_KEY_VARIABLES and key not in self.key_variables:
            # Remove first key (oldest in insertion order for Python 3.7+)
            first_key = next(iter(self.key_variables))
            del self.key_variables[first_key]

        self.key_variables[key] = value
        self.updated_at = datetime.now()

    def add_variables(self, variables: dict[str, Any]) -> None:
        """Add multiple variables."""
        for key, value in variables.items():
            self.add_variable(key, value)

    def add_error(self, error: ErrorEntry) -> None:
        """Add an error record."""
        self.errors.append(error)
        self.updated_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "task_id": self.task_id,
            "tenant_id": self.tenant_id,
            "task_type": self.task_type,
            "task_description": self.task_description,
            "step_summaries": self.step_summaries,
            "key_variables": self.key_variables,
            "errors": [e.to_dict() for e in self.errors],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskMemory":
        """Create from dictionary"""
        return cls(
            task_id=data["task_id"],
            tenant_id=data["tenant_id"],
            task_type=data["task_type"],
            task_description=data["task_description"],
            step_summaries=data.get("step_summaries", []),
            key_variables=data.get("key_variables", {}),
            errors=[ErrorEntry.from_dict(e) for e in data.get("errors", [])],
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


class TaskContextStore:
    """
    Task context storage manager.

    Provides in-memory storage for task contexts with support for:
    - Multi-tenant isolation
    - Step summary tracking (max 20)
    - Key variable storage (max 50)
    - Error recording
    - Context generation for prompts

    Example usage:
        store = TaskContextStore()

        # Start a task
        store.start_task("task-001", "tenant-001", "search", "Search for info")

        # Record progress
        store.record_step_completion(
            "task-001", "step-001", "Web Search",
            "Found 5 results", {"query": "info"}
        )

        # Get context for prompt injection
        context = store.to_prompt("task-001")

        # End task (cleans up memory)
        store.end_task("task-001")
    """

    def __init__(self) -> None:
        """Initialize empty context store."""
        self._contexts: dict[str, TaskMemory] = {}

    def start_task(
        self,
        task_id: str,
        tenant_id: str,
        task_type: str,
        description: str,
    ) -> TaskMemory:
        """
        Start a new task context.

        Args:
            task_id: Unique task identifier
            tenant_id: Tenant ID for isolation
            task_type: Type of task
            description: Task description/goal

        Returns:
            Created TaskMemory object
        """
        context = TaskMemory(
            task_id=task_id,
            tenant_id=tenant_id,
            task_type=task_type,
            task_description=description,
        )
        self._contexts[task_id] = context
        return context

    def end_task(self, task_id: str) -> bool:
        """
        End a task and remove its context.

        Args:
            task_id: Task identifier

        Returns:
            True if task was found and removed, False otherwise
        """
        if task_id in self._contexts:
            del self._contexts[task_id]
            return True
        return False

    def get_context(self, task_id: str) -> TaskMemory | None:
        """
        Get task context by ID.

        Args:
            task_id: Task identifier

        Returns:
            TaskMemory if found, None otherwise
        """
        return self._contexts.get(task_id)

    def record_step_completion(
        self,
        task_id: str,
        step_id: str,
        step_name: str,
        summary: str,
        variables: dict[str, Any],
    ) -> bool:
        """
        Record step completion for a task.

        Args:
            task_id: Task identifier
            step_id: Step identifier
            step_name: Name of the step
            summary: Completion summary
            variables: Key variables from this step

        Returns:
            True if task exists and step was recorded, False otherwise
        """
        context = self._contexts.get(task_id)
        if not context:
            return False

        context.add_step_summary(step_name, summary)
        context.add_variables(variables)
        return True

    def record_error(
        self,
        task_id: str,
        step_id: str,
        error_type: str,
        error_message: str,
        resolution: str | None = None,
    ) -> bool:
        """
        Record an error for a task.

        Args:
            task_id: Task identifier
            step_id: Step where error occurred
            error_type: Type of error
            error_message: Error message
            resolution: How it was resolved (optional)

        Returns:
            True if task exists and error was recorded, False otherwise
        """
        context = self._contexts.get(task_id)
        if not context:
            return False

        error = ErrorEntry(
            step_id=step_id,
            error_type=error_type,
            error_message=error_message,
            resolution=resolution,
        )
        context.add_error(error)
        return True

    def to_prompt(self, task_id: str) -> str:
        """
        Generate prompt-formatted context string.

        Args:
            task_id: Task identifier

        Returns:
            Formatted string for prompt injection.
            Empty string if task not found.
        """
        context = self._contexts.get(task_id)
        if not context:
            return ""

        lines = ["## Task Context", ""]

        # Task description
        lines.append(f"**Task**: {context.task_description}")
        lines.append(f"**Type**: {context.task_type}")
        lines.append("")

        # Step summaries
        if context.step_summaries:
            lines.append("**Completed Steps**:")
            for i, summary in enumerate(context.step_summaries, 1):
                lines.append(f"  {i}. {summary}")
            lines.append("")

        # Key variables
        if context.key_variables:
            lines.append("**Key Variables**:")
            for key, value in context.key_variables.items():
                lines.append(f"  - {key}: {value}")
            lines.append("")

        # Errors (if any)
        if context.errors:
            lines.append("**Errors Encountered**:")
            for error in context.errors:
                resolution = f" (resolved: {error.resolution})" if error.resolution else ""
                lines.append(f"  - [{error.error_type}] {error.error_message}{resolution}")
            lines.append("")

        return "\n".join(lines)

    def get_stats(self, task_id: str) -> dict[str, Any]:
        """
        Get statistics for a task.

        Args:
            task_id: Task identifier

        Returns:
            Dictionary with task statistics.
            Empty dict if task not found.
        """
        context = self._contexts.get(task_id)
        if not context:
            return {}

        return {
            "task_id": context.task_id,
            "tenant_id": context.tenant_id,
            "task_type": context.task_type,
            "step_count": len(context.step_summaries),
            "variable_count": len(context.key_variables),
            "error_count": len(context.errors),
            "created_at": context.created_at.isoformat(),
            "updated_at": context.updated_at.isoformat(),
        }

    def get_tasks_by_tenant(self, tenant_id: str) -> list[TaskMemory]:
        """
        Get all tasks for a specific tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            List of TaskMemory objects for the tenant
        """
        return [
            ctx for ctx in self._contexts.values() if ctx.tenant_id == tenant_id
        ]

    def clear_all(self) -> None:
        """Clear all task contexts."""
        self._contexts.clear()

    @property
    def task_count(self) -> int:
        """Get total number of active tasks."""
        return len(self._contexts)
