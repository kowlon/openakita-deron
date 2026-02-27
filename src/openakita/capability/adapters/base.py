"""
能力适配器基类

定义能力适配器的抽象接口，用于统一封装不同来源的能力（Tool、Skill、MCP）。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..types import CapabilityMeta, CapabilityType

logger = logging.getLogger(__name__)


class CapabilityLoadError(Exception):
    """能力加载错误"""
    pass


class CapabilityExecutionError(Exception):
    """能力执行错误"""
    pass


@dataclass
class ExecutionResult:
    """
    能力执行结果

    属性:
        success: 是否成功
        output: 输出内容
        error: 错误信息（如果失败）
        metadata: 额外元数据
    """
    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def success_result(cls, output: Any, metadata: dict[str, Any] | None = None) -> "ExecutionResult":
        """创建成功结果"""
        return cls(
            success=True,
            output=output,
            metadata=metadata or {},
        )

    @classmethod
    def error_result(cls, error: str, metadata: dict[str, Any] | None = None) -> "ExecutionResult":
        """创建错误结果"""
        return cls(
            success=False,
            error=error,
            metadata=metadata or {},
        )


class CapabilityAdapter(ABC):
    """
    能力适配器抽象基类

    所有能力适配器（ToolAdapter、SkillAdapter、MCPAdapter）都需要继承此类。

    职责：
    - 从不同来源加载能力元数据
    - 提供统一的能力执行接口
    - 处理能力调用的错误和日志

    使用示例：
        class MyToolAdapter(CapabilityAdapter):
            def load(self) -> list[CapabilityMeta]:
                # 加载能力元数据
                return [CapabilityMeta(name="tool1", type=CapabilityType.TOOL)]

            async def execute(self, name: str, params: dict) -> ExecutionResult:
                # 执行能力
                result = await some_execution(name, params)
                return ExecutionResult.success_result(result)
    """

    def __init__(self, source: str = ""):
        """
        初始化适配器。

        Args:
            source: 能力来源标识（如文件路径、服务器地址等）
        """
        self._source = source
        self._capabilities: dict[str, CapabilityMeta] = {}
        self._loaded = False

    @property
    def source(self) -> str:
        """获取能力来源"""
        return self._source

    @property
    def loaded(self) -> bool:
        """是否已加载"""
        return self._loaded

    @property
    def capabilities(self) -> dict[str, CapabilityMeta]:
        """获取已加载的能力"""
        return self._capabilities

    @abstractmethod
    def load(self) -> list[CapabilityMeta]:
        """
        加载能力元数据。

        Returns:
            加载的能力列表

        Raises:
            CapabilityLoadError: 加载失败
        """
        pass

    @abstractmethod
    async def execute(self, name: str, params: dict[str, Any]) -> ExecutionResult:
        """
        执行能力。

        Args:
            name: 能力名称
            params: 执行参数

        Returns:
            执行结果

        Raises:
            CapabilityExecutionError: 执行失败
        """
        pass

    def reload(self) -> list[CapabilityMeta]:
        """
        重新加载能力。

        Returns:
            重新加载的能力列表
        """
        self._loaded = False
        self._capabilities.clear()
        return self.load()

    def get_capability(self, name: str) -> CapabilityMeta | None:
        """
        获取指定能力。

        Args:
            name: 能力名称

        Returns:
            能力元数据，不存在则返回 None
        """
        return self._capabilities.get(name)

    def has_capability(self, name: str) -> bool:
        """
        检查能力是否存在。

        Args:
            name: 能力名称

        Returns:
            是否存在
        """
        return name in self._capabilities

    def list_capabilities(self) -> list[CapabilityMeta]:
        """
        列出所有能力。

        Returns:
            能力列表
        """
        return list(self._capabilities.values())

    def list_capability_names(self) -> list[str]:
        """
        列出所有能力名称。

        Returns:
            能力名称列表
        """
        return list(self._capabilities.keys())

    def _register_capabilities(self, capabilities: list[CapabilityMeta]) -> None:
        """
        注册能力到内部存储。

        Args:
            capabilities: 能力列表
        """
        for cap in capabilities:
            # 设置来源
            if not cap.source:
                cap.source = self._source
            self._capabilities[cap.name] = cap

        self._loaded = True
        logger.info(
            f"[{self.__class__.__name__}] Loaded {len(capabilities)} capabilities "
            f"from {self._source or 'default source'}"
        )

    def validate_params(self, name: str, params: dict[str, Any]) -> tuple[bool, str | None]:
        """
        验证参数是否符合能力定义。

        Args:
            name: 能力名称
            params: 参数字典

        Returns:
            (是否有效, 错误信息)
        """
        capability = self._capabilities.get(name)
        if capability is None:
            return False, f"Capability not found: {name}"

        # 检查必填参数
        for param_name, schema in capability.parameters.items():
            if schema.get("required", False) and param_name not in params:
                return False, f"Missing required parameter: {param_name}"

        return True, None

    def get_stats(self) -> dict[str, Any]:
        """
        获取适配器统计信息。

        Returns:
            统计信息字典
        """
        return {
            "source": self._source,
            "loaded": self._loaded,
            "capabilities_count": len(self._capabilities),
            "capabilities": list(self._capabilities.keys()),
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(source={self._source!r}, loaded={self._loaded})"


class MockCapabilityAdapter(CapabilityAdapter):
    """
    模拟能力适配器

    用于测试和开发环境。
    """

    def __init__(
        self,
        source: str = "mock",
        capabilities: list[CapabilityMeta] | None = None,
    ):
        super().__init__(source)
        self._mock_capabilities = capabilities or []
        self._mock_results: dict[str, Any] = {}
        self._execution_log: list[dict[str, Any]] = []

    def set_mock_result(self, name: str, result: Any) -> None:
        """设置模拟能力的执行结果"""
        self._mock_results[name] = result

    def load(self) -> list[CapabilityMeta]:
        """加载模拟能力"""
        self._register_capabilities(self._mock_capabilities)
        return self._mock_capabilities

    async def execute(self, name: str, params: dict[str, Any]) -> ExecutionResult:
        """执行模拟能力"""
        self._execution_log.append({
            "name": name,
            "params": params,
        })

        if name not in self._capabilities:
            return ExecutionResult.error_result(f"Capability not found: {name}")

        if name in self._mock_results:
            return ExecutionResult.success_result(self._mock_results[name])

        # 默认返回参数的 echo
        return ExecutionResult.success_result({
            "echo": params,
            "capability": name,
        })

    def get_execution_log(self) -> list[dict[str, Any]]:
        """获取执行日志"""
        return self._execution_log.copy()

    def clear_execution_log(self) -> None:
        """清空执行日志"""
        self._execution_log.clear()