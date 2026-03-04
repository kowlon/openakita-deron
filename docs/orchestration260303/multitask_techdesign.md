# OpenAkita 多任务编排技术设计文档

> 版本: v3.1
> 日期: 2026-03-04
> 状态: 设计评审
> 更新: **SubAgent 以独立进程步骤执行模式落地，复用 WorkerAgent 架构与 ZMQ 通信**

---

## 1. 架构审查与关键发现

### 1.1 现有代码架构分析

在开始设计之前，我们对现有 orchestration 模块进行了深入分析，发现以下关键点：

#### 1.1.1 Agent 架构的本质

```python
# src/openakita/core/agent.py:124-289 (简化)
class Agent:
    def __init__(self, ...):
        self.brain = Brain(api_key=api_key)
        self.ralph = RalphLoop(...)
        self.skill_manager = SkillManager(...)
        self.mcp_manager = MCPManager(...)
        self.memory_manager = MemoryManager(...)
        self.reasoning_engine = ReasoningEngine(...)
        self.agent_state = AgentState()
        # ... 更多子系统
```

**关键发现**: Agent 是一个完整的执行单元，包含 Brain、ReasoningEngine、ToolExecutor 等子系统。

#### 1.1.2 WorkerAgent 的本质

```python
# src/openakita/orchestration/worker.py:180-186
async def _init_agent(self) -> None:
    """初始化内置 Agent"""
    from ..core.agent import Agent
    self._agent = Agent()
    await self._agent.initialize(start_scheduler=False)
```

**关键发现**:
- 每个 WorkerAgent **内部创建一个完整的 Agent 实例**
- WorkerAgent 是独立进程 + 完整 Agent 能力
- 这是 **SubAgent 应该参考的架构模式**

#### 1.1.3 设计决策：统一 Agent 架构

**SubAgent 与 WorkerAgent 采用统一架构**，核心差异仅在于**执行语义与配置**：

| 维度 | SubAgent | WorkerAgent | 说明 |
|------|----------|-------------|------|
| **架构基础** | Agent 实例 | Agent 实例 | **统一架构** |
| **进程模式** | 独立进程（步骤执行模式） | 独立进程 | 通过 `process_mode` 区分 |
| **Brain** | 共享模型配置/Brain 代理 | 独立创建 | 通过 `brain_mode` 区分 |
| **工具集** | 受限 (allowed_tools) | 可配置 | 通过配置区分 |
| **Prompt** | 专用 (system_prompt) | 可配置 | 通过配置区分 |
| **生命周期** | 任务期间 | 长期运行 | 通过管理方式区分 |
| **通信方式** | ZMQ 消息 | ZMQ 消息 | 统一通信方式 |

**核心结论**: SubAgent 和 WorkerAgent **本质相同**，都是独立进程 Agent，差异仅在于配置参数。

#### 1.1.4 SubAgent 作为独立进程 Agent 的设计

**SubAgent 是真正的独立进程 Agent**，具备完整能力：

```
┌─────────────────────────────────────────────────────────────────┐
│                    SubAgent 独立进程 Agent 架构                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   SubAgent (独立进程 Agent)                                     │
│   ├── brain: BrainProxy/Config  # 共享模型配置/代理             │
│   ├── reasoning_engine          # 独立推理引擎                   │
│   ├── tool_executor             # 工具执行器 (受限/完整)          │
│   ├── agent_state               # 独立状态管理                   │
│   ├── memory_manager            # 记忆管理                       │
│   └── system_prompt             # 专用系统提示词                 │
│                                                                 │
│   与 MainAgent 的关系:                                           │
│   ├── 共享模型配置/Brain 代理                                    │
│   ├── 独立 ReasoningEngine (完整推理能力)                         │
│   ├── 受限 ToolExecutor (通过 allowed_tools 限制)                 │
│   └── 对话历史由 SubAgent 进程维护                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**关键特性**:
1. **独立进程 Agent 实例**: SubAgent 是真正的 Agent，不是配置对象
2. **完整推理能力**: 使用 ReasoningEngine，具备多轮工具调用能力
3. **独立上下文**: SubAgent 进程维护完整历史，StepSession 保留快照
4. **灵活配置**: 通过 SubAgentConfig 控制行为差异

#### 1.1.5 MainAgent 与 SubAgent 的路由机制

**设计原则**: MainAgent 作为路由中心，根据用户问题自动路由到相关 SubAgent。

```
┌─────────────────────────────────────────────────────────────────┐
│                    MainAgent 路由机制                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   用户消息                                                       │
│       │                                                         │
│       ▼                                                         │
│   MainAgent.chat(message)                                       │
│       │                                                         │
│       ├── 检查是否有活跃任务                                      │
│       │       │                                                 │
│       │       ├── 有活跃任务 → 路由到当前 SubAgent                │
│       │       │       └── task_session.dispatch_step()          │
│       │       │                                                 │
│       │       └── 无活跃任务 → 尝试场景匹配                        │
│       │               │                                         │
│       │               ├── 匹配成功 → 创建任务，路由到 SubAgent     │
│       │               │       └── create_task() → start_step()  │
│       │               │                                         │
│       │               └── 不匹配 → 普通对话                        │
│       │                       └── reasoning_engine.run()        │
│       │                                                         │
│       └── 返回响应给用户                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**与 MainAgent-WorkerAgent 的对比**:

| 维度 | MainAgent ↔ SubAgent | MainAgent ↔ WorkerAgent |
|------|---------------------|------------------------|
| **路由方式** | 自动路由 (场景匹配 + 任务状态) | 手动分发 (find_idle_agent) |
| **通信方式** | ZMQ 消息 (跨进程) | ZMQ 消息 (跨进程) |
| **状态管理** | TaskSession 管理 | Registry 管理 |
| **生命周期** | 任务期间 | 长期运行 |
| **Brain 共享** | 共享模型配置/Brain 代理 | 独立 |

#### 1.1.6 brain.messages_create 与 ReasoningEngine 能力对比

