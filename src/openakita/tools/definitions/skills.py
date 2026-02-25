"""
Skills 工具定义

包含技能管理相关的工具（遵循 Agent Skills 规范）：
- list_skills: 列出已安装的技能
- get_skill_info: 获取技能详细信息
- run_skill_script: 运行技能脚本
- get_skill_reference: 获取技能参考文档
- install_skill: 安装新技能
- load_skill: 加载新创建的技能
- reload_skill: 重新加载已修改的技能

说明：技能创建/封装等工作流建议使用专门的技能（外部技能）完成。
"""

SKILLS_TOOLS = [
    {
        "name": "list_skills",
        "category": "Skills",
        "description": "列出所有已安装的技能。主要用于：(1) 回答用户关于“有哪些技能”的询问，(2) 验证新安装的技能是否生效。注意：系统提示中已包含可用技能列表，Agent 在执行任务时通常不需要调用此工具，除非需要向用户展示。",
        "detail": """列出已安装的技能（遵循 Agent Skills 规范）。

**返回信息**：
- 技能名称
- 技能描述
- 是否可自动调用

**适用场景**：
- 回答用户询问（如“你会什么技能？”）
- 验证技能安装状态
- 调试技能加载问题""",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_skill_info",
        "category": "Skills",
        "description": "获取技能的详细说明和使用指南（Level 2 披露）。当你需要：(1) 了解如何使用技能，(2) 检查技能能力，(3) 学习技能参数。注意：这是用于 SKILL 说明（pdf、docx、code-review 等）。对于系统 TOOL 参数模式（run_shell、browser_navigate 等），请改用 get_tool_info。",
        "detail": """获取技能的详细信息和指令（Level 2 披露）。

**返回信息**：
- 完整的 SKILL.md 内容
- 使用说明
- 可用脚本列表
- 参考文档列表

**适用场景**：
- 了解技能的使用方法
- 查看技能的完整能力
- 学习技能参数""",
        "input_schema": {
            "type": "object",
            "properties": {"skill_name": {"type": "string", "description": "技能名称"}},
            "required": ["skill_name"],
        },
    },
    {
        "name": "run_skill_script",
        "category": "Skills",
        "description": "执行技能的脚本文件并传递参数。当你需要：(1) 运行技能功能，(2) 执行特定操作，(3) 使用技能处理数据。",
        "detail": """运行技能的脚本。

**适用场景**：
- 执行技能功能
- 运行特定操作
- 用技能处理数据

**使用方法**：
1. 先用 get_skill_info 了解可用脚本
2. 指定脚本名称和参数执行""",
        "input_schema": {
            "type": "object",
            "properties": {
                "skill_name": {"type": "string", "description": "技能名称"},
                "script_name": {"type": "string", "description": "脚本文件名（如 get_time.py）"},
                "args": {"type": "array", "items": {"type": "string"}, "description": "命令行参数"},
            },
            "required": ["skill_name", "script_name"],
        },
    },
    {
        "name": "get_skill_reference",
        "category": "Skills",
        "description": "获取技能参考文档以获得额外指导。当你需要：(1) 获取详细技术文档，(2) 查找示例，(3) 了解高级用法。",
        "detail": """获取技能的参考文档。

**适用场景**：
- 获取详细技术文档
- 查找使用示例
- 了解高级用法

**默认文档**：REFERENCE.md""",
        "input_schema": {
            "type": "object",
            "properties": {
                "skill_name": {"type": "string", "description": "技能名称"},
                "ref_name": {
                    "type": "string",
                    "description": "参考文档名称（默认 REFERENCE.md）",
                    "default": "REFERENCE.md",
                },
            },
            "required": ["skill_name"],
        },
    },
    {
        "name": "install_skill",
        "category": "Skills",
        "description": "从 URL 或 Git 仓库安装技能到本地 skills/ 目录。当你需要：(1) 从 GitHub 添加新技能，(2) 从 URL 安装 SKILL.md。支持 Git 仓库和单个 SKILL.md 文件。",
        "detail": """从 URL 或 Git 仓库安装技能到本地 skills/ 目录。

**支持的安装源**：
1. Git 仓库 URL（如 https://github.com/user/repo）
   - 自动克隆仓库并查找 SKILL.md
   - 支持指定子目录路径
2. 单个 SKILL.md 文件 URL
   - 创建规范目录结构（scripts/, references/, assets/）

**安装后**：
技能会自动加载到 skills/<skill-name>/ 目录""",
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Git 仓库 URL 或 SKILL.md 文件 URL"},
                "name": {"type": "string", "description": "技能名称（可选，自动从 SKILL.md 提取）"},
                "subdir": {
                    "type": "string",
                    "description": "Git 仓库中技能所在的子目录路径（可选）",
                },
                "extra_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "额外需要下载的文件 URL 列表",
                },
            },
            "required": ["source"],
        },
    },
    {
        "name": "load_skill",
        "category": "Skills",
        "description": "Load a newly created skill from skills/ directory. Use after creating a skill with skill-creator to make it immediately available.",
        "detail": """加载新创建的技能到系统中。

**适用场景**：
- 使用 skill-creator 创建技能后
- 手动在 skills/ 目录创建技能后
- 需要立即使用新技能时

**使用流程**：
1. 使用 skill-creator 创建 SKILL.md
2. 保存到 skills/<skill-name>/SKILL.md
3. 调用 load_skill 加载
4. 技能立即可用

**注意**：技能目录必须包含有效的 SKILL.md 文件""",
        "input_schema": {
            "type": "object",
            "properties": {
                "skill_name": {"type": "string", "description": "技能名称（即 skills/ 下的目录名）"}
            },
            "required": ["skill_name"],
        },
    },
    {
        "name": "reload_skill",
        "category": "Skills",
        "description": "重新加载现有技能以应用更改。在修改技能的 SKILL.md 或脚本后使用。",
        "detail": """重新加载已存在的技能以应用修改。

**适用场景**：
- 修改了技能的 SKILL.md 后
- 更新了技能的脚本后
- 需要刷新技能配置时

**工作原理**：
1. 卸载原有技能
2. 重新解析 SKILL.md
3. 重新注册到系统

**注意**：只能重新加载已加载过的技能""",
        "input_schema": {
            "type": "object",
            "properties": {"skill_name": {"type": "string", "description": "技能名称"}},
            "required": ["skill_name"],
        },
    },
]
