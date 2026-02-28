# 任务清单 - Plan 模式 UI 修复

## Phase 1: 诊断和修复核心渲染问题 (1 个任务)

### TASK-001: 诊断前端渲染问题
**预估时间**: 2-4 小时
**优先级**: Critical
**依赖**: 无
**输出文件**:
- `webapps/seeagent-webui/src/api/client.ts` (可能需要修复)
- `webapps/seeagent-webui/src/hooks/useChat.ts` (添加调试日志)
- `webapps/seeagent-webui/src/components/Layout/MainContent.tsx` (检查渲染条件)

**问题描述**:
当前前端完全无法显示后端返回的内容：
- 后端 API 正常工作（curl 测试返回正确的 SSE 事件）
- 前端 API 请求返回 200 OK
- 但页面上完全没有显示任何步骤、Plan 卡片或 AI 响应
- 只显示计时器（TTFT 和总计时间）

**诊断步骤**:

1. **添加 SSE 事件日志**
```typescript
// src/api/client.ts - apiPostStream 函数
for (const line of lines) {
  if (line.startsWith('data: ')) {
    const data = line.slice(6).trim()
    console.log('[apiPostStream] Raw SSE data:', data)
    if (data === '[DONE]') {
      onComplete?.()
      return
    }
    try {
      const event = JSON.parse(data)
      console.log('[apiPostStream] Parsed event:', event)
      onEvent(event)
    } catch (e) {
      console.error('[apiPostStream] Parse error:', e, 'data:', data)
    }
  }
}
```

2. **添加 handleSSEEvent 日志**
```typescript
// src/hooks/useChat.ts - handleSSEEvent 函数开始
function handleSSEEvent(...) {
  console.log('[handleSSEEvent] Received event:', event.type, event)

  switch (event.type) {
    case 'plan_created':
      console.log('[plan_created] Setting plan and clearing steps')
      // ...
      break

    case 'tool_call_start':
      console.log('[tool_call_start] Creating step:', { toolName, stepTitle, stepCategory })
      // ...
      break

    case 'text_delta':
      console.log('[text_delta] Content:', content)
      // ...
      break
  }
}
```

3. **检查 React 状态更新**
- 使用 React DevTools 检查 useChat hook 的状态
- 验证 `steps`, `activePlan`, `llmOutput` 是否有数据
- 检查组件是否重新渲染

4. **检查渲染条件**
```typescript
// src/components/Layout/MainContent.tsx
// 确保这个条件不会阻止内容显示
{session?.userMessage &&
 !conversationHistory.some(t => t.userMessage === session.userMessage) &&
 (isWaiting || isRunning || isCompleted || steps.length > 0 || askUserQuestion || llmOutput || activePlan) && (
  <div>
    {/* 内容应该在这里显示 */}
  </div>
)}
```

**验收标准**:
- [ ] 浏览器控制台能看到 SSE 事件日志
- [ ] React DevTools 显示 steps/activePlan/llmOutput 有数据
- [ ] 页面能正常显示 AI 响应内容
- [ ] 页面能正常显示步骤卡片
- [ ] 页面能正常显示 Plan 卡片（如果有）

**测试用例**:
```typescript
// 手动测试
1. 打开浏览器开发者工具
2. 发送消息："测试"
3. 观察 Console 标签页
4. 应该看到：
   - [apiPostStream] Raw SSE data: ...
   - [apiPostStream] Parsed event: ...
   - [handleSSEEvent] Received event: ...
5. 检查 React DevTools
6. 验证页面显示内容
```

---

## Phase 2: Plan 卡片显示和步骤过滤 (3 个任务)

### TASK-101: 验证并修复 plan_created 事件处理
**预估时间**: 1-2 小时
**优先级**: High
**依赖**: TASK-001
**输出文件**:
- `webapps/seeagent-webui/src/hooks/useChat.ts`

**问题描述**:
需要验证 `plan_created` 事件的处理逻辑：
1. 是否正确接收并解析后端发送的 plan 数据
2. 是否正确映射 camelCase 字段到 snake_case
3. 是否正确清除预计划步骤
4. Plan 卡片是否在步骤卡片之前显示

**实现步骤**:

1. **验证后端数据格式**
```bash
curl -N -X POST http://127.0.0.1:18900/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"请打开百度网站，搜索北京今天天气，然后截图保存","conversation_id":null}' \
  2>&1 | grep -A 20 "plan_created"
```

