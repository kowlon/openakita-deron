"""
Legacy Context Backend Adapter

This adapter wraps the existing ContextManager to implement the ContextBackend
protocol, providing backward compatibility with the legacy context system.

The legacy context system uses:
- ContextManager for context compression (LLM-based)
- In-memory message storage per session
- Task context tracking

Reference:
- docs/context-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

import asyncio
import logging
from typing import Any

from openakita.core.context_manager import ContextManager

logger = logging.getLogger(__name__)


class LegacyContextBackend:
    """
    Legacy Context Backend Adapter.

    Wraps the existing ContextManager to implement the ContextBackend protocol.
    This allows the Agent to use either the legacy or enterprise context system
    through a unified interface.

    Key differences from EnterpriseContextManager:
    - Uses LLM-based compression (slower, 2-5s latency)
    - Stores messages in memory (no sliding window by default)
    - No structured three-layer separation

    Note:
        This adapter provides compatibility but doesn't support all enterprise
        features like sliding window (without LLM) or structured three-layer context.

    Example:
        from openakita.core.brain import Brain
        from openakita.context.backends.legacy_adapter import LegacyContextBackend

        brain = Brain(...)
        backend = LegacyContextBackend(brain)

        # Use through ContextBackend protocol
        backend.initialize(identity="I am an assistant", rules=["Be helpful"])
        backend.start_task("task-001", "tenant-001", "search", "Search task")
        backend.add_message("session-001", "user", "Hello")

        system_prompt, messages = backend.build_context("task-001", "session-001")
    """

    def __init__(self, brain: Any = None, cancel_event: asyncio.Event | None = None) -> None:
        """
        Initialize the legacy backend adapter.

        Args:
            brain: Brain instance for LLM compression (optional).
                   If None, compression will be disabled.
            cancel_event: Optional cancel event for interrupting LLM calls.
        """
        self._brain = brain
        self._cancel_event = cancel_event
        self._context_manager: ContextManager | None = None

        # System context
        self._identity: str = ""
        self._rules: list[str] = []
        self._tools_manifest: str = ""

        # Session message storage: session_id -> list of messages
        self._sessions: dict[str, list[dict[str, Any]]] = {}

        # Task context storage: task_id -> task context dict
        self._tasks: dict[str, dict[str, Any]] = {}

        # Initialize ContextManager if brain is provided
        if brain is not None:
            self._context_manager = ContextManager(brain, cancel_event)

    def set_cancel_event(self, event: asyncio.Event | None) -> None:
        """Update cancel event for LLM compression."""
        self._cancel_event = event
        if self._context_manager is not None:
            self._context_manager.set_cancel_event(event)

    # ========== ContextBackend Protocol Implementation ==========

    def initialize(
        self,
        identity: str,
        rules: list[str] | None = None,
        tools_manifest: str | None = None,
    ) -> None:
        """
        Initialize system context.

        Args:
            identity: Agent identity description
            rules: List of behavioral rules
            tools_manifest: Description of available tools
        """
        self._identity = identity
        self._rules = rules or []
        self._tools_manifest = tools_manifest or ""

        logger.info(f"LegacyContextBackend initialized with identity: {identity[:50]}...")

    def start_task(
        self, task_id: str, tenant_id: str, task_type: str, description: str
    ) -> None:
        """
        Start a task context.

        Args:
            task_id: Unique task identifier
            tenant_id: Tenant ID for multi-tenant isolation
            task_type: Type of task
            description: Task description/goal
        """
        self._tasks[task_id] = {
            "task_id": task_id,
            "tenant_id": tenant_id,
            "task_type": task_type,
            "description": description,
            "steps": [],
            "variables": {},
        }

        logger.info(f"Started task: {task_id} - {description}")

    def end_task(self, task_id: str) -> None:
        """
        End a task context.

        Args:
            task_id: Task identifier to end
        """
        if task_id in self._tasks:
            del self._tasks[task_id]
            logger.info(f"Ended task: {task_id}")
        else:
            logger.warning(f"Task {task_id} not found when ending")

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

        Args:
            task_id: Task identifier
            step_id: Step identifier
            step_name: Human-readable step name
            summary: Step summary
            variables: Key variables from this step
        """
        if task_id not in self._tasks:
            logger.warning(f"Task {task_id} not found, creating context")
            self._tasks[task_id] = {
                "task_id": task_id,
                "tenant_id": "default",
                "task_type": "unknown",
                "description": "Auto-created task",
                "steps": [],
                "variables": {},
            }

        task = self._tasks[task_id]

        # Record step
        task["steps"].append({
            "step_id": step_id,
            "step_name": step_name,
            "summary": summary,
            "variables": variables,
        })

        # Update variables
        task["variables"].update(variables)

        logger.debug(f"Recorded step: {step_name} for task {task_id}")

    def add_message(
        self, session_id: str, role: str, content: str | list[dict[str, Any]]
    ) -> None:
        """
        Add a message to the conversation history.

        Args:
            session_id: Session identifier
            role: Message role ("user", "assistant", "tool", "system")
            content: Message content
        """
        if session_id not in self._sessions:
            self._sessions[session_id] = []

        message: dict[str, Any] = {"role": role, "content": content}

        self._sessions[session_id].append(message)

        logger.debug(f"Added message to session {session_id}: role={role}")

    def build_context(
        self, task_id: str, session_id: str
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Build complete context for LLM interaction.

        This is a synchronous wrapper that returns context without compression.
        For async compression, use build_context_async instead.

        Args:
            task_id: Task identifier
            session_id: Session identifier

        Returns:
            tuple: (system_prompt, messages)
        """
        # Build system prompt
        system_prompt = self._build_system_prompt(task_id)

        # Get messages
        messages = self._sessions.get(session_id, [])

        return system_prompt, list(messages)

    async def build_context_async(
        self,
        task_id: str,
        session_id: str,
        *,
        tools: list | None = None,
        max_tokens: int | None = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Build complete context with async LLM compression.

        Uses the legacy ContextManager for LLM-based compression when
        the context approaches token limits.

        Args:
            task_id: Task identifier
            session_id: Session identifier
            tools: Tool definitions for token estimation
            max_tokens: Maximum context tokens

        Returns:
            tuple: (system_prompt, compressed_messages)
        """
        # Build system prompt
        system_prompt = self._build_system_prompt(task_id)

        # Get messages
        messages = self._sessions.get(session_id, [])

        # Apply LLM compression if ContextManager is available
        if self._context_manager is not None and messages:
            try:
                messages = await self._context_manager.compress_if_needed(
                    messages,
                    system_prompt=system_prompt,
                    tools=tools,
                    max_tokens=max_tokens,
                )
                logger.debug(f"Context compressed for session {session_id}")
            except Exception as e:
                logger.warning(f"Context compression failed: {e}, using uncompressed messages")

        return system_prompt, list(messages)

    def get_stats(self, task_id: str, session_id: str) -> dict[str, Any]:
        """
        Get context statistics.

        Args:
            task_id: Task identifier
            session_id: Session identifier

        Returns:
            dict: Statistics dictionary
        """
        task = self._tasks.get(task_id, {})
        messages = self._sessions.get(session_id, [])

        # Estimate tokens
        system_tokens = self._estimate_tokens(self._build_system_prompt(task_id))
        conversation_tokens = self._estimate_messages_tokens(messages)

        # Task tokens
        task_tokens = 0
        if task:
            task_str = self._format_task_context(task)
            task_tokens = self._estimate_tokens(task_str)

        # Count rounds (user messages)
        rounds = sum(1 for m in messages if m.get("role") == "user")

        return {
            "system_tokens": system_tokens,
            "task_tokens": task_tokens,
            "conversation_tokens": conversation_tokens,
            "total_tokens": system_tokens + task_tokens + conversation_tokens,
            "conversation_rounds": rounds,
            "message_count": len(messages),
            "step_count": len(task.get("steps", [])) if task else 0,
            "variable_count": len(task.get("variables", {})) if task else 0,
            "backend_type": "legacy",
            "compression_enabled": self._context_manager is not None,
        }

    def clear_session(self, session_id: str) -> None:
        """
        Clear session data.

        Args:
            session_id: Session identifier to clear
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Cleared session: {session_id}")

    # ========== Helper Methods ==========

    def _build_system_prompt(self, task_id: str) -> str:
        """
        Build the system prompt from identity, rules, and task context.

        Args:
            task_id: Task identifier

        Returns:
            Complete system prompt string
        """
        sections: list[str] = []

        # Identity
        if self._identity:
            sections.append(f"# Identity\n\n{self._identity}")

        # Rules
        if self._rules:
            rules_text = "\n".join(f"- {rule}" for rule in self._rules)
            sections.append(f"# Rules\n\n{rules_text}")

        # Tools manifest
        if self._tools_manifest:
            sections.append(f"# Available Tools\n\n{self._tools_manifest}")

        # Task context
        if task_id in self._tasks:
            task_ctx = self._format_task_context(self._tasks[task_id])
            if task_ctx:
                sections.append(task_ctx)

        return "\n\n".join(sections)

    def _format_task_context(self, task: dict[str, Any]) -> str:
        """
        Format task context for system prompt.

        Args:
            task: Task context dictionary

        Returns:
            Formatted string
        """
        lines = ["# Current Task", ""]

        lines.append(f"**Task**: {task.get('description', 'Unknown')}")
        lines.append(f"**Type**: {task.get('task_type', 'unknown')}")
        lines.append("")

        # Steps
        steps = task.get("steps", [])
        if steps:
            lines.append("**Completed Steps**:")
            for i, step in enumerate(steps, 1):
                lines.append(
                    f"  {i}. {step.get('step_name', 'Unknown')}: {step.get('summary', '')}"
                )
            lines.append("")

        # Variables
        variables = task.get("variables", {})
        if variables:
            lines.append("**Key Variables**:")
            for key, value in variables.items():
                lines.append(f"  - {key}: {value}")
            lines.append("")

        return "\n".join(lines)

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Uses Chinese/English aware estimation:
        - Chinese: ~1.5 chars/token
        - English: ~4 chars/token
        """
        if not text:
            return 0

        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        total_chars = len(text)
        english_chars = total_chars - chinese_chars

        chinese_tokens = chinese_chars / 1.5
        english_tokens = english_chars / 4

        return max(int(chinese_tokens + english_tokens), 1)

    def _estimate_messages_tokens(self, messages: list[dict]) -> int:
        """Estimate token count for message list."""
        if not messages:
            return 0

        import json
        try:
            text = json.dumps(messages, ensure_ascii=False, default=str)
            return max(int(len(text) / 2), 1)
        except Exception:
            total = 0
            for msg in messages:
                content = msg.get("content", "")
                if isinstance(content, str):
                    total += self._estimate_tokens(content)
                elif isinstance(content, list):
                    import json
                    total += self._estimate_tokens(
                        json.dumps(content, ensure_ascii=False, default=str)
                    )
                total += 4  # overhead per message
            return total

    # ========== Properties ==========

    @property
    def context_manager(self) -> ContextManager | None:
        """Get the underlying ContextManager instance."""
        return self._context_manager

    @property
    def active_task_count(self) -> int:
        """Get the number of active tasks."""
        return len(self._tasks)

    @property
    def active_session_count(self) -> int:
        """Get the number of active sessions."""
        return len(self._sessions)

    def get_all_tasks(self) -> list[dict[str, Any]]:
        """Get all active task contexts."""
        return list(self._tasks.values())

    def get_session_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Get all messages for a session."""
        return list(self._sessions.get(session_id, []))
