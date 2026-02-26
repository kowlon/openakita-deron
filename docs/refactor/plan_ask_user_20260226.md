# Plan 模式处理逻辑分析

> 分析时间: 2026-02-26

## 1. 概述

Plan 模式是 OpenAkita 项目中用于处理复杂多步骤任务的核心机制。它强制 LLM 在执行多步骤任务前先制定计划，然后按步骤执行并跟踪进度。

## 2. 核心文件

| 文件 | 职责 |
|------|------|
| `src/openakita/tools/definitions/plan.py` | 工具定义 (create_plan, update_plan_step, get_plan_status, complete_plan) |
| `src/openakita/tools/handlers/plan.py` | 工具处理器实现、状态管理 |
| `src/openakita/core/agent.py` | Plan 模式集成、动态提示词注入、任务验证 |
| `src/openakita/core/reasoning_engine.py` | ReAct 循环中的 Plan 状态检查 |
| `src/openakita/prompt/builder.py` | Plan 模式使用规则 |

## 3. 数据流

```
用户请求 → should_require_plan() 检测
    ↓
标记 session 为 plan_required
    ↓
LLM 调用非 plan 工具 → 拦截返回错误提示
    ↓
LLM 调用 create_plan → 创建计划
    ↓
register_active_plan() 注册活跃计划
    ↓
循环执行: update_plan_step → 执行步骤 → update_plan_step
    ↓
LLM 调用 complete_plan → 完成计划
    ↓
unregister_active_plan() 清理状态
```

## 4. 状态管理

### 4.1 模块级状态字典

```python
# handlers/plan.py

# 记录哪些 session 被标记为需要 Plan
_session_plan_required: dict[str, bool] = {}

# 记录 session 的活跃 Plan (session_id -> plan_id)
_session_active_plans: dict[str, str] = {}

# 存储 session -> PlanHandler 实例的映射
_session_handlers: dict[str, "PlanHandler"] = {}
```

### 4.2 Plan 数据结构

```python
{
    "id": "plan_20260226_143052_a1b2c3",
    "task_summary": "任务描述",
    "steps": [
        {
            "id": "step_1",
            "description": "步骤描述",
            "tool": "browser_navigate",  # 可选
            "skills": ["browser-task"],   # 关联技能
            "status": "pending",          # pending/in_progress/completed/failed/skipped
            "result": "",
            "started_at": None,
            "completed_at": None,
            "depends_on": []             # 可选依赖
        }
    ],
    "status": "in_progress",             # in_progress/completed/cancelled
    "created_at": "2026-02-26T14:30:52",
    "completed_at": None,
    "logs": [],
    "summary": ""                         # 完成时填写
}
```

## 5. 触发机制

### 5.1 自动检测 (should_require_plan)

```python
# handlers/plan.py:202-268

def should_require_plan(user_message: str) -> bool:
    """
    触发条件:
    1. 包含 5+ 个动作词（明显的复杂任务）
    2. 包含 3+ 个动作词 + 连接词（明确的多步骤）
    3. 包含 3+ 个动作词 + 逗号分隔（明确的多步骤）
    """
    action_words = ["打开", "搜索", "截图", "发送", "写", "创建", ...]
    connector_words = ["然后", "接着", "之后", "并且", "再", "最后"]

    action_count = sum(1 for word in action_words if word in msg)
    has_connector = any(word in msg for word in connector_words)
    comma_separated = "，" in msg or "," in msg

    if action_count >= 5: return True
    if action_count >= 3 and has_connector: return True
    return action_count >= 3 and comma_separated
```

### 5.2 强制检查 (agent.py:2233-2251)

```python
# 执行工具前的拦截检查
if tool_name != "create_plan":
    if session_id and is_plan_required(session_id) and not has_active_plan(session_id):
        return "⚠️ **这是一个多步骤任务，必须先创建计划！**..."
```

## 6. 动态提示词注入

### 6.1 System Prompt 注入

