"""
Browser 工具定义

包含浏览器自动化相关的工具（遵循 tool-definition-spec.md 规范）：
- browser_task: 【推荐优先使用】智能浏览器任务
- browser_open: 启动浏览器 + 状态查询
- browser_navigate: 导航到 URL
- browser_get_content: 获取页面内容
- browser_screenshot: 截取页面截图
- browser_close: 关闭浏览器
"""

from .base import build_detail

# ==================== 工具定义 ====================

BROWSER_TOOLS = [
    # ---------- browser_task ---------- 【推荐优先使用】
    {
        "name": "browser_task",
        "category": "Browser",
        "description": "【强烈推荐】【优先使用】智能浏览器任务 - 描述你想完成的任务，browser-use Agent 会自动规划和执行所有步骤。适用于：(1) 多步骤操作（如搜索+筛选+排序），(2) 复杂的网页交互（包括点击、输入、填表），(3) 不确定具体步骤的任务，(4) 任何需要元素交互的任务（点击、输入、标签页管理）。⚠️ 重要：在 Plan 模式下，浏览器相关步骤必须使用 browser_task，不要使用 browser_click/browser_type 等底层工具。如果仅打开 URL，请使用 browser_navigate。",
        "detail": build_detail(
            summary="智能浏览器任务 - 描述你想完成的任务，browser-use Agent 会自动规划和执行所有步骤。",
            scenarios=[
                "多步骤操作（如：搜索商品 → 筛选价格 → 按销量排序）",
                "复杂网页交互（如：登录 → 填表 → 提交）",
                "不确定具体步骤的任务",
                "需要智能判断和处理的场景",
                "点击按钮、输入文本、管理标签页等所有页面交互",
            ],
            params_desc={
                "task": "要完成的任务描述，越详细越好。例如：'打开淘宝搜索机械键盘，筛选价格200-500元，按销量排序'",
                "max_steps": "最大执行步骤数，默认15步。复杂任务可以增加。",
            },
            workflow_steps=[
                "描述你想完成的任务",
                "browser-use Agent 自动分析任务",
                "自动规划执行步骤",
                "逐步执行并处理异常",
                "返回执行结果",
            ],
            notes=[
                "✅ 推荐用于多步骤、复杂的浏览器任务",
                "✅ 推荐用于所有需要点击、输入、表单填写的操作",
                "⚠️ Plan 模式下，浏览器步骤必须使用 browser_task，禁止使用底层工具",
                "自动继承系统 LLM 配置，无需额外设置 API Key",
                "通过 CDP 复用已启动的浏览器",
                "任务描述要清晰具体，避免歧义",
                "复杂任务可能需要增加 max_steps",
            ],
        ),
        "triggers": [
            "当用户要求在网站上执行复杂操作时",
            "当任务涉及多个步骤（搜索、筛选、排序等）时",
            "当确切步骤不清楚时",
            "当任务描述是高级别的，如'帮我在淘宝上找...'时",
            "当点击按钮、填写表单或与页面元素交互时",
            "当管理多个标签页或在页面之间切换时",
        ],
        "prerequisites": [],
        "warnings": [
            "任务描述应清晰具体",
            "复杂任务可能需要更高的 max_steps",
        ],
        "examples": [
            {
                "scenario": "淘宝搜索筛选排序",
                "params": {
                    "task": "打开淘宝搜索机械键盘，筛选价格200-500元，按销量排序，截图发给我"
                },
                "expected": "Agent 自动：打开淘宝 → 搜索 → 筛选价格 → 按销量排序 → 截图",
            },
            {
                "scenario": "GitHub 查找项目",
                "params": {"task": "在 GitHub 找 star 数最多的 Python 项目"},
                "expected": "Agent 自动：打开 GitHub → 导航到搜索 → 按 star 排序 → 筛选 Python",
            },
            {
                "scenario": "新闻搜索",
                "params": {"task": "打开百度搜索今天的科技新闻，截图给我"},
                "expected": "Agent 自动：打开百度 → 搜索 → 截图",
            },
        ],
        "related_tools": [
            {"name": "browser_navigate", "relation": "alternative for simple URL opening"},
            {
                "name": "browser_screenshot",
                "relation": "can be used after task for manual screenshot",
            },
        ],
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "要完成的任务描述，例如：'打开淘宝搜索机械键盘，筛选价格200-500元，按销量排序'",
                },
                "max_steps": {
                    "type": "integer",
                    "description": "最大执行步骤数，默认15。复杂任务可以增加。",
                    "default": 15,
                },
            },
            "required": ["task"],
        },
    },
    # ---------- browser_open ---------- (合并了 browser_status)
    {
        "name": "browser_open",
        "category": "Browser",
        "description": "启动浏览器或检查浏览器状态。始终返回当前状态（是否打开、URL、标题、tab 数）。如果浏览器已在运行，则返回状态而不重启。如果未运行，则启动它。在任何浏览器操作之前调用此函数以确保浏览器已准备就绪。服务重启时浏览器状态会重置。",
        "detail": build_detail(
            summary="启动浏览器或检查浏览器状态。始终返回当前状态（是否打开、URL、标题、tab 数）。",
            scenarios=[
                "开始 Web 自动化任务前确认浏览器状态",
                "启动浏览器",
                "检查浏览器是否正常运行",
            ],
            params_desc={
                "visible": "True=显示浏览器窗口（用户可见），False=后台运行（不可见）",
            },
            notes=[
                "⚠️ 每次浏览器任务前建议调用此工具确认状态",
                "如果浏览器已在运行，直接返回当前状态，不会重复启动",
                "服务重启后浏览器会关闭，不能假设已打开",
                "默认显示浏览器窗口",
            ],
        ),
        "triggers": [
            "在任何浏览器操作之前",
            "当开始 Web 自动化任务时",
            "当检查浏览器是否正在运行时",
        ],
        "prerequisites": [],
        "warnings": [
            "服务重启时浏览器状态会重置 - 永远不要假设它根据历史记录是打开的",
        ],
        "examples": [
            {
                "scenario": "检查浏览器状态并启动",
                "params": {},
                "expected": "返回 {is_open: true/false, url: '...', title: '...', tab_count: N}。如果未运行则启动浏览器。",
            },
            {
                "scenario": "启动可见浏览器",
                "params": {"visible": True},
                "expected": "浏览器窗口打开且对用户可见，返回状态",
            },
            {
                "scenario": "后台模式启动",
                "params": {"visible": False},
                "expected": "浏览器在后台运行，无可见窗口，返回状态",
            },
        ],
        "related_tools": [
            {"name": "browser_navigate", "relation": "commonly used after opening"},
            {"name": "browser_task", "relation": "recommended for complex tasks"},
            {"name": "browser_close", "relation": "close browser when done"},
        ],
        "input_schema": {
            "type": "object",
            "properties": {
                "visible": {
                    "type": "boolean",
                    "description": "True=显示浏览器窗口, False=后台运行。默认 True",
                    "default": True,
                },
            },
            "required": [],
        },
    },
    # ---------- browser_navigate ----------
    {
        "name": "browser_navigate",
        "category": "Browser",
        "description": "将浏览器导航到指定 URL 以打开网页。仅用于简单的 URL 打开。对于多步骤任务（搜索+点击+输入），请改用 browser_task。如果浏览器未运行，则自动启动。",
        "detail": build_detail(
            summary="导航到指定 URL。",
            scenarios=[
                "打开网页查看内容",
                "Web 自动化任务的第一步",
                "切换到新页面",
            ],
            params_desc={
                "url": "要访问的完整 URL（必须包含协议，如 https://）",
            },
            workflow_steps=[
                "调用此工具导航到目标页面",
                "等待页面加载",
                "使用 browser_get_content 获取内容 或 browser_screenshot 截图",
            ],
            notes=[
                "如果浏览器未启动会自动启动",
                "URL 必须包含协议（http:// 或 https://）",
                "如需与页面交互（点击、输入），请改用 browser_task",
            ],
        ),
        "triggers": [
            "当用户要求打开网页时",
            "当使用已知 URL 开始 Web 自动化任务时",
        ],
        "prerequisites": [],
        "warnings": [],
        "examples": [
            {
                "scenario": "打开搜索引擎",
                "params": {"url": "https://www.google.com"},
                "expected": "浏览器导航到 Google 首页",
            },
            {
                "scenario": "打开本地文件",
                "params": {"url": "file:///C:/Users/test.html"},
                "expected": "浏览器打开本地 HTML 文件",
            },
        ],
        "related_tools": [
            {"name": "browser_task", "relation": "recommended for multi-step tasks or page interaction"},
            {"name": "browser_get_content", "relation": "extract content after navigation"},
            {"name": "browser_screenshot", "relation": "capture page after navigation"},
        ],
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "要访问的 URL（必须包含协议）"},
            },
            "required": ["url"],
        },
    },
    # ---------- browser_get_content ----------
    {
        "name": "browser_get_content",
        "category": "Browser",
        "description": "从当前网页提取页面内容和元素文本。当你需要：(1) 读取页面信息，(2) 获取元素值，(3) 抓取数据，(4) 验证页面内容。",
        "detail": build_detail(
            summary="获取页面内容（文本或 HTML）。",
            scenarios=[
                "读取页面信息",
                "获取元素值",
                "抓取数据",
                "验证页面内容",
            ],
            params_desc={
                "selector": "元素选择器（可选，不填则获取整个页面）",
                "format": "返回格式：text（纯文本，默认）或 html（HTML 源码）",
            },
            notes=[
                "不指定 selector：获取整个页面文本",
                "指定 selector：获取特定元素的文本",
                "format 默认为 text，如需 HTML 源码请指定为 html",
            ],
        ),
        "triggers": [
            "当读取页面信息时",
            "当从网页提取数据时",
            "当导航后验证页面内容时",
        ],
        "prerequisites": [
            "页面必须已加载（已调用 browser_navigate 或 browser_task 已完成）",
        ],
        "warnings": [],
        "examples": [
            {
                "scenario": "获取整个页面内容",
                "params": {},
                "expected": "返回完整页面文本内容",
            },
            {
                "scenario": "获取特定元素内容",
                "params": {"selector": ".article-body"},
                "expected": "返回文章主体的文本内容",
            },
            {
                "scenario": "获取页面 HTML 源码",
                "params": {"format": "html"},
                "expected": "返回完整页面 HTML 内容",
            },
        ],
        "related_tools": [
            {"name": "browser_navigate", "relation": "load page before getting content"},
            {"name": "browser_screenshot", "relation": "alternative - visual capture"},
        ],
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "元素选择器（可选，不填则获取整个页面）",
                },
                "format": {
                    "type": "string",
                    "enum": ["text", "html"],
                    "description": "返回格式：text（纯文本，默认）或 html（HTML 源码）",
                    "default": "text",
                },
                "max_length": {
                    "type": "integer",
                    "description": "最大返回字符数，默认 12000。超出部分保存到溢出文件，可用 read_file 分页读取",
                    "default": 12000,
                },
            },
            "required": [],
        },
    },
    # ---------- browser_screenshot ----------
    {
        "name": "browser_screenshot",
        "category": "Browser",
        "description": "截取浏览器页面截图（仅网页内容，不包括桌面）。当你需要：(1) 向用户展示页面状态，(2) 记录 Web 结果，(3) 调试页面问题。如需截取桌面/应用程序截图，请改用 desktop_screenshot。",
        "detail": build_detail(
            summary="截取当前页面截图。",
            scenarios=[
                "向用户展示页面状态",
                "记录网页操作结果",
                "调试页面问题",
            ],
            params_desc={
                "full_page": "是否截取整个页面（包含滚动区域），默认 False 只截取可视区域",
                "path": "保存路径（可选，不填自动生成）",
            },
            notes=[
                "仅截取浏览器页面内容",
                "如需截取桌面或其他应用，请使用 desktop_screenshot",
                "full_page=True 会截取页面的完整内容（包含需要滚动才能看到的部分）",
            ],
        ),
        "triggers": [
            "When user asks to see the webpage",
            "When documenting web automation results",
            "When debugging page display issues",
        ],
        "prerequisites": [
            "Page must be loaded (browser_navigate called or browser_task completed)",
        ],
        "warnings": [],
        "examples": [
            {
                "scenario": "截取当前页面",
                "params": {},
                "expected": "Saves screenshot with auto-generated filename",
            },
            {
                "scenario": "截取完整页面",
                "params": {"full_page": True},
                "expected": "Saves full-page screenshot including scrollable content",
            },
            {
                "scenario": "保存到指定路径",
                "params": {"path": "C:/screenshots/result.png"},
                "expected": "Saves screenshot to specified path",
            },
        ],
        "related_tools": [
            {"name": "desktop_screenshot", "relation": "alternative for desktop apps"},
            {
                "name": "deliver_artifacts",
                "relation": "deliver the screenshot as an attachment (with receipts)",
            },
        ],
        "input_schema": {
            "type": "object",
            "properties": {
                "full_page": {
                    "type": "boolean",
                    "description": "是否截取整个页面（包含滚动区域），默认只截取可视区域",
                    "default": False,
                },
                "path": {"type": "string", "description": "保存路径（可选，不填自动生成）"},
            },
            "required": [],
        },
    },
    # ---------- browser_close ----------
    {
        "name": "browser_close",
        "category": "Browser",
        "description": "关闭浏览器并释放资源。当浏览器自动化完成且不再需要时调用。这将释放内存和系统资源。",
        "detail": build_detail(
            summary="关闭浏览器，释放资源。",
            scenarios=[
                "浏览器任务全部完成后",
                "需要释放系统资源",
                "需要重新启动浏览器（先关闭再打开）",
            ],
            notes=[
                "关闭后需要再次调用 browser_open 才能使用浏览器",
                "所有标签页都会关闭",
            ],
        ),
        "triggers": [
            "当浏览器自动化任务完成时",
            "当用户明确要求关闭浏览器时",
            "当释放系统资源时",
        ],
        "prerequisites": [],
        "warnings": [
            "所有打开的标签页和页面都将被关闭",
        ],
        "examples": [
            {
                "scenario": "任务完成后关闭浏览器",
                "params": {},
                "expected": "浏览器关闭，资源释放",
            },
        ],
        "related_tools": [
            {"name": "browser_open", "relation": "reopen browser after closing"},
        ],
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]
