"""
提示词组装器

从 agent.py 提取的系统提示词构建逻辑，负责:
- 构建完整系统提示词（含身份、技能清单、MCP、记忆、工具列表）
- 编译管线 v2 (低 token 版本)
- 工具列表文本生成
- 系统环境信息注入
- Prompt 编译（两段式 Prompt 第一阶段）
"""

import asyncio
import logging
import os
import platform
import re
from typing import Any

from ..config import settings

logger = logging.getLogger(__name__)

# Prompt Compiler 系统提示词（两段式 Prompt 第一阶段）
PROMPT_COMPILER_SYSTEM = """【角色】
你是 Prompt Compiler，不是解题模型。

【输入】
用户的原始请求。

【目标】
将请求转化为一个结构化、明确、可执行的任务定义。

【输出结构】
请用以下 YAML 格式输出：

```yaml
task_type: [任务类型: question/action/creation/analysis/reminder/other]
goal: [一句话描述任务目标]
inputs:
  given: [已提供的信息列表]
  missing: [缺失但可能需要的信息列表，如果没有则为空]
constraints: [约束条件列表，如果没有则为空]
output_requirements: [输出要求列表]
risks_or_ambiguities: [风险或歧义点列表，如果没有则为空]
```

【规则】
- 不要解决任务
- 不要给建议
- 不要输出最终答案
- 不要假设执行能力的限制（如"AI无法操作浏览器"等）
- 只输出 YAML 格式的结构化任务定义
- 保持简洁，每项不超过一句话

【示例】
用户: "帮我写一个Python脚本，读取CSV文件并统计每列的平均值"

输出:
```yaml
task_type: creation
goal: 创建一个读取CSV文件并计算各列平均值的Python脚本
inputs:
  given:
    - 需要处理的文件格式是CSV
    - 需要统计的是平均值
    - 使用Python语言
  missing:
    - CSV文件的路径或示例
    - 是否需要处理非数值列
output_requirements:
  - 可执行的Python脚本
  - 能够读取CSV文件
  - 输出每列的平均值
constraints: []
risks_or_ambiguities:
  - 未指定如何处理包含非数值数据的列
  - 未指定输出格式（打印到控制台还是保存到文件）
```"""