```python
# agent.py:915-920, reasoning_engine.py:1053-1061

from ..tools.handlers.plan import get_active_plan_prompt

plan_section = get_active_plan_prompt(conversation_id)
if plan_section:
    effective_base_prompt += f"\n\n{plan_section}\n"
```

### 6.2 注入内容格式

```
## Active Plan: 任务描述  (id: plan_xxx)
Progress: 2/5 done

  [  ] 1. 打开百度
  [>>] 2. 输入关键词
  [OK] 3. 点击搜索 => 已成功
  [  ] 4. 截图保存
  [  ] 5. 发送给用户

IMPORTANT: This plan already exists. Do NOT call create_plan again.
Continue from the current step using update_plan_step.
```

## 7. 工具定义

### 7.1 create_plan

```json
{
    "name": "create_plan",
    "description": "多步骤任务必须首先调用！",
    "input_schema": {
        "type": "object",
        "properties": {
            "task_summary": {"type": "string", "description": "任务一句话总结"},
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "description": {"type": "string"},
                        "tool": {"type": "string"},
                        "skills": {"type": "array", "items": {"type": "string"}},
                        "depends_on": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["id", "description"]
                }
            }
        },
        "required": ["task_summary", "steps"]
    }
}
```

### 7.2 update_plan_step

更新步骤状态: `pending` → `in_progress` → `completed`/`failed`/`skipped`

### 7.3 get_plan_status

获取计划当前状态，返回 Markdown 表格。

### 7.4 complete_plan

标记计划完成，生成总结报告。

## 8. 任务验证集成

### 8.1 Plan 步骤检查 (agent.py:1772-1795)

```python
def _is_task_completed(...):
    # ...
    # === Plan 步骤检查：如果有活跃 Plan 且有未完成步骤，强制继续执行 ===
    if conversation_id and has_active_plan(conversation_id):
        handler = get_plan_handler_for_session(conversation_id)
        plan = handler.get_plan_for(conversation_id) if handler else None
        if plan:
            steps = plan.get("steps", [])
            pending = [s for s in steps if s.get("status") in ("pending", "in_progress")]
            if pending:
                return False  # 强制继续执行
```

### 8.2 LLM 自检增强 (reasoning_engine.py:3449-3456)

```python
if consecutive_rounds > 0 and consecutive_rounds % self_check_interval == 0:
    if has_plan:
        working_messages.append({
            "role": "user",
            "content": f"[系统提示] 已连续执行 {consecutive_rounds} 轮，Plan 仍有未完成步骤..."
        })
```

### 8.3 Verify 轮数调整 (reasoning_engine.py:3703-3711)

```python
def _get_effective_force_retries(...):
    retries = base_retries
    if has_active_plan(conversation_id) or is_plan_required(conversation_id):
        retries = max(retries, 1)  # 有活跃 Plan 时至少重试 1 次
    return max(0, int(retries))
```

## 9. 自动关闭机制

### 9.1 任务结束自动关闭

```python
# handlers/plan.py:78-132

def auto_close_plan(session_id: str) -> bool:
    """
    当一轮 ReAct 循环结束但 LLM 未显式调用 complete_plan 时自动关闭。

    - in_progress 步骤 → completed
    - pending 步骤 → skipped
    - Plan 状态设为 completed
    """
```

### 9.2 用户取消时关闭

```python
# handlers/plan.py:135-175

def cancel_plan(session_id: str) -> bool:
    """
    用户主动取消时将未完成步骤标记为 cancelled。
    """
```

## 10. 持久化

### 10.1 Markdown 文件保存

```python
# handlers/plan.py:660-706

def _save_plan_markdown(self, plan: dict | None = None):
    """保存到 data/plans/{plan_id}.md"""
```

### 10.2 文件格式

```markdown
# 任务计划：任务描述

**计划ID**: plan_xxx
**创建时间**: 2026-02-26T14:30:52
**状态**: completed
**完成时间**: 2026-02-26T14:35:00

## 步骤列表

| ID | 描述 | Skills | 工具 | 状态 | 结果 |
|----|------|--------|------|------|------|
| step_1 | 打开百度 | browser-task | browser_navigate | ✅ | 已打开 |

## 执行日志

- [14:30:52] 计划创建：...
- [14:31:00] ✅ step_1: 已打开百度

## 完成总结

任务完成总结...
```

