"""
System 工具定义

包含系统功能相关的工具：
- ask_user: 向用户提问并等待回复（暂停执行）
- enable_thinking: 控制深度思考模式
- get_session_logs: 获取会话日志
- get_tool_info: 获取工具详细信息
- generate_image: AI 生成图片
- set_task_timeout: 调整任务超时策略
"""

SYSTEM_TOOLS = [
    {
        "name": "ask_user",
        "category": "System",
        "description": "向用户提问并暂停执行，直到他们回复。当你需要：(1) 缺少关键信息，(2) 任务模棱两可需要澄清，(3) 继续前需要用户确认。不要将问题放在纯文本中 —— 只有此工具才会触发真正的暂停。当问题有选项时，务必提供 options。支持单选和多选（通过 allow_multiple）。对于多个相关问题，使用 questions 数组一次性提问。",
        "detail": """向用户提问并暂停执行，等待用户回复。支持单个问题和多个问题。

**何时使用**：
- 关键信息缺失（如：路径、账号、具体目标不明确）
- 任务有歧义，需要用户澄清
- 需要用户确认后才能继续（如：危险操作、多选方案）

**单个简单问题**：
- 使用 question + options 即可

**多个问题 / 复杂问题**：
- 使用 questions 数组，每个问题可以独立配置选项和单选/多选
- question 字段作为总体说明或标题

**选项（options）**：
- 当问题有有限个选项时（如二选一、多选一），**必须**提供 options 参数
- 用户可以直接点选，不需要手动输入
- 默认是单选（allow_multiple=false），如需多选请设置 allow_multiple=true
- 例如单选："确认还是取消？" → options: [{id:"confirm",label:"确认"},{id:"cancel",label:"取消"}]
- 例如多选："需要安装哪些功能？" → options: [...], allow_multiple: true
- 用户也可以选择"其他"手动输入，无需在 options 中包含"其他"选项

**重要**：
- 调用此工具后，系统会立即暂停当前任务的执行循环
- 用户回复后，系统会在保留上下文的情况下继续执行
- **不要**在纯文本回复中提出问题然后继续执行——文本中的问号不会触发暂停
- 不需要提问的场景：闲聊/问候、简单确认、任务总结""",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "单个问题文本，或多问题时的总体说明/标题",
                },
                "options": {
                    "type": "array",
                    "description": "单个问题的选项列表（简单模式）。当使用 questions 数组时，选项放在各问题中。",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "选项唯一标识（会作为用户回复内容）",
                            },
                            "label": {
                                "type": "string",
                                "description": "选项显示文本",
                            },
                        },
                        "required": ["id", "label"],
                    },
                },
                "allow_multiple": {
                    "type": "boolean",
                    "description": "单个问题的选项是否允许多选（默认 false = 单选）。使用 questions 数组时在各问题中设置。",
                    "default": False,
                },
                "questions": {
                    "type": "array",
                    "description": "多个问题列表。用于一次性问多个相关问题，每个问题可以有自己的选项和单选/多选设置。",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "问题唯一标识（用于匹配用户回复）",
                            },
                            "prompt": {
                                "type": "string",
                                "description": "问题文本",
                            },
                            "options": {
                                "type": "array",
                                "description": "此问题的选项列表",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {
                                            "type": "string",
                                            "description": "选项唯一标识",
                                        },
                                        "label": {
                                            "type": "string",
                                            "description": "选项显示文本",
                                        },
                                    },
                                    "required": ["id", "label"],
                                },
                            },
                            "allow_multiple": {
                                "type": "boolean",
                                "description": "是否允许多选（默认 false = 单选）",
                                "default": False,
                            },
                        },
                        "required": ["id", "prompt"],
                    },
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "enable_thinking",
        "category": "System",
        "description": "控制深度思考模式。默认启用。对于非常简单的任务（简单提醒、问候、快速查询），可以临时禁用以加快响应。完成后自动恢复为启用。",
        "detail": """控制深度思考模式。

**默认状态**：启用

**可临时关闭的场景**：
- 简单提醒
- 简单问候
- 快速查询

**注意**：
- 完成后会自动恢复默认启用状态
- 复杂任务建议保持启用""",
        "input_schema": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "description": "是否启用 thinking 模式"},
                "reason": {"type": "string", "description": "简要说明原因"},
            },
            "required": ["enabled", "reason"],
        },
    },
    {
        "name": "get_session_logs",
        "category": "System",
        "description": "获取当前会话系统日志。重要提示：当命令失败、遇到错误或需要了解先前的操作结果时，请调用此工具。日志包含：命令详情、错误信息、系统状态。",
        "detail": """获取当前会话的系统日志。

**重要**: 当命令执行失败、遇到错误、或需要了解之前的操作结果时，应该调用此工具查看日志。

**日志包含**:
- 命令执行详情
- 错误信息
- 系统状态

**使用场景**:
1. 命令返回错误码
2. 操作没有预期效果
3. 需要了解之前发生了什么""",
        "input_schema": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "返回的日志条数（默认 20，最大 200）",
                    "default": 20,
                },
                "level": {
                    "type": "string",
                    "enum": ["DEBUG", "INFO", "WARNING", "ERROR"],
                    "description": "过滤日志级别（可选，ERROR 可快速定位问题）",
                },
            },
        },
    },
    {
        "name": "get_tool_info",
        "category": "System",
        "description": "获取系统工具的详细参数定义。**仅在需要了解不熟悉工具的详细用法时调用**。对于常用工具（run_shell、read_file、write_file等），直接调用即可，无需先查看参数。不要在简单问答场景调用此工具。",
        "detail": """获取系统工具的详细参数定义（Level 2 披露）。

**适用场景**：
- 了解不熟悉的工具用法（如 schedule_task、browser_automation 等）
- 查看复杂工具的参数说明

**不适用场景**：
- 简单问答、闲聊（直接文字回复）
- 使用常用工具（run_shell、read_file、write_file、list_directory、ask_user）
- 已知工具用法的情况

**注意**：高频工具的完整 schema 已直接提供给 LLM，无需调用此工具查看。""",
        "input_schema": {
            "type": "object",
            "properties": {"tool_name": {"type": "string", "description": "工具名称"}},
            "required": ["tool_name"],
        },
    },
    {
        "name": "generate_image",
        "category": "System",
        "description": "Generate an image from a text prompt using the configured image model API, saving to a local .png file. Use when user asks for image generation, posters, illustrations, or visual concepts that must be rendered as an actual image file.",
        "detail": """文生图：根据提示词生成图片并保存为本地 PNG 文件。

说明：
- 默认使用通义 Qwen-Image（如 `qwen-image-max`）。
- 需要在环境变量中配置 `DASHSCOPE_API_KEY`（与通义其它模型共用同一个 Key）。
- 生成结果会返回一个临时 URL（通常 24 小时有效），本工具会自动下载并落盘到本地文件。

输出：
- 返回 JSON 字符串，包含 `saved_to`（本地路径）与 `image_url`（临时链接）。

交付：
- 如需把图片发到 IM，请再调用 `deliver_artifacts`，并以回执作为交付证据。""",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "正向提示词（期望生成的内容）"},
                "model": {
                    "type": "string",
                    "description": "模型名称（默认 qwen-image-max）",
                    "default": "qwen-image-max",
                },
                "negative_prompt": {"type": "string", "description": "反向提示词（可选）"},
                "size": {
                    "type": "string",
                    "description": "输出分辨率，格式 宽*高（如 1664*928）",
                    "default": "1664*928",
                },
                "prompt_extend": {
                    "type": "boolean",
                    "description": "是否启用提示词智能改写（默认 true）",
                    "default": True,
                },
                "watermark": {
                    "type": "boolean",
                    "description": "是否添加水印（默认 false）",
                    "default": False,
                },
                "seed": {
                    "type": "integer",
                    "description": "随机种子（0~2147483647，可选）",
                },
                "output_path": {
                    "type": "string",
                    "description": "保存路径（可选）。不填则保存到 data/generated_images/ 下自动命名",
                },
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "set_task_timeout",
        "category": "System",
        "description": "调整当前任务超时策略。当预期任务耗时较长，或系统切换模型过于激进时使用。建议对进展稳定的长时间运行任务增加超时时间；减少超时时间以更快捕获卡死。",
        "detail": """动态调整当前任务的超时策略（主要用于避免“卡死检测”误触发）。\n\n- 本项目的超时重点是：**检测无进展卡死**，而不是限制长任务。\n- 你可以在长任务开始前，或发现任务被频繁触发超时警告时，调高超时秒数。\n\n注意：该设置只影响当前会话正在执行的任务，不影响全局配置。""",
        "input_schema": {
            "type": "object",
            "properties": {
                "progress_timeout_seconds": {
                    "type": "integer",
                    "description": "无进展超时阈值（秒）。连续超过该时间没有任何进展则触发超时处理。建议 600~3600。",
                },
                "hard_timeout_seconds": {
                    "type": "integer",
                    "description": "硬超时上限（秒，0=禁用）。仅最终兜底。",
                    "default": 0,
                },
                "reason": {"type": "string", "description": "简要说明调整原因"},
            },
            "required": ["progress_timeout_seconds", "reason"],
        },
    },
]
