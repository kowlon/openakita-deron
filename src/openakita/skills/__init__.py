"""
技能系统

遵循 Agent Skills 规范 (agentskills.io/specification)
支持渐进式披露:
- Level 1: 技能清单 (name + description) - 系统提示
- Level 2: 完整指令 (SKILL.md body) - 激活时
- Level 3: 资源文件 - 按需加载

SkillManager:
负责技能的发现、加载、解析和生命周期管理。
"""

from .catalog import (
    SkillCatalog,
    generate_skill_catalog,
)
from .loader import (
    SKILL_DIRECTORIES,
    SkillLoader,
)
from .manager import SkillManager
from .parser import (
    ParsedSkill,
    SkillMetadata,
    SkillParser,
    parse_skill,
    parse_skill_directory,
)
from .registry import (
    SkillEntry,
    SkillRegistry,
    default_registry,
    get_skill,
    register_skill,
)

__all__ = [
    # Manager
    "SkillManager",
    # Parser
    "SkillParser",
    "SkillMetadata",
    "ParsedSkill",
    "parse_skill",
    "parse_skill_directory",
    # Registry
    "SkillRegistry",
    "SkillEntry",
    "default_registry",
    "register_skill",
    "get_skill",
    # Loader
    "SkillLoader",
    "SKILL_DIRECTORIES",
    # Catalog
    "SkillCatalog",
    "generate_skill_catalog",
]
