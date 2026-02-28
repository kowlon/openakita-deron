# Plan 模式 UI 修复项目

## 项目背景

当前 seeagent-webui 的 Plan 模式存在三个核心问题：

1. **时序问题**：Plan 卡片在步骤卡片之后才出现
2. **步骤不一致**：Plan 中的步骤和实际执行的步骤不对应，显示了内部步骤
3. **上下文丢失**：ask_user 回答后 Plan 模式上下文丢失

## Plan 模式预期行为

### 1. Plan 卡片优先显示
- `plan_created` 事件触发时，立即显示 Plan 卡片
- 清除所有预计划步骤（失败的尝试、create_plan 等）
- Plan 卡片始终在步骤列表之前

### 2. 步骤一致性
- Plan 卡片中的步骤与实际执行步骤完全对应
- 内部步骤被过滤（create_plan, update_plan_step, complete_plan 等）
- 步骤标题使用 Plan 步骤描述，而不是工具名

### 3. ask_user 上下文保持
- 用户回答作为当前对话延续，不是新消息
- `activePlan` 状态保持不变
- 已执行的步骤保留
- 回答后继续执行 Plan 中的剩余步骤

## 技术架构

### 前端事件流

```
1. 用户发送消息 → sendMessage()
2. 后端处理（可能先尝试直接执行）
3. 后端创建 Plan → plan_created 事件
4. 前端接收 → setActivePlan() + setSteps([])
5. 后端执行步骤 → tool_call_start/end 事件
6. 前端显示步骤（使用 Plan 步骤描述）
7. 如果触发 ask_user → 显示问题
8. 用户回答 → sendMessage(answer, isAskUserAnswer=true)
9. 继续执行（保持 activePlan 和 steps）
```

### 关键数据结构

```typescript
// Plan 状态
interface Plan {
  id: string
  task_summary: string
  steps: PlanStep[]
  status: 'in_progress' | 'completed' | 'failed'
  created_at: string
}

// Plan 步骤
interface PlanStep {
  id: string
  description: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'skipped'
  result?: string
  completed_at?: string
}

// 执行步骤
interface Step {
  id: string
  title: string  // 使用 Plan 步骤的 description
  category: 'core' | 'internal'  // internal 不显示
  outputData?: {
    planStepId?: string  // 关联到 Plan 步骤
    originalToolName?: string
  }
}
```

## 当前实现状态

### 已完成
- ✅ Plan 类型定义
- ✅ PlanCard 组件
- ✅ plan_created/plan_step_updated 事件处理
- ✅ 工具名映射
- ✅ 步骤分类
- ✅ ask_user 回答参数

### 存在问题
- ❌ 前端无法显示任何内容（SSE 事件处理问题）
- ❌ plan_created 时清除步骤的逻辑需要验证
- ❌ categorizeStep 对 create_plan 的过滤需要验证
- ❌ ask_user 回答后的状态保持需要验证

## Phase 划分

### Phase 1: 诊断和修复核心渲染问题 (1 个任务)
- TASK-001: 诊断前端渲染问题

### Phase 2: Plan 卡片显示和步骤过滤 (3 个任务)
- TASK-101: 验证并修复 plan_created 事件处理
- TASK-102: 验证并修复步骤过滤逻辑
- TASK-103: 验证并修复 Plan 步骤与执行步骤关联

### Phase 3: ask_user 上下文保持 (1 个任务)
- TASK-201: 验证并修复 ask_user 上下文保持

### Phase 4: UI 优化和测试 (2 个任务)
- TASK-301: 优化 PlanCard 显示和交互
- TASK-302: 添加端到端测试

## 预计时间

- Phase 1: 2-4 小时
- Phase 2: 4-7 小时
- Phase 3: 2-3 小时
- Phase 4: 6-9 小时

**总计**: 14-23 小时（约 2-3 天）
