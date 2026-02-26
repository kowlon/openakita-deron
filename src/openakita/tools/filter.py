"""
工具按需加载过滤器

根据任务内容动态选择需要的工具子集，减少 tokens 消耗。
"""

import logging

logger = logging.getLogger(__name__)

# 工具预设配置
TOOL_PRESETS = {
    "minimal": {
        "run_shell", "read_file", "write_file", "edit_file", "list_directory",
        "ask_user", "get_tool_info", "get_skill_info"
    },
    "web": {
        "run_shell", "read_file", "write_file", "web_search",
        "browser_navigate", "browser_click", "browser_screenshot",
        "ask_user", "get_tool_info"
    },
    "file": {
        "run_shell", "read_file", "write_file", "edit_file", "list_directory",
        "grep", "ask_user", "get_tool_info", "get_skill_info"
    },
    "code": {
        "run_shell", "read_file", "write_file", "edit_file", "list_directory",
        "grep", "web_search", "ask_user", "get_tool_info"
    },
    "plan": {
        "create_plan", "update_plan_step", "complete_plan", "get_plan_info",
        "run_shell", "read_file", "write_file", "ask_user", "get_tool_info"
    },
    "memory": {
        "add_memory", "search_memory", "get_memory_stats",
        "run_shell", "ask_user", "get_tool_info"
    },
    "im": {
        "send_im_message", "deliver_artifacts", "ask_user",
        "run_shell", "read_file", "write_file", "get_tool_info"
    },
}

# 任务类型关键词映射
TASK_KEYWORDS = {
    "web": [
        "搜索", "查找", "查询", "search", "find", "look up", "查一下", "搜一下",
        "网页", "网站", "浏览器", "browser", "website", "web",
        "新闻", "资讯", "news",
    ],
    "file": [
        "文件", "写入", "编辑", "读取", "目录", "folder", "directory",
        "file", "write", "read", "edit", "保存", "save",
        "pdf", "doc", "txt", "json", "csv",
    ],
    "code": [
        "代码", "运行", "执行", "脚本", "编程", "code", "run", "execute",
        "script", "programming", "python", "javascript", "bash", "shell",
        "调试", "debug", "测试", "test",
    ],
    "plan": [
        "计划", "规划", "步骤", "多步", "复杂", "plan", "schedule",
        "首先", "然后", "最后", "first", "then", "finally",
        "分步", "step by step",
    ],
    "memory": [
        "记住", "记忆", "回忆", "保存", "remember", "memory", "recall",
        "忘记", "forget", "历史", "history",
    ],
    "im": [
        "发送", "消息", "通知", "send", "message", "notify",
        "交付", "deliver", "文件", "attachment",
    ],
}

# 高频工具（始终包含）
ALWAYS_INCLUDE = {
    "run_shell", "read_file", "write_file", "ask_user",
    "get_tool_info", "get_skill_info"
}

# Plan 工具（多步骤任务必须）
PLAN_TOOLS = {
    "create_plan", "update_plan_step", "get_plan_status", "complete_plan"
}

# 低频工具（通常不需要）
RARELY_NEEDED = {
    "schedule_task", "list_scheduled_tasks", "cancel_scheduled_task",
}

# 搜索关键词 - 如果包含这些，强制添加 web_search
SEARCH_KEYWORDS = {
    "搜索", "查找", "查询", "search", "find", "look up",
    "查一下", "搜一下", "查查", "查是谁", "是谁",
    "新闻", "资讯", "news", "了解", "信息",
}

# 多步骤任务关键词 - 用于检测是否需要 Plan
# 与 handlers/plan.py 的 should_require_plan() 保持一致
PLAN_ACTION_WORDS = [
    "打开", "搜索", "截图", "发", "发送", "写", "创建",
    "执行", "运行", "读取", "查看", "保存", "下载", "上传",
    "复制", "粘贴", "删除", "编辑", "修改", "更新",
    "安装", "配置", "设置", "启动", "关闭",
]
PLAN_CONNECTOR_WORDS = ["然后", "接着", "之后", "并且", "再", "最后"]


