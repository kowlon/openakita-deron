# Plan模式深度分析：为什么步骤不显示？

## 问题回顾

用户问题：**当使用plan模式时，能否也跟现有的非plan模式一样把步骤卡片都显示出来？**

## 深度代码分析

### 1. 事件流程追踪

#### 后端事件发送流程

**文件**: `src/openakita/core/reasoning_engine.py`

```python
# Line 2194: 发送 tool_call_start 事件
yield {"type": "tool_call_start", "tool": t_name, "args": t_args, "id": t_id}

# 执行工具
r = await self._tool_executor.execute_tool(...)

# Line 2206: 发送 tool_call_end 事件
yield {"type": "tool_call_end", "tool": t_name, "result": r[:32000], "id": t_id, "is_error": _tool_is_error}
```

**关键发现**：
- ✅ 后端**确实发送**了 `tool_call_start` 和 `tool_call_end` 事件
- ✅ 包括 `browser_navigate`, `browser_task`, `browser_screenshot` 等工具
- ✅ 同时也发送了 `create_plan`, `update_plan_step`, `complete_plan` 等plan工具

#### SSE传输层

**文件**: `src/openakita/api/routes/chat.py`

```python
# Line 146-170: 直接转发所有事件
async for event in actual_agent.chat_with_session_stream(...):
    event_type = event.get("type", "")

    # 直接转发事件（包括 tool_call_start/end）
    yield _sse(event_type, {k: v for k, v in event.items() if k != "type"})
```

**关键发现**：
- ✅ SSE层**不过滤**任何事件，全部转发到前端
- ✅ 包括 `tool_call_start`, `tool_call_end`, `plan_created`, `plan_step_updated` 等

### 2. 前端事件处理分析

#### 前端接收事件

**文件**: `webapps/seeagent-webui/src/hooks/useChat.ts`

```typescript
// Line 269-307: tool_call_start 处理
case 'tool_call_start': {
  const toolName = eventRecord.tool as string
  const args = eventRecord.args as Record<string, unknown> | undefined
  const stepTitle = formatToolTitleSmart(toolName, args)
  const stepCategory = categorizeStep(stepTitle, toolName, args)  // 关键！

  setSteps((prev) => {
    // Line 278: 如果是 internal 类型，直接跳过！
    if (stepCategory === 'internal') {
      return prev
    }

    // 创建新步骤
    const newStep: Step = {
      id: eventRecord.id || eventRecord.step_id || generateStepId(),
      type: mapToolToStepType(toolName),
      status: 'running',
      title: stepTitle,
      ...
    }
    return [...prev, newStep]
  })
}
```

#### 步骤分类逻辑

**文件**: `webapps/seeagent-webui/src/hooks/useChat.ts:552-623`

```typescript
function categorizeStep(title: string, tool?: string, args?: Record<string, unknown>): StepCategory {
  const textToCheck = `${title} ${tool || ''}`.toLowerCase()

  // 检查是否匹配 INTERNAL_STEP_PATTERNS
  for (const pattern of INTERNAL_STEP_PATTERNS) {
    if (pattern.test(textToCheck)) {
      return 'internal'  // 返回 internal，步骤会被过滤掉！
    }
  }

  // 检查是否匹配 CORE_STEP_PATTERNS
  for (const pattern of CORE_STEP_PATTERNS) {
    if (pattern.test(textToCheck)) {
      return 'core'
    }
  }

  // 默认：返回 internal（隐藏未知步骤）
  return 'internal'
}
```

#### 内部步骤模式定义

**文件**: `webapps/seeagent-webui/src/types/step.ts:54-99`

```typescript
export const INTERNAL_STEP_PATTERNS = [
  // Plan management (internal)
  /^create_plan$/i,
  /^update_plan/i,
  /^complete_plan$/i,
  /^get_plan/i,
  /plan.*step/i,  // 匹配任何包含 "plan" 和 "step" 的工具！

  // System operations
  /execute\s*command/i,
  /run\s*command/i,
  /shell/i,
  /bash/i,
  /terminal/i,

  // Delivery and summary
  /^deliver$/i,
  /交付/i,
  /deliver_artifacts/i,
  ...
]
```

### 3. 问题根因

#### 根因1: Plan管理工具被过滤

```typescript
// create_plan, update_plan_step, complete_plan 都被标记为 internal
/^create_plan$/i,
/^update_plan/i,
/^complete_plan$/i,
```

