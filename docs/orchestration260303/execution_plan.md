# 多任务编排实现计划

> 日期: 2026-03-04
> 基于: docs/orchestration260303/ 下的需求与技术设计文档

---

## 1. 需求分析

### 1.1 核心目标
建立一套多任务编排机制：识别最佳实践场景 → 拆解为多步骤任务 → 逐步执行 → 用户可编辑与确认。

### 1.2 核心角色
- **MainAgent**: 对话入口与路由中心；负责场景匹配、任务创建、消息路由
- **SubAgent**: 步骤执行代理；独立进程、独立对话历史、完整推理能力
- **TaskSession**: 任务会话；管理任务生命周期、步骤会话、上下文传递

### 1.3 现有架构分析
- `orchestration/worker.py`: WorkerAgent 是独立进程 Agent，内部创建完整 Agent 实例
- `orchestration/messages.py`: 定义了 AgentMessage, TaskPayload, TaskResult 等消息协议
- `core/agent_state.py`: 定义了 TaskState, AgentState 状态管理
- SubAgent 将复用 WorkerAgent 的独立进程架构，通过配置区分行为

---

## 2. 实现范围

- Phase 1-5 完整实现
- 创建一个简单场景用于测试验证
- 同步编写单元测试

---

## 3. 详细任务拆分

### Phase 1: 基础框架 (预计 3 天)

#### T1.1 实现状态定义 `task/state.py`
**依赖**: 无

**任务内容**:
1. 创建 `src/openakita/orchestration/task/` 目录
2. 实现 `TaskStatus` 枚举 (扩展):
   - PENDING, RUNNING, WAITING_USER, COMPLETED, CANCELLED
3. 实现 `StepStatus` 枚举:
   - PENDING, RUNNING, WAITING_CONFIRM, COMPLETED, FAILED, SKIPPED
4. 实现 `StepState` 数据类:
   - step_id, status, started_at, completed_at, error_message
5. 实现 `MultiTaskState` 数据类 (扩展 TaskState):
   - scenario_id, current_step_id, steps, context (步骤间传递)
6. 编写单元测试 `tests/orchestration/task/test_state.py`

**关键设计**:
- 继承/组合现有 `TaskState`，保持向后兼容
- 使用 dataclass 定义，支持序列化

---

#### T1.2 实现步骤定义 `task/step.py`
**依赖**: T1.1

**任务内容**:
1. 实现 `StepDefinition` 数据类:
   - step_id, name, description
   - system_prompt (SubAgent 专用)
   - tools (允许的工具列表)
   - skills (提示词侧能力约束)
   - input_schema, output_key
   - requires_user_confirm, allow_user_edit
   - condition (执行条件函数)
2. 实现 `StepSession` 数据类:
   - step_id, status, messages (快照)
   - sub_agent_id (独立进程标识)
   - agent_config (SubAgentConfig)
   - input_data, output_data
   - user_edited, edit_content
3. 编写单元测试 `tests/orchestration/task/test_step.py`

**关键设计**:
- StepSession 是步骤执行的运行时状态
- sub_agent_id 指向独立进程的 SubAgent

---

#### T1.3 实现场景定义与注册表 `task/scenario.py`
**依赖**: T1.2

**任务内容**:
1. 实现 `ScenarioTrigger` 枚举:
   - DIALOG (对话触发), MANUAL (手动触发), BOTH
2. 实现 `ScenarioDefinition` 数据类:
   - scenario_id, name, description, category
   - trigger (触发方式)
   - steps (步骤列表)
   - trigger_keywords (关键词)
   - trigger_patterns (正则模式)
   - metadata
3. 实现 `ScenarioRegistry` 类:
   - `register(scenario)`: 注册场景
   - `get(scenario_id)`: 获取场景
   - `match_from_dialog(message)`: 从对话匹配场景
   - `list_all()`: 列出所有场景
   - `list_by_category(category)`: 按分类列出
4. 编写单元测试 `tests/orchestration/task/test_scenario.py`

**关键设计**:
- 匹配逻辑：正则模式优先，关键词次之
- 支持动态注册场景

---

### Phase 2: 编排核心 (预计 4 天)

#### T2.1 实现任务会话 `task/session.py`
**依赖**: T1.1, T1.2

