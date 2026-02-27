"""
能力系统集成帮助器

提供 Agent 与能力系统的集成支持。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..capability import (
    CapabilityExecutor,
    CapabilityRegistry,
    CapabilityType,
)
from ..capability.adapters.tool_adapter import ToolAdapter
from ..capability.adapters.skill_adapter import SkillAdapter
from ..capability.adapters.mcp_adapter import MCPAdapter

if TYPE_CHECKING:
    from ..core.agent import Agent

logger = logging.getLogger(__name__)


def setup_capability_system(agent: "Agent") -> CapabilityExecutor:
    """
    为 Agent 设置能力系统。

    这个函数初始化能力注册表、执行器和适配器，
    并将它们连接到 Agent 的现有组件。

    Args:
        agent: Agent 实例

    Returns:
        配置好的 CapabilityExecutor 实例
    """
    # 创建注册表
    registry = CapabilityRegistry()

    # 创建执行器
    executor = CapabilityExecutor(registry)

    # 创建并注册工具适配器
    tool_adapter = ToolAdapter(
        catalog=agent.tool_catalog,
        executor=agent.tool_executor,
        source="system_tools",
    )
    executor.register_adapter("tools", tool_adapter)

    # 创建并注册技能适配器
    skill_adapter = SkillAdapter(
        skill_manager=agent.skill_manager,
        source="skills",
    )
    executor.register_adapter("skills", skill_adapter)

    # 创建并注册 MCP 适配器
    mcp_adapter = MCPAdapter(
        mcp_client=agent.mcp_client,
        mcp_catalog=agent.mcp_catalog,
        source="mcp",
    )
    executor.register_adapter("mcp", mcp_adapter)

    # 加载所有能力
    capabilities = executor.load_all_adapters()

    total = sum(len(caps) for caps in capabilities.values())
    logger.info(
        f"[CapabilitySystem] Loaded {total} capabilities: "
        + ", ".join(f"{k}:{len(v)}" for k, v in capabilities.items())
    )

    # 存储到 Agent
    agent.capability_registry = registry
    agent.capability_executor = executor

    return executor


def generate_capability_manifest(agent: "Agent") -> str:
    """
    生成能力清单，用于注入到系统提示。

    Args:
        agent: Agent 实例

    Returns:
        Markdown 格式的能力清单
    """
    if not hasattr(agent, "capability_registry"):
        return ""

    registry = agent.capability_registry
    return registry.generate_system_prompt_section(
        include_parameters=False,
        include_examples=False,
        only_available=True,
    )


def get_capability_summary(agent: "Agent") -> dict[str, Any]:
    """
    获取能力系统摘要。

    Args:
        agent: Agent 实例

    Returns:
        能力系统摘要字典
    """
    if not hasattr(agent, "capability_registry"):
        return {"error": "Capability system not initialized"}

    registry = agent.capability_registry
    summary = registry.generate_summary()

    if hasattr(agent, "capability_executor"):
        executor_stats = agent.capability_executor.get_stats_report()
        summary["executor_stats"] = executor_stats

    return summary


async def execute_capability(
    agent: "Agent",
    name: str,
    params: dict[str, Any],
    adapter_hint: str | None = None,
) -> Any:
    """
    执行能力。

    这是 Agent 执行能力的统一入口。

    Args:
        agent: Agent 实例
        name: 能力名称
        params: 执行参数
        adapter_hint: 适配器提示（可选）

    Returns:
        执行结果
    """
    if not hasattr(agent, "capability_executor"):
        raise RuntimeError("Capability system not initialized")

    result = await agent.capability_executor.execute(name, params, adapter_hint)

    if not result.success:
        raise RuntimeError(f"Capability execution failed: {result.error}")

    return result.output


def refresh_capabilities(agent: "Agent") -> dict[str, int]:
    """
    刷新所有能力。

    重新加载所有适配器的能力定义。

    Args:
        agent: Agent 实例

    Returns:
        适配器名称 -> 能力数量的映射
    """
    if not hasattr(agent, "capability_executor"):
        raise RuntimeError("Capability system not initialized")

    capabilities = agent.capability_executor.reload_all_adapters()
    return {name: len(caps) for name, caps in capabilities.items()}


class CapabilitySystemMixin:
    """
    能力系统混入类。

    可用于为 Agent 类添加能力系统支持。
    """

    def init_capability_system(self: "Agent") -> None:
        """初始化能力系统"""
        setup_capability_system(self)

    def get_capability_manifest(self: "Agent") -> str:
        """获取能力清单"""
        return generate_capability_manifest(self)

    def get_capability_info(self: "Agent") -> dict[str, Any]:
        """获取能力信息"""
        return get_capability_summary(self)

    async def call_capability(
        self: "Agent",
        name: str,
        params: dict[str, Any],
    ) -> Any:
        """调用能力"""
        return await execute_capability(self, name, params)

    def refresh_all_capabilities(self: "Agent") -> dict[str, int]:
        """刷新所有能力"""
        return refresh_capabilities(self)