```
┌─────────────────────────────────────────────────────────────────┐
│                    能力对比                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  brain.messages_create          ReasoningEngine                 │
│  ─────────────────────          ────────────────                │
│                                                                 │
│  ✓ 单次 LLM 调用                ✓ 完整推理循环                   │
│  ✓ 传入工具定义                 ✓ 工具执行+结果处理               │
│  ✓ 返回原始响应                 ✓ Reason-Act-Observe 模式        │
│                                                                 │
│  ✗ 工具执行循环                 ✓ 多轮工具调用                   │
│  ✗ 多轮推理                     ✓ 循环检测                       │
│  ✗ 循环检测                     ✓ 任务完成度验证                 │
│  ✗ 上下文管理                   ✓ 上下文裁剪                     │
│  ✗ 任务完成验证                 ✓ Checkpoint + Rollback          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**设计决策**: SubAgent 使用 **ReasoningEngine**，确保与 MainAgent 能力一致。

### 1.2 架构风险与调整方向

| 原设计问题 | 调整方案 |
|-----------|---------|
| SubAgent 作为配置对象，能力受限 | **SubAgent 以独立进程运行**，完整能力 |
| 缺少步骤隔离与历史管理 | SubAgent 进程维护历史，StepSession 保留快照 |
| 路由机制不清晰 | **MainAgent 作为路由中心**，自动路由到 SubAgent |
| 与 WorkerAgent 架构不一致 | **统一 Agent 架构**，通过配置区分 |

---

## 2. 设计目标与约束

### 2.1 设计目标

1. **架构清晰简单**: 分层明确，职责单一
2. **统一 Agent 架构**: SubAgent 和 WorkerAgent 架构一致
3. **简洁路由机制**: MainAgent 自动路由到 SubAgent
4. **支持任务拆分**: 设计可按模块独立实现

### 2.2 设计约束

1. **不破坏现有接口**: 保持向后兼容
2. **不重复造轮子**: 复用 Brain、ReasoningEngine、Agent 等
3. **支持两种入口**: 对话触发 + 最佳实践入口

---

## 3. 架构设计

### 3.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           多任务编排架构                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                      入口层 (Entry Points)                       │   │
│   │                                                                  │   │
│   │   ┌─────────────────┐              ┌─────────────────┐          │   │
│   │   │  对话入口        │              │  最佳实践入口    │          │   │
│   │   │  Agent.chat()   │              │  WebUI/API      │          │   │
│   │   └────────┬────────┘              └────────┬────────┘          │   │
│   │            │                                │                   │   │
│   │            └────────────────┬───────────────┘                   │   │
│   └─────────────────────────────┼───────────────────────────────────┘   │
│                                 ▼                                       │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                    MainAgent (路由中心)                          │   │
│   │                                                                  │   │
│   │   ┌─────────────────────────────────────────────────────────┐   │   │
│   │   │                    消息路由逻辑                          │   │   │
│   │   │                                                          │   │   │
│   │   │   1. 检查是否有活跃任务                                   │   │   │
│   │   │      └─ 有 → 路由到当前 SubAgent                         │   │   │
│   │   │                                                          │   │   │
│   │   │   2. 尝试场景匹配                                        │   │   │
│   │   │      └─ 匹配 → 创建任务，路由到 SubAgent                  │   │   │
│   │   │                                                          │   │   │
│   │   │   3. 普通对话                                            │   │   │
│   │   │      └─ 使用 MainAgent 全量能力                           │   │   │
│   │   │                                                          │   │   │
│   │   └─────────────────────────────────────────────────────────┘   │   │
│   └─────────────────────────────┬───────────────────────────────────┘   │
│                                 ▼                                       │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                    任务编排层 (Task Orchestration)                │   │
│   │                                                                  │   │
│   │   ┌────────────────┐    ┌────────────────┐    ┌────────────────┐ │   │
│   │   │ TaskOrchestrator│◄──►│  TaskSession   │◄──►│   TaskState    │ │   │
│   │   │   (编排控制器)   │    │  (任务会话)     │    │   (任务状态)    │ │   │
│   │   └───────┬────────┘    └────────────────┘    └────────────────┘ │   │
│   │           │                                                       │   │
│   │           ▼                                                       │   │
│   │   ┌─────────────────────────────────────────────────────────┐   │   │
│   │   │                    SubAgentManager                       │   │   │
│   │   │   - SubAgent 创建/销毁                                   │   │   │
│   │   │   - Agent 配置管理                                       │   │   │
│   │   │   - 上下文传递                                           │   │   │
│   │   └─────────────────────────────────────────────────────────┘   │   │
│   └─────────────────────────────┬───────────────────────────────────┘   │
│                                 ▼                                       │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                    执行层 (Execution Layer)                      │   │
│   │                                                                  │   │
│   │   ┌───────────────────────────────────────────────────────────┐  │   │
│   │   │                 统一 Agent 架构                            │  │   │
│   │   │                                                          │  │   │
│   │   │    ┌─────────────────────────────────────────────────┐   │  │   │
│   │   │    │                 SubAgent                        │   │  │   │
│   │   │    │      (独立进程 / 步骤执行模式)                   │   │  │   │
│   │   │    │                                                 │   │  │   │
│   │   │    │   ┌─────────┐  ┌─────────┐  ┌─────────┐        │   │  │   │
│   │   │    │   │ Brain   │  │Reasoning│  │  Tool   │        │   │  │   │
│   │   │    │   │ Proxy   │  │ Engine  │  │Executor │        │   │  │   │
│   │   │    │   └─────────┘  └─────────┘  └─────────┘        │   │  │   │
│   │   │    │                                                 │   │  │   │
│   │   │    │   + 对话历史由进程维护                          │   │  │   │
│   │   │    │   + 专用 system_prompt                          │   │  │   │
│   │   │    │   + 受限 allowed_tools                          │   │  │   │
│   │   │    └─────────────────────────────────────────────────┘   │  │   │
│   │   │                                                          │  │   │
│   │   │    同架构不同配置:                                        │  │   │
│   │   │    ┌─────────────┐   ┌─────────────┐                    │  │   │
│   │   │    │  SubAgent   │   │ WorkerAgent  │                    │  │   │
│   │   │    │ (独立进程)  │   │ (独立进程)   │                    │  │   │
│   │   │    │ Brain 代理  │   │ 独立 Brain   │                    │  │   │
│   │   │    └─────────────┘   └─────────────┘                    │  │   │
│   │   └───────────────────────────────────────────────────────────┘  │   │
│   └──────────────────────────────────────────────────────────────────┘   │
│                                 ▼                                       │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                 基础设施层 (Infrastructure)                       │   │
│   │                                                                  │   │
│   │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │   │
│   │   │  Brain  │  │ Reasoning│  │  Agent  │  │  Memory │           │   │
│   │   │ (LLM)   │  │ Engine  │  │  State  │  │ Manager │           │   │
│   │   └─────────┘  └─────────┘  └─────────┘  └─────────┘           │   │
│   └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 统一 Agent 架构

**核心设计原则**: SubAgent 和 WorkerAgent 都基于 Agent 架构，通过配置参数区分行为。

### 3.3 模块结构

```
src/openakita/orchestration/
├── __init__.py                    # 模块导出
├── master.py                      # Master-Agent 模式 (现有，复用)
├── worker.py                      # Worker-Agent 模式 (现有，复用)
├── bus.py                         # ZMQ 通信总线 (现有)
├── messages.py                    # 消息协议 (现有)
├── registry.py                    # Agent 注册中心 (现有)
├── monitor.py                     # 监控模块 (现有)
│
├── task/                          # 新增: 多任务编排模块
│   ├── __init__.py                # 模块导出
│   ├── scenario.py                # 场景定义与注册表
│   ├── step.py                    # 步骤定义
│   ├── state.py                   # 任务状态 (扩展 TaskState)
│   ├── session.py                 # 任务会话
│   ├── orchestrator.py            # 任务编排器
│   ├── subagent_manager.py        # SubAgent 管理器 (核心)
│   └── router.py                  # 消息路由器 (核心)
```

### 3.4 MainAgent 路由机制详解

**路由器设计**: MainAgent 作为路由中心，自动将用户消息路由到正确的 Agent。

```python
class MessageRouter:
    """
    消息路由器 - MainAgent 的路由决策中心

    职责:
    1. 判断是否有活跃任务 → 路由到 SubAgent
    2. 尝试场景匹配 → 创建任务并路由
    3. 普通对话 → 使用 MainAgent 能力
    """

    def __init__(
        self,
        main_agent: Agent,
        task_orchestrator: TaskOrchestrator,
        scenario_registry: ScenarioRegistry,
    ):
        self._main_agent = main_agent
        self._task_orchestrator = task_orchestrator
        self._scenario_registry = scenario_registry

    async def route(self, message: str, session_id: str) -> str:
        """
        路由用户消息

        决策顺序:
        1. 检查是否有活跃任务 → 路由到当前 SubAgent
        2. 尝试场景匹配 → 创建任务，路由到第一个 SubAgent
        3. 普通对话 → MainAgent 自己处理
        """
        # 1. 检查是否有活跃任务
        active_task = self._task_orchestrator.get_active_task(session_id)
        if active_task:
            # 有活跃任务，路由到当前 SubAgent
            return await self._route_to_subagent(active_task, message)

        # 2. 尝试场景匹配
        scenario = self._scenario_registry.match_from_dialog(message)
        if scenario:
            # 匹配成功，创建任务并路由到第一个 SubAgent
            task = await self._task_orchestrator.create_task(
                scenario_id=scenario.scenario_id,
                session_id=session_id,
                initial_message=message,
            )
            return await self._route_to_subagent(task, message)

        # 3. 普通对话，MainAgent 自己处理
        return await self._main_agent.chat(message, session_id)

    async def _route_to_subagent(
        self,
        task: TaskSession,
        message: str,
    ) -> str:
        """
        路由到 SubAgent

        关键: SubAgent 为独立进程步骤执行模式，
        通过 ZMQ 发送 StepRequest 并等待 StepResult
        """
        response = await task.dispatch_step(message)

        return response
