"""
Tool helpers for Agent.
"""

import logging
import sys
from typing import TYPE_CHECKING

from ...tools.handlers.browser import create_handler as create_browser_handler
from ...tools.handlers.filesystem import create_handler as create_filesystem_handler
from ...tools.handlers.im_channel import create_handler as create_im_channel_handler
from ...tools.handlers.mcp import create_handler as create_mcp_handler
from ...tools.handlers.memory import create_handler as create_memory_handler
from ...tools.handlers.plan import create_plan_handler
from ...tools.handlers.scheduled import create_handler as create_scheduled_handler
from ...tools.handlers.skills import create_handler as create_skills_handler
from ...tools.handlers.system import create_handler as create_system_handler
from ...tools.handlers.web_search import create_handler as create_web_search_handler

if TYPE_CHECKING:
    from ..agent import Agent

logger = logging.getLogger(__name__)


def init_handlers(agent: "Agent") -> None:
    """
    初始化系统工具处理器

    将各个模块的处理器注册到 handler_registry
    """
    # 文件系统
    agent.handler_registry.register(
        "filesystem",
        create_filesystem_handler(agent),
        ["run_shell", "write_file", "read_file", "list_directory"],
    )

    # 记忆系统
    agent.handler_registry.register(
        "memory",
        create_memory_handler(agent),
        ["add_memory", "search_memory", "get_memory_stats"],
    )

    # 浏览器
    agent.handler_registry.register(
        "browser",
        create_browser_handler(agent),
        [
            "browser_task",
            "browser_open",
            "browser_navigate",
            "browser_get_content",
            "browser_screenshot",
            "browser_close",
        ],
    )

    # 定时任务
    agent.handler_registry.register(
        "scheduled",
        create_scheduled_handler(agent),
        [
            "schedule_task",
            "list_scheduled_tasks",
            "cancel_scheduled_task",
            "update_scheduled_task",
            "trigger_scheduled_task",
        ],
    )

    # MCP
    agent.handler_registry.register(
        "mcp",
        create_mcp_handler(agent),
        ["list_mcp_servers", "get_mcp_instructions", "call_mcp_tool"],
    )

    # Plan 模式
    agent.handler_registry.register(
        "plan",
        create_plan_handler(agent),
        ["create_plan", "update_plan_step", "get_plan_status", "complete_plan"],
    )

    # 系统工具
    agent.handler_registry.register(
        "system",
        create_system_handler(agent),
        [
            "ask_user",
            "get_tool_info",
            "get_session_logs",
            "enable_thinking",
            "set_task_timeout",
            "generate_image",
        ],
    )

    # IM 渠道
    agent.handler_registry.register(
        "im_channel",
        create_im_channel_handler(agent),
        ["deliver_artifacts", "get_voice_file", "get_image_file", "get_chat_history"],
    )

    # 技能管理
    agent.handler_registry.register(
        "skills",
        create_skills_handler(agent),
        [
            "list_skills",
            "get_skill_info",
            "run_skill_script",
            "get_skill_reference",
            "install_skill",
            "load_skill",
            "reload_skill",
        ],
    )

    # Web 搜索
    agent.handler_registry.register(
        "web_search",
        create_web_search_handler(agent),
        ["web_search", "news_search"],
    )

    # 桌面工具（仅 Windows）
    if sys.platform == "win32":
        try:
            from ...tools.handlers.desktop import create_handler as create_desktop_handler

            agent.handler_registry.register(
                "desktop",
                create_desktop_handler(agent),
                [
                    "desktop_screenshot",
                    "desktop_find_element",
                    "desktop_click",
                    "desktop_type",
                    "desktop_hotkey",
                    "desktop_scroll",
                    "desktop_window",
                    "desktop_wait",
                    "desktop_inspect",
                ],
            )
        except ImportError:
            pass

    logger.info(
        f"Initialized {len(agent.handler_registry._handlers)} handlers with {len(agent.handler_registry._tool_to_handler)} tools"
    )
