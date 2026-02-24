# Core 模块重构计划：高内聚低耦合

## 项目概述

**目标**：重新整理 `src/openakita/core` 和各个组件模块的关联关系，进行文件级别的内聚，使得：
- `core` 下面只管理和组织流程相关
- 其他各个组件模块是高内聚的
- 整体架构达到高内聚低耦合

**策略**：直接更新所有引用，不保留兼容性导入层

---

## 当前问题分析

### 1. Core 模块现状（17个文件，约 14,000 行代码）

| 文件 | 行数 | 当前职责 | 目标位置 |
|------|------|----------|----------|
| `agent.py` | 5,164 | 主协调器 + 几乎所有功能 | **保留**（精简） |
| `reasoning_engine.py` | 3,028 | 推理-行动循环 | **保留** |
| `brain.py` | 1,369 | LLM 交互层 | **移到 llm/** |
| `task_monitor.py` | 752 | 任务监控 | **保留** |
| `tool_executor.py` | 553 | 工具执行 | **移到 tools/** |
| `identity.py` | 441 | 身份管理 | **保留** |
| `agent_state.py` | 488 | 状态管理 | **保留** |
| `memory.py` | 347 | 记忆系统(旧版) | **移到 memory/legacy.py** |
| `skill_manager.py` | 349 | 技能管理 | **移到 skills/** |
| `response_handler.py` | 349 | 响应处理 | **保留** |
| `ralph.py` | 363 | Ralph 循环 | **保留** |
| `prompt_assembler.py` | 341 | 提示词组装 | **保留** |
| `token_tracking.py` | 157 | Token 追踪 | **移到 infra/** |
| `tool_filter.py` | 211 | 工具过滤 | **移到 tools/** |
| `errors.py` | 20 | 错误定义 | **保留** |
| `im_context.py` | 41 | IM 上下文 | **保留** |

### 2. 目标架构

```
src/openakita/
├── core/                    # 流程编排层 (保留 10 个文件)
│   ├── __init__.py         # 导出 Agent, AgentState, TaskState 等
│   ├── agent.py            # 精简后的主协调器
│   ├── agent_state.py      # 状态管理
│   ├── reasoning_engine.py # 推理-行动循环
│   ├── response_handler.py # 响应处理
│   ├── ralph.py            # Ralph 循环
│   ├── prompt_assembler.py # 提示词组装
│   ├── identity.py         # 身份管理
│   ├── task_monitor.py     # 任务监控
│   ├── im_context.py       # IM 上下文
│   └── errors.py           # 错误定义
│
├── llm/                     # LLM 层
│   ├── ... (现有文件)
│   └── brain.py            # ← 从 core 移入
│
├── tools/                   # 工具层
│   ├── ... (现有文件)
│   ├── executor.py         # ← 从 core/tool_executor.py 移入
│   └── filter.py           # ← 从 core/tool_filter.py 移入
│
├── skills/                  # 技能层
│   ├── ... (现有文件)
│   └── manager.py          # ← 从 core/skill_manager.py 移入
│
├── memory/                  # 记忆层
│   ├── ... (现有文件)
│   └── legacy.py           # ← 从 core/memory.py 移入 (标记为 deprecated)
│
└── infra/                   # 基础设施层 (新建)
    ├── __init__.py
    └── token_tracking.py   # ← 从 core 移入
```

---

## 执行阶段

### Phase 0: 准备工作（PREP-001 ~ PREP-003）
- 创建测试基线脚本
- 创建依赖图分析脚本
- 建立功能测试基线

### Phase 1: 基础设施层分离（INFRA-001 ~ INFRA-003）
- 创建 `infra` 模块
- 移动 `token_tracking.py`
- 更新所有引用
- 验证

### Phase 2: 工具层分离（TOOLS-001 ~ TOOLS-003）
- 移动 `tool_filter.py` → `tools/filter.py`
- 移动 `tool_executor.py` → `tools/executor.py`
- 更新所有引用
- 验证

### Phase 3: 技能层分离（SKILLS-001 ~ SKILLS-002）
- 移动 `skill_manager.py` → `skills/manager.py`
- 更新所有引用
- 验证

### Phase 4: LLM 层分离（LLM-001 ~ LLM-003）
- 移动 `brain.py` → `llm/brain.py`
- 更新所有引用（8个文件）
- 验证

### Phase 5: 记忆层分离（MEM-001 ~ MEM-002）
- 分析 `core/memory.py` 使用情况
- 移动到 `memory/legacy.py`
- 更新引用
- 验证

### Phase 6: Agent 精简（CORE-001 ~ CORE-003）
- 分析 agent.py 方法职责
- 提取辅助函数
- 更新 core/__init__.py

### Phase 7: 最终验证（VERIFY-001 ~ VERIFY-003）
- 运行完整导入测试
- 基线测试对比
- 运行现有测试套件

### Phase 8: 文档更新（DOC-001 ~ DOC-003）
- 更新模块文档字符串
- 生成最终依赖图
- 更新 CLAUDE.md（如适用）

### Phase 9: 最终验证（FINAL-001）
- 验证所有功能
- 确认架构达成目标

---

## 需要更新的文件清单

### token_tracking.py 迁移
- `src/openakita/evaluation/judge.py`
- `src/openakita/orchestration/handoff.py`
- `src/openakita/core/agent.py`
- `src/openakita/core/brain.py` → `llm/brain.py`
- `src/openakita/core/reasoning_engine.py`

### tool_filter.py 迁移
- `src/openakita/core/reasoning_engine.py`

### tool_executor.py 迁移
- `src/openakita/tools/handlers/skills.py`
- `src/openakita/core/agent.py`
- `src/openakita/core/reasoning_engine.py`

### skill_manager.py 迁移
- `src/openakita/core/agent.py`

### brain.py 迁移
- `src/openakita/evolution/generator.py`
- `src/openakita/evolution/self_check.py`
- `src/openakita/evolution/analyzer.py`
- `src/openakita/scheduler/executor.py` (3处)
- `src/openakita/channels/gateway.py`
- `src/openakita/core/agent.py`
- `src/openakita/core/__init__.py`

---

## 风险与缓解措施

### 风险 1: 循环依赖
**可能性**：中等
**缓解措施**：每个 Phase 后检查循环依赖，使用 TYPE_CHECKING 延迟导入

### 风险 2: 破坏现有功能
**可能性**：低
**缓解措施**：每步都有测试验证，分阶段执行

### 风险 3: 导入错误
**可能性**：低
**缓解措施**：完整扫描所有引用，逐一更新

---

## 成功标准

1. **core 文件数量减少**：从 17 个减少到约 10 个
2. **导入测试通过**：所有核心模块可以正常导入
3. **无循环依赖**：`import openakita` 无错误
4. **架构清晰**：core 只负责流程编排，其他功能在对应模块
5. **依赖方向正确**：core → llm, tools, skills, memory（调用关系）

---

*创建日期: 2026-02-24*
*状态: ready*