**任务内容**:
1. 实现 `TaskSession` 类:
   - 属性:
     - state: MultiTaskState
     - scenario: ScenarioDefinition
     - step_sessions: dict[str, StepSession]
     - context: dict (步骤间传递)
     - mode: "step" | "free"
   - 方法:
     - `dispatch_step(message)`: 向当前步骤 SubAgent 发送请求
     - `dispatch_step_to(step_id, message)`: 向指定步骤发送请求
     - `complete_step(step_id)`: 完成步骤，生成输出
     - `switch_to_step(step_id)`: 切换到指定步骤
     - `switch_to_free_mode()`: 切换到自由模式
     - `switch_to_step_mode()`: 切换到步骤模式
     - `_create_step_session(step_id)`: 创建步骤会话
     - `_build_step_prompt(step_session)`: 构建步骤系统提示词
2. 编写单元测试 `tests/orchestration/task/test_session.py`

**关键设计**:
- `_build_step_prompt` 自动注入前置步骤输出
- 支持多轮对话（SubAgent 维护完整历史）

---

#### T2.2 实现 SubAgent 配置 `task/config.py`
**依赖**: T1.2

**任务内容**:
1. 实现 `CapabilitiesConfig` 数据类:
   - allow_shell, allow_write
2. 实现 `RuntimeConfig` 数据类:
   - max_iterations, session_type, memory_policy, prompt_budget
3. 实现 `SubAgentConfig` 数据类:
   - subagent_id, name, description, system_prompt
   - allowed_tools, skills
   - capabilities, runtime
   - process_mode ("WORKER")
   - brain_mode ("SHARED_PROXY" | "INDEPENDENT")
4. 实现 `SubAgentConfigLoader` 类:
   - `load(config_path)`: 从 YAML 加载配置
   - `parse(raw_dict)`: 解析配置字典
   - `_resolve_tools(tools_config)`: 解析工具列表
   - `_apply_capabilities(tools, capabilities)`: 应用能力限制
5. 编写单元测试 `tests/orchestration/task/test_config.py`

**关键设计**:
- tools/mcp_tools 为可执行集合
- skills 仅注入提示词，不自动变成可执行工具

---

#### T2.3 实现 SubAgent 管理器 `task/subagent_manager.py`
**依赖**: T2.2

**任务内容**:
1. 实现 `SubAgentManager` 类:
   - 属性:
     - _main_agent: Agent 引用
     - _sub_agents: dict[str, str] (step_id -> sub_agent_id)
   - 方法:
     - `spawn_sub_agent(step_id, config)`: 创建 SubAgent 进程
     - `destroy_sub_agent(step_id)`: 销毁 SubAgent
     - `send_step_request(sub_agent_id, messages, system_prompt, session_id)`: 发送步骤请求
     - `get_sub_agent(step_id)`: 获取 SubAgent 标识
     - `destroy_all()`: 销毁所有 SubAgent
2. 复用 WorkerAgent 架构:
   - 使用 ZMQ 消息通信
   - 共享模型配置/Brain 代理
3. 编写单元测试 `tests/orchestration/task/test_subagent_manager.py`

**关键设计**:
- SubAgent 以独立进程运行
- 与 WorkerAgent 架构统一

---

#### T2.4 实现任务编排器 `task/orchestrator.py`
**依赖**: T1.3, T2.1, T2.3

**任务内容**:
1. 实现 `TaskOrchestrator` 类:
   - 属性:
     - scenario_registry: ScenarioRegistry
     - sub_agent_manager: SubAgentManager
     - agent: Agent 引用
     - _tasks: dict[str, TaskSession]
     - _session_tasks: dict[str, str] (session_id -> task_id)
   - 方法:
     - `create_task(scenario_id, session_id, initial_message)`: 创建任务
     - `create_task_from_dialog(message, session_id)`: 从对话创建任务
     - `start_task(task_id)`: 启动任务
     - `confirm_step(task_id, step_id)`: 确认步骤
     - `cancel_task(task_id)`: 取消任务
     - `get_task(task_id)`: 获取任务
     - `get_active_task(session_id)`: 获取会话活跃任务
     - `complete_task(task_id)`: 完成任务
2. 编写单元测试 `tests/orchestration/task/test_orchestrator.py`

**关键设计**:
- 任务创建时初始化所有步骤的 StepSession
- 支持任务取消时清理资源

---