```

**路由流程图**:

```
┌─────────────────────────────────────────────────────────────────┐
│                    MainAgent 路由流程                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   用户消息: "请帮我分析这段代码"                                   │
│       │                                                         │
│       ▼                                                         │
│   MessageRouter.route(message, session_id)                      │
│       │                                                         │
│       ├── Step 1: 检查活跃任务                                   │
│       │       │                                                 │
│       │       ├── 有任务 → task.dispatch_step()                 │
│       │       │       │                                         │
│       │       │       ▼                                         │
│       │       │   send StepRequest via ZMQ                      │
│       │       │       │                                         │
│       │       │       ▼                                         │
│       │       │   返回响应 ✓                                     │
│       │       │                                                 │
│       │       └── 无任务 ↓                                       │
│       │                                                         │
│       ├── Step 2: 场景匹配                                       │
│       │       │                                                 │
│       │       ├── 匹配 "代码审查" 场景                            │
│       │       │       │                                         │
│       │       │       ▼                                         │
│       │       │   创建任务 (TaskSession)                         │
│       │       │       │                                         │
│       │       │       ▼                                         │
│       │       │   启动第一个 SubAgent 进程                        │
│       │       │       │                                         │
│       │       │       ▼                                         │
│       │       │   send StepRequest via ZMQ                      │
│       │       │       │                                         │
│       │       │       ▼                                         │
│       │       │   返回响应 ✓                                     │
│       │       │                                                 │
│       │       └── 不匹配 ↓                                       │
│       │                                                         │
│       └── Step 3: 普通对话                                       │
│               │                                                 │
│               ▼                                                 │
│           MainAgent.reasoning_engine.run()                      │
│               │                                                 │
│               ▼                                                 │
│           返回响应 ✓                                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.5 与 MainAgent-WorkerAgent 的交互对比

| 维度 | MainAgent ↔ SubAgent | MainAgent ↔ WorkerAgent |
|------|---------------------|------------------------|
| **架构** | 统一 Agent 架构 | 统一 Agent 架构 |
| **进程** | 独立进程 | 独立进程 |
| **通信** | ZMQ 消息传递 | ZMQ 消息传递 |
| **路由方式** | 自动 (基于任务状态 + 场景匹配) | 手动 (find_idle_agent) |
| **Brain** | 共享模型配置/Brain 代理 | 独立 |
| **状态管理** | TaskSession | Registry |
| **生命周期** | 任务期间 | 长期运行 |

**关键相似点**:
- **都是独立进程 Agent**: SubAgent 和 WorkerAgent 内部都是完整的 Agent
- **都使用 ReasoningEngine**: 完整的推理和工具执行能力
- **都通过配置区分行为**: allowed_tools, system_prompt 等

**关键差异**:
- **路由触发**: SubAgent 自动路由（场景匹配+任务状态），WorkerAgent 手动分发
- **生命周期**: SubAgent 随任务创建销毁，WorkerAgent 长期运行
- **模型接入**: SubAgent 共享模型配置/Brain 代理，WorkerAgent 独立 Brain

---

## 4. 核心数据结构

### 4.1 场景定义 (ScenarioDefinition)

场景定义描述一个"最佳实践"的完整流程：

```
ScenarioDefinition
├── scenario_id: str              # 场景唯一标识
├── name: str                     # 场景名称
├── description: str              # 场景描述
├── trigger: ScenarioTrigger      # 触发方式 (DIALOG/MANUAL/BOTH)
├── steps: list[StepDefinition]   # 步骤列表 (有序)
├── trigger_keywords: list[str]   # 对话触发关键词
├── trigger_patterns: list[str]   # 对话触发正则
└── metadata: dict                # 元数据 (分类、标签等)
```

### 4.2 步骤定义 (StepDefinition)

步骤定义描述单个步骤的执行要求：

```
StepDefinition
├── step_id: str                  # 步骤唯一标识
├── name: str                     # 步骤名称
├── description: str              # 步骤描述
├── system_prompt: str            # SubAgent 系统提示词
├── tools: list[str]              # 允许使用的工具
├── input_schema: dict            # 输入参数定义
├── output_key: str               # 输出存储键名
├── requires_user_confirm: bool   # 是否需要用户确认
├── allow_user_edit: bool         # 是否允许用户编辑
└── condition: Callable           # 执行条件 (可选)
```

### 4.3 任务状态 (TaskState)

扩展现有的 TaskState 以支持多步骤任务：

```
TaskState (扩展)
├── task_id: str                  # 任务唯一标识
├── scenario_id: str              # 场景标识
├── status: TaskStatus            # 任务状态
├── trigger_source: str           # 触发来源 (dialog/manual)
├── initial_context: dict         # 初始上下文
├── current_step_id: str          # 当前步骤
├── steps: dict[str, StepState]   # 步骤状态字典
├── context: dict                 # 累积上下文 (步骤间传递)
├── created_at: datetime
├── started_at: datetime
├── completed_at: datetime
└── total_tokens: int
```

### 4.4 步骤会话 (StepSession) - 关键设计

**问题背景**: 需要支持用户与特定 SubAgent 独立对话，每个步骤需要维护独立的执行上下文。

**解决方案**: 为每个步骤维护独立的会话快照与 SubAgent 进程标识。

```
StepSession
├── step_id: str                    # 步骤标识
├── status: StepStatus              # 步骤状态
├── messages: list[dict]            # 交互快照/摘要
├── sub_agent_id: str               # SubAgent 进程标识 (关键!)
├── agent_config: SubAgentConfig    # SubAgent 配置
├── input_data: dict                # 输入数据
├── output_data: dict               # 输出数据
├── started_at: datetime
├── completed_at: datetime
├── error_message: str              # 错误信息
├── user_edited: bool               # 用户是否编辑
└── edit_content: str               # 用户编辑内容
```

**关键设计点**:
- `sub_agent_id` 指向独立进程的 SubAgent
- `messages` 保存步骤交互的快照/摘要，完整历史由 SubAgent 进程维护
- `agent_config` 包含该步骤的配置信息（system_prompt, allowed_tools 等）

### 4.5 SubAgent 配置文件 (YAML 格式)

**用途**: 通过 YAML 配置文件定义 SubAgent 的行为，支持从文件加载配置初始化 SubAgent。

**配置文件示例** (`subagents/code-reviewer.yaml`):

```yaml
schema_version: "1.0"
subagent_id: "code-reviewer"
name: "CodeReviewer"
description: "专注代码审查与质量改进"
system_prompt: |
  你是代码审查专家，关注可读性、正确性与安全性。
  输出格式:
  - issues: [{severity, detail, suggestion}]
  - summary: string
tools:
  system_tools: ["read_file", "search_codebase"]
  skills: ["lint-helper", "security-audit"]
  mcp: []
capabilities:
  allow_shell: false
  allow_write: false
runtime:
  max_iterations: 12
  session_type: "cli"
  memory_policy: "task_scoped"
  prompt_budget: "standard"
metadata:
  source_doc: "best_practice_x.md"
  compiled_at: "2026-03-03T10:00:00Z"
  author: "subagent-compiler"
```

**配置字段说明**:

```
SubAgentConfigFile (YAML)
├── schema_version: str              # 配置文件版本
├── subagent_id: str                 # SubAgent 唯一标识
├── name: str                        # SubAgent 名称
├── description: str                 # 描述
├── system_prompt: str               # 系统提示词 (支持多行)
│
├── tools:                           # 工具配置
│   ├── system_tools: list[str]      # 系统工具 (read_file, write_file 等)
│   ├── skills: list[str]            # Skills 工具集
│   └── mcp: list[str]               # MCP 工具
│
├── capabilities:                    # 能力限制
│   ├── allow_shell: bool            # 是否允许 shell 命令
│   └── allow_write: bool            # 是否允许写入文件
│
├── runtime:                         # 运行时配置
│   ├── max_iterations: int          # 最大迭代次数
│   ├── session_type: str            # 会话类型 (cli/im/web)
│   ├── memory_policy: str           # 记忆策略 (task_scoped/persistent)
│   └── prompt_budget: str           # 提示词预算 (minimal/standard/extended)
│
└── metadata:                        # 元数据
    ├── source_doc: str              # 来源文档
    ├── compiled_at: str             # 编译时间
    └── author: str                  # 作者
```

### 4.6 SubAgentConfig 运行时结构

**用途**: 从 YAML 配置文件解析后的运行时配置结构。

