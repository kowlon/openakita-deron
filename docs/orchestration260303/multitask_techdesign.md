# OpenAkita 多任务编排技术设计文档

> 版本: v3.2  
> 日期: 2026-03-06  
> 状态: 设计定稿（已合并迭代）  
> 更新: 引入 LLM 上下文决策、任务激活管理、任务卡片投影层

---

## 1. 设计背景与目标

### 1.1 已落地主架构（保持不变）

- MainAgent 作为统一路由入口。
- TaskOrchestrator 负责任务生命周期与执行编排。
- TaskSession 负责步骤调度与上下文传递。
- SubAgent 以独立进程 Agent 形式执行步骤任务。

### 1.2 本次合并目标

1. 由规则路由升级为 LLM 上下文决策。
2. 引入多会话任务激活管理（支持抢占、显式激活、出域、恢复）。
3. 引入任务卡片投影层，统一“首大后简”展示策略。
4. 独立维护路由与场景触发 Prompt。
5. 保持执行层稳定，避免破坏现有任务执行链路。

---

## 2. 架构总览

### 2.1 分层模型

```
┌─────────────────────────────────────────────────────────────────┐
│ Entry Layer                                                      │
│   Agent.chat / WebUI / API                                      │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Decision Layer                                                   │
│   OrchestrationDecisionEngine                                   │
│   ├─ ScenarioDetector                                           │
│   └─ StepRouter                                                 │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Activation Layer                                                 │
│   TaskActivationManager                                         │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Execution Layer                                                  │
│   TaskOrchestrator -> TaskSession -> SubAgentManager            │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Projection Layer                                                 │
│   TaskCardProjectionService + OrchestrationEventPublisher       │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 设计原则

- 高内聚：决策、激活、投影、执行职责分离。
- 低耦合：层间通过结构化模型通信，不共享隐式状态。
- 渐进替换：保留规则降级开关，分阶段切主路径。

---

## 3. 执行层基线设计（延续 v3.1）

### 3.1 SubAgent 执行形态

- SubAgent 是独立进程内的完整 Agent 实例。
- 与 MainAgent 共享模型配置/Brain 代理，不共享运行时对象。
- 每个 SubAgent 拥有独立 ReasoningEngine、工具执行上下文与对话历史。

### 3.2 场景与步骤定义

- 一个场景 YAML 对应一个最佳实践。
- 场景内多个 `steps` 对应多个步骤 SubAgent 配置来源。
- `step_def.system_prompt` 保持作为步骤执行 Prompt 的唯一配置来源。

### 3.3 上下文传递

- Step N 输出写入 TaskSession context。
- Step N+1 自动注入依赖上下文执行。
- 用户确认后才固化为可传递输出。

---

## 4. 决策层设计

### 4.1 OrchestrationDecisionEngine

#### 4.1.1 职责

- 统一判定消息是普通对话还是任务对话。
- 判定是否触发新场景。
- 判定是否激活已有任务。
- 判定任务内路由目标步骤。
- 判定输入是否满足步骤前置条件。

#### 4.1.2 输入

- 用户消息与近期对话摘要。
- 会话任务列表与任务激活状态。
- 当前激活任务与步骤状态。
- 卡片交互上下文（点击激活、切换意图）。

#### 4.1.3 输出模型

`OrchestrationDecision`：

- `route_type`: `NORMAL_CHAT | START_SCENARIO | ACTIVATE_TASK | ACTIVE_STEP | ASK_USER`
- `scenario_id`
- `target_task_id`
- `target_step_id`
- `confidence`
- `missing_inputs`
- `reason`

#### 4.1.4 路由优先级

1. 显式激活目标（用户点击卡片或明确指令）
2. 命中已有任务
3. 触发新场景
4. 普通对话

### 4.2 ScenarioDetector

- 使用独立 Prompt 判定是否应创建新最佳实践任务。
- 产出 `scenario_id + confidence + reason`。
- 低置信度或冲突场景时返回 `ASK_USER` 建议。

### 4.3 StepRouter

- 在活跃任务内判定目标步骤。
- 对未激活步骤先触发步骤激活再分发。
- 对输入不足返回 `ASK_USER`，并输出缺失字段列表。

---

## 5. 激活层设计

### 5.1 TaskActivationManager

#### 5.1.1 职责

- 管理会话内激活任务映射。
- 管理全局焦点任务。
- 处理抢占、出域、显式激活、恢复。

#### 5.1.2 状态模型

`ActivationState`：

- `ACTIVE`
- `EXPLICIT_ACTIVE`
- `OUT_OF_FOCUS`
- `INACTIVE`

`TaskStatus` 与 `ActivationState` 正交维护。

#### 5.1.3 核心存储

- `session_active_task: dict[session_id, task_id]`
- `task_activation_state: dict[task_id, ActivationState]`
- `global_active_task_id: str | None`

#### 5.1.4 核心接口

- `activate_task(session_id, task_id, reason, explicit=False)`
- `preempt_with_new_task(session_id, new_task_id, reason)`
- `get_session_active_task(session_id)`
- `list_session_tasks(session_id, include_inactive=True)`
- `deactivate_task(task_id, reason)`

---

## 6. 投影层设计

### 6.1 TaskCardProjectionService

#### 6.1.1 职责

- 将编排与状态变化投影为前端可渲染卡片事件。
- 管理“首大后简”展示策略。

#### 6.1.2 规则

- 会话内同一 `task_id` 首次出现，发布 `task_card_created`。
- 同一任务后续相关轮次，发布 `task_card_compact`。
- 普通对话不发布任务卡片事件。

### 6.2 OrchestrationEventPublisher

- 负责按 sequence 发布结构化事件。
- 保证事件可排序、可幂等消费。

---

## 7. Prompt 独立管理设计

### 7.1 管理范围

仅管理以下两类 Prompt：

1. MainAgent -> SubAgent 路由判定 Prompt
2. 最佳实践触发判定 Prompt

SubAgent 步骤 Prompt 不迁移，继续保留在场景 YAML。

### 7.2 推荐目录

- `prompts/orchestration/route_step.md`
- `prompts/orchestration/detect_scenario.md`

### 7.3 加载策略

- 支持版本化与热更新。
- 加载失败自动回退本地默认模板。
- 记录加载版本与生效来源。

---

## 8. 关键时序

### 8.1 对话主流程

1. `Agent.chat` 调用编排入口。
2. `DecisionEngine.decide(...)` 输出决策。
3. `TaskOrchestrator.execute_decision(...)` 执行。
4. `TaskActivationManager` 更新激活状态。
5. `TaskCardProjectionService` 投影卡片事件。
6. 返回文本响应与结构化事件。

### 8.2 新场景抢占流程

1. 判定 `START_SCENARIO`
2. 创建新任务
3. `preempt_with_new_task`：旧任务 -> `OUT_OF_FOCUS`
4. 新任务 -> `ACTIVE/EXPLICIT_ACTIVE`
5. 发布 `task_activation_changed` 与 `task_out_of_focus`

### 8.3 卡片显式激活流程

1. 前端点击任务卡片
2. 调用 `POST /api/tasks/{task_id}/activate`
3. 更新激活态并刷新会话焦点
4. 发布 `task_activation_changed`
5. 后续任务对话路由至被激活任务

---

## 9. 数据模型

### 9.1 新增模型

`TaskActivationRecord`：

- `task_id`
- `session_id`
- `activation_state`
- `activated_at`
- `activated_by` (`system | user | llm`)
- `reason`

`OrchestrationDecision`：

- 决策输出结构（见 4.1.3）

### 9.2 现有模型扩展

`TaskState` 新增只读投影字段：

- `activation_state`
- `is_explicitly_activated`

---

## 10. API 与事件协议

### 10.1 REST API

```
POST   /api/tasks                            # 创建任务
GET    /api/tasks                            # 查询任务（支持 session_id / include_inactive）
GET    /api/tasks/{task_id}                  # 任务详情
DELETE /api/tasks/{task_id}                  # 取消任务
POST   /api/tasks/{task_id}/confirm          # 确认步骤
POST   /api/tasks/{task_id}/activate         # 激活任务（新增）
GET    /api/sessions/{session_id}/active-task # 查询会话激活任务（新增）
GET    /api/scenarios                        # 场景列表
GET    /api/scenarios/{scenario_id}          # 场景详情
POST   /api/scenarios/{scenario_id}/start    # 手动启动场景
```

### 10.2 SSE 事件

- `task_card_created`
- `task_card_compact`
- `task_activation_changed`
- `task_out_of_focus`
- `orchestration_decision`（调试开关）

统一字段：

- `session_id`
- `task_id`
- `event_id`
- `sequence`
- `timestamp`

---

## 11. 模块集成点

### 11.1 Agent 集成

- 重构 `_try_orchestration_route` 为“决策 + 执行”模式。

### 11.2 TaskOrchestrator 集成

新增：

- `execute_decision(decision, message, session_id)`
- `activate_task(task_id, session_id, reason, explicit=False)`

保留：

- `create/start/dispatch/confirm/cancel`

### 11.3 ScenarioRegistry 集成

- 保留注册与查询职责。
- 对话匹配职责迁移到 `ScenarioDetector`，Registry 不再承担主路径匹配决策。

### 11.4 前端集成

- `useTasks` 支持按 `session_id` 过滤。
- `activeTask` 由会话激活任务接口驱动。
- `TaskCard` 增加激活点击行为与抢占提示态。

---

## 12. 迁移计划

### Phase A：激活管理基座

- 引入 TaskActivationManager
- 新增激活 API 与状态同步
- 前端接入显式激活

### Phase B：卡片投影统一

- 引入 TaskCardProjectionService
- 落地首大后简策略
- 统一事件协议

### Phase C：LLM 场景判定替换

- 接入 ScenarioDetector
- 保留规则降级

### Phase D：LLM 步骤路由替换

- 接入 StepRouter
- 输入校验不满足时走 `ASK_USER`

### Phase E：完全切换与收敛

- 关闭规则主路径
- 建立观测与误判回流闭环

---

## 13. 风险与控制

### 13.1 任务频繁抢占

- 控制：最短激活窗口 + 显式激活优先策略

### 13.2 事件乱序导致 UI 抖动

- 控制：`sequence` 顺序控制 + 前端幂等合并

### 13.3 LLM 误判

- 控制：置信度阈值 + `ASK_USER` 兜底 + 规则降级开关

### 13.4 多会话串扰

- 控制：会话级过滤 + 激活 API 强校验 `session_id`

---

## 14. 验收标准

### 14.1 功能验收

- 新任务可正确抢占旧任务，旧任务进入 `OUT_OF_FOCUS`。
- 用户点击任务卡片后可稳定激活并继续执行。
- 聊天区实现首轮大卡片与后续简洁卡片策略。
- 任务相关消息可路由到正确任务与步骤。

### 14.2 工程验收

- 决策、激活、投影模块职责清晰且可单测。
- 路由决策日志可观测。
- 降级链路可一键启停。

---

## 15. 设计结论

本版在不改变主执行架构前提下，完成以下增强：

1. 决策层：LLM 上下文判定替代规则主路径  
2. 激活层：多会话任务激活与抢占管理  
3. 投影层：任务卡片事件化与首大后简策略

该方案兼顾兼容性、可维护性与可扩展性，可作为后续实施与验收的唯一设计基线。
