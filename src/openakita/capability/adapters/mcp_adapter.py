"""
MCP 适配器

将 MCP (Model Context Protocol) 服务器工具转换为能力元数据，并通过 MCPClient 执行工具。
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
    from ...tools.mcp import MCPClient
    from ...tools.mcp_catalog import MCPCatalog, MCPServerInfo, MCPToolInfo

logger = logging.getLogger(__name__)


class MCPAdapter(CapabilityAdapter):
    """
    MCP 适配器

    将 MCP 服务器工具转换为统一的能力元数据格式，
    并通过 MCPClient 执行工具调用。

    使用示例：
        from openakita.tools.mcp import MCPClient
        from openakita.tools.mcp_catalog import MCPCatalog

        # 创建 MCP 客户端和目录
        mcp_client = MCPClient()
        mcp_catalog = MCPCatalog()

        # 创建适配器
        adapter = MCPAdapter(mcp_client=mcp_client, mcp_catalog=mcp_catalog)
        adapter.load()

        # 获取能力列表
        capabilities = adapter.list_capabilities()

        # 执行 MCP 工具
        result = await adapter.execute("server__tool_name", {"arg": "value"})
    """

    def __init__(
        self,
        mcp_client: MCPClient | None = None,
        mcp_catalog: MCPCatalog | None = None,
        source: str = "mcp",
    ):
        """
        初始化 MCP 适配器。

        Args:
            mcp_client: MCP 客户端实例
            mcp_catalog: MCP 目录实例
            source: 来源标识
        """
        super().__init__(source)
        self._mcp_client = mcp_client
        self._mcp_catalog = mcp_catalog

    def set_mcp_client(self, mcp_client: MCPClient) -> None:
        """设置 MCP 客户端"""
        self._mcp_client = mcp_client

    def set_mcp_catalog(self, mcp_catalog: MCPCatalog) -> None:
        """设置 MCP 目录"""
        self._mcp_catalog = mcp_catalog

    def load(self) -> list[CapabilityMeta]:
        """
        从 MCPCatalog 加载 MCP 工具能力。

        Returns:
            加载的能力列表

        Raises:
            CapabilityLoadError: 加载失败
        """
        if self._mcp_catalog is None:
            logger.warning("[MCPAdapter] No catalog set, returning empty list")
            self._loaded = True
            return []

        capabilities = []

        try:
            # 从 catalog 获取所有服务器
            servers = getattr(self._mcp_catalog, "_servers", [])

            for server in servers:
                try:
                    server_caps = self._convert_server_to_capabilities(server)
                    capabilities.extend(server_caps)
                except Exception as e:
                    logger.warning(
                        f"[MCPAdapter] Failed to convert server '{server.identifier}': {e}"
                    )
                    continue

            self._register_capabilities(capabilities)
            return capabilities

        except Exception as e:
            raise CapabilityLoadError(f"Failed to load MCP tools from catalog: {e}") from e

    def _convert_server_to_capabilities(
        self, server: MCPServerInfo
    ) -> list[CapabilityMeta]:
        """
        将 MCP 服务器工具转换为能力元数据。

        Args:
            server: MCP 服务器信息

        Returns:
            能力元数据列表
        """
        capabilities = []

        for tool in server.tools:
            try:
                cap = self._convert_tool_to_capability(server, tool)
                capabilities.append(cap)
            except Exception as e:
                logger.warning(
                    f"[MCPAdapter] Failed to convert tool '{tool.name}': {e}"
                )
                continue

        return capabilities

    def _convert_tool_to_capability(
        self, server: MCPServerInfo, tool: MCPToolInfo
    ) -> CapabilityMeta:
        """
        将单个 MCP 工具转换为能力元数据。

        Args:
            server: MCP 服务器信息
            tool: MCP 工具信息

        Returns:
            能力元数据
        """
        # 生成唯一名称: server__tool_name
        name = f"{server.identifier}__{tool.name}"

        # 提取参数 schema
        parameters = {}
        if tool.arguments:
            # arguments 可能是 input_schema 或 properties
            if "properties" in tool.arguments:
                required = set(tool.arguments.get("required", []))
                for param_name, param_schema in tool.arguments.get("properties", {}).items():
                    parameters[param_name] = {
                        "type": param_schema.get("type", "any"),
                        "description": param_schema.get("description", ""),
                        "required": param_name in required,
                    }

        # 标签
        tags = ["mcp", server.identifier]
        if server.transport:
            tags.append(server.transport)

        return CapabilityMeta(
            name=name,
            type=CapabilityType.MCP,
            description=tool.description or f"MCP tool from {server.name}",
            version="1.0.0",
            tags=tags,
            parameters=parameters,
            returns={"type": "any"},
            status=CapabilityStatus.ACTIVE,
            source=self._source,
            metadata={
                "server_id": server.identifier,
                "server_name": server.name,
                "tool_name": tool.name,
                "transport": server.transport,
                "command": server.command,
                "url": server.url,
            },
        )

    async def execute(self, name: str, params: dict[str, Any]) -> ExecutionResult:
        """
        执行 MCP 工具。

        Args:
            name: 工具名称 (格式: server__tool_name)
            params: 工具参数

        Returns:
            执行结果

        Raises:
            CapabilityExecutionError: 执行失败
        """
        # 检查能力是否存在
        if not self.has_capability(name):
            return ExecutionResult.error_result(f"MCP tool not found: {name}")

        # 检查 MCP 客户端
        if self._mcp_client is None:
            return ExecutionResult.error_result("No MCP client configured")

        # 验证参数
        valid, error = self.validate_params(name, params)
        if not valid:
            return ExecutionResult.error_result(error or "Invalid parameters")

        try:
            # 从元数据获取服务器和工具名称
            capability = self.get_capability(name)
            server_id = capability.metadata.get("server_id", "")
            tool_name = capability.metadata.get("tool_name", name)

            # 通过 MCP 客户端执行
            result = await self._mcp_client.call_tool(
                server_name=server_id,
                tool_name=tool_name,
                arguments=params,
            )

            # 记录使用
            capability.record_usage(success=True)

            return ExecutionResult.success_result(
                output=result,
                metadata={"server": server_id, "tool": tool_name},
            )

        except Exception as e:
            # 记录失败
            capability = self.get_capability(name)
            if capability:
                capability.record_usage(success=False)

            logger.error(f"[MCPAdapter] MCP tool '{name}' execution failed: {e}")
            return ExecutionResult.error_result(
                error=str(e),
                metadata={"tool": name},
            )

    def get_servers(self) -> list[str]:
        """
        获取所有 MCP 服务器 ID。

        Returns:
            服务器 ID 列表
        """
        servers = set()
        for cap in self._capabilities.values():
            server_id = cap.metadata.get("server_id")
            if server_id:
                servers.add(server_id)
        return list(servers)

    def get_tools_by_server(self, server_id: str) -> list[CapabilityMeta]:
        """
        按服务器获取工具。

        Args:
            server_id: 服务器 ID

        Returns:
            该服务器的所有工具能力
        """
        return [
            cap for cap in self._capabilities.values()
            if cap.metadata.get("server_id") == server_id
        ]

    def get_transport_types(self) -> dict[str, list[str]]:
        """
        按传输类型获取工具。

        Returns:
            传输类型 -> 工具名称列表的映射
        """
        result: dict[str, list[str]] = {}
        for cap in self._capabilities.values():
            transport = cap.metadata.get("transport", "stdio")
            if transport not in result:
                result[transport] = []
            result[transport].append(cap.name)
        return result

    def get_stats(self) -> dict[str, Any]:
        """获取适配器统计信息"""
        stats = super().get_stats()

        # 服务器统计
        stats["servers"] = self.get_servers()
        stats["server_count"] = len(stats["servers"])

        # 传输类型统计
        stats["transport_types"] = self.get_transport_types()

        return stats


class MockMCPAdapter(MCPAdapter):
    """
    模拟 MCP 适配器

    用于测试，不需要真实的 MCP 客户端和目录。
    """

    def __init__(
        self,
        source: str = "mock_mcp",
        servers: list[dict[str, Any]] | None = None,
    ):
        """
        初始化模拟适配器。

        Args:
            source: 来源标识
            servers: 服务器配置列表
                [{"server_id": "..., "tools": [{"name": "...", "description": "..."}]}]
        """
        super().__init__(mcp_client=None, mcp_catalog=None, source=source)
        self._mock_servers = servers or []
        self._mock_results: dict[str, Any] = {}

    def set_mock_result(self, tool_name: str, result: Any) -> None:
        """设置模拟执行结果"""
        self._mock_results[tool_name] = result

    def load(self) -> list[CapabilityMeta]:
        """加载模拟 MCP 工具"""
        capabilities = []

        for server in self._mock_servers:
            server_id = server.get("server_id", "unknown")
            server_name = server.get("server_name", server_id)
            transport = server.get("transport", "stdio")

            for tool in server.get("tools", []):
                name = f"{server_id}__{tool.get('name', 'unknown')}"
                cap = self._create_mock_capability(
                    name=name,
                    server_id=server_id,
                    server_name=server_name,
                    transport=transport,
                    tool=tool,
                )
                capabilities.append(cap)

        self._register_capabilities(capabilities)
        return capabilities

    def _create_mock_capability(
        self,
        name: str,
        server_id: str,
        server_name: str,
        transport: str,
        tool: dict[str, Any],
    ) -> CapabilityMeta:
        """创建模拟能力"""
        return CapabilityMeta(
            name=name,
            type=CapabilityType.MCP,
            description=tool.get("description", ""),
            version="1.0.0",
            tags=["mcp", server_id, transport],
            parameters=tool.get("parameters", {}),
            status=CapabilityStatus.ACTIVE,
            source=self._source,
            metadata={
                "server_id": server_id,
                "server_name": server_name,
                "tool_name": tool.get("name", "unknown"),
                "transport": transport,
            },
        )

    async def execute(self, name: str, params: dict[str, Any]) -> ExecutionResult:
        """执行模拟 MCP 工具"""
        if not self.has_capability(name):
            return ExecutionResult.error_result(f"MCP tool not found: {name}")

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

        # 默认返回
        server_id = capability.metadata.get("server_id", "unknown") if capability else ""
        tool_name = capability.metadata.get("tool_name", name) if capability else ""
        return ExecutionResult.success_result(
            output=f"Mock MCP tool '{tool_name}' on server '{server_id}' executed",
            metadata={"tool": name, "server": server_id, "mock": True},
        )