"""
SubAgent 配置加载器

从 YAML 配置文件加载 SubAgent 配置。
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .models import (
    BrainMode,
    CapabilitiesConfig,
    ProcessMode,
    RuntimeConfig,
    StepDefinition,
    SubAgentConfig,
    ToolsConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class SubAgentConfigFile:
    """
    SubAgent YAML 配置文件结构

    对应 YAML 文件的顶层结构
    """

    schema_version: str = "1.0"
    subagent_id: str = ""
    name: str = ""
    description: str = ""
    system_prompt: str = ""
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    skills: list[str] = field(default_factory=list)
    capabilities: CapabilitiesConfig = field(default_factory=CapabilitiesConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    process_mode: ProcessMode = ProcessMode.WORKER
    brain_mode: BrainMode = BrainMode.SHARED_PROXY
    metadata: dict[str, Any] = field(default_factory=dict)


class SubAgentConfigLoader:
    """
    SubAgent 配置加载器

    从 YAML 文件加载并解析 SubAgent 配置。
    支持工具解析、能力过滤和运行时配置合并。
    """

    # 需要过滤的工具（基于能力限制）
    SHELL_TOOLS = {"run_shell", "execute_command", "bash", "shell"}
    WRITE_TOOLS = {"write_file", "edit_file", "create_file", "delete_file"}
    NETWORK_TOOLS = {"web_search", "web_fetch", "http_request"}

    # 默认核心工具集（当未配置工具时使用）
    DEFAULT_CORE_TOOLS = [
        "read_file",
        "list_directory",
        "search_file",
        "grep",
        "list_skills",
        "get_skill_info",
        "run_skill_script",
    ]

    def __init__(
        self,
        system_tools_registry: dict[str, Any] | None = None,
        mcp_manager: Any = None,
        skill_manager: Any = None,
    ):
        """
        初始化配置加载器

        Args:
            system_tools_registry: 系统工具注册表
            mcp_manager: MCP 管理器实例
            skill_manager: Skill 管理器实例
        """
        self._system_tools = system_tools_registry or {}
        self._mcp_manager = mcp_manager
        self._skill_manager = skill_manager

    def load(self, config_path: str | Path) -> SubAgentConfig:
        """
        从 YAML 文件加载配置

        Args:
            config_path: 配置文件路径

        Returns:
            SubAgentConfig 运行时配置

        Raises:
            FileNotFoundError: 配置文件不存在
            ValueError: 配置格式错误
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"SubAgent config not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        if not isinstance(raw, dict):
            raise ValueError(f"Invalid config format: {path}")

        return self.parse(raw)

    def parse(self, raw: dict) -> SubAgentConfig:
        """
        解析原始配置字典

        Args:
            raw: 原始配置字典

        Returns:
            SubAgentConfig 运行时配置
        """
        # 验证版本
        schema_version = raw.get("schema_version", "1.0")
        if schema_version != "1.0":
            raise ValueError(f"Unsupported schema version: {schema_version}")

        # 解析工具配置
        tools_config = self._parse_tools_config(raw.get("tools", {}))

        # 解析并合并工具
        allowed_tools = self._resolve_tools(tools_config)

        # 解析技能列表
        skills = raw.get("skills", [])

        # 解析能力限制
        capabilities = self._parse_capabilities(raw.get("capabilities", {}))

        # 应用能力限制（过滤工具）
        allowed_tools = self._apply_capabilities(allowed_tools, capabilities)

        # 解析运行时配置
        runtime = self._parse_runtime(raw.get("runtime", {}))

        # 解析进程模式和 Brain 模式
        process_mode = ProcessMode(raw.get("process_mode", "worker"))
        brain_mode = BrainMode(raw.get("brain_mode", "shared_proxy"))

        return SubAgentConfig(
            subagent_id=raw["subagent_id"],
            name=raw["name"],
            description=raw.get("description", ""),
            system_prompt=raw.get("system_prompt", ""),
            allowed_tools=allowed_tools,
            skills=skills,
            capabilities=capabilities,
            runtime=runtime,
            process_mode=process_mode,
            brain_mode=brain_mode,
            metadata=raw.get("metadata", {}),
        )

    def _parse_tools_config(self, tools_raw: dict) -> ToolsConfig:
        """解析工具配置"""
        return ToolsConfig(
            system_tools=tools_raw.get("system_tools", []),
            mcp_tools=tools_raw.get("mcp_tools", []),
        )

    def _resolve_tools(self, tools_config: ToolsConfig) -> list[str]:
        """
        解析并合并工具列表

        如果未配置任何工具，则使用默认核心工具集。

        Args:
            tools_config: 工具配置

        Returns:
            合并后的工具名称列表
        """
        tools = []

        # 添加系统工具
        for tool_name in tools_config.system_tools:
            if self._system_tools:
                # 如果有注册表，验证工具存在
                if tool_name in self._system_tools:
                    tools.append(tool_name)
                else:
                    logger.warning(f"System tool not found: {tool_name}")
            else:
                # 无注册表时直接添加
                tools.append(tool_name)

        # 添加 MCP 工具
        for mcp_tool in tools_config.mcp_tools:
            if self._mcp_manager:
                # 如果有 MCP 管理器，验证工具存在
                if hasattr(self._mcp_manager, "has_tool") and self._mcp_manager.has_tool(mcp_tool):
                    tools.append(mcp_tool)
                else:
                    logger.warning(f"MCP tool not found: {mcp_tool}")
            else:
                # 无管理器时直接添加
                tools.append(mcp_tool)

        # 如果没有配置任何工具，使用默认核心工具集
        if not tools:
            logger.info("No tools configured, using default core tools")
            tools = list(self.DEFAULT_CORE_TOOLS)

        return list(set(tools))  # 去重

    def _parse_capabilities(self, caps_raw: dict) -> CapabilitiesConfig:
        """解析能力限制配置"""
        return CapabilitiesConfig(
            allow_shell=caps_raw.get("allow_shell", False),
            allow_write=caps_raw.get("allow_write", False),
            allow_network=caps_raw.get("allow_network", True),
        )

    def _apply_capabilities(
        self,
        tools: list[str],
        capabilities: CapabilitiesConfig,
    ) -> list[str]:
        """
        根据能力限制过滤工具

        Args:
            tools: 工具列表
            capabilities: 能力限制

        Returns:
            过滤后的工具列表
        """
        filtered = []

        for tool in tools:
            tool_lower = tool.lower()

            # 过滤 shell 工具
            if not capabilities.allow_shell:
                if tool_lower in self.SHELL_TOOLS:
                    logger.debug(f"Filtering shell tool: {tool}")
                    continue
                if "shell" in tool_lower or "bash" in tool_lower:
                    logger.debug(f"Filtering shell-related tool: {tool}")
                    continue

            # 过滤写入工具
            if not capabilities.allow_write:
                if tool_lower in self.WRITE_TOOLS:
                    logger.debug(f"Filtering write tool: {tool}")
                    continue
                if "write" in tool_lower or "edit" in tool_lower or "delete" in tool_lower:
                    logger.debug(f"Filtering write-related tool: {tool}")
                    continue

            # 过滤网络工具
            if not capabilities.allow_network:
                if tool_lower in self.NETWORK_TOOLS:
                    logger.debug(f"Filtering network tool: {tool}")
                    continue
                if "web" in tool_lower or "http" in tool_lower:
                    logger.debug(f"Filtering network-related tool: {tool}")
                    continue

            filtered.append(tool)

        return filtered

    def _parse_runtime(self, runtime_raw: dict) -> RuntimeConfig:
        """解析运行时配置"""
        return RuntimeConfig(
            max_iterations=runtime_raw.get("max_iterations", 20),
            session_type=runtime_raw.get("session_type", "cli"),
            memory_policy=runtime_raw.get("memory_policy", "task_scoped"),
            prompt_budget=runtime_raw.get("prompt_budget", "standard"),
            timeout_seconds=runtime_raw.get("timeout_seconds", 300),
        )

    def create_step_config(
        self,
        step_def: StepDefinition,
        base_config: SubAgentConfig | None = None,
    ) -> SubAgentConfig:
        """
        从步骤定义创建 SubAgent 配置

        将步骤定义转换为可执行的 SubAgent 配置。
        如果提供了基础配置，会合并基础配置。

        Args:
            step_def: 步骤定义
            base_config: 基础配置（可选）

        Returns:
            SubAgentConfig 实例
        """
        # 解析步骤的工具配置
        allowed_tools = self._resolve_tools(step_def.tools)

        # 如果有基础配置，合并
        if base_config:
            capabilities = base_config.capabilities
            runtime = base_config.runtime
            process_mode = base_config.process_mode
            brain_mode = base_config.brain_mode
            # 合并技能
            skills = list(set(base_config.skills + step_def.skills))
        else:
            capabilities = CapabilitiesConfig()
            runtime = RuntimeConfig()
            process_mode = ProcessMode.WORKER
            brain_mode = BrainMode.SHARED_PROXY
            skills = step_def.skills

        # 应用能力限制
        allowed_tools = self._apply_capabilities(allowed_tools, capabilities)

        return SubAgentConfig(
            subagent_id=f"step-{step_def.step_id}",
            name=step_def.name,
            description=step_def.description,
            system_prompt=step_def.system_prompt,
            allowed_tools=allowed_tools,
            skills=skills,
            capabilities=capabilities,
            runtime=runtime,
            process_mode=process_mode,
            brain_mode=brain_mode,
            metadata={
                "step_id": step_def.step_id,
                "output_key": step_def.output_key,
                "requires_confirmation": step_def.requires_confirmation,
            },
        )


# ==================== 便捷函数 ====================


def load_subagent_config(
    config_path: str | Path,
    system_tools_registry: dict | None = None,
    mcp_manager: Any = None,
) -> SubAgentConfig:
    """
    加载 SubAgent 配置的便捷函数

    Args:
        config_path: 配置文件路径
        system_tools_registry: 系统工具注册表
        mcp_manager: MCP 管理器

    Returns:
        SubAgentConfig 实例
    """
    loader = SubAgentConfigLoader(
        system_tools_registry=system_tools_registry,
        mcp_manager=mcp_manager,
    )
    return loader.load(config_path)