class PromptAssembler:
    """
    系统提示词组装器。

    集成身份信息、技能清单、MCP 清单、记忆上下文、
    工具列表和环境信息来构建完整的系统提示词。
    """

    def __init__(
        self,
        tool_catalog: Any,
        skill_catalog: Any,
        mcp_catalog: Any,
        memory_manager: Any,
        brain: Any,
    ) -> None:
        self._tool_catalog = tool_catalog
        self._skill_catalog = skill_catalog
        self._mcp_catalog = mcp_catalog
        self._memory_manager = memory_manager
        self._brain = brain

        self._mcp_catalog_text: str = ""

    @property
    def mcp_catalog_text(self) -> str:
        return self._mcp_catalog_text

    @mcp_catalog_text.setter
    def mcp_catalog_text(self, value: str) -> None:
        self._mcp_catalog_text = value

    def build_system_prompt(
        self,
        base_prompt: str,
        tools: list[dict],
        *,
        task_description: str = "",
        use_compiled: bool = False,
        session_type: str = "cli",
        skill_catalog_text: str = "",
    ) -> str:
        """
        构建完整的系统提示词。

        Args:
            base_prompt: 基础提示词（身份信息）
            tools: 当前工具列表
            task_description: 任务描述（用于记忆检索）
            use_compiled: 是否使用编译管线 v2
            session_type: 会话类型 "cli" 或 "im"
            skill_catalog_text: 技能清单文本

        Returns:
            完整的系统提示词
        """
        if use_compiled:
            return self._build_compiled_sync(task_description, session_type=session_type)

        # 技能清单
        skill_catalog = skill_catalog_text or self._skill_catalog.generate_catalog()

        # MCP 清单
        mcp_catalog = self._mcp_catalog_text

        # 相关记忆
        memory_context = self._memory_manager.get_injection_context(task_description)

        # 工具列表
        tools_text = self._generate_tools_text(tools)

        # 系统环境信息
        system_info = self._build_system_info()

        # 工具使用指南
        tools_guide = self._build_tools_guide()

        # 核心原则
        core_principles = self._build_core_principles()

        return f"""{base_prompt}

{system_info}
{skill_catalog}
{mcp_catalog}
{memory_context}

{tools_text}

{tools_guide}

{core_principles}"""

    async def build_system_prompt_compiled(
        self,
        task_description: str = "",
        session_type: str = "cli",
    ) -> str:
        """
        使用编译管线构建系统提示词 (v2) - 异步版本。

        Token 消耗降低约 55%。

        Args:
            task_description: 任务描述
            session_type: 会话类型

        Returns:
            编译后的系统提示词
        """
        from ..prompt.builder import build_system_prompt
        from ..prompt.compiler import check_compiled_outdated, compile_all
        from ..prompt.retriever import retrieve_memory

        identity_dir = settings.identity_path

        if check_compiled_outdated(identity_dir):
            logger.info("Compiled identity files outdated, recompiling...")
            compile_all(identity_dir)

        precomputed_memory = ""
        if self._memory_manager and task_description:
            try:
                precomputed_memory = await asyncio.to_thread(
                    retrieve_memory,
                    query=task_description,
                    memory_manager=self._memory_manager,
                    max_tokens=400,
                )
            except Exception as e:
                logger.warning(f"Async memory retrieval failed: {e}")

        return build_system_prompt(
            identity_dir=identity_dir,
            tools_enabled=True,
            tool_catalog=self._tool_catalog,
            skill_catalog=self._skill_catalog,
            mcp_catalog=self._mcp_catalog,
            memory_manager=self._memory_manager,
            task_description=task_description,
            include_tools_guide=True,
            session_type=session_type,
            precomputed_memory=precomputed_memory,
        )

    def _build_compiled_sync(self, task_description: str = "", session_type: str = "cli") -> str:
        """同步版本：启动时构建初始系统提示词"""
        from ..prompt.builder import build_system_prompt
        from ..prompt.compiler import check_compiled_outdated, compile_all

        identity_dir = settings.identity_path

        if check_compiled_outdated(identity_dir):
            logger.info("Compiled identity files outdated, recompiling...")
            compile_all(identity_dir)

        return build_system_prompt(
            identity_dir=identity_dir,
            tools_enabled=True,
            tool_catalog=self._tool_catalog,
            skill_catalog=self._skill_catalog,
            mcp_catalog=self._mcp_catalog,
            memory_manager=self._memory_manager,
            task_description=task_description,
            include_tools_guide=True,
            session_type=session_type,
        )

    def _generate_tools_text(self, tools: list[dict]) -> str:
        """
        生成精简版工具列表 (Token Diet) - 动态归类版

        策略：
        1. High-Freq (Shell/File): 优先展示完整描述
        2. Low-Freq (All Others): 按 category 动态分组，仅列出名称
        """
        # 1. 核心高频工具 (Always visible with description)
        core_names = {"run_shell", "write_file", "read_file", "list_directory", "ask_user"}
        tool_map = {t["name"]: t for t in tools}
        
        lines = ["## Tools"]

        # A. Core Tools (详细)
        lines.append("### Core (Files & Shell)")
        for name in ["run_shell", "read_file", "write_file", "list_directory", "ask_user"]:
            if name in tool_map:
                desc = tool_map[name].get("description", "")
                lines.append(f"- **{name}**: {desc}")

        # B. Capabilities (动态分组，紧凑)
        lines.append("\n### Capabilities (Use `get_tool_info` for details)")
        
        # 收集非核心工具并按 category 分组
        categories = {}
        for tool in tools:
            name = tool["name"]
            if name in core_names or name.startswith("_"):
                continue
                
            # 获取分类，默认为 "Other"
            cat = tool.get("category", "Other")
            # 规范化分类名称（例如 "Skills Management" -> "Skills"）
            if "skill" in cat.lower(): cat = "Skills"
            elif "browser" in cat.lower(): cat = "Browser"
            elif "memory" in cat.lower(): cat = "Memory"
            elif "file" in cat.lower(): cat = "FileSystem" # 虽然核心文件工具已列出，防止有漏网之鱼
            elif "mcp" in cat.lower(): cat = "MCP"
            
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(name)
            
        # 按分类名称排序输出
        for cat in sorted(categories.keys()):
            names = sorted(categories[cat])
            if names:
                lines.append(f"- **{cat}**: {', '.join(names)}")

        return "\n".join(lines)

    @staticmethod
    def _build_system_info() -> str:
        """构建精简版环境信息"""
        return f"""## Runtime Context
- OS: {platform.system()} {platform.release()}
- CWD: {os.getcwd()}
- Note: Runtime state (browser, memory) resets on restart."""

    @staticmethod
    def _build_tools_guide() -> str:
        """构建极简工具指南"""
        return """## Tool Usage
1. **Core Tools**: Ready to use.
2. **Unknown Tools**: Call `get_tool_info(tool_name)` first.
3. **Skills**: Found in `skills/`. Use `run_skill_script` for external skills.
4. **Missing Capability?**: Use `skill-creator` to make one."""

    @staticmethod
    def _build_core_principles() -> str:
        """构建核心原则"""
        return """## 核心原则 (最高优先级!!!)

### 第一铁律：任务型请求必须使用工具

**⚠️ 先判断请求类型，再决定是否调用工具！**

| 请求类型 | 示例 | 处理方式 |
|---------|------|----------|
| **任务型** | "打开百度"、"提醒我开会"、"查天气" | ✅ **必须调用工具** |
| **对话型** | "你好"、"什么是机器学习"、"谢谢" | ✅ 可直接回复 |

### 第二铁律：没有工具就创造工具

**绝不说"我没有这个能力"！立即行动：**
- 临时脚本 → write_file + run_shell
- 搜索安装 → search_github → install_skill
- 创建技能 → skill-creator → load_skill

### 第三铁律：问题自己解决

报错了？自己读日志、分析、修复。缺信息？自己用工具查找。

### 第四铁律：永不放弃

第一次失败？换个方法再试。工具不够用？创建新工具。

**禁止说"我做不到"、"这超出了我的能力"！**

---

## 重要提示

### 诚实原则 (极其重要!!!)
**绝对禁止编造不存在的功能或进度！**
用户信任比看起来厉害更重要！

### 记忆管理
**主动使用记忆功能**，学到新东西记录为 FACT，发现偏好记录为 PREFERENCE。

### 记忆使用原则
**上下文优先**：当前对话内容永远优先于记忆中的信息。不要让记忆主导对话。
"""

    # ==================== Prompt 编译方法 ====================

    async def compile_prompt(self, user_message: str) -> tuple[str, str]:
        """
        两段式 Prompt 第一阶段：Prompt Compiler

        将用户的原始请求转化为结构化的任务定义。
        使用独立上下文，不进入核心对话历史。

        Args:
            user_message: 用户原始消息

        Returns:
            (compiled_prompt, raw_compiler_output)
            - compiled_prompt: 编译后的提示词（默认保持用户原始消息）
            - raw_compiler_output: Prompt Compiler 的原始输出（用于日志）
        """
        from .response_handler import strip_thinking_tags

        try:
            # 调用 Brain 的 Compiler 专用方法
            response = await self._brain.compiler_think(
                prompt=user_message,
                system=PROMPT_COMPILER_SYSTEM,
            )

            # 移除 thinking 标签
            compiler_output = (
                strip_thinking_tags(response.content).strip() if response.content else ""
            )
            logger.info(f"Prompt compiled: {compiler_output}")

            return user_message, compiler_output

        except Exception as e:
            logger.warning(f"Prompt compilation failed: {e}, using original message")
            return user_message, ""

    def summarize_compiler_output(self, compiler_output: str, max_chars: int = 600) -> str:
        """
        将 Prompt Compiler 的 YAML 输出压缩为短摘要

        用于 system/developer 注入与 memory query。

        Args:
            compiler_output: Compiler 的 YAML 输出
            max_chars: 最大字符数

        Returns:
            压缩后的摘要
        """
        if not compiler_output:
            return ""

        # 提取关键字段
        goal_match = re.search(r"goal:\s*(.+)", compiler_output)
        type_match = re.search(r"task_type:\s*(\w+)", compiler_output)

        goal = goal_match.group(1).strip() if goal_match else ""
        task_type = type_match.group(1) if type_match else "unknown"

        # 提取 missing 信息
        missing = []
        in_missing = False
        for line in compiler_output.split("\n"):
            if "missing:" in line:
                in_missing = True
                continue
            if in_missing:
                if line.strip().startswith("- "):
                    missing.append(line.strip()[2:])
                elif not line.startswith(" ") and line.strip():
                    break

        # 构建摘要
        parts = [f"[{task_type}] {goal}"]
        if missing:
            parts.append(f"待确认: {', '.join(missing[:3])}")

        summary = " | ".join(parts)
        if len(summary) > max_chars:
            summary = summary[:max_chars] + "…"

        return summary

    def should_compile_prompt(self, message: str) -> bool:
        """
        判断是否需要编译 Prompt

        Args:
            message: 用户消息

        Returns:
            是否需要编译
        """
        # 简单消息不需要编译
        simple_patterns = [
            r"^(hi|hello|hey|你好|嗨|您好)[\s!.]*$",
            r"^(谢谢|感谢|thanks|thank you)[\s!.]*$",
            r"^(ok|好的|收到|明白|清楚)[\s!.]*$",
            r"^(bye|再见|拜拜)[\s!.]*$",
        ]

        msg_lower = message.strip().lower()
        for pattern in simple_patterns:
            if re.match(pattern, msg_lower, re.IGNORECASE):
                return False

        # 非常短的消息不需要编译
        if len(message.strip()) < 10:
            return False

        return True

    def get_last_user_request(self, messages: list[dict]) -> str:
        """
        从消息列表中提取最后一个用户请求

        Args:
            messages: 消息列表

        Returns:
            最后一个用户请求
        """
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content
                elif isinstance(content, list):
                    # 多模态消息
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            return part.get("text", "")
        return ""
