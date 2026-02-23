"""
System Rule Store

Manages system-level rules that persist across all tasks.
Rules are configured by administrators and cannot be modified by AI.

Reference:
- docs/memory-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


class RuleCategory(Enum):
    """Rule category for classification and filtering"""

    COMPLIANCE = "compliance"  # Compliance constraints (e.g., no PII storage)
    SECURITY = "security"  # Security constraints (e.g., no dangerous commands)
    BUSINESS = "business"  # Business rules (e.g., approval workflows)
    CUSTOM = "custom"  # Custom rules


@dataclass
class SystemRule:
    """
    System rule definition.

    Rules are permanent storage, not task-specific.
    They are configured by administrators and injected into system prompts.

    Attributes:
        id: Unique rule identifier
        category: Rule category for classification
        content: Rule content/description
        priority: Priority level 1-10 (higher = more important)
        enabled: Whether rule is active
        created_by: Administrator who created the rule
        created_at: Creation timestamp
    """

    id: str
    category: RuleCategory
    content: str
    priority: int  # 1-10, higher = more important
    enabled: bool = True
    created_by: str = "system"
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "id": self.id,
            "category": self.category.value,
            "content": self.content,
            "priority": self.priority,
            "enabled": self.enabled,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SystemRule":
        """Create from dictionary"""
        return cls(
            id=data["id"],
            category=RuleCategory(data["category"]),
            content=data["content"],
            priority=data.get("priority", 5),
            enabled=data.get("enabled", True),
            created_by=data.get("created_by", "system"),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if "created_at" in data
                else datetime.now()
            ),
        )


class SystemRuleStore:
    """
    System rule storage manager.

    Loads rules from YAML/JSON configuration files and provides
    query methods for rule retrieval.

    Example YAML format:
        rules:
          - id: rule-001
            category: compliance
            content: "Do not store sensitive information"
            priority: 10
            enabled: true

    Example JSON format:
        {
            "rules": [
                {
                    "id": "rule-001",
                    "category": "compliance",
                    "content": "Do not store sensitive information",
                    "priority": 10,
                    "enabled": true
                }
            ]
        }

    Example usage:
        store = SystemRuleStore()
        store.load_from_yaml("config/rules.yaml")

        # Get all enabled rules (sorted by priority)
        rules = store.get_enabled_rules()

        # Get rules by category
        compliance_rules = store.get_rules_by_category(RuleCategory.COMPLIANCE)
    """

    def __init__(self) -> None:
        """Initialize empty rule store"""
        self._rules: list[SystemRule] = []

    def load_from_yaml(self, path: str) -> None:
        """
        Load rules from YAML file.

        Args:
            path: Path to YAML file

        Raises:
            FileNotFoundError: If file does not exist
            yaml.YAMLError: If YAML parsing fails
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Rules file not found: {path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self._parse_rules_data(data)

    def load_from_json(self, path: str) -> None:
        """
        Load rules from JSON file.

        Args:
            path: Path to JSON file

        Raises:
            FileNotFoundError: If file does not exist
            json.JSONDecodeError: If JSON parsing fails
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Rules file not found: {path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._parse_rules_data(data)

    def _parse_rules_data(self, data: dict[str, Any] | None) -> None:
        """
        Parse rules from loaded data.

        Args:
            data: Dictionary containing 'rules' key with list of rule dicts
        """
        if not data or "rules" not in data:
            self._rules = []
            return

        self._rules = [SystemRule.from_dict(rule_data) for rule_data in data["rules"]]

    def get_enabled_rules(self) -> list[SystemRule]:
        """
        Get all enabled rules, sorted by priority (descending).

        Returns:
            List of enabled SystemRule objects, sorted by priority.
            Higher priority rules come first.
        """
        enabled = [rule for rule in self._rules if rule.enabled]
        return sorted(enabled, key=lambda r: r.priority, reverse=True)

    def get_rules_by_category(self, category: RuleCategory) -> list[SystemRule]:
        """
        Get rules by category, sorted by priority (descending).

        Args:
            category: RuleCategory to filter by

        Returns:
            List of SystemRule objects matching the category.
            Only enabled rules are returned.
            Sorted by priority (higher first).
        """
        matching = [
            rule
            for rule in self._rules
            if rule.category == category and rule.enabled
        ]
        return sorted(matching, key=lambda r: r.priority, reverse=True)

    def get_rule_by_id(self, rule_id: str) -> SystemRule | None:
        """
        Get a specific rule by ID.

        Args:
            rule_id: Rule identifier

        Returns:
            SystemRule if found, None otherwise
        """
        for rule in self._rules:
            if rule.id == rule_id:
                return rule
        return None

    def add_rule(self, rule: SystemRule) -> None:
        """
        Add a new rule to the store.

        Args:
            rule: SystemRule to add
        """
        self._rules.append(rule)

    def remove_rule(self, rule_id: str) -> bool:
        """
        Remove a rule by ID.

        Args:
            rule_id: Rule identifier

        Returns:
            True if rule was removed, False if not found
        """
        for i, rule in enumerate(self._rules):
            if rule.id == rule_id:
                self._rules.pop(i)
                return True
        return False

    def clear_rules(self) -> None:
        """Clear all rules from the store."""
        self._rules = []

    @property
    def rule_count(self) -> int:
        """Get total number of rules (including disabled)."""
        return len(self._rules)

    def to_prompt(self) -> str:
        """
        Generate prompt-formatted string of enabled rules.

        Returns:
            Formatted string for injection into system prompt.
        """
        rules = self.get_enabled_rules()
        if not rules:
            return ""

        lines = ["## System Rules", ""]
        for rule in rules:
            lines.append(f"- [{rule.category.value}] {rule.content}")

        return "\n".join(lines)
