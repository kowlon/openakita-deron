"""
Skill Store

Manages skill patterns cache for enterprise memory system.
Skills are reusable operation patterns that can be matched to task types.

Reference:
- docs/memory-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any


class SkillCategory(Enum):
    """Categories of skills."""

    SEARCH = "search"
    ANALYSIS = "analysis"
    CODING = "coding"
    WRITING = "writing"
    PLANNING = "planning"
    CUSTOM = "custom"


@dataclass
class Skill:
    """
    A reusable skill pattern.

    Attributes:
        id: Unique skill identifier
        name: Human-readable skill name
        category: Skill category
        task_types: List of task types this skill applies to
        pattern: The skill pattern (template or instructions)
        usage_count: Number of times this skill has been used
        last_used_at: When this skill was last used
        created_at: When this skill was created
        ttl_seconds: Time-to-live in seconds (0 = no expiry)
        metadata: Additional metadata
    """

    id: str
    name: str
    category: SkillCategory
    task_types: list[str] = field(default_factory=list)
    pattern: str = ""
    usage_count: int = 0
    last_used_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)
    ttl_seconds: int = 0  # 0 = no expiry
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if this skill has expired."""
        if self.ttl_seconds <= 0:
            return False
        if self.last_used_at is None:
            expiry_time = self.created_at + timedelta(seconds=self.ttl_seconds)
        else:
            expiry_time = self.last_used_at + timedelta(seconds=self.ttl_seconds)
        return datetime.now() > expiry_time

    def record_usage(self) -> None:
        """Record a usage of this skill."""
        self.usage_count += 1
        self.last_used_at = datetime.now()

    def matches_task_type(self, task_type: str) -> bool:
        """Check if this skill matches a task type."""
        return task_type.lower() in [t.lower() for t in self.task_types]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "task_types": self.task_types,
            "pattern": self.pattern,
            "usage_count": self.usage_count,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat(),
            "ttl_seconds": self.ttl_seconds,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Skill":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            category=SkillCategory(data["category"]),
            task_types=data.get("task_types", []),
            pattern=data.get("pattern", ""),
            usage_count=data.get("usage_count", 0),
            last_used_at=datetime.fromisoformat(data["last_used_at"]) if data.get("last_used_at") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            ttl_seconds=data.get("ttl_seconds", 0),
            metadata=data.get("metadata", {}),
        )


class SkillStore:
    """
    Store for skill patterns.

    Manages skill caching with TTL support and task type matching.

    Example:
        store = SkillStore()

        # Add a skill
        skill = Skill(
            id="skill-001",
            name="Web Search Pattern",
            category=SkillCategory.SEARCH,
            task_types=["search", "web_search"],
            pattern="Use search engine to find information..."
        )
        store.add_skill(skill)

        # Get skills for a task
        skills = store.get_skills_for_task("search")

        # Cleanup expired skills
        removed = store.cleanup_expired()
    """

    def __init__(self) -> None:
        """Initialize the skill store."""
        self._skills: dict[str, Skill] = {}

    def add_skill(self, skill: Skill) -> None:
        """
        Add a skill to the store.

        Args:
            skill: The skill to add
        """
        self._skills[skill.id] = skill

    def get_skill(self, skill_id: str) -> Skill | None:
        """
        Get a skill by ID.

        Args:
            skill_id: The skill ID

        Returns:
            The skill if found and not expired, None otherwise
        """
        skill = self._skills.get(skill_id)
        if skill is None:
            return None
        if skill.is_expired():
            del self._skills[skill_id]
            return None
        return skill

    def get_skills_for_task(self, task_type: str) -> list[Skill]:
        """
        Get all skills that match a task type.

        Args:
            task_type: The task type to match

        Returns:
            List of matching skills (excluding expired ones)
        """
        matching_skills = []
        expired_ids = []

        for skill_id, skill in self._skills.items():
            if skill.is_expired():
                expired_ids.append(skill_id)
            elif skill.matches_task_type(task_type):
                matching_skills.append(skill)

        # Remove expired skills
        for skill_id in expired_ids:
            del self._skills[skill_id]

        # Sort by usage count (most used first)
        matching_skills.sort(key=lambda s: s.usage_count, reverse=True)

        return matching_skills

    def get_skills_by_category(self, category: SkillCategory) -> list[Skill]:
        """
        Get all skills in a category.

        Args:
            category: The skill category

        Returns:
            List of skills in the category (excluding expired ones)
        """
        matching_skills = []
        expired_ids = []

        for skill_id, skill in self._skills.items():
            if skill.is_expired():
                expired_ids.append(skill_id)
            elif skill.category == category:
                matching_skills.append(skill)

        for skill_id in expired_ids:
            del self._skills[skill_id]

        return matching_skills

    def record_skill_usage(self, skill_id: str) -> bool:
        """
        Record usage of a skill.

        Args:
            skill_id: The skill ID

        Returns:
            True if skill was found, False otherwise
        """
        skill = self.get_skill(skill_id)
        if skill is None:
            return False
        skill.record_usage()
        return True

    def cleanup_expired(self) -> list[str]:
        """
        Remove all expired skills.

        Returns:
            List of removed skill IDs
        """
        expired_ids = [
            skill_id for skill_id, skill in self._skills.items()
            if skill.is_expired()
        ]

        for skill_id in expired_ids:
            del self._skills[skill_id]

        return expired_ids

    def get_all_skills(self) -> list[Skill]:
        """
        Get all non-expired skills.

        Returns:
            List of all skills
        """
        self.cleanup_expired()
        return list(self._skills.values())

    def clear(self) -> None:
        """Clear all skills."""
        self._skills.clear()

    def count(self) -> int:
        """Get the number of skills (including expired)."""
        return len(self._skills)

    def to_prompt(self, task_type: str | None = None) -> str:
        """
        Generate a prompt string from skills.

        Args:
            task_type: Optional task type to filter skills

        Returns:
            Formatted skill list for prompt injection
        """
        if task_type:
            skills = self.get_skills_for_task(task_type)
        else:
            skills = self.get_all_skills()

        if not skills:
            return ""

        lines = ["## Relevant Skills", ""]

        for skill in skills[:10]:  # Limit to 10 skills
            lines.append(f"**{skill.name}** ({skill.category.value})")
            if skill.pattern:
                lines.append(f"  {skill.pattern[:200]}")
            lines.append("")

        return "\n".join(lines)

    def load_from_json(self, path: str) -> int:
        """
        Load skills from a JSON file.

        Args:
            path: Path to JSON file

        Returns:
            Number of skills loaded
        """
        import json
        from pathlib import Path

        file_path = Path(path)
        if not file_path.exists():
            return 0

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        skills_data = data.get("skills", [])
        loaded = 0

        for skill_data in skills_data:
            try:
                skill = Skill.from_dict(skill_data)
                self.add_skill(skill)
                loaded += 1
            except Exception:
                continue

        return loaded

    def save_to_json(self, path: str) -> int:
        """
        Save skills to a JSON file.

        Args:
            path: Path to JSON file

        Returns:
            Number of skills saved
        """
        import json
        from pathlib import Path

        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        skills = self.get_all_skills()
        data = {
            "skills": [skill.to_dict() for skill in skills],
            "exported_at": datetime.now().isoformat(),
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return len(skills)
