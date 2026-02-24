"""
企业级记忆配置

企业级记忆后端的配置类。

参考：
- docs/memory-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class EnterpriseMemoryConfig:
    """
    EnterpriseMemoryRouter 的配置。

    该配置控制企业级记忆系统的行为，包括规则加载和可选的技能缓存。

    属性：
        rules_path: 包含系统规则的 YAML/JSON 文件路径。
                   若未提供，将不会加载规则。
        skills_path: 包含技能模式的可选 JSON 文件路径。
                    若未提供，将禁用技能缓存。
        context_backend: 上下文存储后端类型（当前固定为 "memory"）
        max_step_summaries: 每个任务保留的最大步骤摘要数量
        max_key_variables: 每个任务保留的最大关键变量数量

    示例：
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
        校验配置并返回警告列表。

        返回：
            警告信息列表（若有效则为空）
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
