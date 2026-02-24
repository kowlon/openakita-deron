"""
OpenAkita 工具模块

提供标准工具接口和执行引擎：
- ToolExecutor: 负责解析工具调用，执行本地工具或 MCP 工具
- Filter: 负责根据上下文选择合适的工具，优化 Token 使用
"""

import sys

from .executor import ToolExecutor
from .file import FileTool
from .filter import (
    detect_task_type,
    detect_task_types,
    estimate_tool_tokens,
    get_tools_for_message,
)
from .mcp import MCPClient, mcp_client
from .mcp_catalog import MCPCatalog, scan_mcp_servers
from .shell import ShellTool
from .web import WebTool

__all__ = [
    "ShellTool",
    "FileTool",
    "WebTool",
    "ToolExecutor",
    "MCPClient",
    "mcp_client",
    "MCPCatalog",
    "scan_mcp_servers",
    "detect_task_type",
    "detect_task_types",
    "estimate_tool_tokens",
    "get_tools_for_message",
]

# Windows 桌面自动化模块（仅 Windows 平台可用）
if sys.platform == "win32":
    try:
        from .desktop import (  # noqa: F401
            DESKTOP_TOOLS,
            DesktopController,
            DesktopToolHandler,
            KeyboardController,
            MouseController,
            ScreenCapture,
            UIAClient,
            VisionAnalyzer,
            get_controller,
            register_desktop_tools,
        )

        __all__.extend(
            [
                "DesktopController",
                "get_controller",
                "ScreenCapture",
                "MouseController",
                "KeyboardController",
                "UIAClient",
                "VisionAnalyzer",
                "DESKTOP_TOOLS",
                "DesktopToolHandler",
                "register_desktop_tools",
            ]
        )
    except ImportError as e:
        # 依赖未安装时的警告
        import logging

        logging.getLogger(__name__).debug(
            f"Desktop automation module not available: {e}. "
            "Install with: pip install mss pyautogui pywinauto"
        )
