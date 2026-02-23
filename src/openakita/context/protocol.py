"""
Context Backend Protocol

Define abstract protocol interface for Context backends.
The Context system manages conversation history and context assembly
for LLM interactions.

Reference:
- docs/context-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ContextBackend(Protocol):
    """
    Context Backend Protocol.

    This is an abstract protocol defining the interface for Context systems.
    Supports multiple backend implementations:
    - LegacyContextBackend: Wraps existing ContextManager for backward compatibility
    - EnterpriseContextManager: Enterprise three-layer context implementation

    The Context system provides:
    1. System context (identity, rules, tools manifest) - permanent
    2. Task context (step summaries, key variables) - task lifecycle
    3. Conversation context (message history) - sliding window

    Key optimization: Uses sliding window instead of LLM compression,
    reducing context build latency from 2-5s to <50ms.

    Example:
        def process_with_context(backend: ContextBackend):
            backend.initialize(identity="I am an assistant", rules=["Be helpful"])
            backend.start_task("task-001", "tenant-001", "search", "Search task")
            backend.add_message("session-001", "user", "Hello")

            system_prompt, messages = backend.build_context("task-001", "session-001")

            backend.end_task("task-001")
            backend.clear_session("session-001")
    """

    def build_context(
        self, task_id: str, session_id: str
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Build complete context for LLM interaction.

        Assembles context from all three layers:
        1. System context (identity, rules, tools)
        2. Task context (step summaries, variables)
        3. Conversation context (message history with sliding window)

        Args:
            task_id: Task identifier for task-level context
            session_id: Session identifier for conversation history

        Returns:
            tuple containing:
            - str: System prompt with identity, rules, and task context
            - list[dict]: List of message dicts with role and content

        Example:
            system_prompt, messages = backend.build_context("task-001", "session-001")
            # system_prompt contains: identity + rules + task context
            # messages contains: conversation history (max 20 rounds)
        """
        ...

    def add_message(
        self, session_id: str, role: str, content: str | list[dict[str, Any]]
    ) -> None:
        """
        Add a message to the conversation history.

        Messages are stored per-session and will be included in
        build_context calls. Sliding window is applied to limit
        conversation rounds (default: 20 rounds).

        Args:
            session_id: Session identifier
            role: Message role ("user", "assistant", "tool", "system")
            content: Message content (string or content block list)

        Example:
            backend.add_message("session-001", "user", "Hello")
            backend.add_message("session-001", "assistant", [
                {"type": "text", "text": "Hi there!"},
                {"type": "tool_use", "id": "tool-1", "name": "search", "input": {}}
            ])
            backend.add_message("session-001", "tool", {
                "tool_call_id": "tool-1",
                "content": "Search results..."
            })
        """
        ...

    def get_stats(self, task_id: str, session_id: str) -> dict[str, Any]:
        """
        Get context statistics.

        Returns statistics about the current context state for
        monitoring and debugging purposes.

        Args:
            task_id: Task identifier
            session_id: Session identifier

        Returns:
            dict: Statistics including:
                - system_tokens: Estimated tokens in system context
                - task_tokens: Estimated tokens in task context
                - conversation_tokens: Estimated tokens in conversation
                - conversation_rounds: Number of conversation rounds
                - step_count: Number of task steps recorded
                - variable_count: Number of key variables

        Example:
            stats = backend.get_stats("task-001", "session-001")
            print(f"Context size: {stats['system_tokens'] + stats['conversation_tokens']} tokens")
        """
        ...

    def clear_session(self, session_id: str) -> None:
        """
        Clear session data.

        Removes all conversation history for the specified session.
        Call this when starting a new conversation or cleaning up.

        Args:
            session_id: Session identifier to clear

        Example:
            backend.clear_session("session-001")
        """
        ...

    def initialize(
        self,
        identity: str,
        rules: list[str] | None = None,
        tools_manifest: str | None = None,
    ) -> None:
        """
        Initialize system context.

        Sets up the permanent system context layer with agent identity,
        rules, and available tools. Must be called before using other methods.

        Args:
            identity: Agent identity description (who am I)
            rules: List of behavioral rules/constraints
            tools_manifest: Description of available tools

        Example:
            backend.initialize(
                identity="I am a helpful AI assistant",
                rules=[
                    "Always be respectful",
                    "Do not share sensitive information"
                ],
                tools_manifest="Available tools: search, calculator, file_reader"
            )
        """
        ...

    def start_task(
        self, task_id: str, tenant_id: str, task_type: str, description: str
    ) -> None:
        """
        Start a task context.

        Initializes task-level context for the specified task.
        Task context includes step summaries and key variables
        that accumulate during task execution.

        Args:
            task_id: Unique task identifier
            tenant_id: Tenant ID for multi-tenant isolation
            task_type: Type of task (e.g., "search", "analysis")
            description: Brief description of task goal

        Example:
            backend.start_task(
                task_id="task-001",
                tenant_id="tenant-001",
                task_type="search",
                description="Search for information about X"
            )
        """
        ...

    def end_task(self, task_id: str) -> None:
        """
        End a task context.

        Cleans up task-level context. Call this when task execution
        completes or is cancelled.

        Args:
            task_id: Task identifier to end

        Example:
            backend.end_task("task-001")
        """
        ...

    def record_step(
        self,
        task_id: str,
        step_id: str,
        step_name: str,
        summary: str,
        variables: dict[str, Any],
    ) -> None:
        """
        Record a step completion in task context.

        Adds step information to the task context for use in
        subsequent context builds.

        Args:
            task_id: Task identifier
            step_id: Step identifier
            step_name: Human-readable step name
            summary: Brief summary of what the step accomplished
            variables: Key variables extracted/used in this step

        Example:
            backend.record_step(
                task_id="task-001",
                step_id="step-001",
                step_name="Web Search",
                summary="Found 5 relevant results",
                variables={"query": "test", "result_count": 5}
            )
        """
        ...
