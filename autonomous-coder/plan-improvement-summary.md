# Plan功能测试总结与改进建议

## 测试概况

**测试时间**: 2026-02-28 11:02-11:06
**测试任务**: "打开百度搜索今天的天气，然后截图保存"
**Plan ID**: plan_20260228_110435_524750

## 测试结果

### ✅ 后端功能正常

1. **Plan自动检测** - 成功识别多步骤任务
2. **Plan创建** - 正确拆分为3个步骤
3. **步骤执行** - 按顺序执行，状态更新正常
4. **进度跟踪** - 记录详细的执行日志
5. **Plan完成** - 生成完成总结

### ❌ 前端展示问题

**核心问题**: 前端页面显示"0 steps"，用户完全看不到Plan的执行过程

**截图证据**:
- 初始状态: `.playwright-mcp/page-2026-02-28T03-02-43-112Z.png`
- 执行中: `.playwright-mcp/page-2026-02-28T03-05-02-558Z.png`
- 完成后: `.playwright-mcp/page-2026-02-28T03-06-27-543Z.png`

所有截图都显示"0 steps"，说明前端没有接收或处理Plan相关的步骤。

## 问题根因分析

### 1. 前端事件处理缺失

**位置**: `webapps/seeagent-webui/src/hooks/useChat.ts:413-417`

```typescript
case 'plan_created':
case 'plan_step_updated':
case 'agent_switch':
  // These are internal events, don't create visible steps
  break
```

**问题**: Plan事件被标记为"内部事件"，直接忽略，不创建任何可见步骤。

### 2. 步骤过滤过于激进

**位置**: `webapps/seeagent-webui/src/types/step.ts:54-99`

```typescript
export const INTERNAL_STEP_PATTERNS = [
  // Plan management (internal)
  /^create_plan$/i,
  /^update_plan/i,
  /^complete_plan$/i,
  /^get_plan/i,
  /plan.*step/i,
  ...
]
```

**问题**: 所有包含"plan"的工具调用都被过滤掉，即使是实际的业务步骤。

## 后端Plan执行详情

### Plan结构
```markdown
任务: 打开百度搜索今日天气并截图保存

步骤1: 打开百度首页
  - Tool: browser_navigate
  - Skills: browser-task
  - 状态: ✅ completed
  - 结果: 已成功打开百度首页
  - 耗时: 16秒 (11:04:41 → 11:04:57)

步骤2: 搜索今日天气
  - Tool: browser_task
  - Skills: browser-task
  - 状态: ✅ completed
  - 结果: 已搜索今日天气
  - 耗时: 17秒 (11:04:57 → 11:05:14)

步骤3: 截取结果页面并保存
  - Tool: browser_screenshot
  - Skills: browser-task
  - 状态: ✅ completed
  - 结果: 截图已保存到 data/temp/baidu_weather.png
  - 耗时: 72秒 (11:05:14 → 11:06:26)

总耗时: 105秒
```

### 执行日志
```
[11:04:35] 计划创建：打开百度搜索今日天气并截图保存
[11:04:41] 🔄 step_1: in_progress
[11:04:57] ✅ step_1: 已成功打开百度首页
[11:04:57] 🔄 step_2: in_progress
[11:05:14] ✅ step_2: 已搜索今日天气
[11:05:14] 🔄 step_3: in_progress
[11:06:26] ✅ step_3: 截图已保存到 data/temp/baidu_weather.png
[11:06:26] 计划完成：已成功打开百度搜索今日天气并截图保存
```

## 改进方案

### 方案1: 快速修复 (最小改动)

**目标**: 让Plan步骤在前端可见

**修改文件**: `webapps/seeagent-webui/src/hooks/useChat.ts`

