"""
技能适配器

将系统技能（Skills）转换为能力元数据，并通过 SkillManager 执行技能。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..types import CapabilityMeta, CapabilityStatus, CapabilityType
from .base import (
    CapabilityAdapter,
    CapabilityExecutionError,
    CapabilityLoadError,
    ExecutionResult,
)

if TYPE_CHECKING:
    from ...skills.manager import SkillManager
    from ...skills.registry import SkillEntry

logger = logging.getLogger(__name__)


class SkillAdapter(CapabilityAdapter):
    """
    技能适配器

    将系统技能（Skills）转换为统一的能力元数据格式，
    并通过 SkillManager 执行技能调用。

    使用示例：
        from openakita.skills.manager import SkillManager

        # 创建技能管理器
        skill_manager = SkillManager(brain=..., shell_tool=...)

        # 创建适配器
        adapter = SkillAdapter(skill_manager=skill_manager)
        adapter.load()

        # 获取能力列表
        capabilities = adapter.list_capabilities()

        # 执行技能
        result = await adapter.execute("my-skill", {"param": "value"})
    """

    def __init__(
        self,
        skill_manager: SkillManager | None = None,
        source: str = "skill_manager",
    ):
        """
        初始化技能适配器。

        Args:
            skill_manager: 技能管理器实例
            source: 来源标识
        """
        super().__init__(source)
        self._skill_manager = skill_manager

    def set_skill_manager(self, skill_manager: SkillManager) -> None:
        """设置技能管理器"""
        self._skill_manager = skill_manager

    def load(self) -> list[CapabilityMeta]:
        """
        从 SkillManager 加载技能能力。

        Returns:
            加载的能力列表

        Raises:
            CapabilityLoadError: 加载失败
        """
        if self._skill_manager is None:
            logger.warning("[SkillAdapter] No skill manager set, returning empty list")
            self._loaded = True
            return []

        capabilities = []

        try:
            # 从 registry 获取所有技能
            registry = self._skill_manager.registry
            for skill_name in registry.list_skills():
                entry = registry.get(skill_name)
                if entry:
                    try:
                        cap = self._convert_skill_to_capability(entry)
                        capabilities.append(cap)
                    except Exception as e:
                        logger.warning(
                            f"[SkillAdapter] Failed to convert skill '{skill_name}': {e}"
                        )
                        continue

            self._register_capabilities(capabilities)
            return capabilities

        except Exception as e:
            raise CapabilityLoadError(f"Failed to load skills from manager: {e}") from e

    def _convert_skill_to_capability(self, entry: SkillEntry) -> CapabilityMeta:
        """
        将技能条目转换为能力元数据。

        Args:
            entry: 技能条目

        Returns:
            能力元数据
        """
        # 提取标签
        tags = []
        if entry.category:
            tags.append(entry.category.lower().replace(" ", "_"))
        if entry.system:
            tags.append("system")

        # 构建参数 schema
        parameters = {}
        input_schema = entry.to_tool_schema().get("input_schema", {})
        if input_schema and "properties" in input_schema:
            required = set(input_schema.get("required", []))
            for param_name, param_schema in input_schema.get("properties", {}).items():
                parameters[param_name] = {
                    "type": param_schema.get("type", "any"),
                    "description": param_schema.get("description", ""),
                    "required": param_name in required,
                }

        # 确定状态
        status = CapabilityStatus.ACTIVE

        # 确定工具名称（系统技能使用原名称，外部技能加前缀）
        tool_name = entry.tool_name if entry.system else f"skill_{entry.name.replace('-', '_')}"

        return CapabilityMeta(
            name=entry.name,
            type=CapabilityType.SKILL,
            description=entry.description,
            version="1.0.0",
            tags=tags,
            parameters=parameters,
            returns={"type": "string"},
            status=status,
            source=self._source,
            priority=10 if entry.system else 5,
            metadata={
                "system": entry.system,
                "handler": entry.handler,
                "tool_name": tool_name,
                "category": entry.category,
                "license": entry.license,
                "compatibility": entry.compatibility,
                "allowed_tools": entry.allowed_tools,
                "disable_model_invocation": entry.disable_model_invocation,
                "skill_path": entry.skill_path,
            },
        )

    async def execute(self, name: str, params: dict[str, Any]) -> ExecutionResult:
        """
        执行技能。

        Args:
            name: 技能名称
            params: 技能参数

        Returns:
            执行结果

        Raises:
            CapabilityExecutionError: 执行失败
        """
        # 检查能力是否存在
        if not self.has_capability(name):
            return ExecutionResult.error_result(f"Skill not found: {name}")

        # 检查技能管理器
        if self._skill_manager is None:
            return ExecutionResult.error_result("No skill manager configured")

        # 验证参数
        valid, error = self.validate_params(name, params)
        if not valid:
            return ExecutionResult.error_result(error or "Invalid parameters")

        try:
            # 获取能力元数据
            capability = self.get_capability(name)
            tool_name = capability.metadata.get("tool_name", f"skill_{name}")

            # 通过技能管理器执行
            # 注意：实际执行由 Agent 的工具系统处理
            # 这里返回一个提示信息
            result = f"Skill '{name}' execution requested with tool '{tool_name}'"

            # 记录使用
            capability.record_usage(success=True)

            return ExecutionResult.success_result(
                output=result,
                metadata={"skill": name, "tool_name": tool_name},
            )

        except Exception as e:
            # 记录失败
            capability = self.get_capability(name)
            if capability:
                capability.record_usage(success=False)

            logger.error(f"[SkillAdapter] Skill '{name}' execution failed: {e}")
            return ExecutionResult.error_result(
                error=str(e),
                metadata={"skill": name},
            )

    def get_system_skills(self) -> list[CapabilityMeta]:
        """
        获取系统技能列表。

        Returns:
            系统技能的能力元数据列表
        """
        return [
            cap for cap in self._capabilities.values()
            if cap.metadata.get("system", False)
        ]

    def get_external_skills(self) -> list[CapabilityMeta]:
        """
        获取外部技能列表。

        Returns:
            外部技能的能力元数据列表
        """
        return [
            cap for cap in self._capabilities.values()
            if not cap.metadata.get("system", False)
        ]

    def get_skills_by_category(self) -> dict[str, list[CapabilityMeta]]:
        """
        按分类获取技能。

        Returns:
            分类 -> 技能列表的映射
        """
        result: dict[str, list[CapabilityMeta]] = {}

        for cap in self._capabilities.values():
            category = cap.metadata.get("category") or "other"
            if category not in result:
                result[category] = []
            result[category].append(cap)

        return result

    def get_stats(self) -> dict[str, Any]:
        """获取适配器统计信息"""
        stats = super().get_stats()

        # 添加技能类型统计
        stats["system_skills"] = len(self.get_system_skills())
        stats["external_skills"] = len(self.get_external_skills())

        # 添加分类统计
        by_category = self.get_skills_by_category()
        stats["by_category"] = {
            cat: len(skills) for cat, skills in by_category.items()
        }

        return stats


class MockSkillAdapter(SkillAdapter):
    """
    模拟技能适配器

    用于测试，不需要真实的 SkillManager。
    """

    def __init__(
        self,
        source: str = "mock_skills",
        skills: list[dict[str, Any]] | None = None,
    ):
        """
        初始化模拟适配器。

        Args:
            source: 来源标识
            skills: 技能定义列表
        """
        super().__init__(skill_manager=None, source=source)
        self._mock_skills = skills or []
        self._mock_results: dict[str, Any] = {}

    def set_mock_result(self, skill_name: str, result: Any) -> None:
        """设置模拟执行结果"""
        self._mock_results[skill_name] = result

    def load(self) -> list[CapabilityMeta]:
        """加载模拟技能"""
        capabilities = []

        for skill_def in self._mock_skills:
            name = skill_def.get("name", "unknown")
            cap = self._create_mock_capability(name, skill_def)
            capabilities.append(cap)

        self._register_capabilities(capabilities)
        return capabilities

    def _create_mock_capability(
        self, name: str, skill_def: dict[str, Any]
    ) -> CapabilityMeta:
        """创建模拟能力"""
        tags = []
        category = skill_def.get("category")
        if category:
            tags.append(category.lower().replace(" ", "_"))
        if skill_def.get("system"):
            tags.append("system")

        return CapabilityMeta(
            name=name,
            type=CapabilityType.SKILL,
            description=skill_def.get("description", ""),
            version=skill_def.get("version", "1.0.0"),
            tags=tags,
            parameters=skill_def.get("parameters", {}),
            status=CapabilityStatus.ACTIVE,
            source=self._source,
            priority=10 if skill_def.get("system") else 5,
            metadata={
                "system": skill_def.get("system", False),
                "handler": skill_def.get("handler"),
                "tool_name": skill_def.get("tool_name", f"skill_{name}"),
                "category": category,
            },
        )

    async def execute(self, name: str, params: dict[str, Any]) -> ExecutionResult:
        """执行模拟技能"""
        if not self.has_capability(name):
            return ExecutionResult.error_result(f"Skill not found: {name}")

        # 验证参数
        valid, error = self.validate_params(name, params)
        if not valid:
            return ExecutionResult.error_result(error or "Invalid parameters")

        # 记录使用（成功）
        capability = self.get_capability(name)
        if capability:
            capability.record_usage(success=True)

        if name in self._mock_results:
            return ExecutionResult.success_result(
                output=self._mock_results[name],
                metadata={"skill": name, "mock": True},
            )

        # 默认返回
        tool_name = capability.metadata.get("tool_name", f"skill_{name}") if capability else name
        return ExecutionResult.success_result(
            output=f"Mock skill '{name}' executed with tool '{tool_name}'",
            metadata={"skill": name, "tool_name": tool_name, "mock": True},
        )