2. **添加详细日志**
```typescript
case 'plan_created': {
  console.log('[plan_created] Raw event:', eventRecord)
  const raw = eventRecord.plan as Record<string, unknown> | undefined
  console.log('[plan_created] Raw plan data:', raw)

  if (raw) {
    const plan: Plan = {
      id: (raw.id as string) || '',
      task_summary: (raw.taskSummary as string) || (raw.task_summary as string) || '',
      steps: ((raw.steps as Array<Record<string, unknown>>) || []).map((s) => ({
        id: String(s.id || ''),
        description: String(s.description || ''),
        status: (s.status as PlanStepStatus) || 'pending',
      })),
      status: (raw.status as PlanStatus) || 'in_progress',
      created_at: new Date().toISOString(),
    }
    console.log('[plan_created] Mapped plan:', plan)
    console.log('[plan_created] Calling setActivePlan')
    setActivePlan(plan)
    console.log('[plan_created] Calling setSteps([]) to clear pre-plan steps')
    setSteps([])
  } else {
    console.warn('[plan_created] No plan data in event')
  }
  break
}
```

3. **验证 UI 渲染**
- 检查 MainContent.tsx 中 PlanCard 的渲染逻辑
- 确保 PlanCard 在 StepTimeline 之前

**验收标准**:
- [ ] 后端 plan_created 事件数据格式正确
- [ ] 前端正确解析并映射 plan 数据
- [ ] setActivePlan 被调用且状态更新成功
- [ ] setSteps([]) 被调用且清空预计划步骤
- [ ] PlanCard 在页面上正确显示
- [ ] PlanCard 显示在步骤卡片之前

**测试用例**:
```typescript
// 测试 1: 基本 Plan 创建
输入: "请打开百度网站，搜索北京今天天气，然后截图保存"
预期:
1. 显示 PlanCard，标题为任务摘要
2. PlanCard 显示 3 个步骤
3. 没有预计划的失败步骤显示
```

---

### TASK-102: 验证并修复步骤过滤逻辑
**预估时间**: 1-2 小时
**优先级**: High
**依赖**: TASK-001
**输出文件**:
- `webapps/seeagent-webui/src/hooks/useChat.ts`
- `webapps/seeagent-webui/src/types/step.ts`

**问题描述**:
需要验证 `categorizeStep` 函数是否正确过滤内部步骤：
1. `create_plan`, `update_plan_step`, `complete_plan` 应该被标记为 internal
2. 失败的预计划尝试应该被清除
3. 只有 core 类型的步骤显示在 UI 上

**实现步骤**:

1. **验证 categorizeStep 函数**
```typescript
// 当前实现
function categorizeStep(title: string, tool?: string, args?: Record<string, unknown>): StepCategory {
  const textToCheck = `${title} ${tool || ''}`.toLowerCase()
  const toolLower = (tool || '').toLowerCase()

  // ... core operations checks ...

  // Check raw tool name against internal patterns
  for (const pattern of INTERNAL_STEP_PATTERNS) {
    if (pattern.test(toolLower) || pattern.test(textToCheck)) {
      return 'internal'
    }
  }

  // ... more checks ...
}
```

2. **添加调试日志**
```typescript
case 'tool_call_start': {
  const toolName = eventRecord.tool as string
  const stepCategory = categorizeStep(stepTitle, toolName, args)
  console.log('[tool_call_start] Tool:', toolName, 'Title:', stepTitle, 'Category:', stepCategory)

  setSteps((prev) => {
    if (stepCategory === 'internal') {
      console.log('[tool_call_start] Skipping internal step:', toolName)
      return prev
    }
    console.log('[tool_call_start] Adding core step:', toolName)
    // ...
  })
}
```

3. **单元测试**
```typescript
// 测试内部步骤
console.assert(categorizeStep('创建计划', 'create_plan') === 'internal')
console.assert(categorizeStep('更新计划步骤', 'update_plan_step') === 'internal')
console.assert(categorizeStep('完成计划', 'complete_plan') === 'internal')

// 测试核心步骤
console.assert(categorizeStep('打开百度首页', 'browser_navigate') === 'core')
console.assert(categorizeStep('搜索北京天气', 'browser_task') === 'core')
```

**验收标准**:
- [ ] categorizeStep 正确识别所有计划管理工具为 internal
- [ ] create_plan, update_plan_step, complete_plan 不显示在 UI 上
- [ ] 失败的预计划尝试不显示在 UI 上
- [ ] 只有 core 类型的步骤显示在 StepTimeline 中

**测试用例**:
```typescript
// 测试 1: 计划管理工具过滤
输入: "请打开百度网站，搜索北京今天天气，然后截图保存"
预期:
- 不显示 "创建计划" 步骤
- 不显示 "完成计划" 步骤
- 只显示 3 个核心步骤
```

---

### TASK-103: 验证并修复 Plan 步骤与执行步骤关联
**预估时间**: 2-3 小时
**优先级**: High
**依赖**: TASK-001, TASK-101
**输出文件**:
- `webapps/seeagent-webui/src/hooks/useChat.ts`

