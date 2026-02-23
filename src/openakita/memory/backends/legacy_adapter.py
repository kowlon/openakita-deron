"""
Legacy Memory Backend Adapter

This adapter wraps the existing Memory class to implement the MemoryBackend
protocol, providing backward compatibility with the legacy memory system.

The legacy memory system uses:
- MEMORY.md for task progress and experiences
- USER.md for user preferences
- Database for persistent memory storage

Reference:
- docs/memory-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

import logging
from typing import Any

from openakita.core.memory import Memory

logger = logging.getLogger(__name__)


class LegacyMemoryBackend:
    """
    Legacy Memory Backend Adapter.

    Wraps the existing Memory class to implement the MemoryBackend protocol.
    This allows the Agent to use either the legacy or enterprise memory system
    through a unified interface.

    Note:
        This adapter provides compatibility but doesn't support all enterprise
        features like multi-tenant isolation or structured task context.

    Example:
        from openakita.core.memory import Memory
        from openakita.memory.backends.legacy_adapter import LegacyMemoryBackend

        legacy_memory = Memory()
        backend = LegacyMemoryBackend(legacy_memory)

        # Use through MemoryBackend protocol
        await backend.initialize()
        backend.start_task("task-001", "default", "search", "Search task")
        context = await backend.get_injection_context("task-001", "search", "query")
    """

    def __init__(self, memory: Memory | None = None) -> None:
        """
        Initialize the legacy backend adapter.

        Args:
            memory: Optional Memory instance to wrap.
                   If None, creates a new instance.
        """
        self._memory = memory or Memory()
        self._task_contexts: dict[str, dict[str, Any]] = {}

    async def initialize(self) -> None:
        """
        Initialize the underlying memory system.

        This should be called before using the backend.
        """
        await self._memory.initialize()
        logger.info("LegacyMemoryBackend initialized")

    # ========== MemoryBackend Protocol Implementation ==========

    async def get_injection_context(
        self, task_id: str, task_type: str, query: str
    ) -> str:
        """
        Get memory context for injection into system prompt.

        This combines:
        1. Task-related memories from database (via get_context_for_task)
        2. Current task context (if any)

        Args:
            task_id: Unique task identifier
            task_type: Task type (not used in legacy, kept for interface)
            query: User query for semantic memory search

        Returns:
            Formatted context string for system prompt injection
        """
        sections: list[str] = []

        # Get task-related context from legacy memory
        task_context = await self._memory.get_context_for_task(query)
        if task_context:
            sections.append(task_context)

        # Add current task context if exists
        if task_id in self._task_contexts:
            ctx = self._task_contexts[task_id]
            context_str = self._format_task_context(ctx)
            if context_str:
                sections.append(context_str)

        return "\n\n".join(sections) if sections else ""

    def record_step_completion(
        self,
        task_id: str,
        step_id: str,
        step_name: str,
        summary: str,
        variables: dict[str, Any],
    ) -> None:
        """
        Record step completion for a task.

        In the legacy system, this updates the task context and adds
        an experience entry.

        Args:
            task_id: Unique task identifier
            step_id: Unique step identifier
            step_name: Name of the step
            summary: Step completion summary
            variables: Key variables extracted from this step
        """
        if task_id not in self._task_contexts:
            logger.warning(f"Task {task_id} not found, creating context")
            self._task_contexts[task_id] = {
                "task_id": task_id,
                "tenant_id": "default",
                "task_type": "unknown",
                "description": "Auto-created task",
                "steps": [],
                "variables": {},
            }

        ctx = self._task_contexts[task_id]

        # Record step
        step_entry = {
            "step_id": step_id,
            "step_name": step_name,
            "summary": summary,
            "variables": variables,
        }
        ctx["steps"].append(step_entry)

        # Update variables
        ctx["variables"].update(variables)

        # Add experience to legacy memory
        self._memory.add_experience(
            category="step",
            content=f"{step_name}: {summary}",
        )

        logger.debug(f"Recorded step completion: {step_name} for task {task_id}")

    def record_error(
        self,
        task_id: str,
        step_id: str,
        error_type: str,
        error_message: str,
        resolution: str | None,
    ) -> None:
        """
        Record an error for a task.

        In the legacy system, this adds an error experience entry.

        Args:
            task_id: Unique task identifier
            step_id: Step where error occurred
            error_type: Type of error
            error_message: Error message
            resolution: Resolution if resolved, None otherwise
        """
        # Add error experience
        error_content = f"[{error_type}] {error_message}"
        if resolution:
            error_content += f" (resolved: {resolution})"

        self._memory.add_experience(
            category="error",
            content=error_content,
        )

        # Also update task context if exists
        if task_id in self._task_contexts:
            ctx = self._task_contexts[task_id]
            if "errors" not in ctx:
                ctx["errors"] = []

            ctx["errors"].append({
                "step_id": step_id,
                "error_type": error_type,
                "error_message": error_message,
                "resolution": resolution,
            })

        logger.debug(f"Recorded error: {error_type} for task {task_id}")

    def start_task(
        self, task_id: str, tenant_id: str, task_type: str, description: str
    ) -> None:
        """
        Start a new task.

        In the legacy system, this updates the active task in MEMORY.md
        and creates an internal task context.

        Args:
            task_id: Unique task identifier
            tenant_id: Tenant ID (not used in legacy, stored for compatibility)
            task_type: Task type
            description: Task description/goal
        """
        # Create internal task context
        self._task_contexts[task_id] = {
            "task_id": task_id,
            "tenant_id": tenant_id,
            "task_type": task_type,
            "description": description,
            "steps": [],
            "variables": {},
            "errors": [],
        }

        # Update legacy memory's active task
        self._memory.update_active_task(
            task_id=task_id,
            description=description,
            status="started",
        )

        logger.info(f"Started task: {task_id} - {description}")

    def end_task(self, task_id: str) -> None:
        """
        End a task.

        In the legacy system, this updates the task status and statistics,
        then removes the internal task context.

        Args:
            task_id: Unique task identifier
        """
        if task_id in self._task_contexts:
            ctx = self._task_contexts[task_id]

            # Update legacy memory's active task
            self._memory.update_active_task(
                task_id=task_id,
                description=ctx.get("description", "Unknown"),
                status="completed",
            )

            # Update statistics
            self._memory.update_statistics(总任务数=1, 成功任务=1)

            # Remove context
            del self._task_contexts[task_id]

            logger.info(f"Ended task: {task_id}")
        else:
            logger.warning(f"Task {task_id} not found when ending")

    def get_stats(self, task_id: str) -> dict[str, Any]:
        """
        Get statistics for a task.

        Args:
            task_id: Unique task identifier

        Returns:
            Dictionary with task statistics
        """
        if task_id not in self._task_contexts:
            return {}

        ctx = self._task_contexts[task_id]

        return {
            "task_id": task_id,
            "tenant_id": ctx.get("tenant_id", "default"),
            "task_type": ctx.get("task_type", "unknown"),
            "step_count": len(ctx.get("steps", [])),
            "variable_count": len(ctx.get("variables", {})),
            "error_count": len(ctx.get("errors", [])),
        }

    # ========== Helper Methods ==========

    def _format_task_context(self, ctx: dict[str, Any]) -> str:
        """
        Format task context for prompt injection.

        Args:
            ctx: Task context dictionary

        Returns:
            Formatted string
        """
        lines = ["## Current Task Context", ""]

        lines.append(f"**Task**: {ctx.get('description', 'Unknown')}")
        lines.append(f"**Type**: {ctx.get('task_type', 'unknown')}")
        lines.append("")

        # Steps
        steps = ctx.get("steps", [])
        if steps:
            lines.append("**Completed Steps**:")
            for i, step in enumerate(steps, 1):
                lines.append(f"  {i}. {step.get('step_name', 'Unknown')}: {step.get('summary', '')}")
            lines.append("")

        # Variables
        variables = ctx.get("variables", {})
        if variables:
            lines.append("**Key Variables**:")
            for key, value in variables.items():
                lines.append(f"  - {key}: {value}")
            lines.append("")

        # Errors
        errors = ctx.get("errors", [])
        if errors:
            lines.append("**Errors**:")
            for error in errors:
                resolution = f" (resolved: {error.get('resolution')})" if error.get("resolution") else ""
                lines.append(f"  - [{error.get('error_type')}] {error.get('error_message')}{resolution}")
            lines.append("")

        return "\n".join(lines)

    @property
    def memory(self) -> Memory:
        """Get the underlying Memory instance."""
        return self._memory

    @property
    def active_task_count(self) -> int:
        """Get the number of active tasks."""
        return len(self._task_contexts)

    def get_all_tasks(self) -> list[dict[str, Any]]:
        """Get all active task contexts."""
        return list(self._task_contexts.values())