```
SubAgentConfig (运行时)
├── subagent_id: str                 # SubAgent 唯一标识
├── name: str                        # SubAgent 名称
├── description: str                 # 描述
├── system_prompt: str               # 系统提示词
├── allowed_tools: list[str]         # 合并后的工具列表 (system_tools + skills + mcp)
├── capabilities: CapabilitiesConfig # 能力限制
│   ├── allow_shell: bool
│   └── allow_write: bool
├── runtime: RuntimeConfig           # 运行时配置
│   ├── max_iterations: int
│   ├── session_type: str
│   ├── memory_policy: str
│   └── prompt_budget: str
├── process_mode: ProcessMode        # WORKER
├── brain_mode: BrainMode            # SHARED_PROXY | INDEPENDENT
└── metadata: dict                   # 元数据
```

### 4.7 配置加载流程

```
┌─────────────────────────────────────────────────────────────────┐
│                    SubAgent 配置加载流程                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   1. 加载 YAML 配置文件                                          │
│      │                                                          │
│      │  SubAgentConfigLoader.load("code-reviewer.yaml")         │
│      │                                                          │
│      ▼                                                          │
│   2. 解析 YAML → SubAgentConfigFile                             │
│      │                                                          │
│      │  - 验证 schema_version                                   │
│      │  - 解析 tools 配置                                       │
│      │  - 解析 capabilities 配置                                │
│      │  - 解析 runtime 配置                                     │
│      │                                                          │
│      ▼                                                          │
│   3. 工具解析与合并                                              │
│      │                                                          │
│      │  system_tools → 查找系统工具注册表                        │
│      │  skills → 查找 SkillManager 注册的 skills                │
│      │  mcp → 查找 MCPManager 注册的工具                        │
│      │                                                          │
│      │  合并所有工具名称 → allowed_tools: list[str]             │
│      │                                                          │
│      ▼                                                          │
│   4. 能力限制转换                                                │
│      │                                                          │
│      │  allow_shell: false → 过滤 shell 相关工具                │
│      │  allow_write: false → 过滤写入相关工具                   │
│      │                                                          │
│      ▼                                                          │
│   5. 生成 SubAgentConfig (运行时配置)                            │
│      │                                                          │
│      │  SubAgentConfig(                                         │
│      │      subagent_id="code-reviewer",                        │
│      │      name="CodeReviewer",                                │
│      │      allowed_tools=["read_file", "search_codebase", ...],│
│      │      ...                                                 │
│      │  )                                                       │
│      │                                                          │
│      ▼                                                          │
│   6. 创建 SubAgent 进程/实例                                     │
│      │                                                          │
│      │  SubAgentManager.spawn_sub_agent(config)                 │
│      │                                                          │
│      ▼                                                          │
│   SubAgent (独立进程 Agent 实例)                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.8 配置加载器实现

```python
from dataclasses import dataclass
from pathlib import Path
import yaml

@dataclass
class CapabilitiesConfig:
    """能力限制配置"""
    allow_shell: bool = False
    allow_write: bool = False

@dataclass
class RuntimeConfig:
    """运行时配置"""
    max_iterations: int = 20
    session_type: str = "cli"
    memory_policy: str = "task_scoped"
    prompt_budget: str = "standard"

@dataclass
class SubAgentConfig:
    """SubAgent 运行时配置"""
    subagent_id: str
    name: str
    description: str
    system_prompt: str
    allowed_tools: list[str]
    capabilities: CapabilitiesConfig
    runtime: RuntimeConfig
    process_mode: str = "WORKER"  # WORKER
    brain_mode: str = "SHARED_PROXY"    # SHARED_PROXY | INDEPENDENT
    metadata: dict = None

class SubAgentConfigLoader:
    """SubAgent 配置加载器"""

    # 需要过滤的工具（基于能力限制）
    SHELL_TOOLS = {"run_shell", "execute_command", "bash"}
    WRITE_TOOLS = {"write_file", "edit_file", "create_file", "delete_file"}

    def __init__(
        self,
        skill_manager,  # SkillManager 实例
        mcp_manager,    # MCPManager 实例
        system_tools_registry: dict,  # 系统工具注册表
    ):
        self._skill_manager = skill_manager
        self._mcp_manager = mcp_manager
        self._system_tools = system_tools_registry

    def load(self, config_path: str | Path) -> SubAgentConfig:
        """从 YAML 文件加载配置"""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"SubAgent config not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        return self.parse(raw)

    def parse(self, raw: dict) -> SubAgentConfig:
        """解析原始配置字典"""
        # 验证版本
        schema_version = raw.get("schema_version", "1.0")
        if schema_version != "1.0":
            raise ValueError(f"Unsupported schema version: {schema_version}")

        # 解析工具
        allowed_tools = self._resolve_tools(raw.get("tools", {}))

        # 解析能力限制
        caps_raw = raw.get("capabilities", {})
        capabilities = CapabilitiesConfig(
            allow_shell=caps_raw.get("allow_shell", False),
            allow_write=caps_raw.get("allow_write", False),
        )

        # 应用能力限制（过滤工具）
        allowed_tools = self._apply_capabilities(allowed_tools, capabilities)

        # 解析运行时配置
        runtime_raw = raw.get("runtime", {})
        runtime = RuntimeConfig(
            max_iterations=runtime_raw.get("max_iterations", 20),
            session_type=runtime_raw.get("session_type", "cli"),
            memory_policy=runtime_raw.get("memory_policy", "task_scoped"),
            prompt_budget=runtime_raw.get("prompt_budget", "standard"),
        )

        return SubAgentConfig(
            subagent_id=raw["subagent_id"],
            name=raw["name"],
            description=raw.get("description", ""),
            system_prompt=raw.get("system_prompt", ""),
            allowed_tools=allowed_tools,
            capabilities=capabilities,
            runtime=runtime,
            metadata=raw.get("metadata", {}),
        )

    def _resolve_tools(self, tools_config: dict) -> list[str]:
        """解析并合并工具列表"""
        tools = []

        # 1. 系统工具
        for tool_name in tools_config.get("system_tools", []):
            if tool_name in self._system_tools:
                tools.append(tool_name)

        # 2. Skills
        for skill_name in tools_config.get("skills", []):
            # 从 SkillManager 获取 skill 中的所有工具
            skill_tools = self._skill_manager.get_skill_tools(skill_name)
            tools.extend(skill_tools)

        # 3. MCP 工具
        for mcp_tool in tools_config.get("mcp", []):
            # 从 MCPManager 获取 MCP 工具
            if self._mcp_manager.has_tool(mcp_tool):
                tools.append(mcp_tool)

        return list(set(tools))  # 去重

    def _apply_capabilities(
        self,
        tools: list[str],
        capabilities: CapabilitiesConfig,
    ) -> list[str]:
        """根据能力限制过滤工具"""
        filtered = []

        for tool in tools:
            # 过滤 shell 工具
            if not capabilities.allow_shell and tool in self.SHELL_TOOLS:
                continue

            # 过滤写入工具
            if not capabilities.allow_write and tool in self.WRITE_TOOLS:
                continue

            filtered.append(tool)

        return filtered
```

### 4.9 步骤状态 (StepState)

```
StepState (简化版，用于状态追踪)
├── step_id: str                  # 步骤标识
├── status: StepStatus            # 步骤状态
├── started_at: datetime
├── completed_at: datetime
└── error_message: str            # 错误信息
```

### 4.7 独立对话架构图

**关键设计**: 每个步骤维护独立 SubAgent 进程标识与交互快照，用户可以选择与任意 SubAgent 对话。

```
┌─────────────────────────────────────────────────────────────────┐
│              支持独立对话的架构设计                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  TaskSession                                                    │
│  ├── task_id: "task-abc123"                                    │
│  ├── current_step_id: "analyze"                                │
│  ├── mode: "step"  # "step" | "free"                           │
│  │                                                             │
│  ├── step_sessions:                                            │
│  │   │                                                         │
│  │   ├── "analyze": StepSession ──────────────────────┐        │
│  │   │   ├── messages: [                              │        │
│  │   │   │   {user: "请分析这段代码"},                 │        │
│  │   │   │   {assistant: "分析结果..."},              │        │
│  │   │   │   {user: "我想了解更多..."},  ◄─ 快照     │        │
│  │   │   ]                                           │        │
│  │   │   ├── sub_agent_id: str ◄─ 独立进程标识         │        │
│  │   │   └── agent_config: SubAgentConfig             │        │
│  │   │                                               │        │
│  │   ├── "review": StepSession ──────────────────────┐        │
│  │   │   ├── messages: []  ◄─ 快照，尚未开始        │        │
│  │   │   ├── sub_agent_id: str                        │        │
│  │   │   └── agent_config: SubAgentConfig             │        │
│  │   │                                               │        │
│  │   └── "summary": StepSession                      │        │
│  │       └── ...                                     │        │
│  │                                                   │        │
│  └── context: {分析结果, 审查报告, ...}  ◄─ 步骤间传递          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.8 SubAgent 独立进程架构详解

