# Plan功能分析与改进建议

## 一、Plan功能代码分析

### 1. 后端实现 (Python)

#### 核心文件
- **定义文件**: `src/openakita/tools/definitions/plan.py`
- **处理器**: `src/openakita/tools/handlers/plan.py`

#### 主要功能
1. **create_plan**: 创建任务执行计划
   - 将多步骤任务拆分为独立的步骤
   - 每个步骤包含：id, description, tool, skills, status
   - 自动检测多步骤任务（通过动作词和连接词）

2. **update_plan_step**: 更新步骤状态
   - 状态：pending → in_progress → completed/failed/skipped
   - 记录执行结果和时间戳
   - 发送进度事件到前端

3. **get_plan_status**: 获取计划执行状态
   - 显示所有步骤及其状态
   - 统计完成/失败/待执行数量

4. **complete_plan**: 完成计划
   - 生成执行摘要和统计信息
   - 自动关闭计划

#### Plan检测逻辑
```python
def should_require_plan(user_message: str) -> bool:
    """
    触发条件：
    1. 包含 5+ 个动作词（明显的复杂任务）
    2. 包含 3+ 个动作词 + 连接词（明确的多步骤）
    3. 包含 3+ 个动作词 + 逗号分隔（明确的多步骤）
    """
```

#### Plan存储
- 保存位置：`data/plans/plan_{timestamp}_{id}.md`
- 格式：Markdown表格，包含步骤列表和执行日志

### 2. 前端实现 (TypeScript/React)

#### 核心文件
- **类型定义**: `webapps/seeagent-webui/src/types/step.ts`
- **API类型**: `webapps/seeagent-webui/src/types/api.ts`
- **事件处理**: `webapps/seeagent-webui/src/hooks/useChat.ts`
- **步骤展示**: `webapps/seeagent-webui/src/components/Step/StepCard.tsx`

#### 步骤类型
```typescript
export type StepType = 'llm' | 'tool' | 'skill' | 'thinking' | 'planning'
export type StepStatus = 'pending' | 'running' | 'completed' | 'failed'
```

#### SSE事件类型
```typescript
export type SSEEventType =
  | 'plan_created'
  | 'plan_step_updated'
  | 'tool_call_start'
  | 'tool_call_end'
  | ...
```

## 二、当前问题分析

### 问题1: Plan步骤不显示在前端

**原因**: 在`useChat.ts`的事件处理函数中（第413-417行），`plan_created`和`plan_step_updated`事件被标记为内部事件，直接break掉了：

```typescript
case 'plan_created':
case 'plan_step_updated':
case 'agent_switch':
  // These are internal events, don't create visible steps
  break
```

**影响**:
- 用户看不到计划的创建和执行进度
- 页面显示"0 steps"，无法感知任务进展
- 失去了Plan模式的可视化优势

### 问题2: 步骤过滤逻辑过于激进

在`step.ts`中定义了`INTERNAL_STEP_PATTERNS`，将plan相关的工具调用都标记为内部步骤：

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

这导致即使是`tool_call_start`/`tool_call_end`事件，如果工具名包含"plan"，也会被过滤掉。

## 三、改进建议

### 建议1: 添加Plan步骤的可视化展示

#### 方案A: 创建专门的Plan卡片组件

创建一个新的`PlanCard`组件，在对话流中显示计划概览：

```typescript
// PlanCard.tsx
export function PlanCard({ plan }: { plan: Plan }) {
  return (
    <div className="plan-card">
      <h3>📋 任务计划：{plan.task_summary}</h3>
      <div className="plan-steps">
        {plan.steps.map((step, index) => (
          <div key={step.id} className="plan-step">
            <span className="step-number">{index + 1}</span>
            <span className="step-status">{getStatusIcon(step.status)}</span>
            <span className="step-description">{step.description}</span>
            {step.result && <span className="step-result">{step.result}</span>}
          </div>
        ))}
      </div>
      <div className="plan-progress">
        进度: {completedCount}/{totalCount}
      </div>
    </div>
  )
}
```

#### 方案B: 在现有Step系统中集成Plan信息