def needs_plan(message: str) -> bool:
    """
    检测消息是否需要 Plan 模式。

    使用与 handlers/plan.py 的 should_require_plan() 相同的逻辑：
    1. 包含 5+ 个动作词
    2. 包含 3+ 个动作词 + 连接词
    3. 包含 3+ 个动作词 + 逗号分隔
    """
    msg = message.lower()

    action_count = sum(1 for word in PLAN_ACTION_WORDS if word in msg)
    has_connector = any(word in msg for word in PLAN_CONNECTOR_WORDS)
    comma_separated = "，" in msg or "," in msg

    if action_count >= 5:
        return True
    if action_count >= 3 and has_connector:
        return True
    return bool(action_count >= 3 and comma_separated)


def detect_task_types(message: str) -> list[str]:
    """
    检测消息涉及的所有任务类型（多类型检测）。

    Args:
        message: 用户消息

    Returns:
        匹配的任务类型列表（按得分降序）
    """
    message_lower = message.lower()

    scores = {}
    for task_type, keywords in TASK_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in message_lower)
        if score > 0:
            scores[task_type] = score

    if not scores:
        return ["minimal"]

    # 返回所有匹配类型（按得分降序）
    return sorted(scores.keys(), key=lambda x: scores[x], reverse=True)


def needs_search(message: str) -> bool:
    """检测消息是否需要搜索功能"""
    message_lower = message.lower()
    return any(kw in message_lower for kw in SEARCH_KEYWORDS)


def detect_task_type(message: str) -> str:
    """
    根据消息内容检测任务类型（向后兼容，返回主类型）。
    """
    types = detect_task_types(message)
    return types[0] if types else "minimal"


def get_tools_for_message(
    all_tools: list[dict],
    message: str,
    session_type: str = "desktop",
) -> list[dict]:
    """
    根据消息内容选择需要的工具子集。

    使用多类型检测，合并所有相关类型的工具。

    Args:
        all_tools: 所有可用工具列表
        message: 用户消息
        session_type: 会话类型 (desktop/im)

    Returns:
        过滤后的工具列表
    """
    from ..config import settings

    # 如果禁用按需加载，返回全部工具
    if not getattr(settings, "tool_lazy_loading", True):
        logger.info("[ToolFilter] Lazy loading disabled, using all tools")
        return all_tools

    # 检测所有相关任务类型
    detected_types = detect_task_types(message)

    # 合并所有检测到的类型的工具
    needed_tools = set(ALWAYS_INCLUDE)
    for task_type in detected_types:
        preset = TOOL_PRESETS.get(task_type, set())
        needed_tools |= preset

    # ★ 关键修复：如果检测到搜索关键词，强制添加 web_search
    if needs_search(message):
        needed_tools.add("web_search")
        # 同时添加浏览器工具（可能需要）
        needed_tools |= {"browser_navigate", "browser_screenshot"}

    # ★ 关键修复：如果检测到多步骤任务，强制添加 Plan 工具
    # 与 handlers/plan.py 的 should_require_plan() 使用相同逻辑
    if needs_plan(message):
        needed_tools |= PLAN_TOOLS
        logger.info("[ToolFilter] Multi-step task detected, adding Plan tools")

    # IM 模式额外添加 IM 工具
    if session_type == "im":
        needed_tools |= TOOL_PRESETS.get("im", set())

    # 过滤工具
    filtered = []
    for tool in all_tools:
        tool_name = tool.get("name", "")
        if tool_name in needed_tools:
            filtered.append(tool)

    # 记录过滤结果
    original_count = len(all_tools)
    filtered_count = len(filtered)
    reduction_pct = (1 - filtered_count / original_count) * 100 if original_count > 0 else 0

    logger.info(
        f"[ToolFilter] Detected types: {detected_types}, "
        f"needs_search={needs_search(message)}, needs_plan={needs_plan(message)}, "
        f"Tools: {original_count} → {filtered_count} (-{reduction_pct:.0f}%)"
    )

    return filtered


def estimate_tool_tokens(tools: list[dict]) -> int:
    """
    估算工具定义的 token 数量。

    Args:
        tools: 工具列表

    Returns:
        估算的 token 数量
    """
    # 粗略估算：每个工具平均 ~300 tokens
    # 包含 name, description, input_schema
    return len(tools) * 300
