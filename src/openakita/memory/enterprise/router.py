"""
Enterprise Memory Router

Unified memory router that coordinates three-layer storage:
1. System Rules - Permanent business constraints
2. Task Context - Task-level step summaries and variables
3. Skills - Optional skill pattern cache

This router implements the MemoryBackend protocol and provides a clean
interface for the Agent to interact with the memory system.

Reference:
- docs/memory-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

from typing import Any

from openakita.memory.enterprise.config import EnterpriseMemoryConfig
from openakita.memory.enterprise.rules import SystemRuleStore
from openakita.memory.enterprise.task_context import TaskContextStore


class EnterpriseMemoryRouter:
    """
    Enterprise Memory Router.

    This is the main entry point for the Enterprise Memory system.
    It coordinates three-layer storage and implements the MemoryBackend protocol.

    Layer 1 - System Rules (Permanent):
        Rules loaded from configuration file. These are business constraints
        that apply to all tasks and cannot be modified by AI.

    Layer 2 - Task Context (Task Lifecycle):
        Step summaries and key variables for the current task.
        Created when task starts, destroyed when task ends.

    Layer 3 - Skills (Optional):
        Cached skill patterns that match task types.
        Not implemented in this version.

    Example:
        config = EnterpriseMemoryConfig(rules_path="config/rules.yaml")
        router = EnterpriseMemoryRouter(config)

        # Start a task
        router.start_task("task-001", "tenant-001", "search", "Search for info")

        # Record progress
        router.record_step_completion(
            "task-001", "step-001", "Web Search",
            "Found 5 results", {"query": "info"}
        )

        # Get context for prompt injection
        context = await router.get_injection_context("task-001", "search", "query")

        # End task (cleans up task context)
        router.end_task("task-001")
    """

    def __init__(self, config: EnterpriseMemoryConfig | None = None) -> None:
        """
        Initialize the memory router.

        Args:
            config: Configuration for the router. If None, uses defaults.
        """
        self._config = config or EnterpriseMemoryConfig()

        # Layer 1: System Rules (permanent)
        self._rule_store = SystemRuleStore()
        if self._config.rules_path:
            self._load_rules(self._config.rules_path)

        # Layer 2: Task Context (task lifecycle)
        self._task_store = TaskContextStore()

        # Layer 3: Skills (optional, not implemented yet)
        # self._skill_store = SkillStore() if config.skills_path else None
        self._skill_store = None

    def _load_rules(self, path: str) -> None:
        """
        Load system rules from configuration file.

        Args:
            path: Path to YAML or JSON file
        """
        if path.endswith(".yaml") or path.endswith(".yml"):
            self._rule_store.load_from_yaml(path)
        elif path.endswith(".json"):
            self._rule_store.load_from_json(path)
        else:
            raise ValueError(f"Unsupported rules file format: {path}")

    # ========== MemoryBackend Protocol Implementation ==========

    async def get_injection_context(
        self, task_id: str, task_type: str, query: str
    ) -> str:
        """
        Get memory context for injection into system prompt.

        This assembles context from all three layers:
        1. System Rules (always included if present)
        2. Task Context (included if task exists)
        3. Skills (optional, matches task type)

        Args:
            task_id: Unique task identifier
            task_type: Task type for skill matching
            query: User query (used for semantic matching in future)

        Returns:
            Formatted context string for system prompt injection
        """
        sections: list[str] = []

        # Layer 1: System Rules
        rules_prompt = self._rule_store.to_prompt()
        if rules_prompt:
            sections.append(rules_prompt)

        # Layer 2: Task Context
        task_prompt = self._task_store.to_prompt(task_id)
        if task_prompt:
            sections.append(task_prompt)

        # Layer 3: Skills (optional)
        # if self._skill_store:
        #     skills_prompt = self._skill_store.to_prompt(task_type)
        #     if skills_prompt:
        #         sections.append(skills_prompt)

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

        Args:
            task_id: Unique task identifier
            step_id: Unique step identifier
            step_name: Name of the step
            summary: Step completion summary
            variables: Key variables extracted from this step
        """
        self._task_store.record_step_completion(
            task_id, step_id, step_name, summary, variables
        )

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

        Args:
            task_id: Unique task identifier
            step_id: Step where error occurred
            error_type: Type of error
            error_message: Error message
            resolution: Resolution if resolved, None otherwise
        """
        self._task_store.record_error(
            task_id, step_id, error_type, error_message, resolution
        )

    def start_task(
        self, task_id: str, tenant_id: str, task_type: str, description: str
    ) -> None:
        """
        Start a new task.

        Args:
            task_id: Unique task identifier
            tenant_id: Tenant ID for multi-tenant isolation
            task_type: Task type
            description: Task description/goal
        """
        self._task_store.start_task(task_id, tenant_id, task_type, description)

    def end_task(self, task_id: str) -> None:
        """
        End a task and clean up its context.

        Args:
            task_id: Unique task identifier
        """
        self._task_store.end_task(task_id)

    def get_stats(self, task_id: str) -> dict[str, Any]:
        """
        Get statistics for a task.

        Args:
            task_id: Unique task identifier

        Returns:
            Dictionary with task statistics
        """
        task_stats = self._task_store.get_stats(task_id)

        # Add rule count
        task_stats["rule_count"] = self._rule_store.rule_count

        # Add context size if task exists
        if task_stats:
            context = self._task_store.to_prompt(task_id)
            task_stats["context_size"] = len(context)

        return task_stats

    # ========== Additional Helper Methods ==========

    @property
    def rule_store(self) -> SystemRuleStore:
        """Get the underlying rule store for direct manipulation."""
        return self._rule_store

    @property
    def task_store(self) -> TaskContextStore:
        """Get the underlying task store for direct manipulation."""
        return self._task_store

    def get_tasks_by_tenant(self, tenant_id: str) -> list[Any]:
        """
        Get all active tasks for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            List of task memory objects for the tenant
        """
        return self._task_store.get_tasks_by_tenant(tenant_id)

    @property
    def active_task_count(self) -> int:
        """Get the number of active tasks."""
        return self._task_store.task_count

    def clear_all_tasks(self) -> None:
        """Clear all task contexts."""
        self._task_store.clear_all()

    def clear_all_rules(self) -> None:
        """Clear all system rules."""
        self._rule_store.clear_rules()

    def reload_rules(self, path: str | None = None) -> None:
        """
        Reload system rules from configuration file.

        Args:
            path: Path to rules file. If None, uses config.rules_path.
        """
        rules_path = path or self._config.rules_path
        if rules_path:
            self._rule_store.clear_rules()
            self._load_rules(rules_path)
            # Update config to remember the path for future reloads
            self._config.rules_path = rules_path