修改`useChat.ts`中的事件处理，为plan事件创建特殊的步骤：

```typescript
case 'plan_created': {
  const planData = eventRecord.plan as Record<string, unknown>
  const newStep: Step = {
    id: generateStepId(),
    type: 'planning',
    status: 'running',
    title: `📋 计划创建：${planData.task_summary}`,
    summary: `共${planData.steps.length}个步骤`,
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

  // 更新或创建步骤卡片
  setSteps((prev) => {
    const existingStep = prev.find(s => s.id === stepId)
    if (existingStep) {
      return prev.map(s => s.id === stepId ? {
        ...s,
        status: mapPlanStatusToStepStatus(status),
        summary: result,
        endTime: status === 'completed' ? Date.now() : undefined,
      } : s)
    } else {
      // 创建新步骤
      return [...prev, {
        id: stepId,
        type: 'planning',
        status: mapPlanStatusToStepStatus(status),
        title: eventRecord.description as string || stepId,
        summary: result,
        startTime: Date.now(),
        category: 'core',
      }]
    }
  })
  break
}
```

### 建议2: 添加实时进度指示器

在主界面添加一个进度条或进度环，显示当前计划的执行进度：

```typescript
// ProgressIndicator.tsx
export function ProgressIndicator({ plan }: { plan: Plan | null }) {
  if (!plan) return null

  const total = plan.steps.length
  const completed = plan.steps.filter(s => s.status === 'completed').length
  const current = plan.steps.findIndex(s => s.status === 'in_progress') + 1

  return (
    <div className="progress-indicator">
      <div className="progress-bar">
        <div
          className="progress-fill"
          style={{ width: `${(completed / total) * 100}%` }}
        />
      </div>
      <div className="progress-text">
        {current > 0 && `正在执行第 ${current} 步：${plan.steps[current-1].description}`}
        <span className="progress-count">{completed}/{total}</span>
      </div>
    </div>
  )
}
```

### 建议3: 优化步骤展示逻辑

#### 3.1 区分Plan步骤和工具调用步骤

当前的步骤展示混合了：
- Plan的逻辑步骤（如"打开百度首页"）
- 实际的工具调用（如`browser_navigate`）

建议：
- Plan步骤作为"父步骤"显示
- 工具调用作为"子步骤"折叠在父步骤下

```typescript
interface Step {
  id: string
  type: StepType
  status: StepStatus
  title: string
  summary: string
  children?: Step[]  // 子步骤
  isPlanStep?: boolean  // 是否是Plan步骤
  planStepId?: string  // 关联的Plan步骤ID
}
```

#### 3.2 添加步骤时间线视图

在DetailPanel中添加时间线视图，清晰展示步骤的执行顺序和时间：

```typescript
// StepTimeline.tsx
export function StepTimeline({ steps }: { steps: Step[] }) {
  return (
    <div className="timeline">
      {steps.map((step, index) => (
        <div key={step.id} className="timeline-item">
          <div className="timeline-marker">
            <StepStatusIcon status={step.status} />
          </div>
          <div className="timeline-content">
            <div className="timeline-time">
              {formatTime(step.startTime)}
            </div>
            <div className="timeline-title">{step.title}</div>
            {step.duration && (
              <div className="timeline-duration">
                耗时: {(step.duration / 1000).toFixed(1)}s
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
```

### 建议4: 添加Plan管理功能

#### 4.1 Plan历史记录

在侧边栏添加Plan历史记录，用户可以查看之前执行的计划：

```typescript
// PlanHistory.tsx
export function PlanHistory() {
  const [plans, setPlans] = useState<Plan[]>([])

  useEffect(() => {
    // 从API加载历史计划
    fetch('/api/plans/history')
      .then(res => res.json())
      .then(data => setPlans(data))
  }, [])

  return (
    <div className="plan-history">
      <h3>计划历史</h3>
      {plans.map(plan => (
        <div key={plan.id} className="plan-item">
          <div className="plan-summary">{plan.task_summary}</div>
          <div className="plan-meta">
            {plan.steps.length}步 · {plan.status}
          </div>
        </div>
      ))}
    </div>
  )
}
```

