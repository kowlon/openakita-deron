"""
Enterprise Memory Configuration

Configuration classes for Enterprise Memory backend.

Reference:
- docs/memory-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class EnterpriseMemoryConfig:
    """
    Configuration for EnterpriseMemoryRouter.

    This configuration controls the behavior of the enterprise memory system,
    including rule loading and optional skill caching.

    Attributes:
        rules_path: Path to YAML/JSON file containing system rules.
                   If not provided, no rules will be loaded.
        skills_path: Optional path to JSON file containing skill patterns.
                    If not provided, skill caching will be disabled.
        context_backend: Backend type for context storage (always "memory" for now)
        max_step_summaries: Maximum number of step summaries to retain per task
        max_key_variables: Maximum number of key variables to retain per task

    Example:
        config = EnterpriseMemoryConfig(
            rules_path="/config/rules.yaml",
            skills_path="/config/skills.json",
        )
        router = EnterpriseMemoryRouter(config)
    """

    rules_path: str | None = None
    skills_path: str | None = None
    context_backend: Literal["memory"] = "memory"
    max_step_summaries: int = 20
    max_key_variables: int = 50

    def validate(self) -> list[str]:
        """
        Validate configuration and return list of warnings.

        Returns:
            List of warning messages (empty if valid)
        """
        warnings = []

        if self.rules_path:
            if not Path(self.rules_path).exists():
                warnings.append(f"Rules file not found: {self.rules_path}")

        if self.skills_path:
            if not Path(self.skills_path).exists():
                warnings.append(f"Skills file not found: {self.skills_path}")

        if self.max_step_summaries < 1:
            warnings.append("max_step_summaries should be at least 1")

        if self.max_key_variables < 1:
            warnings.append("max_key_variables should be at least 1")

        return warnings