```typescript
case 'plan_created': {
  const planData = eventRecord.plan as Record<string, unknown>
  if (!planData) break

  const steps = planData.steps as Array<any> || []
  const newStep: Step = {
    id: generateStepId(),
    type: 'planning',
    status: 'running',
    title: `📋 ${planData.task_summary}`,
    summary: `计划包含 ${steps.length} 个步骤`,
    startTime: Date.now(),
    category: 'core',
    outputData: planData,
  }
  setSteps((prev) => [...prev, newStep])
  break
}

case 'plan_step_updated': {
  const stepId = eventRecord.step_id as string
  const status = eventRecord.status as string
  const result = eventRecord.result as string
  const description = eventRecord.description as string
  const stepNumber = eventRecord.step_number as number
  const totalSteps = eventRecord.total_steps as number

  const stepStatus: StepStatus =
    status === 'in_progress' ? 'running' :
    status === 'completed' ? 'completed' :
    status === 'failed' ? 'failed' : 'pending'

  setSteps((prev) => {
    // 查找是否已存在该步骤
    const existingIndex = prev.findIndex(s => s.id === stepId)

    if (existingIndex >= 0) {
      // 更新现有步骤
      return prev.map((s, i) => i === existingIndex ? {
        ...s,
        status: stepStatus,
        summary: result || s.summary,
        endTime: status === 'completed' ? Date.now() : s.endTime,
        duration: status === 'completed' && s.startTime
          ? Date.now() - s.startTime
          : s.duration,
      } : s)
    } else {
      // 创建新步骤
      const statusIcon = status === 'in_progress' ? '🔄' :
                        status === 'completed' ? '✅' :
                        status === 'failed' ? '❌' : '⬜'

      return [...prev, {
        id: stepId,
        type: 'planning',
        status: stepStatus,
        title: `${statusIcon} [${stepNumber}/${totalSteps}] ${description}`,
        summary: result || '',
        startTime: Date.now(),
        category: 'core',
      }]
    }
  })
  break
}
```

**效果**:
- Plan创建时显示一个"计划卡片"
- 每个步骤更新时创建或更新对应的步骤卡片
- 用户可以看到执行进度

### 方案2: 完整方案 (推荐)

**目标**: 提供完整的Plan可视化体验

#### 2.1 创建Plan专用组件

**新建文件**: `webapps/seeagent-webui/src/components/Plan/PlanCard.tsx`

```typescript
import { useState } from 'react'

interface PlanStep {
  id: string
  description: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'skipped'
  result?: string
  tool?: string
  skills?: string[]
}

interface Plan {
  id: string
  task_summary: string
  steps: PlanStep[]
  status: 'in_progress' | 'completed' | 'failed'
  created_at: string
  completed_at?: string
}

export function PlanCard({ plan }: { plan: Plan }) {
  const [expanded, setExpanded] = useState(true)

  const completedCount = plan.steps.filter(s => s.status === 'completed').length
  const totalCount = plan.steps.length
  const currentStep = plan.steps.findIndex(s => s.status === 'in_progress')

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending': return '⬜'
      case 'in_progress': return '🔄'
      case 'completed': return '✅'
      case 'failed': return '❌'
      case 'skipped': return '⏭️'
      default: return '❓'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'in_progress': return 'text-blue-400'
      case 'completed': return 'text-green-400'
      case 'failed': return 'text-red-400'
      case 'skipped': return 'text-gray-400'
      default: return 'text-slate-400'
    }
  }

  return (
    <div className="plan-card bg-slate-800/50 rounded-xl p-4 border border-primary/20 mb-4">
      {/* Header */}
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <span className="text-2xl">📋</span>
          <div>
            <h3 className="text-white font-bold">{plan.task_summary}</h3>
            <p className="text-xs text-slate-400">
              进度: {completedCount}/{totalCount} 步骤
              {currentStep >= 0 && ` · 正在执行第 ${currentStep + 1} 步`}
            </p>
          </div>
        </div>
        <button className="text-slate-400 hover:text-white">
          <span className="material-symbols-outlined">
            {expanded ? 'expand_less' : 'expand_more'}
          </span>
        </button>
      </div>

      {/* Progress Bar */}
      <div className="mt-3 mb-2">
        <div className="w-full bg-slate-700 rounded-full h-2">
          <div
            className="bg-primary h-2 rounded-full transition-all duration-300"
            style={{ width: `${(completedCount / totalCount) * 100}%` }}
          />
        </div>
      </div>

      {/* Steps List */}
      {expanded && (
        <div className="mt-4 space-y-2">
          {plan.steps.map((step, index) => (
            <div
              key={step.id}
              className={`flex items-start gap-3 p-3 rounded-lg transition-all ${
                step.status === 'in_progress'
                  ? 'bg-blue-500/10 border border-blue-500/30'
                  : 'bg-slate-900/30'
              }`}
            >
              <span className="text-xl flex-shrink-0">
                {getStatusIcon(step.status)}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500 font-mono">
                    {index + 1}/{totalCount}
                  </span>
                  <span className={`text-sm font-medium ${getStatusColor(step.status)}`}>
                    {step.description}
                  </span>
                </div>
                {step.result && (
                  <p className="text-xs text-slate-400 mt-1">
                    {step.result}
                  </p>
                )}
                {step.tool && (
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-slate-500">工具:</span>
                    <span className="text-xs text-primary font-mono">
                      {step.tool}
                    </span>
                  </div>
                )}
              </div>
              {step.status === 'in_progress' && (
                <div className="flex space-x-1">
                  <div className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce" />
                  <div className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce [animation-delay:-0.15s]" />
                  <div className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce [animation-delay:-0.3s]" />
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Footer */}
      {plan.status === 'completed' && (
        <div className="mt-3 pt-3 border-t border-slate-700">
          <p className="text-xs text-green-400 flex items-center gap-2">
            <span className="material-symbols-outlined text-sm">check_circle</span>
            计划已完成
          </p>
        </div>
      )}
    </div>
  )
}
```

