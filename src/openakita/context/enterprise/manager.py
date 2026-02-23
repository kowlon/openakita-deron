"""
Enterprise Context Manager

Unified context manager that coordinates the three context layers:
1. SystemContext - Permanent (identity, rules, tools)
2. TaskContext - Task lifecycle (step summaries, variables)
3. ConversationContext - Sliding window (message history)

Reference:
- docs/context-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

from typing import Any

from openakita.context.enterprise.config import ContextConfig
from openakita.context.enterprise.conversation_context import ConversationContext
from openakita.context.enterprise.system_context import SystemContext
from openakita.context.enterprise.task_context import TaskContext


class EnterpriseContextManager:
    """
    Enterprise Context Manager - Unified context coordinator.

    Manages three layers of context:
    - SystemContext: Permanent, initialized once at startup
    - TaskContext: Per-task lifecycle, created/destroyed with tasks
    - ConversationContext: Per-session, sliding window

    This manager provides the build_context() method that assembles
    all three layers into the format needed for LLM API calls.

    Example:
        config = ContextConfig(max_conversation_rounds=20)
        manager = EnterpriseContextManager(config)

        # Initialize system context (once at startup)
        manager.initialize(
            identity="I am a helpful assistant",
            rules=["Be helpful", "Be safe"],
            tools_manifest="search, calculator"
        )

        # Start a task
        manager.start_task("task-001", "tenant-001", "search", "Search for info")

        # Add conversation
        manager.add_message("session-001", "user", "Hello")

        # Build context for LLM
        system_prompt, messages = manager.build_context("task-001", "session-001")

        # End task
        manager.end_task("task-001")
    """

    def __init__(self, config: ContextConfig | None = None):
        """
        Initialize the context manager.

        Args:
            config: Configuration object. Uses defaults if not provided.
        """
        self.config = config or ContextConfig()
        self.system_ctx: SystemContext | None = None
        self.task_contexts: dict[str, TaskContext] = {}
        self.conversation_contexts: dict[str, ConversationContext] = {}

    # ========== Initialization ==========

    def initialize(
        self,
        identity: str,
        rules: list[str] | None = None,
        tools_manifest: str | None = None,
    ) -> None:
        """
        Initialize system context.

        Should be called once at application startup.

        Args:
            identity: Agent identity description
            rules: List of behavioral rules
            tools_manifest: Description of available tools
        """
        self.system_ctx = SystemContext(
            identity=identity,
            rules=rules or [],
            tools_manifest=tools_manifest or "",
            max_tokens=self.config.max_system_tokens,
        )

    # ========== Task Management ==========

    def start_task(
        self,
        task_id: str,
        tenant_id: str,
        task_type: str,
        description: str,
        total_steps: int = 0,
    ) -> TaskContext:
        """
        Start a new task context.

        Args:
            task_id: Unique task identifier
            tenant_id: Tenant ID for multi-tenant isolation
            task_type: Type of task
            description: Task description/goal
            total_steps: Expected number of steps (0 if unknown)

        Returns:
            Created TaskContext
        """
        ctx = TaskContext(
            task_id=task_id,
            tenant_id=tenant_id,
            task_type=task_type,
            task_description=description,
            total_steps=total_steps,
        )
        self.task_contexts[task_id] = ctx
        return ctx

    def end_task(self, task_id: str) -> bool:
        """
        End a task and clean up its context.

        Args:
            task_id: Task identifier

        Returns:
            True if task was found and removed
        """
        if task_id in self.task_contexts:
            del self.task_contexts[task_id]
            # Clean up associated conversation contexts
            to_remove = [
                sid
                for sid in self.conversation_contexts
                if sid.startswith(f"{task_id}:")
            ]
            for sid in to_remove:
                del self.conversation_contexts[sid]
            return True
        return False

    def get_task(self, task_id: str) -> TaskContext | None:
        """
        Get task context by ID.

        Args:
            task_id: Task identifier

        Returns:
            TaskContext if found, None otherwise
        """
        return self.task_contexts.get(task_id)

    def record_step(
        self,
        task_id: str,
        step_id: str,
        step_name: str,
        summary: str,
        variables: dict[str, Any] | None = None,
    ) -> bool:
        """
        Record a step completion in task context.

        Args:
            task_id: Task identifier
            step_id: Step identifier
            step_name: Step name
            summary: Completion summary
            variables: Key variables from this step

        Returns:
            True if task exists and step was recorded
        """
        ctx = self.task_contexts.get(task_id)
        if not ctx:
            return False

        ctx.add_step_summary(step_name, summary)
        if variables:
            ctx.add_variables(variables)
        return True

    # ========== Conversation Management ==========

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str | list[dict[str, Any]],
    ) -> None:
        """
        Add a message to conversation context.

        Args:
            session_id: Session identifier
            role: Message role
            content: Message content
        """
        if session_id not in self.conversation_contexts:
            self.conversation_contexts[session_id] = ConversationContext(
                max_rounds=self.config.max_conversation_rounds,
                max_tokens=self.config.max_conversation_tokens,
            )

        self.conversation_contexts[session_id].add_message(role, content)

    def get_conversation(self, session_id: str) -> ConversationContext | None:
        """
        Get conversation context by session ID.

        Args:
            session_id: Session identifier

        Returns:
            ConversationContext if found, None otherwise
        """
        return self.conversation_contexts.get(session_id)

    def clear_session(self, session_id: str) -> bool:
        """
        Clear a conversation session.

        Args:
            session_id: Session identifier

        Returns:
            True if session was found and cleared
        """
        if session_id in self.conversation_contexts:
            self.conversation_contexts[session_id].clear()
            return True
        return False

    # ========== Context Building ==========

    def build_context(
        self, task_id: str, session_id: str
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Build complete context for LLM API call.

        Assembles all three layers:
        1. System context (identity, rules, tools)
        2. Task context (description, steps, variables)
        3. Conversation context (message history)

        Args:
            task_id: Task identifier
            session_id: Session identifier

        Returns:
            tuple of (system_prompt, messages)
        """
        parts = []

        # Layer 1: System context
        if self.system_ctx:
            parts.append(self.system_ctx.to_prompt())

        # Layer 2: Task context
        task_ctx = self.task_contexts.get(task_id)
        if task_ctx:
            parts.append(task_ctx.to_prompt())

        # Combine system parts
        system_prompt = "\n\n---\n\n".join(parts) if parts else ""

        # Layer 3: Conversation context
        conv_ctx = self.conversation_contexts.get(session_id)
        messages = conv_ctx.to_messages() if conv_ctx else []

        return system_prompt, messages

    # ========== Statistics ==========

    def get_stats(self, task_id: str, session_id: str) -> dict[str, Any]:
        """
        Get context statistics.

        Args:
            task_id: Task identifier
            session_id: Session identifier

        Returns:
            Dictionary with statistics from all layers
        """
        stats = {
            "system": None,
            "task": None,
            "conversation": None,
            "total_estimated_tokens": 0,
        }

        # System stats
        if self.system_ctx:
            stats["system"] = self.system_ctx.get_stats()
            stats["total_estimated_tokens"] += stats["system"]["estimated_tokens"]

        # Task stats
        task_ctx = self.task_contexts.get(task_id)
        if task_ctx:
            stats["task"] = task_ctx.get_stats()
            stats["total_estimated_tokens"] += stats["task"]["estimated_tokens"]

        # Conversation stats
        conv_ctx = self.conversation_contexts.get(session_id)
        if conv_ctx:
            stats["conversation"] = conv_ctx.get_stats()
            stats["total_estimated_tokens"] += conv_ctx.estimate_tokens()

        return stats

    def get_task_count(self) -> int:
        """Get number of active tasks."""
        return len(self.task_contexts)

    def get_session_count(self) -> int:
        """Get number of active sessions."""
        return len(self.conversation_contexts)

    def clear_all(self) -> None:
        """Clear all task and conversation contexts (keep system context)."""
        self.task_contexts.clear()
        self.conversation_contexts.clear()
