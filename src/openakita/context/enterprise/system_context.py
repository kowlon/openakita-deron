"""
System Context

Manages permanent system-level context including identity, rules,
and tools manifest. This context is read-only after initialization.

Reference:
- docs/context-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SystemContext:
    """
    System Context - Permanent read-only context layer.

    Contains identity, rules, and tools manifest that persist
    across all tasks and sessions. Initialized once at startup.

    Attributes:
        identity: Agent identity description (who am I)
        rules: List of behavioral rules/constraints
        tools_manifest: Description of available tools
        max_tokens: Maximum token budget for system context

    Example:
        system_ctx = SystemContext(
            identity="I am a helpful AI assistant",
            rules=["Always be respectful", "Do not share sensitive info"],
            tools_manifest="Available tools: search, calculator, file_reader"
        )

        prompt = system_ctx.to_prompt()
        tokens = system_ctx.estimate_tokens()
    """

    identity: str = ""
    rules: list[str] = field(default_factory=list)
    tools_manifest: str = ""
    max_tokens: int = 8000

    def to_prompt(self) -> str:
        """
        Generate system prompt string.

        Returns:
            Formatted system prompt with identity, rules, and tools.

        Example output:
            # Identity
            I am a helpful AI assistant.

            # Rules
            - Always be respectful
            - Do not share sensitive information

            # Available Tools
            search: Search the web for information
            calculator: Perform calculations
        """
        parts = []

        # Identity section
        if self.identity:
            parts.append("# Identity\n" + self.identity)

        # Rules section
        if self.rules:
            rules_text = "\n".join(f"- {rule}" for rule in self.rules)
            parts.append("# Rules\n" + rules_text)

        # Tools section
        if self.tools_manifest:
            parts.append("# Available Tools\n" + self.tools_manifest)

        return "\n\n".join(parts)

    def estimate_tokens(self, chars_per_token: float = 4.0) -> int:
        """
        Estimate token count for the system context.

        Uses simple character-based estimation. For more accurate
        estimation, use a tokenizer library.

        Args:
            chars_per_token: Average characters per token (default 4)

        Returns:
            Estimated token count
        """
        prompt = self.to_prompt()
        return int(len(prompt) / chars_per_token)

    def is_within_budget(self) -> bool:
        """
        Check if context is within token budget.

        Returns:
            True if estimated tokens <= max_tokens
        """
        return self.estimate_tokens() <= self.max_tokens

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about the system context.

        Returns:
            Dictionary with context statistics
        """
        return {
            "identity_length": len(self.identity),
            "rules_count": len(self.rules),
            "tools_manifest_length": len(self.tools_manifest),
            "estimated_tokens": self.estimate_tokens(),
            "max_tokens": self.max_tokens,
            "within_budget": self.is_within_budget(),
        }

    def add_rule(self, rule: str) -> None:
        """
        Add a rule to the context.

        Args:
            rule: Rule text to add
        """
        self.rules.append(rule)

    def set_identity(self, identity: str) -> None:
        """
        Set the agent identity.

        Args:
            identity: Identity description
        """
        self.identity = identity

    def set_tools_manifest(self, manifest: str) -> None:
        """
        Set the tools manifest.

        Args:
            manifest: Tools description
        """
        self.tools_manifest = manifest

    def clear_rules(self) -> None:
        """Clear all rules."""
        self.rules = []

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        return {
            "identity": self.identity,
            "rules": self.rules,
            "tools_manifest": self.tools_manifest,
            "max_tokens": self.max_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SystemContext":
        """
        Create from dictionary.

        Args:
            data: Dictionary with context data

        Returns:
            SystemContext instance
        """
        return cls(
            identity=data.get("identity", ""),
            rules=data.get("rules", []),
            tools_manifest=data.get("tools_manifest", ""),
            max_tokens=data.get("max_tokens", 8000),
        )

    def __str__(self) -> str:
        """String representation."""
        return f"SystemContext(identity={len(self.identity)} chars, rules={len(self.rules)}, tokens~{self.estimate_tokens()})"

    def __repr__(self) -> str:
        """Detailed representation."""
        return (
            f"SystemContext(identity='{self.identity[:50]}...', "
            f"rules={len(self.rules)}, tools_manifest={len(self.tools_manifest)} chars, "
            f"max_tokens={self.max_tokens})"
        )
