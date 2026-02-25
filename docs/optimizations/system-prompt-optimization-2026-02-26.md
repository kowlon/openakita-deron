# System Prompt 优化方案 (2026-02-26)

## 背景

用户反馈 Agent 响应延迟过高，特别是在输入问题后，第一轮决策输出（TTFT, Time To First Token）长达 40s+。这通常是由于 System Prompt 过长，导致 LLM 的 Prefill（预处理）时间过长，尤其是在使用大量工具或长 Context 时。

## 核心问题分析

1. **Token 膨胀**：旧版 Prompt Assembler 将所有工具（无论频率高低）都以 `Name + Description` 的形式注入 System Prompt。随着工具数量增加，Prompt 长度线性增长。
2. **冗余信息**：包含大量关于操作系统、临时目录、重启状态丢失的长篇大论说明，以及针对工具使用的详细表格指南。这些对于现代 LLM 来说大多是噪音。
3. **工具定位模糊**：`list_skills` 等工具被设计为 Agent 任务规划的一环，导致 Agent 频繁调用以“自我确认”，增加不必要的 Round-Trip。

## 优化方案 (Token Diet)

本次优化主要针对 `src/openakita/core/prompt_assembler.py` 进行重构，实施 **Prompt 瘦身策略**。

### 1. 工具列表分层 (High/Low Frequency Separation)

我们将工具分为两类，采用不同的展示策略：

*   **High-Freq (Core Tools)**:
    *   **定义**：Agent 完成任务最核心、最高频使用的工具。
    *   **策略**：保留完整 `Name + Description`，确保模型随时可见，无需额外查找。
    *   **包含**：`run_shell`, `read_file`, `write_file`, `list_directory`, `ask_user`。

*   **Low-Freq (Capabilities)**:
    *   **定义**：除了 Core 以外的所有工具（如 Skills, Browser, Memory 等）。
    *   **策略**：仅列出工具名称，按 Category 分组展示，引导模型使用 `get_tool_info` 获取详情。
    *   **实现**：动态读取工具定义的 `category` 字段进行归类，**确保不遗漏任何新工具**。

**Old Format (Example):**
```markdown
## Available Tools
### File System
- **run_shell**: Execute shell commands...
- **read_file**: Read file content...
### Skills
- **git-wizard**: Git operations...
- **linear-mcp**: Linear integration...
... (50+ lines)
```

**New Format (Example):**
```markdown
## Tools
### Core (Files & Shell)
- **run_shell**: Execute shell commands...
- **read_file**: Read file content...
...

### Capabilities (Use `get_tool_info` for details)
- **Browser**: browser_open, browser_navigate, browser_click...
- **Skills**: git-wizard, linear-mcp, list_skills...
- **Memory**: add_memory, search_memory...
```

### 2. 环境信息压缩

将原来约 15 行的详细环境说明和警告，压缩为 3 行核心 Context。

**Old:**
```markdown
## 运行环境
- 操作系统: Darwin 21.6.0
- 当前工作目录: /Users/zd/agents/openakita-deron
- 临时目录: ...
## ⚠️ 重要：运行时状态不持久化
... (表格) ...
```

**New:**
```markdown
## Runtime Context
- OS: Darwin 21.6.0
- CWD: /Users/zd/agents/openakita-deron
- Note: Runtime state (browser, memory) resets on restart.
```

### 3. 指南极简重构

移除冗长的工具使用表格，替换为 4 条核心原则。

**New:**
```markdown
## Tool Usage
1. **Core Tools**: Ready to use.
2. **Unknown Tools**: Call `get_tool_info(tool_name)` first.
3. **Skills**: Found in `skills/`. Use `run_skill_script` for external skills.
4. **Missing Capability?**: Use `skill-creator` to make one.
```

### 4. 工具定位调整

针对 `list_skills` 工具的描述进行微调，明确其主要用途是 **回答用户查询**，而非 Agent 自我规划。

*   **修改文件**: `src/openakita/tools/definitions/skills.py`
*   **新描述**: "列出所有已安装的技能。主要用于：(1) 回答用户关于“有哪些技能”的询问... 注意：系统提示中已包含可用技能列表，Agent 在执行任务时通常不需要调用此工具..."

## 预期效果

1.  **Token 减少**：预计 System Prompt 长度减少 30%-50%（取决于安装的工具数量）。
2.  **延迟降低**：显著降低 Prefill 时间，提升首字响应速度 (TTFT)。
3.  **专注度提升**：减少噪音干扰，让模型更专注于当前任务和 Core Tools 的使用。