```
┌─────────────────────────────────────────────────────────────────┐
│              SubAgent 独立进程架构                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  TaskSession                                                    │
│  ├── task_id: "task-abc123"                                    │
│  ├── current_step_id: "analyze"                                │
│  ├── mode: "step"  # "step" | "free"                           │
│  │                                                             │
│  ├── step_sessions:                                            │
│  │   │                                                         │
│  │   ├── "analyze": StepSession ──────────────────────┐        │
│  │   │   ├── messages: [                              │        │
│  │   │   │   {user: "请分析这段代码"},                 │        │
│  │   │   │   {assistant: "分析结果..."},              │        │
│  │   │   │   {user: "我想了解更多..."},  ◄─ 快照     │        │
│  │   │   ]                                           │        │
│  │   │   │                                           │        │
│  │   │   ├── sub_agent_id: str ◄─ 独立进程标识        │        │
│  │   │   │                                           │        │
│  │   │   └── agent_config: SubAgentConfig            │        │
│  │   │                                               │        │
│  │   ├── "review": StepSession ──────────────────────┐        │
│  │   │   ├── messages: []  ◄─ 快照，尚未开始        │        │
│  │   │   ├── sub_agent_id: str                       │        │
│  │   │   └── agent_config: SubAgentConfig            │        │
│  │   │                                               │        │
│  │   └── "summary": StepSession                      │        │
│  │       └── ...                                     │        │
│  │                                                   │        │
│  └── context: {分析结果, 审查报告, ...}  ◄─ 步骤间传递          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**关键设计点**:
1. **每个 StepSession 绑定独立 SubAgent 进程标识**
2. **SubAgent 进程内是完整 Agent**，具备独立 ReasoningEngine
3. **messages 本地存快照/摘要**，完整历史由 SubAgent 进程维护
4. **共享模型配置/Brain 代理** 以节省资源，但推理逻辑完全独立

---

## 5. 核心组件设计

### 5.1 ScenarioRegistry (场景注册表)

**职责**: 管理所有最佳实践场景的定义和匹配

**核心方法**:
- `register(scenario)`: 注册场景
- `get(scenario_id)`: 获取场景定义
- `match_from_dialog(message)`: 从对话消息匹配场景
- `list_all()`: 列出所有场景
- `list_by_category(category)`: 按分类列出场景

**匹配逻辑**:
1. 正则模式匹配 (优先级高)
2. 关键词匹配 (优先级低)

### 5.2 TaskOrchestrator (任务编排器)

**职责**: 任务创建、步骤调度、状态管理

**核心方法**:
- `create_task_from_dialog(message, context)`: 从对话创建任务
- `create_task_manual(scenario_id, context)`: 手动创建任务
- `start_task(task_id)`: 启动任务
- `confirm_step(task_id, step_id, ...)`: 用户确认步骤
- `cancel_task(task_id)`: 取消任务
- `get_task_state(task_id)`: 获取任务状态
- `get_active_task(session_id)`: 获取会话的活跃任务

**执行流程**:
```
用户输入/点击
    ↓
场景匹配 (ScenarioRegistry.match_from_dialog)
    ↓
任务创建 (TaskSession + TaskState 初始化)
    ↓
步骤执行循环:
    ├── 检查执行条件
    ├── 创建 SubAgentConfig
    ├── 调用 SubAgentManager 启动 SubAgent 进程
    ├── 执行步骤 (SubAgent 进程处理 StepRequest)
    ├── 用户确认 (可选)
    └── 更新上下文
    ↓
任务完成
```

### 5.3 SubAgentManager (SubAgent 管理器) - 核心设计

**职责**: 管理 SubAgent 的生命周期，统一 SubAgent 和 WorkerAgent 的创建逻辑

**核心设计**: 基于 Agent 架构，通过配置区分不同模式

```python
class SubAgentManager:
    """
    SubAgent 管理器 - 统一 Agent 架构

    关键设计: SubAgent 以独立进程运行
    与 WorkerAgent 架构统一，通过配置区分行为
    """

    def __init__(
        self,
        main_agent: Agent,  # 主 Agent 引用
    ):
        self._main_agent = main_agent
        self._sub_agents: dict[str, str] = {}  # step_id -> sub_agent_id

    async def spawn_sub_agent(
        self,
        step_id: str,
        config: SubAgentConfig,
    ) -> str:
        """
        创建 SubAgent 进程

        关键：SubAgent 以独立进程运行
        与 WorkerAgent 架构统一，具备完整推理能力
        """
        sub_agent_id = await self._create_worker_agent(config)
        self._sub_agents[step_id] = sub_agent_id
        return sub_agent_id

    async def destroy_sub_agent(self, step_id: str) -> None:
        """销毁 SubAgent，清理资源"""
        if step_id in self._sub_agents:
            sub_agent_id = self._sub_agents.pop(step_id)
            # 发送关闭指令给 SubAgent 进程

    def get_sub_agent(self, step_id: str) -> str | None:
        """获取 SubAgent 标识"""
        return self._sub_agents.get(step_id)
