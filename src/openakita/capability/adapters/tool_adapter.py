"""
工具适配器

将系统工具目录（ToolCatalog）转换为能力元数据，并通过 ToolExecutor 执行工具。
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
    from ...tools.catalog import ToolCatalog
    from ...tools.executor import ToolExecutor

logger = logging.getLogger(__name__)


class ToolAdapter(CapabilityAdapter):
    """
    工具适配器

    将系统工具目录（ToolCatalog）中的工具转换为统一的能力元数据格式，
    并通过 ToolExecutor 执行工具调用。

    使用示例：
        from openakita.tools.catalog import ToolCatalog
        from openakita.tools.executor import ToolExecutor

        # 创建工具目录和执行器
        catalog = ToolCatalog(tools=[...])
        executor = ToolExecutor(handler_registry=...)

        # 创建适配器
        adapter = ToolAdapter(catalog=catalog, executor=executor)
        adapter.load()

        # 获取能力列表
        capabilities = adapter.list_capabilities()

        # 执行工具
        result = await adapter.execute("search", {"query": "test"})
    """

    def __init__(
        self,
        catalog: ToolCatalog | None = None,
        executor: ToolExecutor | None = None,
        source: str = "tool_catalog",
    ):
        """
        初始化工具适配器。

        Args:
            catalog: 工具目录实例
            executor: 工具执行器实例
            source: 来源标识
        """
        super().__init__(source)
        self._catalog = catalog
        self._executor = executor

    def set_catalog(self, catalog: ToolCatalog) -> None:
        """设置工具目录"""
        self._catalog = catalog

    def set_executor(self, executor: ToolExecutor) -> None:
        """设置工具执行器"""
        self._executor = executor

    def load(self) -> list[CapabilityMeta]:
        """
        从 ToolCatalog 加载工具能力。

        Returns:
            加载的能力列表

        Raises:
            CapabilityLoadError: 加载失败
        """
        if self._catalog is None:
            logger.warning("[ToolAdapter] No catalog set, returning empty list")
            self._loaded = True
            return []

        capabilities = []

        try:
            # 从 catalog 获取所有工具
            tools = getattr(self._catalog, "_tools", {})

            for name, tool_def in tools.items():
                try:
                    cap = self._convert_tool_to_capability(name, tool_def)
                    capabilities.append(cap)
                except Exception as e:
                    logger.warning(
                        f"[ToolAdapter] Failed to convert tool '{name}': {e}"
                    )
                    continue

            self._register_capabilities(capabilities)
            return capabilities

        except Exception as e:
            raise CapabilityLoadError(f"Failed to load tools from catalog: {e}") from e

    def _convert_tool_to_capability(
        self, name: str, tool_def: dict[str, Any]
    ) -> CapabilityMeta:
        """
        将工具定义转换为能力元数据。

        Args:
            name: 工具名称
            tool_def: 工具定义字典

        Returns:
            能力元数据
        """
        # 提取描述
        description = tool_def.get("description") or tool_def.get("short_description", "")

        # 提取参数 schema
        input_schema = tool_def.get("input_schema", {})
        parameters = {}

        if input_schema and "properties" in input_schema:
            required = set(input_schema.get("required", []))
            for param_name, param_schema in input_schema.get("properties", {}).items():
                parameters[param_name] = {
                    "type": param_schema.get("type", "any"),
                    "description": param_schema.get("description", ""),
                    "required": param_name in required,
                }

        # 提取标签
        tags = []
        category = tool_def.get("category")
        if category:
            tags.append(category.lower().replace(" ", "_"))

        # 提取示例
        examples = []
        for example in tool_def.get("examples", [])[:3]:
            if "params" in example:
                examples.append({
                    "input": example["params"],
                    "description": example.get("scenario", ""),
                })

        return CapabilityMeta(
            name=name,
            type=CapabilityType.TOOL,
            description=description,
            version="1.0.0",
            tags=tags,
            parameters=parameters,
            returns={"type": "string"},
            examples=examples,
            status=CapabilityStatus.ACTIVE,
            source=self._source,
            metadata={
                "category": category,
                "triggers": tool_def.get("triggers", []),
                "prerequisites": tool_def.get("prerequisites", []),
                "warnings": tool_def.get("warnings", []),
            },
        )

    async def execute(self, name: str, params: dict[str, Any]) -> ExecutionResult:
        """
        执行工具。

        Args:
            name: 工具名称
            params: 工具参数

        Returns:
            执行结果

        Raises:
            CapabilityExecutionError: 执行失败
        """
        # 检查能力是否存在
        if not self.has_capability(name):
            return ExecutionResult.error_result(f"Tool not found: {name}")

        # 检查执行器
        if self._executor is None:
            return ExecutionResult.error_result("No executor configured")

        # 验证参数
        valid, error = self.validate_params(name, params)
        if not valid:
            return ExecutionResult.error_result(error or "Invalid parameters")

        try:
            # 执行工具
            result = await self._executor.execute_tool(name, params)

            # 记录使用
            capability = self.get_capability(name)
            if capability:
                capability.record_usage(success=True)

            return ExecutionResult.success_result(
                output=result,
                metadata={"tool": name},
            )

        except Exception as e:
            # 记录失败
            capability = self.get_capability(name)
            if capability:
                capability.record_usage(success=False)

            logger.error(f"[ToolAdapter] Tool '{name}' execution failed: {e}")
            return ExecutionResult.error_result(
                error=str(e),
                metadata={"tool": name},
            )

    def get_tools_by_category(self) -> dict[str, list[CapabilityMeta]]:
        """
        按分类获取工具。

        Returns:
            分类 -> 工具列表的映射
        """
        result: dict[str, list[CapabilityMeta]] = {}

        for cap in self._capabilities.values():
            category = cap.metadata.get("category") or "other"
            if category not in result:
                result[category] = []
            result[category].append(cap)

        return result

    def get_high_freq_tools(self) -> list[CapabilityMeta]:
        """
        获取高频工具列表。

        Returns:
            高频工具的能力元数据列表
        """
        high_freq_names = {"run_shell", "read_file", "write_file", "list_directory", "ask_user"}
        return [
            cap for cap in self._capabilities.values()
            if cap.name in high_freq_names
        ]

    def get_stats(self) -> dict[str, Any]:
        """获取适配器统计信息"""
        stats = super().get_stats()

        # 添加分类统计
        by_category = self.get_tools_by_category()
        stats["by_category"] = {
            cat: len(tools) for cat, tools in by_category.items()
        }

        # 高频工具统计
        stats["high_freq_count"] = len(self.get_high_freq_tools())

        return stats


class MockToolAdapter(ToolAdapter):
    """
    模拟工具适配器

    用于测试，不需要真实的 ToolCatalog 和 ToolExecutor。
    """

    def __init__(
        self,
        source: str = "mock_tools",
        tools: list[dict[str, Any]] | None = None,
    ):
        """
        初始化模拟适配器。

        Args:
            source: 来源标识
            tools: 工具定义列表
        """
        super().__init__(catalog=None, executor=None, source=source)
        self._mock_tools = tools or []
        self._mock_results: dict[str, Any] = {}

    def set_mock_result(self, tool_name: str, result: Any) -> None:
        """设置模拟执行结果"""
        self._mock_results[tool_name] = result

    def load(self) -> list[CapabilityMeta]:
        """加载模拟工具"""
        capabilities = []

        for tool_def in self._mock_tools:
            name = tool_def.get("name", "unknown")
            cap = self._convert_tool_to_capability(name, tool_def)
            capabilities.append(cap)

        self._register_capabilities(capabilities)
        return capabilities

    async def execute(self, name: str, params: dict[str, Any]) -> ExecutionResult:
        """执行模拟工具"""
        if not self.has_capability(name):
            return ExecutionResult.error_result(f"Tool not found: {name}")

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
                metadata={"tool": name, "mock": True},
            )

        # 默认返回参数 echo
        return ExecutionResult.success_result(
            output=f"Mock execution of {name} with params: {params}",
            metadata={"tool": name, "mock": True},
        )