"""
技能存储

为企业级记忆系统管理技能模式缓存。
技能是可复用的操作模式，可与任务类型匹配。

参考：
- docs/memory-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any


class SkillCategory(Enum):
    """技能分类。"""

    SEARCH = "search"
    ANALYSIS = "analysis"
    CODING = "coding"
    WRITING = "writing"
    PLANNING = "planning"
    CUSTOM = "custom"


@dataclass
class Skill:
    """
    可复用的技能模式。

    属性：
        id: 技能唯一标识
        name: 人类可读的技能名称
        category: 技能分类
        task_types: 该技能适用的任务类型列表
        pattern: 技能模式（模板或指令）
        usage_count: 技能被使用的次数
        last_used_at: 最近一次使用时间
        created_at: 创建时间
        ttl_seconds: 存活时长（秒，0 表示不过期）
        metadata: 额外元数据
    """

    id: str
    name: str
    category: SkillCategory
    task_types: list[str] = field(default_factory=list)
    pattern: str = ""
    usage_count: int = 0
    last_used_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)
    ttl_seconds: int = 0  # 0 表示不过期
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """检查技能是否过期。"""
        if self.ttl_seconds <= 0:
            return False
        if self.last_used_at is None:
            expiry_time = self.created_at + timedelta(seconds=self.ttl_seconds)
        else:
            expiry_time = self.last_used_at + timedelta(seconds=self.ttl_seconds)
        return datetime.now() > expiry_time

    def record_usage(self) -> None:
        """记录一次技能使用。"""
        self.usage_count += 1
        self.last_used_at = datetime.now()

    def matches_task_type(self, task_type: str) -> bool:
        """检查技能是否匹配任务类型。"""
        return task_type.lower() in [t.lower() for t in self.task_types]

    def to_dict(self) -> dict[str, Any]:
        """转换为用于序列化的字典。"""
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
        """从字典创建。"""
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
    技能模式存储。

    管理技能缓存，支持 TTL 与任务类型匹配。

    示例：
        store = SkillStore()

        # 添加技能
        skill = Skill(
            id="skill-001",
            name="Web Search Pattern",
            category=SkillCategory.SEARCH,
            task_types=["search", "web_search"],
            pattern="Use search engine to find information..."
        )
        store.add_skill(skill)

        # 获取任务匹配的技能
        skills = store.get_skills_for_task("search")

        # 清理过期技能
        removed = store.cleanup_expired()
    """

    def __init__(self) -> None:
        """初始化技能存储。"""
        self._skills: dict[str, Skill] = {}

    def add_skill(self, skill: Skill) -> None:
        """
        向存储中添加技能。

        参数：
            skill: 要添加的技能
        """
        self._skills[skill.id] = skill

    def get_skill(self, skill_id: str) -> Skill | None:
        """
        通过 ID 获取技能。

        参数：
            skill_id: 技能 ID

        返回：
            若找到且未过期则返回技能，否则为 None
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
        获取匹配任务类型的全部技能。

        参数：
            task_type: 要匹配的任务类型

        返回：
            匹配的技能列表（不含过期技能）
        """
        matching_skills = []
        expired_ids = []

        for skill_id, skill in self._skills.items():
            if skill.is_expired():
                expired_ids.append(skill_id)
            elif skill.matches_task_type(task_type):
                matching_skills.append(skill)

        # 移除过期技能
        for skill_id in expired_ids:
            del self._skills[skill_id]

        # 按使用次数排序（使用最多的在前）
        matching_skills.sort(key=lambda s: s.usage_count, reverse=True)

        return matching_skills

    def get_skills_by_category(self, category: SkillCategory) -> list[Skill]:
        """
        获取某分类下的全部技能。

        参数：
            category: 技能分类

        返回：
            该分类下的技能列表（不含过期技能）
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
        记录技能使用。

        参数：
            skill_id: 技能 ID

        返回：
            若找到技能则为 True，否则为 False
        """
        skill = self.get_skill(skill_id)
        if skill is None:
            return False
        skill.record_usage()
        return True

    def cleanup_expired(self) -> list[str]:
        """
        移除所有过期技能。

        返回：
            被移除的技能 ID 列表
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
        获取所有未过期技能。

        返回：
            技能列表
        """
        self.cleanup_expired()
        return list(self._skills.values())

    def clear(self) -> None:
        """清空所有技能。"""
        self._skills.clear()

    def count(self) -> int:
        """获取技能数量（包含过期）。"""
        return len(self._skills)

    def to_prompt(self, task_type: str | None = None) -> str:
        """
        根据技能生成提示词字符串。

        参数：
            task_type: 可选任务类型，用于筛选技能

        返回：
            用于提示词注入的格式化技能列表
        """
        if task_type:
            skills = self.get_skills_for_task(task_type)
        else:
            skills = self.get_all_skills()

        if not skills:
            return ""

        lines = ["## Relevant Skills", ""]

        for skill in skills[:10]:  # 限制为 10 个技能
            lines.append(f"**{skill.name}** ({skill.category.value})")
            if skill.pattern:
                lines.append(f"  {skill.pattern[:200]}")
            lines.append("")

        return "\n".join(lines)

    def load_from_json(self, path: str) -> int:
        """
        从 JSON 文件加载技能。

        参数：
            path: JSON 文件路径

        返回：
            加载的技能数量
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
        将技能保存到 JSON 文件。

        参数：
            path: JSON 文件路径

        返回：
            保存的技能数量
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
