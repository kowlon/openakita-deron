"""
能力执行器

统一的能力执行入口，负责路由到正确的适配器执行能力调用。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .types import CapabilityMeta, CapabilityType
from .registry import CapabilityRegistry
from .adapters.base import CapabilityAdapter, ExecutionResult


logger = logging.getLogger(__name__)


@dataclass
class ExecutorStats:
    """执行器统计"""
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    by_adapter: dict[str, int] = field(default_factory=dict)


class CapabilityExecutor:
    """
    能力执行器

    统一的能力执行入口，负责：
    - 管理多个适配器
    - 路由能力调用到正确的适配器
    - 统一执行结果格式
    - 记录执行统计

    使用示例：
        registry = CapabilityRegistry()
        executor = CapabilityExecutor(registry)

        # 注册适配器
        executor.register_adapter("tools", tool_adapter)
        executor.register_adapter("skills", skill_adapter)
        executor.register_adapter("mcp", mcp_adapter)

        # 执行能力
        result = await executor.execute("search", {"query": "test"})
    """

    def __init__(self, registry: CapabilityRegistry | None = None):
        """
        初始化执行器。

        Args:
            registry: 能力注册表（可选）
        """
        self._registry = registry
        self._adapters: dict[str, CapabilityAdapter] = {}
        self._type_to_adapter: dict[CapabilityType, str] = {
            CapabilityType.TOOL: "tools",
            CapabilityType.SKILL: "skills",
            CapabilityType.MCP: "mcp",
            CapabilityType.BUILTIN: "builtin",
        }
        self._stats = ExecutorStats()

    @property
    def registry(self) -> CapabilityRegistry | None:
        """获取注册表"""
        return self._registry

    @registry.setter
    def registry(self, registry: CapabilityRegistry) -> None:
        """设置注册表"""
        self._registry = registry

    @property
    def stats(self) -> ExecutorStats:
        """获取执行统计"""
        return self._stats

    # ==================== 适配器管理 ====================

    def register_adapter(self, name: str, adapter: CapabilityAdapter) -> None:
        """
        注册适配器。

        Args:
            name: 适配器名称（如 "tools", "skills", "mcp"）
            adapter: 适配器实例
        """
        self._adapters[name] = adapter
        logger.info(f"[Executor] Registered adapter: {name}")

    def unregister_adapter(self, name: str) -> bool:
        """
        注销适配器。

        Args:
            name: 适配器名称

        Returns:
            是否注销成功
        """
        if name in self._adapters:
            del self._adapters[name]
            logger.info(f"[Executor] Unregistered adapter: {name}")
            return True
        return False

    def get_adapter(self, name: str) -> CapabilityAdapter | None:
        """
        获取适配器。

        Args:
            name: 适配器名称

        Returns:
            适配器实例，不存在则返回 None
        """
        return self._adapters.get(name)

    def has_adapter(self, name: str) -> bool:
        """检查适配器是否存在"""
        return name in self._adapters

    def list_adapters(self) -> list[str]:
        """列出所有适配器名称"""
        return list(self._adapters.keys())

    def set_type_adapter(self, cap_type: CapabilityType, adapter_name: str) -> None:
        """
        设置能力类型对应的适配器。

        Args:
            cap_type: 能力类型
            adapter_name: 适配器名称
        """
        self._type_to_adapter[cap_type] = adapter_name

    # ==================== 能力发现 ====================

    def load_all_adapters(self) -> dict[str, list[CapabilityMeta]]:
        """
        加载所有适配器的能力。

        Returns:
            适配器名称 -> 能力列表的映射
        """
        results = {}

        for name, adapter in self._adapters.items():
            try:
                capabilities = adapter.load()
                results[name] = capabilities

                # 注册到注册表
                if self._registry:
                    for cap in capabilities:
                        self._registry.register(cap)

                logger.info(f"[Executor] Loaded {len(capabilities)} capabilities from {name}")
            except Exception as e:
                logger.error(f"[Executor] Failed to load adapter {name}: {e}")
                results[name] = []

        return results

    def reload_all_adapters(self) -> dict[str, list[CapabilityMeta]]:
        """
        重新加载所有适配器的能力。

        Returns:
            适配器名称 -> 能力列表的映射
        """
        results = {}

        for name, adapter in self._adapters.items():
            try:
                capabilities = adapter.reload()
                results[name] = capabilities

                # 更新注册表
                if self._registry:
                    for cap in capabilities:
                        self._registry.register(cap)

                logger.info(f"[Executor] Reloaded {len(capabilities)} capabilities from {name}")
            except Exception as e:
                logger.error(f"[Executor] Failed to reload adapter {name}: {e}")
                results[name] = []

        return results

    # ==================== 能力执行 ====================

    async def execute(
        self,
        name: str,
        params: dict[str, Any],
        adapter_hint: str | None = None,
    ) -> ExecutionResult:
        """
        执行能力。

        Args:
            name: 能力名称
            params: 执行参数
            adapter_hint: 适配器提示（可选，用于加速路由）

        Returns:
            执行结果
        """
        self._stats.total_executions += 1

        # 尝试从提示的适配器执行
        if adapter_hint and adapter_hint in self._adapters:
            adapter = self._adapters[adapter_hint]
            if adapter.has_capability(name):
                return await self._execute_with_adapter(adapter, name, params, adapter_hint)

        # 从注册表查找能力
        if self._registry:
            capability = self._registry.get(name)
            if capability:
                adapter_name = self._type_to_adapter.get(capability.type)
                if adapter_name and adapter_name in self._adapters:
                    adapter = self._adapters[adapter_name]
                    return await self._execute_with_adapter(adapter, name, params, adapter_name)

        # 遍历所有适配器查找能力
        for adapter_name, adapter in self._adapters.items():
            if adapter.has_capability(name):
                return await self._execute_with_adapter(adapter, name, params, adapter_name)

        # 能力未找到
        self._stats.failed_executions += 1
        return ExecutionResult.error_result(f"Capability not found: {name}")

    async def _execute_with_adapter(
        self,
        adapter: CapabilityAdapter,
        name: str,
        params: dict[str, Any],
        adapter_name: str,
    ) -> ExecutionResult:
        """使用指定适配器执行能力"""
        try:
            result = await adapter.execute(name, params)

            # 更新统计
            if result.success:
                self._stats.successful_executions += 1
            else:
                self._stats.failed_executions += 1

            # 更新类型统计
            capability = adapter.get_capability(name)
            if capability:
                type_key = capability.type.value
                self._stats.by_type[type_key] = self._stats.by_type.get(type_key, 0) + 1

            # 更新适配器统计
            self._stats.by_adapter[adapter_name] = self._stats.by_adapter.get(adapter_name, 0) + 1

            return result

        except Exception as e:
            self._stats.failed_executions += 1
            logger.error(f"[Executor] Execution failed: {e}")
            return ExecutionResult.error_result(str(e))

    async def execute_batch(
        self,
        calls: list[dict[str, Any]],
    ) -> list[ExecutionResult]:
        """
        批量执行能力。

        Args:
            calls: 执行调用列表，每个元素包含 {"name": ..., "params": ...}

        Returns:
            执行结果列表
        """
        results = []
        for call in calls:
            name = call.get("name", "")
            params = call.get("params", {})
            adapter_hint = call.get("adapter")

            result = await self.execute(name, params, adapter_hint)
            results.append(result)

        return results

    # ==================== 能力查询 ====================

    def get_capability(self, name: str) -> CapabilityMeta | None:
        """
        获取能力元数据。

        Args:
            name: 能力名称

        Returns:
            能力元数据，不存在则返回 None
        """
        # 先从注册表查找
        if self._registry:
            cap = self._registry.get(name)
            if cap:
                return cap

        # 从适配器查找
        for adapter in self._adapters.values():
            cap = adapter.get_capability(name)
            if cap:
                return cap

        return None

    def has_capability(self, name: str) -> bool:
        """检查能力是否存在"""
        if self._registry and self._registry.has(name):
            return True

        for adapter in self._adapters.values():
            if adapter.has_capability(name):
                return True

        return False

    def list_all_capabilities(self) -> list[CapabilityMeta]:
        """列出所有能力"""
        if self._registry:
            return self._registry.list_all()

        capabilities = []
        for adapter in self._adapters.values():
            capabilities.extend(adapter.list_capabilities())

        return capabilities

    # ==================== 统计 ====================

    def get_stats_report(self) -> dict[str, Any]:
        """
        获取统计报告。

        Returns:
            统计报告字典
        """
        return {
            "total_executions": self._stats.total_executions,
            "successful_executions": self._stats.successful_executions,
            "failed_executions": self._stats.failed_executions,
            "success_rate": (
                self._stats.successful_executions / self._stats.total_executions
                if self._stats.total_executions > 0 else 0.0
            ),
            "by_type": dict(self._stats.by_type),
            "by_adapter": dict(self._stats.by_adapter),
            "adapters": list(self._adapters.keys()),
            "capabilities_count": len(self.list_all_capabilities()),
        }

    def reset_stats(self) -> None:
        """重置统计"""
        self._stats = ExecutorStats()


class MockCapabilityExecutor(CapabilityExecutor):
    """
    模拟能力执行器

    用于测试，不需要真实的适配器。
    """

    def __init__(self):
        super().__init__()
        self._mock_results: dict[str, Any] = {}

    def set_mock_result(self, name: str, result: Any) -> None:
        """设置模拟执行结果"""
        self._mock_results[name] = result

    async def execute(
        self,
        name: str,
        params: dict[str, Any],
        adapter_hint: str | None = None,
    ) -> ExecutionResult:
        """执行模拟能力"""
        self._stats.total_executions += 1

        if name in self._mock_results:
            self._stats.successful_executions += 1
            return ExecutionResult.success_result(
                output=self._mock_results[name],
                metadata={"mock": True},
            )

        self._stats.failed_executions += 1
        return ExecutionResult.error_result(f"Mock capability not found: {name}")