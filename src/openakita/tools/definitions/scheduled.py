"""
Scheduled Tasks 工具定义

包含定时任务管理相关的工具：
- schedule_task: 创建定时任务
- list_scheduled_tasks: 列出所有任务
- cancel_scheduled_task: 取消任务
- update_scheduled_task: 更新任务
- trigger_scheduled_task: 立即触发任务
"""

SCHEDULED_TOOLS = [
    {
        "name": "schedule_task",
        "category": "Scheduled",
        "description": "创建定时任务或提醒。重要提示：必须实际调用此工具来创建任务 - 仅仅说“好的我会提醒你”并不会创建任务！任务类型：(1) reminder - 在预定时间发送消息（默认，90%的情况），(2) task - AI 执行操作。通知通道：默认情况下，提醒/结果会自动发送回用户当前聊天的 IM 通道（例如，如果用户通过微信发送消息，提醒将被推送到微信）。不需要 Webhook URL 或额外配置！仅当用户明确要求推送到不同的通道时才设置 target_channel。",
        "detail": """创建定时任务或提醒。

⚠️ **重要: 必须调用此工具才能创建任务！只是说"好的我会提醒你"不会创建任务！**

📢 **推送通道规则（非常重要）**：
- **默认行为**: 提醒/结果会自动推送到用户 **当前正在聊天的 IM 通道**（例如用户在企业微信中发消息，提醒就自动推到企业微信）
- **你不需要问用户要 Webhook URL 或任何通道配置信息！通道已由系统自动配置好！**
- 只有当用户明确要求推送到 **另一个不同的通道** 时，才需要设置 target_channel
- 绝大多数情况下，直接创建任务即可，不需要设置 target_channel

**任务类型判断规则**：
✅ **reminder**（默认优先）: 所有只需要发送消息的提醒
   - "提醒我喝水" → reminder
   - "站立提醒" → reminder
   - "叫我起床" → reminder

❌ **task**（仅当需要 AI 执行操作时）:
   - "查询天气告诉我" → task（需要查询）
   - "截图发给我" → task（需要操作）

**90%的提醒都应该是 reminder 类型！**

**触发类型**：
- once: 一次性执行
- interval: 间隔执行
- cron: cron 表达式

**推送通道（target_channel）- 通常不需要设置！**：
- ⚠️ **默认不传此参数！** 系统会自动推送到用户当前的 IM 通道
- 仅当用户明确要求推送到 **另一个** 通道时才设置（如用户在 Telegram 中说"推送到企业微信"）
- 可用通道名: wework（企业微信）、telegram、dingtalk（钉钉）、feishu（飞书）、slack 等
- ⚠️ **绝对不要问用户要 Webhook URL！** 通道已在系统中配置好，直接用通道名即可""",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "任务/提醒名称"},
                "description": {"type": "string", "description": "任务描述"},
                "task_type": {
                    "type": "string",
                    "enum": ["reminder", "task"],
                    "default": "reminder",
                    "description": "默认使用 reminder！reminder=发消息提醒，task=AI 执行操作",
                },
                "trigger_type": {
                    "type": "string",
                    "enum": ["once", "interval", "cron"],
                    "description": "触发类型",
                },
                "trigger_config": {
                    "type": "object",
                    "description": "触发配置。once: {run_at: '2026-02-01 10:00'}；interval: {interval_minutes: 30}；cron: {cron: '0 9 * * *'}",
                },
                "reminder_message": {
                    "type": "string",
                    "description": "提醒消息内容（仅 reminder 类型需要）",
                },
                "prompt": {
                    "type": "string",
                    "description": "执行时发送给 Agent 的提示（仅 task 类型需要）",
                },
                "target_channel": {
                    "type": "string",
                    "description": "指定推送到哪个已配置的 IM 通道（如 wework/telegram/dingtalk/feishu/slack）。不传则自动使用当前会话通道。⚠️ 不需要 Webhook URL，通道已在系统中配置好！",
                },
                "notify_on_start": {
                    "type": "boolean",
                    "default": True,
                    "description": "任务开始时发通知？默认 true",
                },
                "notify_on_complete": {
                    "type": "boolean",
                    "default": True,
                    "description": "任务完成时发通知？默认 true",
                },
            },
            "required": ["name", "description", "task_type", "trigger_type", "trigger_config"],
        },
    },
    {
        "name": "list_scheduled_tasks",
        "category": "Scheduled",
        "description": "列出所有定时任务及其 ID、名称、类型、状态和下次执行时间。当你需要：(1) 检查现有任务，(2) 查找任务 ID 以取消/更新，(3) 验证任务创建。",
        "detail": """列出所有定时任务。

**返回信息**：
- 任务 ID
- 名称
- 类型（reminder/task）
- 状态（enabled/disabled）
- 下次执行时间

**适用场景**：
- 查看已创建的任务
- 获取任务 ID 用于取消/更新
- 验证任务是否创建成功""",
        "input_schema": {
            "type": "object",
            "properties": {
                "enabled_only": {
                    "type": "boolean",
                    "description": "是否只列出启用的任务",
                    "default": False,
                }
            },
        },
    },
    {
        "name": "cancel_scheduled_task",
        "category": "Scheduled",
        "description": "永久删除定时任务。当用户说“取消/删除任务”时 → 使用此工具。当用户说“关闭通知”时 → 使用 update_scheduled_task 并设置 notify=false。当用户说“暂停任务”时 → 使用 update_scheduled_task 并设置 enabled=false。",
        "detail": """【永久删除】定时任务。

⚠️ **操作区分**：
- 用户说"取消/删除任务" → 用此工具
- 用户说"关闭提醒" → 用 update_scheduled_task 设 notify=false
- 用户说"暂停任务" → 用 update_scheduled_task 设 enabled=false

**注意**：删除后无法恢复！""",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "string", "description": "任务 ID"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "update_scheduled_task",
        "category": "Scheduled",
        "description": "修改定时任务设置而不删除。可修改：notify_on_start, notify_on_complete, enabled, target_channel。常见用途：(1) “关闭通知” → notify=false, (2) “暂停任务” → enabled=false, (3) “恢复任务” → enabled=true, (4) “推送到企业微信” → target_channel='wework'。不需要 Webhook URL！",
        "detail": """修改定时任务设置【不删除任务】。

**可修改项**：
- notify_on_start: 开始时是否通知
- notify_on_complete: 完成时是否通知
- enabled: 是否启用
- target_channel: 修改推送通道（如 wework/telegram/dingtalk/feishu/slack）

**常见用法**：
- "关闭提醒" → notify_on_start=false, notify_on_complete=false
- "暂停任务" → enabled=false
- "恢复任务" → enabled=true
- "改推送到企业微信" → target_channel="wework"
- ⚠️ 不需要 Webhook URL，通道已在系统中配置好！""",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "要修改的任务 ID"},
                "notify_on_start": {"type": "boolean", "description": "开始时发通知？不传=不修改"},
                "notify_on_complete": {
                    "type": "boolean",
                    "description": "完成时发通知？不传=不修改",
                },
                "enabled": {"type": "boolean", "description": "启用/暂停任务？不传=不修改"},
                "target_channel": {
                    "type": "string",
                    "description": "修改推送通道（如 wework/telegram/dingtalk/feishu/slack）。不传=不修改。⚠️ 不需要 Webhook URL！",
                },
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "trigger_scheduled_task",
        "category": "Scheduled",
        "description": "立即触发定时任务，无需等待预定时间。当你需要：(1) 测试任务执行，(2) 提前运行任务。",
        "detail": """立即触发定时任务（不等待计划时间）。

**适用场景**：
- 测试任务执行
- 提前运行任务

**注意**：
不会影响原有的执行计划""",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "string", "description": "任务 ID"}},
            "required": ["task_id"],
        },
    },
]