#### 4.2 Plan暂停/恢复功能

允许用户暂停正在执行的计划，稍后恢复：

```typescript
// 在useChat.ts中添加
const pausePlan = useCallback(async () => {
  await apiPost('/chat/pause', {
    conversation_id: conversationId,
  })
}, [conversationId])

const resumePlan = useCallback(async () => {
  await apiPost('/chat/resume', {
    conversation_id: conversationId,
  })
}, [conversationId])
```

### 建议5: 改进后端事件发送

#### 5.1 发送plan_created事件

在`plan.py`的`_create_plan`方法中，确保发送`plan_created`事件：

```python
# 发送plan_created事件
try:
    session = getattr(self.agent, "_current_session", None)
    gateway = (
        session.get_metadata("_gateway")
        if session and hasattr(session, "get_metadata")
        else None
    )
    if gateway and hasattr(gateway, "emit_event"):
        await gateway.emit_event(session, {
            "type": "plan_created",
            "plan": {
                "id": plan_id,
                "task_summary": params.get('task_summary', ''),
                "steps": steps,
                "status": "in_progress",
            }
        })
except Exception as e:
    logger.warning(f"Failed to emit plan_created event: {e}")
```

#### 5.2 发送plan_step_updated事件

在`_update_step`方法中，发送详细的步骤更新事件：

```python
# 发送plan_step_updated事件
try:
    session = getattr(self.agent, "_current_session", None)
    gateway = (
        session.get_metadata("_gateway")
        if session and hasattr(session, "get_metadata")
        else None
    )
    if gateway and hasattr(gateway, "emit_event"):
        await gateway.emit_event(session, {
            "type": "plan_step_updated",
            "step_id": step_id,
            "status": status,
            "result": result,
            "description": step_desc,
            "step_number": step_number,
            "total_steps": total_count,
        })
except Exception as e:
    logger.warning(f"Failed to emit plan_step_updated event: {e}")
```

## 四、实现优先级

### P0 (必须实现)
1. **修复plan事件处理** - 让plan步骤在前端可见
2. **添加进度指示器** - 显示当前执行到哪一步

### P1 (重要)
3. **创建PlanCard组件** - 专门展示计划概览
4. **优化步骤展示** - 区分Plan步骤和工具调用

### P2 (可选)
5. **添加时间线视图** - 更清晰的执行历史
6. **Plan历史记录** - 查看之前的计划
7. **暂停/恢复功能** - 更好的控制能力

## 五、测试用例

### 测试1: 简单多步骤任务
```
用户输入: "打开百度搜索今天的天气，然后截图保存"
预期结果:
- 创建包含3个步骤的计划
- 前端显示计划卡片
- 每个步骤完成后更新状态
- 显示进度: 1/3, 2/3, 3/3
```

### 测试2: 复杂任务
```
用户输入: "搜索OpenAI最新新闻，生成PDF报告，然后发送邮件"
预期结果:
- 创建包含5+个步骤的计划
- 显示详细的步骤描述
- 支持步骤展开/折叠
- 显示每个步骤的耗时
```

### 测试3: 错误处理
```
场景: 某个步骤执行失败
预期结果:
- 步骤状态变为failed
- 显示错误信息
- 后续步骤标记为skipped
- 计划状态变为failed
```

## 六、总结

当前Plan功能的后端实现已经比较完善，包括：
- ✅ 自动检测多步骤任务
- ✅ 创建和管理计划
- ✅ 步骤状态跟踪
- ✅ 进度通知
- ✅ 计划持久化

但前端展示存在明显不足：
- ❌ Plan事件被忽略，不创建可见步骤
- ❌ 缺少专门的Plan可视化组件
- ❌ 没有进度指示器
- ❌ 步骤展示逻辑混乱

**核心改进方向**：
1. 修复事件处理，让plan步骤可见
2. 添加专门的Plan UI组件
3. 优化步骤展示的层次结构
4. 增强用户对计划执行的感知和控制

通过这些改进，可以让Plan模式真正发挥作用，为用户提供清晰的任务执行可视化。