#### T2.5 实现消息路由器 `task/router.py`
**依赖**: T2.4

**任务内容**:
1. 实现 `MessageRouter` 类:
   - 属性:
     - main_agent: Agent
     - task_orchestrator: TaskOrchestrator
     - scenario_registry: ScenarioRegistry
   - 方法:
     - `route(message, session_id)`: 路由用户消息
       - 有活跃任务 → 路由到 SubAgent
       - 场景匹配成功 → 创建任务，路由到 SubAgent
       - 普通对话 → MainAgent 处理
     - `_route_to_subagent(task, message)`: 路由到 SubAgent
     - `_handle_normal_chat(message, session_id)`: 普通对话
2. 编写单元测试 `tests/orchestration/task/test_router.py`

**关键设计**:
- MainAgent 作为路由中心
- 自动路由，无需用户干预

---

### Phase 3: 系统集成 (预计 3 天)

#### T3.1 Agent 类扩展
**依赖**: T2.4, T2.5

**任务内容**:
1. 在 `core/agent.py` 中新增:
   - `_scenario_registry: ScenarioRegistry`
   - `_task_orchestrator: TaskOrchestrator`
   - `_sub_agent_manager: SubAgentManager`
   - `_message_router: MessageRouter`
2. 新增 `_init_multitask()` 方法
3. 修改 `chat()` 方法支持自动路由
4. 编写集成测试

**关键设计**:
- 通过配置开关控制是否启用多任务
- 保持向后兼容

---

#### T3.2 工具可见集合裁剪
**依赖**: T2.3

**任务内容**:
1. 实现工具过滤逻辑:
   - 根据 SubAgentConfig.allowed_tools 过滤
   - 根据 capabilities (allow_shell, allow_write) 过滤
2. 修改 ToolExecutor 支持工具白名单
3. 编写单元测试

---

#### T3.3 与现有 WorkerAgent 架构统一验证
**依赖**: T2.3

**任务内容**:
1. 验证 SubAgent 进程创建流程
2. 验证 ZMQ 通信
3. 验证 Brain 共享/代理模式
4. 编写集成测试

---

### Phase 4: API 与前端 (预计 3 天)

#### T4.1 REST API 实现
**依赖**: T2.4

**任务内容**:
1. 实现任务管理 API:
   - `POST /api/tasks`: 创建任务
   - `GET /api/tasks`: 列出活跃任务
   - `GET /api/tasks/{task_id}`: 获取任务详情
   - `DELETE /api/tasks/{task_id}`: 取消任务
   - `POST /api/tasks/{task_id}/confirm`: 确认步骤
2. 实现场景查询 API:
   - `GET /api/scenarios`: 列出所有场景
   - `GET /api/scenarios/{scenario_id}`: 获取场景详情
3. 编写 API 测试

---

#### T4.2 WebSocket 事件推送
**依赖**: T4.1

**任务内容**:
1. 定义事件类型:
   - task.created, task.started, task.completed, task.cancelled
   - step.started, step.completed, step.waiting
2. 实现事件推送机制
3. 编写测试

---

#### T4.3 前端集成
**依赖**: T4.1, T4.2

**任务内容**:
1. 左侧面板: 最佳实践任务列表
2. 中间面板: 任务卡片展示
3. 右侧面板: 步骤详情与编辑
4. 与现有 seeagent 布局一致

---

#### T4.4 前端可视化测试 (Playwright)
**依赖**: T4.3

**任务内容**:
参考现有 `e2e/plan-mode.spec.ts` 编写多任务编排的 E2E 测试。

**测试文件**: `webapps/seeagent-webui/e2e/multitask-orchestration.spec.ts`

**测试用例设计**:

1. **场景入口测试**
   ```typescript
   test('should display scenario list in sidebar', async ({ page }) => {
     // 验证左侧面板显示最佳实践列表
     await expect(page.locator('[data-testid="scenario-list"]')).toBeVisible()
     // 验证场景卡片
     await expect(page.locator('text=数据处理流水线')).toBeVisible()
   })

   test('should trigger scenario from dialog', async ({ page }) => {
     // 对话触发场景
     await page.fill('textarea', '帮我处理这份数据')
     await page.click('button:has-text("send")')
     // 验证任务卡片出现
     await expect(page.locator('[data-testid="task-card"]')).toBeVisible({ timeout: 60000 })
   })

   test('should trigger scenario from sidebar click', async ({ page }) => {
     // 点击场景直接创建任务
     await page.click('text=数据处理流水线')
     // 验证任务创建
     await expect(page.locator('[data-testid="task-card"]')).toBeVisible()
   })
   ```