## 11. 事件通知

### 11.1 进度事件

```python
# agent.py:2427-2449 - SSE 事件

# create_plan 事件
{"type": "plan_created", "plan": {...}}

# update_plan_step 事件
{"type": "plan_step_updated", "stepId": "step_1", "status": "completed"}

# complete_plan 事件
{"type": "plan_completed"}
```

### 11.2 Gateway 进度推送

```python
# handlers/plan.py:404-408, 487-490

await gateway.emit_progress_event(session, f"📋 已创建计划：{task_summary}")
await gateway.emit_progress_event(session, f"{status_emoji} **[{step_number}/{total_count}]** {step_desc}")
```

## 12. 关键设计决策

### 12.1 为什么用模块级字典而非数据库？

- **会话隔离**: Plan 生命周期与会话绑定，无需跨会话持久化
- **性能**: 避免数据库 I/O 开销
- **简单性**: 复杂多步骤任务通常在单一会话内完成

### 12.2 为什么动态注入到 System Prompt？

- **上下文保留**: 即使 working_messages 被压缩，Plan 状态也不会丢失
- **每次推理可见**: LLM 在每轮都能看到完整计划结构

### 12.3 为什么强制 Plan 创建？

- **防止遗漏**: 复杂任务容易遗漏步骤
- **可追溯性**: 计划保存为文件，便于调试和审计
- **用户体验**: 进度推送让用户了解执行状态

---

## 13. Chrome 插件测试结果 (2026-02-26)

### 13.1 测试环境

- **WebUI**: http://127.0.0.1:5173
- **API Server**: http://127.0.0.1:18900
- **测试用例**: 多步骤任务触发 Plan 模式

### 13.2 测试用例 1: "打开百度搜索今天的新闻然后截图保存到桌面"

**输入分析**:
- 动作词: 打开、搜索、截图、保存 (4个)
- 连接词: 然后 (1个)
- 逗号分隔: 无

**预期**: 触发 Plan 模式（4个动作词 >= 3 + 连接词）

**实际结果 (修复前)**:
```
✅ Plan 模式检测: 成功
   - 日志: [Plan] Session chat_78c448ec7ba4 plan_required=True
   - 日志: Multi-step task detected, Plan required

❌ LLM 行为: 未正确调用 create_plan
   - LLM 调用了 get_tool_info 查询 create_plan
   - LLM 调用了 run_shell 而非 create_plan
   - 导致无限循环，返回 "必须先创建计划" 提示

📊 性能数据:
   - TTFT: 22.39s
   - 总耗时: 429.89s (约7分钟)
   - 迭代次数: 29次
```

### 13.3 问题根因分析

**问题**: `should_require_plan()` 正确检测到需要 Plan，但 `get_tools_for_message()` 没有将 `create_plan` 工具添加到 LLM 的工具列表中。

**根本原因**: 两个检测函数使用不同的关键词检测逻辑：
- `handlers/plan.py:should_require_plan()` 使用动作词+连接词检测
- `tools/filter.py:get_tools_for_message()` 使用 `TASK_KEYWORDS["plan"]` 关键词检测

**证据**:
```python
# handlers/plan.py - should_require_plan()
PLAN_ACTION_WORDS = ["打开", "搜索", "截图", "发送", ...]
PLAN_CONNECTOR_WORDS = ["然后", "接着", "之后", ...]

# tools/filter.py - TASK_KEYWORDS (修复前)
"plan": ["计划", "规划", "步骤", "多步", "复杂", "plan", ...]
```

当用户说"打开百度搜索今天的新闻然后截图保存"时：
- `should_require_plan()` → True (检测到动作词+连接词)
- `TASK_KEYWORDS["plan"]` → False (没有"计划"、"规划"等关键词)
- 结果：`create_plan` 工具未被添加到工具列表

