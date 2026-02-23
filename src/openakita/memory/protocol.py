"""
Memory Backend Protocol

Define abstract protocol interface for Memory backends (Legacy/Enterprise).

Reference:
- docs/memory-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MemoryBackend(Protocol):
    """
    Memory Backend Protocol.

    This is an abstract protocol defining the interface for Memory systems.
    Supports multiple backend implementations:
    - LegacyMemoryBackend: Wraps existing MemoryManager for backward compatibility
    - EnterpriseMemoryRouter: Enterprise three-layer storage implementation

    Example:
        def process_with_memory(backend: MemoryBackend):
            backend.start_task("task-001", "tenant-001", "search", "Search task")
            context = await backend.get_injection_context("task-001", "search", "query")
            backend.end_task("task-001")
    """

    async def get_injection_context(
        self, task_id: str, task_type: str, query: str
    ) -> str:
        """
        Get memory context for injection into system prompt.

        This is the core read method for the Memory system. Returns a formatted
        context string that can be directly injected into the LLM system prompt.

        For Enterprise backend, the return includes:
        1. System Rules - permanent business constraints
        2. Task Context - step summaries and key variables for current task
        3. Skill Cache - skill patterns matching task type (optional)

        Args:
            task_id: Unique task identifier for associating task context
            task_type: Task type (e.g., "search", "analysis", "generation")
                      for matching skill cache
            query: User query content for semantic matching (used by Legacy backend)

        Returns:
            str: Formatted context string for system prompt injection.
                 Returns empty string if no relevant context.

        Example:
            context = await backend.get_injection_context(
                task_id="task-001",
                task_type="search",
                query="Who is John Doe"
            )
        """
        ...

    def record_step_completion(
        self,
        task_id: str,
        step_id: str,
        step_name: str,
        summary: str,
        variables: dict[str, Any],
    ) -> None:
        """
        Record step completion.

        Called when Agent completes a step. The recorded content is used for:
        1. Building task context (for reference by subsequent steps)
        2. Generating step summaries (for context injection)
        3. Extracting key variables (for task tracking)

        Note: This is "rule-based write" mode, no AI auto-extraction needed,
        caller explicitly passes in values.

        Args:
            task_id: Unique task identifier
            step_id: Unique step identifier
            step_name: Step name (e.g., "Web Search", "Data Organization")
            summary: Step completion summary (recommended under 100 chars)
            variables: Key variables extracted/produced by this step

        Example:
            backend.record_step_completion(
                task_id="task-001",
                step_id="step-001",
                step_name="Web Search",
                summary="Search completed, found 5 relevant results",
                variables={"query": "John Doe", "result_count": 5}
            )
        """
        ...

    def record_error(
        self,
        task_id: str,
        step_id: str,
        error_type: str,
        error_message: str,
        resolution: str | None,
    ) -> None:
        """
        Record error.

        Called when a step fails or encounters an exception. The recorded error
        is used for:
        1. Error tracking and debugging
        2. Generating error reports
        3. Reference by subsequent steps for known errors

        Args:
            task_id: Unique task identifier
            step_id: ID of the step where error occurred
            error_type: Error type (e.g., "NetworkError", "TimeoutError")
            error_message: Detailed error message
            resolution: Resolution if resolved, None if unresolved

        Example:
            backend.record_error(
                task_id="task-001",
                step_id="step-002",
                error_type="NetworkError",
                error_message="Request timeout, connection failed",
                resolution=None  # Unresolved
            )

            # Update after successful retry
            backend.record_error(
                task_id="task-001",
                step_id="step-002",
                error_type="NetworkError",
                error_message="Request timeout",
                resolution="Retry succeeded after increasing timeout"
            )
        """
        ...

    def start_task(
        self, task_id: str, tenant_id: str, task_type: str, description: str
    ) -> None:
        """
        Start a task.

        Called when starting a new task. This will:
        1. Create task context (for Enterprise backend)
        2. Initialize task-related storage structures
        3. Set TTL (for backends supporting expiration)

        Args:
            task_id: Unique task identifier
            tenant_id: Tenant ID for multi-tenant isolation
            task_type: Task type (e.g., "search", "analysis", "generation")
            description: Task description briefly stating the goal

        Example:
            backend.start_task(
                task_id="task-001",
                tenant_id="tenant-001",
                task_type="search",
                description="Search for John Doe and create a summary"
            )
        """
        ...

    def end_task(self, task_id: str) -> None:
        """
        End a task.

        Called when task execution completes or aborts. This will:
        1. Mark task as ended
        2. Clean up task context (for Enterprise backend, task-level storage released)
        3. Archive task records (if needed)

        Note: After calling this method, the task context will no longer be
        accessible (unless there is an archiving mechanism).

        Args:
            task_id: Unique task identifier

        Example:
            # After task completes
            backend.end_task("task-001")
        """
        ...

    def get_stats(self, task_id: str) -> dict[str, Any]:
        """
        Get statistics.

        Returns task statistics for monitoring and debugging.

        Args:
            task_id: Unique task identifier

        Returns:
            dict: Statistics dictionary with fields (specific fields depend on backend):
                - step_count: Number of completed steps
                - error_count: Number of errors
                - variable_count: Number of variables
                - context_size: Context size in characters
                - created_at: Task creation time
                - updated_at: Last update time

        Example:
            stats = backend.get_stats("task-001")
            print(f"Completed {stats['step_count']} steps")
            print(f"Encountered {stats['error_count']} errors")
        """
        ...
