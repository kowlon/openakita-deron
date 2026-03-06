# OpenAkita 多任务编排技术设计（迭代版，相对 v3.1）

> 基线文档：`multitask_techdesign.md`  
> 版本：v3.2（迭代）  
> 日期：2026-03-06  
> 状态：设计定稿（待实施）

---

## 1. 设计背景与迭代目标

本迭代针对 v3.1 中以下不足进行增强：

1. 任务路由仍以规则匹配为主，语义理解不足
2. 会话内仅支持单任务映射，缺少“显式激活/出域/恢复”机制
3. 任务卡片缺乏事件驱动的统一展示协议
4. 路由与场景触发 Prompt 缺少独立维护机制

### 1.1 迭代目标

- 引入 LLM 驱动的上下文路由决策
- 引入多会话任务激活管理器（TaskActivationManager）
- 引入任务卡片投影层（TaskCardProjection）
- 建立路由与场景触发 Prompt 的独立仓库
- 保持现有执行层（TaskSession/SubAgentManager）稳定

---

## 2. 总体架构增量

在 v3.1 架构基础上新增三层能力：

1. **Decision Layer（决策层）**
   - `OrchestrationDecisionEngine`
   - `ScenarioDetector`
   - `StepRouter`
2. **Activation Layer（激活层）**
   - `TaskActivationManager`
3. **Projection Layer（投影层）**
   - `TaskCardProjectionService`
   - `OrchestrationEventPublisher`

执行层保持不变：`TaskOrchestrator -> TaskSession -> SubAgentManager`。

---

## 3. 核心设计原则

### 3.1 高内聚

- 决策逻辑集中在 DecisionEngine，不散落在 Agent/Orchestrator
- 激活状态集中在 ActivationManager，不混入 TaskStatus 生命周期
- 卡片形态逻辑集中在 ProjectionService，不写进业务路由

### 3.2 低耦合

- 决策层输出结构化结果，执行层只消费结果
- 路由与场景触发 Prompt 内容与业务代码分离
- 事件协议与 UI 组件解耦，前端只消费事件模型

### 3.3 渐进替换

- 保留规则匹配降级链路（feature flag）
- 支持分阶段切主路径

---

## 4. 关键模块设计

### 4.1 TaskActivationManager

#### 4.1.1 职责

- 管理会话内任务激活关系
- 管理全局焦点任务
- 处理抢占、显式激活、出域、恢复

#### 4.1.2 核心状态

- `session_active_task: dict[session_id, task_id]`
- `task_activation_state: dict[task_id, ActivationState]`
- `global_active_task_id: str | None`

#### 4.1.3 ActivationState

- `ACTIVE`
- `EXPLICIT_ACTIVE`
- `OUT_OF_FOCUS`
- `INACTIVE`

#### 4.1.4 核心接口

- `activate_task(session_id, task_id, reason, explicit=False)`
- `preempt_with_new_task(session_id, new_task_id, reason)`
- `get_session_active_task(session_id)`
- `list_session_tasks(session_id, include_inactive=True)`
- `deactivate_task(task_id, reason)`

---

### 4.2 OrchestrationDecisionEngine

#### 4.2.1 职责

统一处理以下判定：

- 是否命中新场景
- 是否应切换到已有任务
- 活跃任务内应路由到哪个步骤
- 当前输入是否满足步骤执行前置条件

#### 4.2.2 输入上下文

- 用户消息
- 会话任务列表及激活状态
- 当前激活任务状态与步骤状态
- 近期对话摘要（含任务卡片交互信息）

#### 4.2.3 输出模型

`OrchestrationDecision`：

- `route_type`: `NORMAL_CHAT | START_SCENARIO | ACTIVATE_TASK | ACTIVE_STEP | ASK_USER`
- `target_task_id`
- `target_step_id`
- `scenario_id`
- `confidence`
- `missing_inputs`
- `reason`

---

### 4.3 TaskCardProjectionService

#### 4.3.1 职责

- 将任务状态变更投影为前端可渲染卡片事件
- 管理“首大后简”展示策略

#### 4.3.2 规则

- 会话内 `task_id` 首次出现：发 `task_card_created`（大卡片）
- 后续任务相关轮次：发 `task_card_compact`（简洁卡片）

#### 4.3.3 投影输入

- 决策结果
- 任务快照
- 历史投影记录（会话维度）

---

### 4.4 PromptRepository（路由与场景触发 Prompt 管理）

#### 4.4.1 目录建议

- `prompts/orchestration/route_step.md`
- `prompts/orchestration/detect_scenario.md`

#### 4.4.2 设计要点

- 本迭代仅管理两类 Prompt：
  - MainAgent -> SubAgent 路由判定 Prompt
  - 最佳实践触发判定 Prompt
- SubAgent 步骤 Prompt 继续保留在场景 YAML（`step_def.system_prompt`）
- Prompt 支持热更新与版本化
- Prompt 加载失败时可回退到本地默认模板

---

## 5. 核心时序设计

### 5.1 对话消息处理主流程（新）