2. **步骤执行测试**
   ```typescript
   test('should display step progress', async ({ page }) => {
     // 创建任务
     await page.click('text=数据处理流水线')
     // 验证步骤进度显示
     await expect(page.locator('text=步骤 1/3')).toBeVisible()
     // 验证当前步骤高亮
     await expect(page.locator('[data-step-id="validate_input"][data-status="running"]')).toBeVisible()
   })

   test('should show step status icons', async ({ page }) => {
     await page.click('text=数据处理流水线')
     // 验证状态图标: pending (⏳), running (▶️), completed (✅), waiting (⏸️)
     const hasStatusIcon =
       (await page.locator('text=⏳').count()) > 0 ||
       (await page.locator('text=▶️').count()) > 0 ||
       (await page.locator('text=✅').count()) > 0
     expect(hasStatusIcon).toBe(true)
   })
   ```

3. **用户确认与编辑测试**
   ```typescript
   test('should show confirm dialog for step', async ({ page }) => {
     await page.click('text=数据处理流水线')
     // 等待需要确认的步骤
     await expect(page.locator('[data-testid="step-confirm-dialog"]')).toBeVisible({ timeout: 90000 })
     // 点击确认按钮
     await page.click('button:has-text("确认")')
     // 验证进入下一步
     await expect(page.locator('text=步骤 2/3')).toBeVisible()
   })

   test('should allow user to edit step output', async ({ page }) => {
     await page.click('text=数据处理流水线')
     // 进入编辑模式
     await page.click('button:has-text("编辑")')
     // 修改输出内容
     const editor = page.locator('[data-testid="step-output-editor"]')
     await editor.fill('{"title": "用户修改的标题", "bullets": ["a", "b"]}')
     // 保存编辑
     await page.click('button:has-text("保存")')
     // 验证编辑已保存
     await expect(page.locator('text=用户修改的标题')).toBeVisible()
   })
   ```

4. **上下文传递测试**
   ```typescript
   test('should pass context between steps', async ({ page }) => {
     await page.click('text=数据处理流水线')
     // 完成第一步
     await page.fill('textarea', '{"title": "测试", "bullets": ["x", "y"]}')
     await page.click('button:has-text("确认")')
     // 等待第二步开始
     await expect(page.locator('text=步骤 2/3')).toBeVisible({ timeout: 60000 })
     // 验证上下文显示在右侧面板
     await expect(page.locator('[data-testid="context-panel"]')).toContainText('测试')
   })
   ```

5. **步骤切换测试**
   ```typescript
   test('should allow step switching', async ({ page }) => {
     await page.click('text=数据处理流水线')
     // 完成第一步
     await page.click('button:has-text("确认")')
     // 点击上一步按钮
     await page.click('button:has-text("上一步")')
     // 验证回到第一步
     await expect(page.locator('text=步骤 1/3')).toBeVisible()
   })

   test('should prevent invalid step switch', async ({ page }) => {
     await page.click('text=数据处理流水线')
     // 尝试跳到未执行的步骤
     await page.click('[data-step-id="diff_report"]')
     // 验证提示信息
     await expect(page.locator('text=该步骤尚未执行')).toBeVisible()
   })
   ```

6. **任务取消测试**
   ```typescript
   test('should cancel task and cleanup', async ({ page }) => {
     await page.click('text=数据处理流水线')
     // 点击取消按钮
     await page.click('button:has-text("取消任务")')
     // 确认取消
     await page.click('button:has-text("确认取消")')
     // 验证任务已取消
     await expect(page.locator('text=任务已取消')).toBeVisible()
     // 验证可以创建新任务
     await expect(page.locator('text=数据处理流水线')).toBeEnabled()
   })
   ```

**使用 Chrome 插件进行调试测试**:
```bash
# 运行测试并打开 Playwright Inspector
cd webapps/seeagent-webui
npx playwright test e2e/multitask-orchestration.spec.ts --ui

# 运行特定测试并生成 trace
npx playwright test e2e/multitask-orchestration.spec.ts -g "should display step progress" --trace on

# 查看 trace 报告
npx playwright show-trace trace.zip
```