```

### 5.4 TaskSession (任务会话) - 核心设计

**职责**: 管理单个任务实例的生命周期，支持独立对话和自动路由

**核心属性**:
- `state: TaskState` - 任务状态
- `scenario: ScenarioDefinition` - 场景定义
- `step_sessions: dict[str, StepSession]` - 步骤会话 (关键!)
- `sub_agent_manager: SubAgentManager` - SubAgent 管理器
- `mode: str` - 当前模式 ("step" | "free")

**核心方法**:

```python
class TaskSession:
    """
    任务会话 - 支持独立对话和自动路由

    关键设计: 每个步骤的 SubAgent 以独立进程运行
    """

    def __init__(
        self,
        state: TaskState,
        scenario: ScenarioDefinition,
        sub_agent_manager: SubAgentManager,
    ):
        self.state = state
        self.scenario = scenario
        self._sub_agent_manager = sub_agent_manager

        self.step_sessions: dict[str, StepSession] = {}
        self.mode: str = "step"  # "step" | "free"
        self.context: dict[str, Any] = {}

    async def dispatch_step(self, message: str) -> str:
        """
        向当前步骤的 SubAgent 发送请求

        关键: SubAgent 以独立进程运行，通过 ZMQ 消息执行
        """
        step_id = self.state.current_step_id
        return await self.dispatch_step_to(step_id, message)

    async def dispatch_step_to(
        self,
        step_id: str,
        message: str,
    ) -> str:
        """
        向指定步骤的 SubAgent 发送请求

        关键: SubAgent 以独立进程运行，
        使用 ZMQ 消息请求/响应
        """
        # 获取或创建步骤会话
        step_session = self.step_sessions.get(step_id)
        if not step_session:
            step_session = await self._create_step_session(step_id)

        # 添加用户消息到本地快照
        step_session.messages.append({
            "role": "user",
            "content": message
        })

        # 构建系统提示词（包含上下文注入）
        system_prompt = self._build_step_prompt(step_session)

        # 通过 ZMQ 发送 StepRequest 到 SubAgent 进程
        response = await self._sub_agent_manager.send_step_request(
            sub_agent_id=step_session.sub_agent_id,
            messages=step_session.messages,
            system_prompt=system_prompt,
            session_id=f"{self.state.task_id}_{step_id}",
        )

        # 更新步骤会话的消息历史
        step_session.messages.append({
            "role": "assistant",
            "content": response
        })

        return response

    async def get_current_sub_agent(self) -> str:
        """
        获取当前步骤的 SubAgent 标识
        """
        step_id = self.state.current_step_id
        step_session = self.step_sessions.get(step_id)
        if not step_session:
            step_session = await self._create_step_session(step_id)
        return step_session.sub_agent_id

    async def complete_step(self, step_id: str) -> dict:
        """
        完成当前步骤，生成结构化输出

        用户确认后调用，将输出存入上下文供后续步骤使用
        """
        step_session = self.step_sessions[step_id]

        # 让 SubAgent 生成结构化输出
        output = await self._generate_step_output(step_session)

        step_session.output_data = output
        step_session.status = StepStatus.COMPLETED

        # 更新累积上下文 (关键: 步骤间传递)
        step_def = self._get_step_definition(step_id)
        if step_def.output_key:
            self.context[step_def.output_key] = output

        return output

    async def switch_to_step(self, step_id: str) -> None:
        """
        切换到指定步骤

        用户显式控制流程跳转
        """
        # 检查是否可以切换（前置条件）
        step_def = self._get_step_definition(step_id)
        if step_def.condition and not step_def.condition(self.context):
            raise ValueError(f"无法切换到步骤 {step_id}: 条件不满足")

        self.state.current_step_id = step_id

        # 如果步骤尚未开始，初始化会话
        if step_id not in self.step_sessions:
            await self._create_step_session(step_id)

    async def switch_to_free_mode(self) -> None:
        """切换到自由模式（使用MainAgent全量能力）"""
        self.mode = "free"

    async def switch_to_step_mode(self) -> None:
        """切换回步骤模式"""
        self.mode = "step"

    async def _create_step_session(self, step_id: str) -> StepSession:
        """
        创建步骤会话

        关键：创建独立进程 SubAgent
        """
        step_def = self._get_step_definition(step_id)

        # 创建 SubAgent 配置
        config = SubAgentConfig(
            name=step_def.name,
            description=step_def.description,
            system_prompt=step_def.system_prompt,
            allowed_tools=step_def.tools,
            max_iterations=step_def.max_iterations or 20,
            process_mode=ProcessMode.WORKER,
            brain_mode=BrainMode.SHARED_PROXY,
        )

        # 通过 SubAgentManager 启动 SubAgent 进程
        sub_agent_id = await self._sub_agent_manager.spawn_sub_agent(
            step_id, config
        )

        # 创建步骤会话
        step_session = StepSession(
            step_id=step_id,
            status=StepStatus.PENDING,
            messages=[],
            sub_agent_id=sub_agent_id,
            agent_config=config,
        )

        self.step_sessions[step_id] = step_session
        return step_session

    def _build_step_prompt(self, step_session: StepSession) -> str:
        """构建步骤系统提示词，注入上下文"""
        step_def = self._get_step_definition(step_session.step_id)

        prompt_parts = [step_def.system_prompt]

        # 注入前置步骤的输出
        if self.context:
            prompt_parts.append("\n## 前置步骤输出")
            for key, value in self.context.items():
                prompt_parts.append(f"### {key}\n{value}")

        # 添加能力边界说明
        prompt_parts.append(f"\n## 当前步骤能力范围")
        prompt_parts.append(f"你当前的工具: {', '.join(step_def.tools)}")
        prompt_parts.append("如果用户请求超出你的能力范围，请明确告知。")

        return "\n".join(prompt_parts)
```

### 5.5 RestrictedToolExecutor (受限工具执行器)

**职责**: 限制 SubAgent 可使用的工具范围

```python
class RestrictedToolExecutor:
    """受限工具执行器 - 限制 SubAgent 的工具使用"""

    def __init__(
        self,
        inner: ToolExecutor,
        allowed_tools: list[str],
    ):
        self._inner = inner
        self._allowed_tools = set(allowed_tools)

    async def execute(self, tool_name: str, **kwargs) -> Any:
        """执行工具，检查是否在允许范围内"""
        if tool_name not in self._allowed_tools:
            raise PermissionError(
                f"工具 '{tool_name}' 不在当前步骤的允许范围内。"
                f"允许的工具: {', '.join(self._allowed_tools)}"
            )

        return await self._inner.execute(tool_name, **kwargs)

    def get_available_tools(self) -> list[str]:
        """获取可用的工具列表"""
        return list(self._allowed_tools)
```

### 5.6 用户交互流程

```
┌─────────────────────────────────────────────────────────────────┐
│                    用户交互流程                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  用户: "请分析这段代码"                                          │
│      │                                                          │
│      ▼                                                          │
│  TaskSession.dispatch_step_to("analyze", "请分析这段代码")       │
│      │                                                          │
│      ▼                                                          │
│  [analyze 步骤会话] messages: [{user: "请分析..."}]              │
│      │                                                          │
│      ▼                                                          │
│  SubAgent(analyze) 响应: "分析结果: ..."                         │
│      │                                                          │
│      ▼                                                          │
│  用户继续对话: "我想了解更多关于循环的问题"                       │
│      │                                                          │
│      ▼                                                          │
│  TaskSession.dispatch_step_to("analyze", "我想了解更多...")      │
│      │                                                          │
│      ▼                                                          │
│  [analyze 步骤会话] messages: [                                  │
│      {user: "请分析..."},                                        │
│      {assistant: "分析结果..."},                                 │
│      {user: "我想了解更多..."},  ◄─ 快照继续累积                 │
│  ]                                                              │
│      │                                                          │
│      ▼                                                          │
│  SubAgent(analyze) 响应: "关于循环的详细解释..."                 │
│      │                                                          │
│      ▼                                                          │
│  用户: "好了，我确认，进入下一步"                                 │
│      │                                                          │
│      ▼                                                          │
│  TaskSession.complete_step("analyze")                           │
│      │                                                          │
│      │  生成输出 → context["analysis"] = {...}                  │
│      │                                                          │
│      ▼                                                          │
│  TaskSession.switch_to_step("review")                           │
│      │                                                          │
│      ▼                                                          │
│  开始新的步骤会话...                                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. 与现有系统集成

### 6.1 与 Agent 类集成

在 `Agent` 类中新增多任务编排支持，MainAgent 作为路由中心：

```python
class Agent:
    def __init__(self, ...):
        # 现有初始化...

        # 新增: 多任务编排
        self._scenario_registry: ScenarioRegistry | None = None
        self._task_orchestrator: TaskOrchestrator | None = None
        self._sub_agent_manager: SubAgentManager | None = None
        self._message_router: MessageRouter | None = None

    async def _init_multitask(self) -> None:
        """初始化多任务编排 (在 initialize() 中调用)"""
        self._scenario_registry = ScenarioRegistry()
        await self._load_scenarios()

        # SubAgentManager 统一管理 SubAgent 创建
        self._sub_agent_manager = SubAgentManager(main_agent=self)

        self._task_orchestrator = TaskOrchestrator(
            scenario_registry=self._scenario_registry,
            sub_agent_manager=self._sub_agent_manager,
            agent=self,  # 注入当前 Agent 实例
        )

        # 创建消息路由器
        self._message_router = MessageRouter(
            main_agent=self,
            task_orchestrator=self._task_orchestrator,
            scenario_registry=self._scenario_registry,
        )

    async def chat(self, message: str, session_id: str | None = None) -> str:
        """
        对话入口 - 自动路由到正确的 Agent

        路由逻辑:
        1. 有活跃任务 → 路由到 SubAgent
        2. 场景匹配成功 → 创建任务，路由到 SubAgent
        3. 普通对话 → MainAgent 自己处理
        """
        if self._message_router:
            return await self._message_router.route(message, session_id or "default")

        # 回退到普通对话
        return await self._chat_normal(message, session_id)
```

### 6.2 与 TaskState 集成

复用现有的 `TaskState` 类，扩展支持多步骤：

```python
# 在 agent_state.py 中扩展 TaskState

@dataclass
class TaskState:
    # 现有字段...
    task_id: str
    status: TaskStatus
    # ...

    # 新增: 多步骤支持
    scenario_id: str = ""
    steps: dict[str, StepState] = field(default_factory=dict)
    current_step_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)  # 步骤间传递
```

### 6.3 与 ReasoningEngine 集成

**关键设计决策**: SubAgent 以独立进程运行，天然使用 ReasoningEngine。