1. `Agent.chat` 调用编排入口
2. `DecisionEngine.decide(...)` 产出结构化决策
3. `TaskOrchestrator.execute_decision(...)` 执行决策
4. `TaskActivationManager` 更新激活态
5. `TaskCardProjectionService` 发卡片事件
6. 返回文本响应与结构化事件

### 5.2 新场景抢占流程

1. 判定 `START_SCENARIO`
2. 创建新任务
3. `preempt_with_new_task`：旧任务 -> `OUT_OF_FOCUS`
4. 新任务 -> `ACTIVE/EXPLICIT_ACTIVE`
5. 输出 `task_activation_changed` + `task_out_of_focus`

### 5.3 卡片显式激活流程

1. 前端点击任务卡片
2. 调用 `POST /api/tasks/{task_id}/activate`
3. 激活管理器更新状态
4. 输出 `task_activation_changed`
5. 后续任务对话路由到该任务

---

## 6. 数据结构与模型变更

### 6.1 模型新增

#### ActivationState

- 新增激活态枚举（独立于 TaskStatus）

#### TaskActivationRecord

- `task_id`
- `session_id`
- `activation_state`
- `activated_at`
- `activated_by`（`system` / `user` / `llm`）
- `reason`

#### OrchestrationDecision

- 决策结构（见 4.2.3）

### 6.2 现有模型扩展建议

`TaskState` 可补充只读投影字段：

- `activation_state`
- `is_explicitly_activated`

---

## 7. API 与事件协议增量

### 7.1 REST API 新增

#### 激活任务

- `POST /api/tasks/{task_id}/activate`
- request:
  - `session_id`
  - `reason`
- response:
  - `task_id`
  - `session_id`
  - `activation_state`

#### 查询会话激活任务

- `GET /api/sessions/{session_id}/active-task`

#### 会话任务列表

- `GET /api/tasks?session_id={id}&include_inactive=true`

---

### 7.2 SSE 事件新增

- `task_card_created`
- `task_card_compact`
- `task_activation_changed`
- `task_out_of_focus`
- `orchestration_decision`（调试开关下输出）

事件统一字段：

- `session_id`
- `task_id`
- `event_id`
- `sequence`
- `timestamp`

---

## 8. 与现有模块的集成点

### 8.1 Agent 集成点

- 重构 `_try_orchestration_route`：
  - 从“硬编码分支”改为“决策 + 执行”

### 8.2 TaskOrchestrator 集成点

- 新增：
  - `execute_decision(decision, message, session_id)`
  - `activate_task(task_id, session_id, reason, explicit=False)`
- 现有 `create/start/dispatch/confirm/cancel` 保持

### 8.3 ScenarioRegistry 集成点

- 保留注册与查询职责
- 匹配职责转移至 `ScenarioDetector`

### 8.4 前端集成点

- `useTasks` 按 `session_id` 过滤任务
- `App` 中 `activeTask` 由“会话激活任务接口”驱动
- `TaskCard` 增加激活点击事件

---

## 9. 迁移实施计划

### Phase A：激活管理基座

- 引入 `TaskActivationManager`
- 新增激活 API 与状态同步
- 前端接入卡片点击激活

### Phase B：卡片投影统一

- 引入 `TaskCardProjectionService`
- 落地首大后简策略
- 统一事件协议

### Phase C：LLM 场景判定替换

- 接入 `ScenarioDetector`
- 保留规则匹配降级

### Phase D：LLM 步骤路由替换

- 接入 `StepRouter` 与输入校验
- 支持 `ASK_USER`

### Phase E：完全切换与收敛

- 关闭规则主路径
- 建立观测看板与误判回流闭环

---

## 10. 风险与控制

### 10.1 任务频繁抢占

- 控制：最短激活窗口 + 显式激活优先

### 10.2 事件乱序导致 UI 抖动

- 控制：事件 `sequence` + 前端幂等合并

### 10.3 LLM 误判

- 控制：置信度阈值 + ASK_USER 兜底 + 规则降级开关

### 10.4 多会话串扰

- 控制：会话级过滤 + 激活 API 强校验 `session_id`

---

## 11. 验收标准

### 11.1 功能验收

- 新任务可正确抢占旧任务，旧任务进入 `OUT_OF_FOCUS`
- 用户点击任务卡片后可稳定激活并继续执行
- 聊天区实现首轮大卡片与后续简洁卡片策略
- 任务相关消息均可被路由到正确任务与步骤

### 11.2 工程验收

- 决策、激活、投影模块职责清晰且可单测
- 路由决策日志可观测
- 降级链路可一键启停

---

## 12. 设计结论

相对 v3.1，本迭代不改变“MainAgent 为路由中心、TaskSession 为执行核心、SubAgent 独立进程执行”的主架构，只补充：

1. 决策层（LLM 上下文判定）
2. 激活层（多会话任务激活管理）
3. 投影层（任务卡片事件化）

该方案在保持兼容性的同时，显著提升任务路由准确性、会话交互一致性与系统可维护性。