---

### Phase 5: 测试与文档 (预计 2 天)

#### T5.1 集成测试
**依赖**: Phase 4 完成

**任务内容**:
1. 端到端测试: 对话触发场景 → 步骤执行 → 确认 → 完成
2. 端到端测试: 最佳实践入口触发 → 步骤执行
3. 边界测试: 任务取消、步骤切换、能力超出
4. 性能测试: 并发任务

---

#### T5.2 基于 Demo Skills 的测试场景
**依赖**: T5.1

**任务内容**:
创建一个"数据处理流水线"场景，组合现有 demo skills 进行端到端测试：

**场景定义**: `scenarios/data_pipeline.yaml`

**步骤设计**:
1. **Step 1: 输入验证** (demo-schema-check)
   - 用户输入原始数据
   - 验证数据结构是否符合 schema
   - 输出: 校验结果

2. **Step 2: 数据处理** (demo-echo-json + demo-context-hash)
   - 接收上一步验证通过的数据
   - 生成处理摘要 (trace_id, digest)
   - 支持用户编辑确认
   - 输出: 处理后的数据 + 摘要

3. **Step 3: 变更对比** (demo-json-diff)
   - 对比原始数据与处理后数据
   - 生成变更报告
   - 用户确认后完成

**测试覆盖**:
- 上下文传递 (Step 1 → Step 2 → Step 3)
- 用户编辑确认 (Step 2)
- 多轮交互 (失败重试)
- 任务取消与恢复

**场景配置文件**:
```yaml
schema_version: "1.0"
scenario_id: "data_pipeline_demo"
name: "数据处理流水线演示"
description: "组合 demo skills 验证多任务编排核心流程"
trigger: BOTH

steps:
  - step_id: "validate_input"
    name: "输入验证"
    description: "验证输入数据结构"
    system_prompt: |
      你是数据验证专家。使用 demo-schema-check 技能验证用户输入。
      内置 schema: demo_draft_v1 (title: string, bullets: array[string])
    tools: ["run_skill_script"]
    skills: ["demo-schema-check"]
    requires_user_confirm: true
    output_key: "validated_data"

  - step_id: "process_data"
    name: "数据处理"
    description: "处理数据并生成摘要"
    system_prompt: |
      你是数据处理专家。基于前置步骤的验证结果：
      1. 使用 demo-echo-json 生成处理记录
      2. 使用 demo-context-hash 生成数据摘要
      用户可以编辑处理结果。
    tools: ["run_skill_script"]
    skills: ["demo-echo-json", "demo-context-hash"]
    allow_user_edit: true
    requires_user_confirm: true
    output_key: "processed_data"

  - step_id: "diff_report"
    name: "变更报告"
    description: "生成变更对比报告"
    system_prompt: |
      你是数据分析专家。使用 demo-json-diff 对比：
      - before: 原始验证数据
      - after: 处理后的数据
      输出变更统计和路径。
    tools: ["run_skill_script"]
    skills: ["demo-json-diff"]
    output_key: "diff_result"

trigger_keywords: ["数据处理", "流水线", "pipeline", "demo"]
trigger_patterns: ["帮我(处理|验证).*数据"]
```

---

#### T5.3 Chrome 插件前端可视化测试
**依赖**: T5.2, T4.4

**任务内容**:
使用 Chrome 插件 (Playwright MCP Tools 或 Playwright Inspector) 进行交互式前端测试。

**测试环境准备**:
```bash
# 1. 启动后端服务
cd /Users/zd/agents/openakita-main
source venv/bin/activate
openakita serve

# 2. 启动前端开发服务器
cd webapps/seeagent-webui
pnpm dev
```

**使用 Playwright Inspector (Chrome DevTools 风格)**:
```bash
# 启动交互式测试
cd webapps/seeagent-webui
npx playwright test e2e/multitask-orchestration.spec.ts --ui

# 这会打开 Playwright Inspector 窗口，可以：
# - 单步执行测试
# - 查看页面快照
# - 录制新的测试用例
# - 调试选择器
```

**使用 Playwright MCP Tools (Claude Code 内置)**:

1. **导航到测试页面**
   ```
   使用 mcp__playwright__browser_navigate 导航到 http://localhost:5175
   ```