**影响**：
- ❌ `create_plan` 工具调用不会创建步骤卡片
- ❌ `update_plan_step` 工具调用不会创建步骤卡片
- ❌ `complete_plan` 工具调用不会创建步骤卡片

#### 根因2: Plan事件被忽略

```typescript
// Line 413-417
case 'plan_created':
case 'plan_step_updated':
case 'agent_switch':
  // These are internal events, don't create visible steps
  break  // 直接忽略，不做任何处理！
```

**影响**：
- ❌ 即使后端发送了 `plan_created` 事件，前端也不处理
- ❌ 即使后端发送了 `plan_step_updated` 事件，前端也不处理

#### 根因3: 业务工具也可能被过滤

在Plan模式下，实际的业务工具（如 `browser_navigate`）**应该**会创建步骤，但让我们验证：

**测试日志分析**：
```
2026-02-28 11:04:41 - tools=['update_plan_step', 'browser_navigate']
2026-02-28 11:04:57 - tools=['update_plan_step', 'update_plan_step', 'browser_navigate']
2026-02-28 11:05:14 - tools=['update_plan_step', 'update_plan_step', 'browser_screenshot']
```

**问题**：
- `browser_navigate`, `browser_task`, `browser_screenshot` 这些工具**应该**创建步骤
- 但为什么页面显示 "0 steps"？

让我检查 `browser_navigate` 是否被过滤：

```typescript
// categorizeStep 函数中
// 检查 INTERNAL_STEP_PATTERNS
/shell/i,      // 匹配 "shell"
/bash/i,       // 匹配 "bash"
/terminal/i,   // 匹配 "terminal"
```

**关键发现**：`browser_navigate` 不应该被这些模式匹配，应该会创建步骤！

### 4. 真正的问题

让我重新检查日志，看看是否有其他线索：

**从日志中发现**：
```
页面显示: "0 steps • 1m ago"
```

这说明：
1. 前端**确实接收到了事件**（否则不会更新时间）
2. 但**没有创建任何步骤卡片**

**可能的原因**：

#### 原因A: 步骤被创建但立即被过滤

```typescript
// Line 276-280
setSteps((prev) => {
  // Skip internal steps - don't add them at all
  if (stepCategory === 'internal') {
    return prev  // 不添加步骤
  }
  ...
})
```

#### 原因B: 步骤标题格式化问题

```typescript
// Line 273
const stepTitle = formatToolTitleSmart(toolName, args)
```

让我检查 `formatToolTitleSmart` 函数：

**文件**: `webapps/seeagent-webui/src/hooks/useChat.ts:486-528`

```typescript
function formatToolTitleSmart(tool: string | undefined, args: Record<string, unknown> | undefined): string {
  if (!tool) return '处理中'

  const toolTitles: Record<string, string> = {
    'web_search': '网络搜索',
    'search': '搜索',
    'news_search': '新闻搜索',
    'image_search': '图片搜索',
    'video_search': '视频搜索',
    'create_plan': '创建计划',
    'update_plan_step': '更新计划步骤',
    'complete_plan': '完成计划',
    'get_skill_info': '获取技能信息',
    'deliver_artifacts': '交付结果',
    'pdf': 'PDF 处理',
    'read_file': '文件读取',
    'write_file': '文件写入',
    'run_shell': '执行命令',
  }

  return toolTitles[tool] || tool
}
```

**关键发现**：
- `browser_navigate` 不在 `toolTitles` 中，会返回原始工具名 `"browser_navigate"`
- 然后 `categorizeStep("browser_navigate", "browser_navigate", args)` 会检查是否匹配内部模式

让我检查 `browser_navigate` 是否会被标记为 internal：

```typescript
// INTERNAL_STEP_PATTERNS 中没有匹配 "browser_navigate" 的模式
// CORE_STEP_PATTERNS 中也没有匹配 "browser_navigate" 的模式

// 所以会走到默认逻辑：
// Line 621-622
// Default: hide unknown steps (internal)
return 'internal'
```

**找到了！这就是问题所在！**

### 5. 问题总结

#### 问题1: 默认策略过于保守

```typescript
// Line 621-622: 默认隐藏未知步骤
return 'internal'
```

**影响**：
- ❌ 所有未在 `CORE_STEP_PATTERNS` 中定义的工具都会被隐藏
- ❌ 包括 `browser_navigate`, `browser_task`, `browser_screenshot` 等

#### 问题2: CORE_STEP_PATTERNS 定义不完整

