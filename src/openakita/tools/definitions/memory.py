"""
Memory 工具定义

包含记忆系统相关的工具：
- add_memory: 记录重要信息
- search_memory: 搜索相关记忆
- get_memory_stats: 获取记忆统计
"""

MEMORY_TOOLS = [
    {
        "name": "add_memory",
        "category": "Memory",
        "description": "将重要信息记录到长期记忆中，以学习用户偏好、成功模式和错误教训。当你需要：(1) 记住用户偏好，(2) 保存成功模式，(3) 记录错误教训。注意：对于结构化的用户个人资料字段（姓名、工作领域、操作系统等），请改用 update_user_profile。使用 add_memory 记录不适合个人资料字段的自由格式、非结构化信息。",
        "detail": """记录重要信息到长期记忆。

**适用场景**：
- 学习用户偏好
- 保存成功模式
- 记录错误教训

**记忆类型**：
- fact: 事实信息
- preference: 用户偏好
- skill: 技能知识
- error: 错误教训
- rule: 规则约定

**重要性**：0-1 的数值，越高越重要""",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "要记住的内容"},
                "type": {
                    "type": "string",
                    "enum": ["fact", "preference", "skill", "error", "rule"],
                    "description": "记忆类型",
                },
                "importance": {"type": "number", "description": "重要性（0-1）", "default": 0.5},
            },
            "required": ["content", "type"],
        },
    },
    {
        "name": "search_memory",
        "category": "Memory",
        "description": "通过关键词和可选的类型过滤器搜索相关记忆。当你需要：(1) 回忆过去的信息，(2) 查找用户偏好，(3) 检查已学习的模式。",
        "detail": """搜索相关记忆。

**适用场景**：
- 回忆过去的信息
- 查找用户偏好
- 检查已学习的模式

**搜索方式**：
- 关键词匹配
- 可按类型过滤""",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "type": {
                    "type": "string",
                    "enum": ["fact", "preference", "skill", "error", "rule"],
                    "description": "记忆类型过滤（可选）",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_memory_stats",
        "category": "Memory",
        "description": "获取记忆系统统计信息，包括总数和按类型的细分。当你需要：(1) 检查记忆使用情况，(2) 了解记忆分布。",
        "detail": """获取记忆系统统计信息。

**返回信息**：
- 总记忆数量
- 按类型分布
- 按重要性分布""",
        "input_schema": {"type": "object", "properties": {}},
    },
]