**问题描述**:
需要验证 Plan 中的步骤与实际执行的步骤是否正确关联：
1. 执行步骤的标题应该使用 Plan 步骤的描述
2. 执行步骤应该记录对应的 Plan 步骤 ID
3. Plan 步骤的状态应该随执行步骤更新

**实现步骤**:

1. **验证 Plan 步骤查找**
```typescript
case 'tool_call_start': {
  const toolName = eventRecord.tool as string
  const args = eventRecord.args as Record<string, unknown> | undefined

  // Find current in_progress Plan step
  let planStepDescription: string | undefined
  let planStepId: string | undefined
  if (activePlan) {
    console.log('[tool_call_start] Active plan:', activePlan)
    const currentPlanStep = activePlan.steps.find(s => s.status === 'in_progress')
    console.log('[tool_call_start] Current plan step:', currentPlanStep)

    if (currentPlanStep) {
      planStepDescription = currentPlanStep.description
      planStepId = currentPlanStep.id
      console.log('[tool_call_start] Using plan step:', planStepDescription, 'ID:', planStepId)
    }
  }

  // Use Plan step description as title
  const stepTitle = planStepDescription || getToolDisplayName(toolName, args) || formatToolTitleSmart(toolName, args)
  console.log('[tool_call_start] Step title:', stepTitle)

  // Create step with planStepId
  const newStep: Step = {
    // ...
    title: stepTitle,
    outputData: planStepId ? { planStepId, originalToolName: toolName } : undefined,
  }
  console.log('[tool_call_start] Created step:', newStep)
}
```

2. **验证 plan_step_updated**
```typescript
case 'plan_step_updated': {
  const stepId = (eventRecord.stepId as string) || (eventRecord.step_id as string)
  const status = eventRecord.status as string
  console.log('[plan_step_updated] Updating step:', stepId, 'to status:', status)

  setActivePlan((prev) => {
    if (!prev) {
      console.warn('[plan_step_updated] No active plan')
      return null
    }
    // ...
  })
}
```

**验收标准**:
- [ ] 执行步骤的标题使用 Plan 步骤的描述
- [ ] 执行步骤的 outputData 包含 planStepId
- [ ] Plan 步骤的状态随执行更新
- [ ] PlanCard 中的步骤状态实时更新

**测试用例**:
```typescript
// 测试 1: 步骤标题使用 Plan 描述
输入: "请打开百度网站，搜索北京今天天气，然后截图保存"
预期:
- 步骤 1 标题: "打开百度首页"（不是 "browser_navigate"）
- 步骤 2 标题: "搜索北京今天天气"（不是 "browser_task"）
- 步骤 3 标题: "截图保存"（不是 "browser_screenshot"）
```

---

## Phase 3: ask_user 上下文保持 (1 个任务)

### TASK-201: 验证并修复 ask_user 上下文保持
**预估时间**: 2-3 小时
**优先级**: Critical
**依赖**: TASK-001, TASK-101
**输出文件**:
- `webapps/seeagent-webui/src/hooks/useChat.ts`
- `webapps/seeagent-webui/src/App.tsx`
- `webapps/seeagent-webui/src/components/Layout/MainContent.tsx`

**问题描述**:
需要验证当 Plan 执行过程中触发 ask_user 时，用户回答后 Plan 模式上下文是否保持：
1. 用户回答应该作为当前对话的延续
2. `activePlan` 状态应该保持不变
3. 已执行的步骤应该保留
4. 回答后继续执行 Plan 中的剩余步骤

**实现步骤**:

1. **验证参数传递**
```typescript
// MainContent.tsx
onClick={() => {
  console.log('[ask_user] User clicked option:', option.label)
  onSendMessage(option.label, true)
}}

// App.tsx
const handleSendMessage = useCallback(
  (message: string, isAskUserAnswer: boolean = false) => {
    console.log('[handleSendMessage] message:', message, 'isAskUserAnswer:', isAskUserAnswer)
    // ...
    sendMessage(message, undefined, executionMode === 'edit', isAskUserAnswer)
  },
  // ...
)

// useChat.ts
const sendMessage = useCallback(
  async (message: string, endpoint?: string, editMode: boolean = false, isAskUserAnswer: boolean = false) => {
    console.log('[sendMessage] message:', message, 'isAskUserAnswer:', isAskUserAnswer)

    if (!isAskUserAnswer) {
      console.log('[sendMessage] Clearing steps and plan (new message)')
      setSteps([])
      setActivePlan(null)
    } else {
      console.log('[sendMessage] Keeping steps and plan (ask_user answer)')
    }
    // ...
  },
  // ...
)
```

2. **验证状态保持**
- 使用 React DevTools 检查状态变化
- 确保 activePlan 和 steps 在回答后保持