```typescript
export const CORE_STEP_PATTERNS = [
  // Search and query
  /search/i,
  /web\s*(browse|scrape|search)/i,

  // PDF and file generation
  /pdf/i,
  /write\s*(file|document)/i,
  /create\s*(file|document)/i,
  /生成/i,

  // Thinking/Intent analysis
  /意图/i,
  /分析/i,
]
```

**缺失**：
- ❌ 没有 `browser` 相关的模式
- ❌ 没有 `navigate` 相关的模式
- ❌ 没有 `screenshot` 相关的模式

#### 问题3: Plan事件被完全忽略

```typescript
case 'plan_created':
case 'plan_step_updated':
  break  // 不做任何处理
```

## 解决方案分析

### 方案1: 修改默认策略（推荐）

**优点**：
- ✅ 最简单，改动最小
- ✅ 让所有工具调用都显示（除非明确标记为 internal）
- ✅ 符合用户期望

**缺点**：
- ⚠️ 可能显示一些不必要的内部工具

**实现**：

```typescript
// webapps/seeagent-webui/src/hooks/useChat.ts:621-622
// 修改前：
// Default: hide unknown steps (internal)
return 'internal'

// 修改后：
// Default: show unknown steps as core (unless explicitly marked as internal)
return 'core'
```

### 方案2: 扩展 CORE_STEP_PATTERNS（推荐）

**优点**：
- ✅ 更精确的控制
- ✅ 只显示明确需要的步骤
- ✅ 保持内部工具隐藏

**缺点**：
- ⚠️ 需要维护模式列表
- ⚠️ 新工具需要手动添加

**实现**：

```typescript
// webapps/seeagent-webui/src/types/step.ts
export const CORE_STEP_PATTERNS = [
  // Search and query
  /search/i,
  /web\s*(browse|scrape|search)/i,

  // PDF and file generation
  /pdf/i,
  /write\s*(file|document)/i,
  /create\s*(file|document)/i,
  /生成/i,

  // Thinking/Intent analysis
  /意图/i,
  /分析/i,

  // 新增：Browser operations
  /browser/i,
  /navigate/i,
  /screenshot/i,
  /click/i,
  /type/i,
  /scroll/i,
]
```

### 方案3: 处理 Plan 事件（推荐）

**优点**：
- ✅ 提供Plan的可视化
- ✅ 显示计划概览和进度
- ✅ 增强用户体验

**缺点**：
- ⚠️ 需要设计Plan UI组件
- ⚠️ 改动较大

**实现**：

```typescript
// webapps/seeagent-webui/src/hooks/useChat.ts:413-417
// 修改前：
case 'plan_created':
case 'plan_step_updated':
  break

// 修改后：
case 'plan_created': {
  const planData = eventRecord.plan as Record<string, unknown>
  if (!planData) break

  // 创建一个特殊的 "Plan 概览" 步骤
  const newStep: Step = {
    id: generateStepId(),
    type: 'planning',
    status: 'running',
    title: `📋 ${planData.task_summary}`,
    summary: `计划包含 ${(planData.steps as any[]).length} 个步骤`,
    startTime: Date.now(),
    category: 'core',
    outputData: planData,
  }
  setSteps((prev) => [...prev, newStep])
  break
}

case 'plan_step_updated': {
  // 可以选择：
  // 选项A: 不创建新步骤，只更新Plan概览步骤的进度
  // 选项B: 为每个Plan步骤创建一个步骤卡片
  // 选项C: 什么都不做，依赖 tool_call_start/end 事件
  break
}
```

### 方案4: 混合方案（最佳）

结合方案1、2、3的优点：

1. **修改默认策略为 'core'** - 让所有工具默认显示
2. **扩展 CORE_STEP_PATTERNS** - 明确标记核心业务工具
3. **处理 plan_created 事件** - 显示Plan概览
4. **不处理 plan_step_updated 事件** - 依赖 tool_call_start/end 显示实际工具执行

**理由**：
- ✅ Plan模式下，实际的业务工具（browser_navigate等）会通过 tool_call_start/end 创建步骤
- ✅ Plan概览通过 plan_created 事件显示
- ✅ 不需要重复显示 update_plan_step 工具调用（这是内部管理工具）
- ✅ 用户看到的是：Plan概览 + 实际执行的业务步骤

## 最终推荐方案

### 实施步骤

#### 步骤1: 修改默认策略

