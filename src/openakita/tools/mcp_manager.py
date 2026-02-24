"""
MCP Manager
负责 MCP 服务器的发现、加载、启动和注册。
整合了 MCPCatalog (目录发现) 和 MCPClient (连接执行)。
"""
import logging
import contextlib
import os
from pathlib import Path
from ..config import settings
from .mcp_catalog import MCPCatalog
from .mcp import MCPClient, MCPServerConfig

logger = logging.getLogger(__name__)

class MCPManager:
    """
    MCP (Model Context Protocol) 管理器。

    负责 MCP 服务器的发现、加载、启动和注册。
    整合了 MCPCatalog (目录发现) 和 MCPClient (连接执行)。
    """

    def __init__(self, mcp_client: "MCPClient", mcp_catalog: "MCPCatalog"):
        self.client = mcp_client
        self.catalog = mcp_catalog
        self._builtin_mcp_count = 0
        self.browser_mcp = None  # 用于存储 browser-use 实例
        self.catalog_text = ""

    @property
    def builtin_count(self) -> int:
        return self._builtin_mcp_count

    async def load_servers(self) -> str:
        """
        加载 MCP 服务器配置
        
        只加载项目本地的 MCP，不加载 Cursor 的（因为无法实际调用）
        
        Returns:
            str: 生成的 MCP Catalog 文本
        """
        # 只加载项目本地 MCP 目录
        possible_dirs = [
            settings.project_root / "mcps",
            settings.project_root / ".mcp",
        ]

        total_count = 0

        for dir_path in possible_dirs:
            if dir_path.exists():
                count = self.catalog.scan_mcp_directory(dir_path)
                if count > 0:
                    total_count += count
                    logger.info(f"Loaded {count} MCP servers from {dir_path}")

        # 将扫描到的 MCP 服务器同步注册到 MCPClient（否则“目录可见但不可调用”）
        # 目录（mcp_catalog）负责发现与提示词披露；执行（mcp_client）负责真实连接与调用。
        try:
            for server in getattr(self.catalog, "_servers", []) or []:
                # server 是 MCPServerInfo，包含 command/args/env/transport/url（来自 SERVER_METADATA.json）
                if not getattr(server, "identifier", None):
                    continue
                transport = getattr(server, "transport", "stdio") or "stdio"
                # stdio 模式需要 command；streamable_http 模式需要 url
                if transport == "stdio" and not getattr(server, "command", None):
                    continue
                if transport == "streamable_http" and not getattr(server, "url", None):
                    continue
                    
                self.client.add_server(
                    MCPServerConfig(
                        name=server.identifier,
                        command=getattr(server, "command", "") or "",
                        args=list(getattr(server, "args", []) or []),
                        env=dict(getattr(server, "env", {}) or {}),
                        description=getattr(server, "name", "") or "",
                        transport=transport,
                        url=getattr(server, "url", "") or "",
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to register MCP servers into MCPClient: {e}")

        # 启动内置 MCP 服务器
        await self._start_builtin_mcp_servers()

        if total_count > 0 or self._builtin_mcp_count > 0:
            self.catalog_text = self.catalog.generate_catalog()
            logger.info(f"Total MCP servers: {total_count + self._builtin_mcp_count}")
        else:
            self.catalog_text = ""
            logger.info("No MCP servers configured")
            
        return self.catalog_text

    async def _start_builtin_mcp_servers(self) -> None:
        """启动内置服务 (如 browser-use)"""
        self._builtin_mcp_count = 0

        # 初始化浏览器服务 (作为内置工具，不是 MCP)
        # 注意: 不自动启动浏览器，由 browser_open 工具控制启动时机和模式
        try:
            # 先检查 playwright 是否可用，避免假阳性日志
            from ._import_helper import import_or_hint
            pw_hint = import_or_hint("playwright")
            if pw_hint:
                logger.warning(f"浏览器自动化不可用: {pw_hint}")
            else:
                from .browser_mcp import BrowserMCP

                self.browser_mcp = BrowserMCP(headless=False)  # 默认可见模式
                # 不在这里 await self.browser_mcp.start()，让 LLM 通过 browser_open 控制

                # 注意: 浏览器工具已在 BASE_TOOLS 中定义，不需要注册到 MCP catalog
                # 这样 LLM 就会直接使用 browser_navigate 等工具名，而不是 MCP 格式
                self._builtin_mcp_count += 1
                logger.info("Started builtin browser service (Playwright)")
        except Exception as e:
            logger.warning(f"Failed to start browser service: {e}")

    def inject_llm_config(self, llm_client: object) -> None:
        """
        为 browser-use 注入 LLM 配置。

        browser_task（browser-use）需要一个 OpenAI-compatible LLM。
        这里尝试从 LLMClient 中提取可用的 OpenAI 配置。

        Args:
            llm_client: LLMClient 实例（使用 object 避免循环导入）
        """
        try:
            if not self.browser_mcp:
                return

            provider = None
            if llm_client:
                # 优先使用当前健康端点；若不是 openai 协议，则退化为任意健康 openai 协议端点
                current = getattr(llm_client, "get_current_model", lambda: None)()
                providers = getattr(llm_client, "providers", {})
                
                if current and current.name in providers:
                    p = providers[current.name]
                    if getattr(p.config, "api_type", "") == "openai" and getattr(p, "is_healthy", False):
                        provider = p
                
                if provider is None:
                    for p in providers.values():
                        if getattr(p.config, "api_type", "") == "openai" and getattr(p, "is_healthy", False):
                            provider = p
                            break

            if provider:
                api_key = provider.config.get_api_key()
                if api_key:
                    self.browser_mcp.set_llm_config(
                        {
                            "model": provider.config.model,
                            "api_key": api_key,
                            "base_url": provider.config.base_url.rstrip("/"),
                        }
                    )
                    logger.debug(f"[BrowserMCP] Injected LLM config from provider: {provider.config.name}")
        except Exception as e:
            logger.debug(f"[BrowserMCP] LLM config injection skipped/failed: {e}")