#### 6.3.1 集成架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    SubAgent 推理架构                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  MainAgent                                                      │
│       │                                                         │
│       │ route(message)                                          │
│       ▼                                                         │
│  TaskSession                                                    │
│       │                                                         │
│       ├── step_sessions:                                        │
│       │       │                                                 │
│       │      "analyze": StepSession                             │
│       │           │                                             │
│       │           │  messages (快照/摘要)                         │
│       │           │  sub_agent_id (独立进程)                     │
│       │           │                                             │
│       │           ▼                                             │
│       │      ┌─────────────────────────────────┐               │
│       │      │   SubAgent (Worker Process)     │               │
│       │      │                                 │               │
│       │      │   ┌─────────────────────────┐  │               │
│       │      │   │     ReasoningEngine     │  │               │
│       │      │   │        (独立)           │  │               │
│       │      │   │                         │  │               │
│       │      │   │ Reason → Act → Observe  │  │               │
│       │      │   │ 多轮工具调用             │  │               │
│       │      │   │ 循环检测                 │  │               │
│       │      │   │ 上下文裁剪               │  │               │
│       │      │   └─────────────────────────┘  │               │
│       │      │              │                  │               │
│       │      │              ▼                  │               │
│       │      │      ┌───────────────┐         │               │
│       │      │      │ ToolExecutor  │         │               │
│       │      │      │ (Restricted)  │         │               │
│       │      │      └───────────────┘         │               │
│       │      │              │                  │               │
│       │      │              ▼                  │               │
│       │      │      ┌───────────────┐         │               │
│       │      │      │  BrainProxy   │         │               │
│       │      │      │ (共享配置)    │         │               │
│       │      │      └───────────────┘         │               │
│       │      └─────────────────────────────────┘               │
│       │                                                         │
│       └── context: {步骤间传递的上下文}                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 6.3.2 共享基础设施

SubAgent 与 MainAgent 共享以下组件：

| 组件 | 来源 | 说明 |
|------|------|------|
| Brain | MainAgent 配置/代理 | 共享模型配置或 Brain 代理 |
| ReasoningEngine | SubAgent 内部创建 | **独立实例**，完整推理循环 |
| ToolExecutor | 包装 MainAgent.tool_executor | 通过 RestrictedToolExecutor 限制 |

#### 6.3.3 SubAgent 独立性

SubAgent 作为独立进程的关键点：

| 维度 | MainAgent | SubAgent |
|------|-----------|----------|
| Agent 实例 | 主实例 | **独立进程实例** |
| ReasoningEngine | 独立 | **独立** |
| system_prompt | 全能助手提示词 | 步骤专用提示词 |
| tools | 全量工具 | 步骤允许的工具子集 |
| messages | 主对话历史 | 步骤快照/摘要 |
| context | 无前置上下文 | 前置步骤输出注入 |

```python
# SubAgent 使用方式（跨进程）
response = await task_session.dispatch_step_to(
    step_id=step_id,
    message=message,
)
```

### 6.4 与 WorkerAgent 架构统一

**关键设计**: SubAgent 和 WorkerAgent 都基于 Agent 架构，通过配置区分。

```python
# 统一的 Agent 创建工厂
class AgentFactory:
    """Agent 工厂 - 统一创建逻辑"""

    @staticmethod
    async def create_agent(config: AgentConfig) -> Agent:
        """
        创建 Agent 实例

        根据 config 区分：
        - MainAgent: 全量工具，完整能力
        - SubAgent: 独立进程步骤执行模式，受限工具，独立 ReasoningEngine
        - WorkerAgent: 独立进程通用执行模式
        """
        return await AgentFactory._create_worker(config)
```

**架构统一带来的好处**:

| 好处 | 说明 |
|------|------|
| **代码复用** | SubAgent 和 WorkerAgent 共享 Agent 核心逻辑 |
| **能力一致** | 都使用 ReasoningEngine，推理能力完全一致 |
| **易于测试** | 可以独立测试 SubAgent 的推理能力 |
| **易于扩展** | 新增执行模式只需调整配置 |

### 6.5 MainAgent 与 SubAgent/WorkerAgent 交互对比

```
┌─────────────────────────────────────────────────────────────────┐
│                MainAgent 交互机制对比                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  MainAgent ↔ SubAgent (本设计)                                  │
│  ─────────────────────────────                                  │
│                                                                 │
│  用户消息 → MainAgent.chat()                                    │
│       │                                                         │
│       ├── MessageRouter.route()                                 │
│       │       │                                                 │
│       │       ├── 有任务 → TaskSession.dispatch_step()          │
│       │       │       │                                         │
│       │       │       ▼                                         │
│       │       │   send StepRequest via ZMQ                      │
│       │       │       │                                         │
│       │       │       └── ZMQ 消息 (跨进程)                      │
│       │       │                                                 │
│       │       └── 无任务 → MainAgent.reasoning_engine.run()     │
│       │                                                         │
│       └── 返回响应                                              │
│                                                                 │
│                                                                 │
│  MainAgent ↔ WorkerAgent (现有)                                 │
│  ─────────────────────────                                      │
│                                                                 │
│  用户消息 → MasterAgent.handle_request()                        │
│       │                                                         │
│       ├── _should_handle_locally()                             │
│       │       │                                                 │
│       │       ├── 本地处理 → _handle_locally()                  │
│       │       │                                                 │
│       │       └── 分发 → _distribute_task()                     │
│       │               │                                         │
│       │               ▼                                         │
│       │       bus.send_command(ASSIGN_TASK)                     │
│       │               │                                         │
│       │               └── ZMQ 消息 (跨进程)                      │
│       │                       │                                 │
│       │                       ▼                                 │
│       │               WorkerAgent._handle_task()                │
│       │                       │                                 │
│       │                       ▼                                 │
│       │               Worker._agent.chat()                      │
│       │                       │                                 │
│       │                       ▼                                 │
│       │               TASK_RESULT → MainAgent                   │
│       │                                                         │
│       └── 返回响应                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**关键相似点**:
- **都是独立进程 Agent**: SubAgent 和 WorkerAgent 内部都是完整的 Agent
- **都使用 ReasoningEngine**: 完整的推理和工具执行能力
- **MainAgent 都是路由中心**: 决定消息如何分发

**关键差异**:
- **路由触发**: SubAgent 自动路由（场景匹配+任务状态），WorkerAgent 手动分发
- **生命周期**: SubAgent 随任务创建销毁，WorkerAgent 长期运行
- **模型接入**: SubAgent 共享模型配置/Brain 代理，WorkerAgent 独立 Brain

---

## 7. API 设计

### 7.1 REST API

```
POST   /api/tasks                    # 创建任务
GET    /api/tasks                    # 列出活跃任务
GET    /api/tasks/{task_id}          # 获取任务详情
DELETE /api/tasks/{task_id}          # 取消任务
POST   /api/tasks/{task_id}/confirm  # 确认步骤
GET    /api/scenarios                # 列出所有场景
GET    /api/scenarios/{scenario_id}  # 获取场景详情
```

### 7.2 WebSocket 事件

```
task.created        # 任务创建
task.started        # 任务开始
step.started        # 步骤开始
step.completed      # 步骤完成
step.waiting        # 等待用户确认
task.completed      # 任务完成
task.cancelled      # 任务取消
```

---

## 8. 场景定义示例

```python
# scenarios/code_review.py

from openakita.orchestration.task import (
    ScenarioDefinition,
    StepDefinition,
    ScenarioTrigger,
)