**文件**: `webapps/seeagent-webui/src/hooks/useChat.ts`

```typescript
// Line 621-622
function categorizeStep(...): StepCategory {
  ...

  // 修改默认策略
  // Default: show unknown steps as core (unless explicitly marked as internal)
  return 'core'  // 改为 'core'
}
```

#### 步骤2: 扩展核心模式（可选但推荐）

**文件**: `webapps/seeagent-webui/src/types/step.ts`

```typescript
export const CORE_STEP_PATTERNS = [
  // Search and query
  /search/i,
  /web\s*(browse|scrape|search)/i,

  // PDF and file generation
  /pdf/i,
  /write\s*(file|document)/i,
  /create\s*(file|document)/i,
  /生成/i,

  // Thinking/Intent analysis
  /意图/i,
  /分析/i,

  // Browser operations (新增)
  /browser/i,
  /navigate/i,
  /screenshot/i,
  /click/i,
  /type/i,
  /scroll/i,
  /snapshot/i,
]
```

#### 步骤3: 添加Plan概览（可选）

**文件**: `webapps/seeagent-webui/src/hooks/useChat.ts`

```typescript
case 'plan_created': {
  const planData = eventRecord.plan as Record<string, unknown>
  if (!planData) break

  const steps = (planData.steps as any[]) || []
  const newStep: Step = {
    id: generateStepId(),
    type: 'planning',
    status: 'running',
    title: `📋 任务计划：${planData.task_summary}`,
    summary: `共 ${steps.length} 个步骤`,
    startTime: Date.now(),
    category: 'core',
    outputData: planData,
  }
  setSteps((prev) => [...prev, newStep])
  break
}

case 'plan_step_updated': {
  // 不创建新步骤，依赖 tool_call_start/end
  // 可以选择更新Plan概览步骤的进度信息
  break
}
```

## 预期效果

### 修改前
```
页面显示: "0 steps"
用户看不到任何执行过程
```

### 修改后（仅步骤1）
```
页面显示: "3 steps"

Step 1: browser_navigate ✅
  - 已成功打开百度首页

Step 2: browser_task ✅
  - 已搜索今日天气

Step 3: browser_screenshot ✅
  - 截图已保存
```

### 修改后（步骤1+3）
```
页面显示: "4 steps"

Step 1: 📋 任务计划：打开百度搜索今日天气并截图保存 🔄
  - 共 3 个步骤

Step 2: browser_navigate ✅
  - 已成功打开百度首页

Step 3: browser_task ✅
  - 已搜索今日天气

Step 4: browser_screenshot ✅
  - 截图已保存
```

## 回答用户问题

**问题**: 当使用plan模式时，能否也跟现有的非plan模式一样把步骤卡片都显示出来？

**答案**:

**可以！而且非常简单！**

问题的根本原因是：
1. **默认策略过于保守** - 未知工具默认被隐藏（返回 'internal'）
2. **CORE_STEP_PATTERNS 不完整** - 没有包含 browser 相关的工具

**最简单的解决方案**：

只需要修改一行代码：

```typescript
// webapps/seeagent-webui/src/hooks/useChat.ts:622
// 将默认返回值从 'internal' 改为 'core'
return 'core'
```

这样，Plan模式下的所有业务工具（browser_navigate, browser_task, browser_screenshot）都会创建步骤卡片，就像非Plan模式一样。

**更好的方案**：

1. 修改默认策略为 'core'
2. 扩展 CORE_STEP_PATTERNS 包含 browser 相关模式
3. 可选：添加 Plan 概览卡片

这样既能显示所有业务步骤，又能提供Plan的整体视图。

## 是否有更好的方案？

经过深入分析，我认为**没有更好的方案**，原因：

1. **当前架构已经很好** - 通过 tool_call_start/end 事件统一处理所有工具调用
2. **Plan模式不需要特殊处理** - Plan只是任务拆分，实际执行还是通过工具调用
3. **修改最小** - 只需要调整过滤逻辑，不需要重构架构

**唯一可以优化的地方**：

添加一个 **Plan进度指示器**，在页面顶部显示当前执行到第几步，但这是UI增强，不是架构改进。

## 总结

1. **问题根因**: 默认策略将未知工具标记为 internal，导致 browser 工具被过滤
2. **解决方案**: 修改默认策略为 'core'，让所有工具默认显示
3. **是否可行**: 完全可行，改动最小，效果最好
4. **更好方案**: 没有，当前方案已经是最优解