### 13.4 修复方案

**修改文件**: `src/openakita/tools/filter.py`

**修复内容**:

1. 添加 `PLAN_TOOLS` 常量和 `needs_plan()` 函数:
```python
# Plan 工具（多步骤任务必须）
PLAN_TOOLS = {
    "create_plan", "update_plan_step", "get_plan_status", "complete_plan"
}

# 多步骤任务关键词 - 用于检测是否需要 Plan
PLAN_ACTION_WORDS = [
    "打开", "搜索", "截图", "发", "发送", "写", "创建",
    "执行", "运行", "读取", "查看", "保存", "下载", "上传",
    ...
]
PLAN_CONNECTOR_WORDS = ["然后", "接着", "之后", "并且", "再", "最后"]

def needs_plan(message: str) -> bool:
    """检测消息是否需要 Plan 模式（与 should_require_plan() 相同逻辑）"""
    msg = message.lower()
    action_count = sum(1 for word in PLAN_ACTION_WORDS if word in msg)
    has_connector = any(word in msg for word in PLAN_CONNECTOR_WORDS)
    comma_separated = "，" in msg or "," in msg

    if action_count >= 5: return True
    if action_count >= 3 and has_connector: return True
    return bool(action_count >= 3 and comma_separated)
```

2. 在 `get_tools_for_message()` 中添加 Plan 工具检测:
```python
# ★ 关键修复：如果检测到多步骤任务，强制添加 Plan 工具
if needs_plan(message):
    needed_tools |= PLAN_TOOLS
    logger.info("[ToolFilter] Multi-step task detected, adding Plan tools")
```

3. 在 `agent.py:execute_task()` 中添加工具过滤:
```python
# === 工具按需加载：根据任务内容过滤工具 ===
from ..tools.filter import get_tools_for_message
filtered_tools = get_tools_for_message(self._tools, task.description, "desktop")
```

### 13.5 修复后测试结果

**测试用例**: "打开百度搜索新闻然后截图保存"

**日志输出**:
```
2026-02-26 21:48:56,841 - [Session:1772113652746-80n32wf] Multi-step task detected
2026-02-26 21:48:56,994 - [ToolFilter] Multi-step task detected, adding Plan tools
2026-02-26 21:48:56,995 - [ToolFilter] Detected types: ['web', 'file', 'code', 'memory', 'im'], needs_search=True, needs_plan=True, Tools: 44 → 18 (-59%)
2026-02-26 21:49:13,864 - [ReAct-Stream] Iter 2 — decision=tool_calls, tools=['create_plan']
2026-02-26 21:49:13,865 - Executing tool: create_plan with {...}
2026-02-26 21:49:13,866 - [Plan] Registered active plan plan_20260226_214913_da6b7c
2026-02-26 21:49:33,141 - [Plan] Step update step_1 status=in_progress
2026-02-26 21:49:43,267 - [Plan] Step update step_1 status=completed
2026-02-26 21:49:43,269 - [Plan] Step update step_2 status=in_progress
2026-02-26 21:50:00,897 - [Plan] Step update step_2 status=completed
2026-02-26 21:50:00,900 - [Plan] Step update step_3 status=completed
2026-02-26 21:50:08,476 - [Plan] Unregistered plan plan_20260226_214913_da6b7c
```

**结果**: ✅ 修复成功
- Plan 工具正确添加到工具列表
- LLM 正确调用 `create_plan` 创建计划
- 计划步骤按顺序执行并完成
- 总耗时: ~70秒 (vs 修复前 429秒失败)

---

## 14. 待改进点

1. **Plan 重入**: 当前不支持中断后恢复（会话结束后 Plan 丢失）
2. **并行步骤**: 当前步骤是线性执行，不支持并行
3. **条件分支**: 当前不支持基于条件的步骤跳转
4. **跨会话持久化**: 可考虑持久化到数据库支持长期任务
5. **LLM 工具调用引导**: 需要增强 LLM 在 Plan 模式下正确调用 `create_plan` 的能力