2. **获取页面快照**
   ```
   使用 mcp__playwright__browser_snapshot 查看当前页面结构
   ```

3. **测试场景入口**
   ```
   使用 mcp__playwright__browser_click 点击 "数据处理流水线" 场景
   使用 mcp__playwright__browser_snapshot 验证任务卡片出现
   ```

4. **测试步骤执行**
   ```
   使用 mcp__playwright__browser_wait_for 等待 "步骤 1/3" 出现
   使用 mcp__playwright__browser_snapshot 查看步骤状态
   使用 mcp__playwright__browser_click 点击 "确认" 按钮
   ```

5. **测试用户编辑**
   ```
   使用 mcp__playwright__browser_click 点击 "编辑" 按钮
   使用 mcp__playwright__browser_type 输入修改内容
   使用 mcp__playwright__browser_click 点击 "保存" 按钮
   ```

**前端测试检查清单**:

| 测试项 | 验证内容 | 预期结果 |
|--------|---------|---------|
| 场景列表显示 | 左侧面板是否显示最佳实践入口 | 显示 "数据处理流水线" 卡片 |
| 对话触发场景 | 输入"帮我处理数据"是否触发场景 | 显示任务创建确认卡片 |
| 点击触发场景 | 点击场景卡片是否创建任务 | 显示步骤进度面板 |
| 步骤进度显示 | 步骤 1/3, 2/3, 3/3 是否正确切换 | 进度条平滑更新 |
| 步骤状态图标 | ⏳ → ▶️ → ✅ 是否正确显示 | 状态图标与执行状态一致 |
| 用户确认对话框 | 确认按钮是否可点击 | 点击后进入下一步 |
| 用户编辑功能 | 编辑按钮是否可用 | 编辑后可保存修改 |
| 上下文传递 | 右侧面板是否显示前置步骤输出 | 显示验证数据和摘要 |
| 步骤切换 | 上一步/下一步按钮是否有效 | 可在已完成步骤间切换 |
| 任务取消 | 取消按钮是否清理状态 | 任务状态变为已取消 |
| WebSocket 事件 | 步骤完成是否实时更新 | 无需刷新页面 |

**录制新测试用例**:
```bash
# 使用 Playwright Codegen 录制新测试
npx playwright codegen http://localhost:5175

# 在打开的浏览器中操作，Playwright 会自动生成测试代码
# 完成后复制生成的代码到 e2e/multitask-orchestration.spec.ts
```

---

#### T5.4 文档完善
**依赖**: T5.3

**任务内容**:
1. API 文档
2. 场景定义指南
3. 使用示例

---

## 4. 文件结构

```
src/openakita/orchestration/
├── __init__.py                    # 更新导出
├── worker.py                      # 现有，复用
├── master.py                      # 现有，复用
├── bus.py                         # 现有
├── messages.py                    # 现有，可能扩展
├── registry.py                    # 现有
├── monitor.py                     # 现有
│
└── task/                          # 新增
    ├── __init__.py
    ├── state.py                   # T1.1
    ├── step.py                    # T1.2
    ├── scenario.py                # T1.3
    ├── session.py                 # T2.1
    ├── config.py                  # T2.2
    ├── subagent_manager.py        # T2.3
    ├── orchestrator.py            # T2.4
    └── router.py                  # T2.5

scenarios/                         # 新增
└── data_pipeline.yaml             # T5.2 基于 demo skills 的测试场景

tests/orchestration/task/          # 新增后端单元测试
├── test_state.py
├── test_step.py
├── test_scenario.py
├── test_session.py
├── test_config.py
├── test_subagent_manager.py
├── test_orchestrator.py
└── test_router.py

webapps/seeagent-webui/e2e/        # 前端 E2E 测试
└── multitask-orchestration.spec.ts # T4.4 多任务编排前端测试
```

---

## 5. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| SubAgent 独立进程资源消耗 | 内存增加 | 共享模型配置，限制并发数 |
| TaskState 扩展影响现有代码 | 状态复杂度 | 使用组合而非继承 |
| 多步骤上下文传递复杂 | 数据流难追踪 | 明确定义 input_schema/output_key |
| 路由逻辑复杂 | 消息分发错误 | MessageRouter 独立测试 |

---

## 6. 下一步行动

建议从 **T1.1 实现状态定义** 开始，这是所有后续任务的基础。