#### 2.2 集成到主界面

**修改文件**: `webapps/seeagent-webui/src/App.tsx`

```typescript
import { PlanCard } from '@/components/Plan/PlanCard'

// 在useChat hook中添加plan状态
const [activePlan, setActivePlan] = useState<Plan | null>(null)

// 在handleSSEEvent中处理plan事件
case 'plan_created': {
  const planData = eventRecord.plan as Plan
  setActivePlan(planData)
  break
}

case 'plan_step_updated': {
  setActivePlan(prev => {
    if (!prev) return null
    return {
      ...prev,
      steps: prev.steps.map(s =>
        s.id === eventRecord.step_id
          ? { ...s, status: eventRecord.status, result: eventRecord.result }
          : s
      )
    }
  })
  break
}

// 在渲染中添加PlanCard
{activePlan && <PlanCard plan={activePlan} />}
```

#### 2.3 添加进度通知

在页面顶部添加一个浮动的进度条，实时显示当前执行的步骤：

```typescript
// ProgressNotification.tsx
export function ProgressNotification({ plan }: { plan: Plan | null }) {
  if (!plan || plan.status === 'completed') return null

  const currentStep = plan.steps.find(s => s.status === 'in_progress')
  if (!currentStep) return null

  const stepIndex = plan.steps.indexOf(currentStep)
  const progress = ((stepIndex + 1) / plan.steps.length) * 100

  return (
    <div className="fixed top-4 right-4 z-50 bg-slate-800 rounded-lg shadow-lg p-4 max-w-sm">
      <div className="flex items-center gap-3">
        <div className="animate-spin">
          <span className="material-symbols-outlined text-primary">
            autorenew
          </span>
        </div>
        <div className="flex-1">
          <p className="text-sm font-medium text-white">
            正在执行: {currentStep.description}
          </p>
          <p className="text-xs text-slate-400">
            步骤 {stepIndex + 1}/{plan.steps.length}
          </p>
        </div>
      </div>
      <div className="mt-2 w-full bg-slate-700 rounded-full h-1">
        <div
          className="bg-primary h-1 rounded-full transition-all"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  )
}
```

## 实施步骤

### 阶段1: 快速修复 (1-2小时)
1. 修改`useChat.ts`中的plan事件处理
2. 测试plan步骤是否显示
3. 调整样式和文案

### 阶段2: 完整方案 (1-2天)
1. 创建`PlanCard`组件
2. 创建`ProgressNotification`组件
3. 集成到主界面
4. 添加动画和交互效果
5. 完整测试

### 阶段3: 增强功能 (可选)
1. Plan历史记录
2. 暂停/恢复功能
3. 步骤时间线视图
4. 导出Plan报告

## 预期效果

### 修复前
- ❌ 页面显示"0 steps"
- ❌ 用户不知道任务在执行什么
- ❌ 无法感知进度
- ❌ 不知道执行到哪一步了

### 修复后
- ✅ 显示完整的计划卡片
- ✅ 实时更新步骤状态
- ✅ 清晰的进度指示
- ✅ 每个步骤的执行结果可见
- ✅ 支持展开/折叠查看详情

## 测试验证

### 测试用例1: 简单任务
```
输入: "打开百度搜索天气并截图"
预期: 显示3步计划，每步完成后更新状态
```

### 测试用例2: 复杂任务
```
输入: "搜索OpenAI新闻，生成PDF，发送邮件"
预期: 显示5+步计划，支持折叠，显示详细信息
```

### 测试用例3: 错误处理
```
场景: 某步骤失败
预期: 显示失败状态，后续步骤标记为跳过
```

## 总结

**当前状态**:
- 后端Plan功能完善 ✅
- 前端展示缺失 ❌

**核心问题**:
- Plan事件被忽略
- 没有专门的UI组件

**解决方案**:
- 快速修复: 修改事件处理逻辑
- 完整方案: 创建专用Plan组件

**预期收益**:
- 用户体验大幅提升
- 任务执行过程透明化
- 增强用户对AI的信任感