**验收标准**:
- [ ] 点击 ask_user 选项时，isAskUserAnswer=true 正确传递
- [ ] ask_user 回答时，activePlan 状态保持不变
- [ ] ask_user 回答时，已执行的 steps 保留
- [ ] 回答后继续执行 Plan 或创建 Plan
- [ ] 整个流程中 Plan 模式上下文连续

**测试用例**:
```typescript
// 测试 1: ask_user 在 Plan 之前
输入: "请帮我查询今天的天气，然后截图保存"
预期:
1. 显示 ask_user 问题
2. 点击 "北京"
3. 创建 Plan
4. 显示 PlanCard
5. 执行 Plan 步骤
6. 完成任务
```

---

## Phase 4: UI 优化和测试 (2 个任务)

### TASK-301: 优化 PlanCard 显示和交互
**预估时间**: 2-3 小时
**优先级**: Medium
**依赖**: TASK-101, TASK-102, TASK-103
**输出文件**:
- `webapps/seeagent-webui/src/components/Plan/PlanCard.tsx`
- `webapps/seeagent-webui/src/components/Layout/MainContent.tsx`

**问题描述**:
优化 PlanCard 组件的显示和交互体验：
1. 添加入场动画
2. 优化步骤状态图标和颜色
3. 添加当前步骤高亮
4. 优化进度条动画

**实现步骤**:

1. **添加入场动画**
```typescript
// PlanCard.tsx
<div className="rounded-xl ... animate-slideIn">
  {/* ... */}
</div>

// CSS
@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

2. **优化步骤状态**
```typescript
const STATUS_ICONS = {
  pending: <span className="text-slate-500">⏳</span>,
  in_progress: <span className="text-primary animate-pulse">▶️</span>,
  completed: <span className="text-green-400">✅</span>,
  failed: <span className="text-red-400">❌</span>,
  skipped: <span className="text-slate-500">⏭️</span>,
}
```

3. **添加当前步骤高亮**
```typescript
{plan.steps.map((step, index) => (
  <div
    key={step.id}
    className={`flex items-start gap-2 text-sm p-2 rounded-lg transition-colors ${
      step.status === 'in_progress'
        ? 'bg-primary/10 border border-primary/30'
        : ''
    }`}
  >
    {/* ... */}
  </div>
))}
```

**验收标准**:
- [ ] PlanCard 有平滑的入场动画
- [ ] 进度条实时更新，动画流畅
- [ ] 步骤状态图标清晰直观
- [ ] 当前执行的步骤有明显的视觉高亮
- [ ] 完成/失败状态有明确的视觉反馈

**测试用例**:
```typescript
// 测试 1: 视觉效果
输入: "请打开百度网站，搜索北京今天天气，然后截图保存"
预期:
- PlanCard 平滑出现
- 当前步骤有高亮背景
- 进度条动画流畅
- 完成后显示 ✨ 消息
```

---

### TASK-302: 添加端到端测试
**预估时间**: 4-6 小时
**优先级**: Medium
**依赖**: TASK-101, TASK-102, TASK-103, TASK-201
**输出文件**:
- `webapps/seeagent-webui/e2e/plan-mode.spec.ts`
- `webapps/seeagent-webui/playwright.config.ts`

**问题描述**:
创建自动化端到端测试，验证 Plan 模式的完整流程。

**实现步骤**:

1. **安装 Playwright**
```bash
cd webapps/seeagent-webui
pnpm add -D @playwright/test
npx playwright install
```

2. **创建测试配置**
```typescript
// playwright.config.ts
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  use: {
    baseURL: 'http://localhost:5174',
  },
  webServer: {
    command: 'pnpm dev',
    url: 'http://localhost:5174',
    reuseExistingServer: true,
  },
})
```

3. **编写测试用例**
```typescript
// e2e/plan-mode.spec.ts
import { test, expect } from '@playwright/test'

test('should create and display plan card', async ({ page }) => {
  await page.goto('/')
  await page.click('button:has-text("New Chat")')
  await page.fill('textarea', '请打开百度网站，搜索北京今天天气，然后截图保存')
  await page.click('button:has-text("send")')

  // Wait for plan card
  await page.waitForSelector('text=任务计划', { timeout: 30000 })

  // Verify plan card content
  const planCard = page.locator('text=任务计划').locator('..')
  await expect(planCard).toBeVisible()

  // Verify steps
  const steps = planCard.locator('text=/\\d+\\./')
  await expect(steps).toHaveCount(3)
})
```

**验收标准**:
- [ ] 测试可以在本地运行
- [ ] 测试覆盖 Plan 创建和显示
- [ ] 测试覆盖步骤执行和状态更新
- [ ] 测试覆盖 ask_user 交互
- [ ] 测试失败时有清晰的错误信息

**测试用例**:
```bash
# 运行测试
pnpm test:e2e

# 预期输出
✓ should create and display plan card
✓ should update plan step status during execution
✓ should maintain plan context after ask_user
```