CODE_REVIEW_SCENARIO = ScenarioDefinition(
    scenario_id="code_review",
    name="代码审查助手",
    description="对代码进行全面分析和审查",
    category="development",
    trigger=ScenarioTrigger.BOTH,

    steps=[
        StepDefinition(
            step_id="analyze",
            name="代码分析",
            description="分析代码结构和潜在问题",
            system_prompt="你是一个代码分析专家...",
            tools=["read_file", "web_search"],
            output_key="analysis",
        ),
        StepDefinition(
            step_id="review",
            name="代码审查",
            description="生成详细的代码审查报告",
            system_prompt="你是一个代码审查专家...\n分析结果: {{analysis}}",
            tools=["read_file"],
            requires_user_confirm=True,
            output_key="review_report",
        ),
        StepDefinition(
            step_id="summary",
            name="总结报告",
            description="生成最终总结",
            system_prompt="基于分析结果和审查报告...",
            output_key="summary",
        ),
    ],

    trigger_keywords=["代码审查", "review", "检查代码"],
    trigger_patterns=[r"帮我(分析|审查).*代码"],
)
```

---

## 9. 实现任务拆分

建议按以下顺序分阶段实现：

### Phase 1: 基础框架 (3天)

| 任务 | 描述 | 依赖 |
|------|------|------|
| T1.1 | 实现 `state.py` - 任务/步骤状态定义 | 无 |
| T1.2 | 实现 `step.py` - 步骤定义 | 无 |
| T1.3 | 实现 `scenario.py` - 场景定义和注册表 | T1.2 |
| T1.4 | 编写单元测试 | T1.1-T1.3 |

### Phase 2: 编排核心 (4天)

| 任务 | 描述 | 依赖 |
|------|------|------|
| T2.1 | 实现 `session.py` - 任务会话 | T1.1 |
| T2.2 | 实现 `orchestrator.py` - 任务编排器核心 | T1.3, T2.1 |
| T2.3 | 实现 `subagent_manager.py` - SubAgent 管理器 | T1.2, T2.2 |
| T2.4 | 实现 `router.py` - 消息路由器 | T2.2 |
| T2.5 | 集成测试 | T2.1-T2.4 |

### Phase 3: 系统集成 (3天)

| 任务 | 描述 | 依赖 |
|------|------|------|
| T3.1 | Agent 类扩展 (集成 MessageRouter) | T2.2, T2.4 |
| T3.2 | 实现 RestrictedToolExecutor | T2.3 |
| T3.3 | 与现有 WorkerAgent 架构统一验证 | T2.3 |
| T3.4 | 集成测试 | T3.1-T3.3 |

### Phase 4: API 与前端 (3天)

| 任务 | 描述 | 依赖 |
|------|------|------|
| T4.1 | REST API 实现 | T2.2 |
| T4.2 | WebSocket 事件推送 | T4.1 |
| T4.3 | 前端集成 | T4.1, T4.2 |

### Phase 5: 测试与文档 (2天)

| 任务 | 描述 | 依赖 |
|------|------|------|
| T5.1 | 集成测试 | T4.1-T4.3 |
| T5.2 | 示例场景 | T5.1 |
| T5.3 | 文档完善 | T5.2 |

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| SubAgent 独立进程资源消耗 | 内存使用增加 | 共享模型配置/Brain 代理，限制并发 |
| TaskState 扩展影响现有代码 | 状态管理复杂度增加 | 使用组合而非继承，保持向后兼容 |
| 多步骤上下文传递复杂 | 数据流难以追踪 | 明确定义 input_schema/output_key |
| 用户交互打断执行流 | 状态管理复杂 | 使用 WAITING_USER 状态暂停 |
| 路由逻辑复杂 | 消息分发可能出错 | MessageRouter 独立测试，清晰的状态检查 |

---

## 11. 总结

本设计基于对现有代码的深入分析，采用了以下关键策略：

### 11.1 核心设计决策

| 设计点 | 决策 | 原因 |
|--------|------|------|
| **SubAgent 本质** | 独立进程步骤执行模式 | 与 WorkerAgent 架构统一，完整推理能力 |
| **独立对话** | SubAgent 进程维护历史，StepSession 保留快照 | 支持多轮交互 |
| **执行引擎** | 独立 ReasoningEngine | 确保 SubAgent 与 MainAgent 能力一致 |
| **路由机制** | MainAgent 自动路由 (场景匹配 + 任务状态) | 简洁高效的消息分发 |
| **流程控制** | 用户显式调用 switch_to_step | 避免 LLM tool_call 主导流程 |

### 11.2 关键改动清单

1. **SubAgent 是独立进程执行模式** - 具备完整推理能力
2. **StepSession** - 每个步骤绑定独立 SubAgent 进程标识与快照
3. **MessageRouter** - MainAgent 作为路由中心，自动分发消息
4. **dispatch_step()** - 向指定 SubAgent 进程发送步骤请求
5. **complete_step()** - 显式结束步骤，生成输出
6. **switch_to_step()** - 用户控制流程跳转

### 11.3 与 MainAgent-WorkerAgent 的关系

```
┌─────────────────────────────────────────────────────────────────┐
│                    统一 Agent 架构                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                    MainAgent                            │  │
│   │   - 路由中心 (MessageRouter)                            │  │
│   │   - 场景匹配 (ScenarioRegistry)                         │  │
│   │   - 任务管理 (TaskOrchestrator)                         │  │
│   └─────────────────────────────────────────────────────────┘  │
│                              │                                  │
│              ┌───────────────┴───────────────┐                 │
│              ▼                               ▼                 │
│   ┌─────────────────────┐      ┌─────────────────────┐        │
│   │      SubAgent       │      │     WorkerAgent     │        │
│   │   (独立进程 Agent)   │      │   (独立进程 Agent)   │        │
│   │                     │      │                     │        │
│   │   - 独立进程        │      │   - 独立进程         │        │
│   │   - Brain 代理      │      │   - 独立 Brain       │        │
│   │   - 独立 Reasoning  │      │   - 独立 Reasoning   │        │
│   │   - 受限工具        │      │   - 完整工具         │        │
│   │   - 自动路由        │      │   - 手动分发         │        │
│   └─────────────────────┘      └─────────────────────┘        │
│                                                                 │
│   关键相似: 都是独立进程 Agent，使用 ReasoningEngine            │
│   关键差异: 进程模式、通信方式、资源隔离                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 11.4 简洁的路由机制

```
用户消息 → MainAgent.chat() → MessageRouter.route()
                                      │
                                      ├── 有活跃任务 → SubAgent
                                      │
                                      ├── 场景匹配成功 → 创建任务 → SubAgent
                                      │
                                      └── 普通对话 → MainAgent
```

### 11.5 设计优势

| 优势 | 说明 |
|------|------|
| **架构统一** | SubAgent 和 WorkerAgent 都是独立进程 Agent |
| **能力完整** | SubAgent 具备完整推理能力，不是阉割版 |
| **路由简洁** | MainAgent 自动路由，无需复杂的 handoff 机制 |
| **独立对话** | SubAgent 进程维护历史，支持多轮交互 |
| **易于扩展** | 通过配置调整 SubAgent 行为，无需修改核心代码 |

---

## 附录 A: 关键类图

```
┌─────────────────────────────────────────────────────────────────┐
│                         类关系图                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────┐      ┌─────────────────┐      ┌───────────────┐ │
│  │  Agent    │──────│ SubAgentManager │──────│  SubAgent     │ │
│  │ (Main)    │      │                 │      │  (Agent)      │ │
│  └─────┬─────┘      └────────┬────────┘      └───────┬───────┘ │
│        │                     │                       │         │
│        │                     │ creates               │         │
│        ▼                     ▼                       ▼         │
│  ┌───────────┐      ┌─────────────────┐      ┌───────────────┐ │
│  │ Message   │      │ TaskOrchestrator│      │ StepSession   │ │
│  │ Router    │──────│                 │──────│               │ │
│  └───────────┘      └────────┬────────┘      └───────┬───────┘ │
│                              │                       │         │
│                              │ manages               │ contains│
│                              ▼                       ▼         │
│                     ┌─────────────────┐      ┌───────────────┐ │
│                     │  TaskSession    │──────│ SubAgentConfig│ │
│                     │                 │      │               │ │
│                     └─────────────────┘      └───────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 附录 B: 架构复用关系

```
┌─────────────────────────────────────────────────────────────────┐
│                    架构复用关系                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  新设计                          复用现有组件                    │
│  ────────                        ────────────                   │
│  SubAgent (独立进程 Agent)      Agent 核心架构                 │
│  StepSession                     WorkerAgent 架构模式           │
│  TaskState                       AgentState.TaskState          │
│  Brain                           LLM 客户端                     │
│  ReasoningEngine                 推理引擎                       │
│                                                                 │
│  新增组件                                                        │
│  ────────                                                       │
│  ScenarioRegistry (场景管理)                                    │
│  TaskSession (独立会话管理)                                      │
│  TaskOrchestrator (任务编排)                                    │
│  MessageRouter (消息路由)                                        │
│  SubAgentManager (SubAgent 生命周期管理)                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

这种设计确保了与现有架构的一致性，最大化代码复用，同时保持清晰的模块边界。SubAgent 以独立进程运行，与 WorkerAgent 架构统一，具备完整的推理能力。MainAgent 作为路由中心，实现简洁高效的消息分发机制。
