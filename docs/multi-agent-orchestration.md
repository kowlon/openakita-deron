# OpenAkita 多 Agent 协同模式

本文档详细介绍 OpenAkita 项目中的多 Agent 协同架构，包括两种核心模式的实现原理、数据流、以及使用方式。

## 目录

- [概述](#概述)
- [架构总览](#架构总览)
- [Handoff 模式](#handoff-模式)
- [Master-Worker 模式](#master-worker-模式)
- [上下文处理机制](#上下文处理机制)
- [两种模式对比](#两种模式对比)
- [配置与使用](#配置与使用)
- [核心组件参考](#核心组件参考)

---

## 概述

OpenAkita 实现了两种多 Agent 协同模式：

| 模式 | 特点 | 适用场景 |
|------|------|---------|
| **Handoff** | 轻量级进程内 Agent 切换 | 串行协作、能力委托 |
| **Master-Worker** | ZMQ 跨进程分布式任务调度 | 并行执行、高并发任务 |

设计参考了 **OpenAI Agents SDK (Swarm)** 的 Handoff 模式，同时结合 ZeroMQ 实现了分布式架构。

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        OpenAkita 架构                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   配置选择: orchestration_mode = "single" | "handoff" | "master-worker" │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                   single (默认)                          │  │
│   │   单 Agent 模式，无协同                                   │  │
│   │                                                         │  │
│   │   CLI/Gateway ──► Agent ──► LLM                         │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                   handoff                                │  │
│   │   进程内 Agent 切换，通过 LLM 工具调用实现                 │  │
│   │                                                         │  │
│   │   CLI/Gateway ──► HandoffOrchestrator                   │  │
│   │                          │                              │  │
│   │                          ▼                              │  │
│   │                    HandoffAgent A ──(handoff)──► Agent B │  │
│   │                          │                              │  │
│   │                          ▼                              │  │
│   │                       共享 Brain (LLM)                   │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                   master-worker                          │  │
│   │   ZMQ 跨进程任务分发                                      │  │
│   │                                                         │  │
│   │   CLI/Gateway ──► MasterAgent                           │  │
│   │                          │                              │  │
│   │              ┌───────────┼───────────┐                  │  │
│   │              ▼           ▼           ▼                  │  │
│   │         Worker 1    Worker 2    Worker N                │  │
│   │         (进程 1)    (进程 2)    (进程 N)                 │  │
│   │              │           │           │                  │  │
│   │              ▼           ▼           ▼                  │  │
│   │           Agent       Agent       Agent                 │  │
│   │           (独立)      (独立)      (独立)                 │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Handoff 模式

### 核心原理

**Handoff 模式通过 LLM 工具调用实现 Agent 切换。**

将"切换到另一个 Agent"定义为 LLM 可调用的工具，让 LLM 根据任务语义自主决定何时切换。

```
┌─────────────────────────────────────────────────────────────────┐
│                    Handoff 核心原理                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   1. 将"切换 Agent"定义为 LLM 工具                               │
│                                                                 │
│      tools: [{                                                  │
│        name: "transfer_to_code_reviewer",                       │
│        description: "当代码编写完成需要审查时",                  │
│        input_schema: {                                          │
│          message: "传递给目标 Agent 的上下文"                    │
│        }                                                        │
│      }]                                                         │
│                                                                 │
│   2. LLM 根据任务决定是否调用 handoff 工具                       │
│                                                                 │
│   3. Orchestrator 检测工具调用，执行切换                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 核心组件

#### HandoffAgent

`HandoffAgent` 是一个 **dataclass 配置对象**，不是真正的 Agent 实例。

```python
@dataclass
class HandoffAgent:
    name: str                           # 角色名称
    description: str                    # 角色描述
    system_prompt: str = ""             # 系统提示词
    tools: list[str] = field(default_factory=list)  # 允许使用的工具
    handoffs: list[HandoffTarget] = field(default_factory=list)  # 可委托目标
    max_iterations: int = 20            # 最大迭代数
```

#### HandoffTarget

描述当前 Agent 可以委托给哪些其他 Agent。

```python
@dataclass
class HandoffTarget:
    agent_name: str      # 目标 Agent 名称
    tool_name: str       # 生成的工具名称 (如 "transfer_to_code_reviewer")
    description: str     # 何时触发 handoff 的说明
    input_filter: Callable | None = None  # 上下文过滤器
```

#### HandoffOrchestrator

管理多个 `HandoffAgent` 之间的切换和消息路由。

```python
class HandoffOrchestrator:
    MAX_HANDOFFS = 10  # 防止 Agent 之间无限互相委托

    def __init__(
        self,
        agents: list[HandoffAgent],
        entry_agent: HandoffAgent | None = None,
        brain: Any = None,  # 共享的 LLM 客户端
    ): ...
```

### 数据流

```
┌─────────────────────────────────────────────────────────────────┐
│                      Handoff 数据流                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Step 1: 初始化                                                  │
│  ─────────────────────────────────────────                      │
│  orchestrator.run("写一个排序算法并审查")                         │
│  │                                                              │
│  ├─► current_agent = coder (入口 Agent)                         │
│  └─► messages = [{"role": "user", "content": "..."}]            │
│                                                                 │
│  Step 2: Coder Agent 推理                                        │
│  ─────────────────────────────────────────                      │
│  调用 LLM:                                                       │
│  {                                                              │
│    system: "你是 'coder' Agent...                               │
│            可用委托: transfer_to_reviewer",                      │
│    messages: [...],                                             │
│    tools: [... + handoff_tools]                                 │
│  }                                                              │
│                                                                 │
│  LLM 响应:                                                       │
│  {                                                              │
│    content: [                                                   │
│      {type: "text", text: "这是冒泡排序..."},                    │
│      {type: "tool_use", name: "transfer_to_reviewer",           │
│       input: {message: "请审查这段代码"}}                        │
│    ]                                                            │
│  }                                                              │
│                                                                 │
│  Step 3: Orchestrator 检测 Handoff                               │
│  ─────────────────────────────────────────                      │
│  检测到 tool_use.name == "transfer_to_reviewer"                  │
│  │                                                              │
│  ├─► 找到目标: target_agent = "reviewer"                         │
│  ├─► 记录事件: handoff_history.append(coder→reviewer)            │
│  └─► 更新消息:                                                   │
│       messages.append({                                         │
│         role: "user",                                           │
│         content: "[Handoff from 'coder'] 请审查..."              │
│       })                                                        │
│                                                                 │
│  Step 4: Reviewer Agent 推理                                     │
│  ─────────────────────────────────────────                      │
│  current_agent = reviewer                                       │
│  调用 LLM (新 system prompt + 更新后的 messages)                 │
│                                                                 │
│  LLM 响应 (无 handoff):                                          │
│  {stop_reason: "end_turn", content: "审查结果: 良好..."}         │
│                                                                 │
│  Step 5: 返回结果                                                │
│  ─────────────────────────────────────────                      │
│  return "审查结果: 良好..."                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 使用示例

```python
from openakita.orchestration import HandoffAgent, HandoffOrchestrator

# 定义 Agent 角色
coder = HandoffAgent(
    name="coder",
    description="擅长编写和修改代码",
    system_prompt="你是代码编写专家...",
    tools=["run_shell", "write_file", "read_file"],
)

reviewer = HandoffAgent(
    name="reviewer",
    description="擅长代码审查和质量改进",
    system_prompt="你是代码审查专家...",
    tools=["read_file", "web_search"],
)

# 建立 handoff 关系
coder.add_handoff(reviewer, description="当代码编写完成需要审查时")
reviewer.add_handoff(coder, description="当审查发现问题需要修改代码时")

# 创建编排器
orchestrator = HandoffOrchestrator(
    agents=[coder, reviewer],
    entry_agent=coder,
    brain=shared_brain,  # 共享的 LLM 客户端
)

# 运行
result = await orchestrator.run("请帮我写一个排序算法并审查")
```

### Agent 创建时机

**必须预先手动创建所有 HandoffAgent。**

Orchestrator 运行时只在已定义的 agents 之间切换，不能动态创建新 Agent。

---

## Master-Worker 模式

### 核心原理

**Master-Worker 模式基于 ZeroMQ 消息队列实现分布式任务调度。**

```
┌──────────────────────────────────────────────────────────────┐
│                 Master-Worker 通信原理                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   Master 进程                          Worker 进程           │
│   ┌─────────────┐                     ┌─────────────┐       │
│   │   ROUTER    │◄───────────────────►│   DEALER    │       │
│   │  (ZMQ)      │    命令/响应         │  (ZMQ)      │       │
│   └──────┬──────┘                     └──────┬──────┘       │
│          │                                   │               │
│          │ 事件广播                          │ 心跳          │
│          ▼                                   ▼               │
│   ┌─────────────┐                     ┌─────────────┐       │
│   │    PUB      │────────────────────►│    SUB      │       │
│   │  (广播事件)  │                     │ (订阅事件)  │       │
│   └─────────────┘                     └─────────────┘       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### ZMQ Socket 角色

| Socket | 位置 | 作用 |
|--------|------|------|
| `ROUTER` | Master | 接收所有 Worker 消息，可路由回复 |
| `DEALER` | Worker | 向 Master 发送消息，接收命令 |
| `PUB` | Master | 广播事件（如 Agent 注册/注销） |
| `SUB` | Worker | 订阅 Master 的事件广播 |

### 核心组件

#### MasterAgent

主协调器，负责：
- 任务分发和路由
- Worker 生命周期管理
- 简单任务直接处理
- 健康监控和故障恢复
- 动态扩缩容

```python
class MasterAgent:
    DEFAULT_MIN_WORKERS = 1
    DEFAULT_MAX_WORKERS = 5
    DEFAULT_HEARTBEAT_INTERVAL = 5
    DEFAULT_HEALTH_CHECK_INTERVAL = 10

    def __init__(
        self,
        agent_id: str = "master",
        bus_config: BusConfig | None = None,
        min_workers: int = 1,
        max_workers: int = 5,
        ...
    ): ...
```

#### WorkerAgent

工作进程，负责：
- 接收 Master 分发的任务
- 使用内置 Agent 执行任务
- 返回结果给 Master
- 定期发送心跳

```python
class WorkerAgent:
    def __init__(
        self,
        agent_id: str,
        router_address: str = "tcp://127.0.0.1:5555",
        pub_address: str = "tcp://127.0.0.1:5556",
        heartbeat_interval: int = 5,
        capabilities: list[str] | None = None,
        ...
    ): ...
```

#### AgentBus

ZMQ 通信总线，处理进程间通信。

```python
class AgentBus:
    def __init__(
        self,
        config: BusConfig | None = None,
        is_master: bool = True,  # True=Master端, False=Worker端
    ): ...
```

### 消息协议

```python
@dataclass
class AgentMessage:
    msg_id: str           # 消息唯一 ID
    msg_type: str         # command | response | event | heartbeat
    sender_id: str        # 发送者
    target_id: str        # 目标（"*" 表示广播）
    payload: dict         # 消息内容
    command_type: str     # ASSIGN_TASK | TASK_RESULT | REGISTER...
    correlation_id: str   # 请求-响应配对
    ttl: int = 60         # 消息有效期（秒）
```

#### 命令类型

```python
class CommandType(Enum):
    # Agent 生命周期
    REGISTER = "register"
    UNREGISTER = "unregister"
    SHUTDOWN = "shutdown"

    # 任务相关
    ASSIGN_TASK = "assign_task"
    CANCEL_TASK = "cancel_task"
    TASK_RESULT = "task_result"

    # 状态查询
    GET_STATUS = "get_status"
    LIST_AGENTS = "list_agents"

    # 通信
    CHAT_REQUEST = "chat_request"
    CHAT_RESPONSE = "chat_response"
```

### 数据流

```
┌─────────────────────────────────────────────────────────────────┐
│                   Master-Worker 数据流                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  时间线 T1: Worker 启动注册                                       │
│  ─────────────────────────────────────────                      │
│  Worker 进程                          Master 进程                │
│       │                                    │                     │
│       ├──► DEALER connect ────────────────►│                     │
│       │                                    │                     │
│       ├──► REGISTER ──────────────────────►│                     │
│       │    {agent_id, status,             │                     │
│       │     capabilities}                  │                     │
│       │                                    ▼                     │
│       │                              Registry.register()         │
│       │                                    │                     │
│       │◄─── AGENT_REGISTERED ─────────────┤ (广播)              │
│       │                                    │                     │
│                                                                 │
│  时间线 T2: 任务分发                                              │
│  ─────────────────────────────────────────                      │
│  CLI/Gateway ──► MasterAgent.handle_request()                   │
│                          │                                      │
│                          ▼                                      │
│                   _should_handle_locally()?                      │
│                          │                                      │
│                     消息复杂? ──► 否 ──► 本地处理                │
│                          │                                      │
│                         是                                       │
│                          │                                      │
│                          ▼                                      │
│                   find_idle_agent()                             │
│                          │                                      │
│                          ▼                                      │
│                   ASSIGN_TASK ───► Worker                       │
│                   {task_id, content}                            │
│                          │                                      │
│                          │◄─── TASK_RESULT ──── Worker          │
│                          │                                      │
│                          ▼                                      │
│                   返回给用户                                     │
│                                                                 │
│  时间线 T3: 心跳监控 (并行)                                        │
│  ─────────────────────────────────────────                      │
│  Worker 每 5 秒:                                                 │
│       HEARTBEAT ──────────────────────► Master                 │
│       {agent_id, status, current_task}                          │
│                                                                 │
│  Master 每 10 秒:                                                │
│       if 心跳超时 > 15秒:                                        │
│           标记 Agent 为 DEAD                                    │
│           重新分配任务                                           │
│           spawn_worker() 补充                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Worker 创建流程

```
┌─────────────────────────────────────────────────────────────────┐
│                Worker 创建时机                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  时机 1: Master 启动时                                           │
│  ─────────────────────────────────────────                      │
│  master.start()                                                 │
│       │                                                         │
│       ▼                                                         │
│  for _ in range(min_workers):  # 默认 min_workers=1            │
│      await self.spawn_worker()                                  │
│                                                                 │
│                                                                 │
│  时机 2: Worker 死亡后自动补充                                    │
│  ─────────────────────────────────────────                      │
│  _health_check_loop()  (每 10 秒)                               │
│       │                                                         │
│       ▼                                                         │
│  if current_workers < min_workers:                              │
│      await self.spawn_worker()  # 补充                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Worker 进程内部流程

```python
# master.py:708-752
def _worker_process_entry(worker_id, router_address, ...):
    """Worker 进程入口函数"""
    async def run_worker():
        worker = WorkerAgent(
            agent_id=worker_id,
            router_address=router_address,
            ...
        )
        await worker.start()

        while worker.is_running:
            await asyncio.sleep(1)

    asyncio.run(run_worker())
```

```python
# worker.py:180-188
async def _init_agent(self):
    """初始化内置 Agent"""
    from ..core.agent import Agent
    self._agent = Agent()  # 创建真正的 Agent 实例
    await self._agent.initialize(start_scheduler=False)
```

### Worker 是否相同？

**默认相同**，但设计上支持不同 capabilities。

```python
# 默认情况
async def spawn_worker(
    self,
    agent_type: str = "worker",           # 相同类型
    capabilities: list[str] | None = None,  # 默认 ["chat", "execute"]
): ...
```

---

## 上下文处理机制

本节详细介绍两种模式下上下文（messages、system_prompt、tools 等）的处理方式。

### 上下文的组成部分

```
┌─────────────────────────────────────────────────────────────────┐
│                        上下文组成                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. messages (对话历史)                                         │
│     - 用户消息、助手回复、工具调用和结果                          │
│                                                                 │
│  2. system_prompt (系统提示词)                                   │
│     - 定义 Agent 的角色和行为                                    │
│                                                                 │
│  3. tools (可用工具集)                                          │
│     - Agent 可以调用的工具列表                                   │
│                                                                 │
│  4. handoff 工具 (仅 Handoff 模式)                              │
│     - 用于切换 Agent 的特殊工具                                  │
│                                                                 │
│  5. handoff_history (仅 Handoff 模式)                           │
│     - Agent 之间的切换历史记录                                   │
│                                                                 │
│  6. session/gateway (仅 Master-Worker 关注)                     │
│     - 会话对象和消息网关（不可序列化）                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### Handoff 模式的上下文处理

#### 1. Messages (对话历史)

**特点：全程共享，持续累积**

```python
# 初始化
messages: list[dict] = [{"role": "user", "content": message}]

# 切换 Agent 时，追加 handoff 上下文
messages.append({
    "role": "user",
    "content": f"[Handoff from '{agent.name}'] {handoff_message}",
})
```

```
┌─────────────────────────────────────────────────────────────────┐
│                Handoff 模式 Messages 处理                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  初始状态:                                                       │
│  messages = [                                                   │
│    {role: "user", content: "写一个排序算法并审查"}                │
│  ]                                                              │
│                                                                 │
│  Coder Agent 处理后 (准备 handoff):                              │
│  messages = [                                                   │
│    {role: "user", content: "写一个排序算法并审查"},               │
│    {role: "assistant", content: "这是冒泡排序...", tool_use: ...}│
│    {role: "user", content: "[Handoff from 'coder'] 请审查..."}   │
│  ]                                                              │
│                                                                 │
│  Reviewer Agent 接收全部 messages                                │
│  → 可以看到之前所有对话内容                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**支持上下文过滤：**

```python
# 可通过 input_filter 过滤敏感信息
if target_handoff and target_handoff.input_filter:
    messages = target_handoff.input_filter(messages)
```

#### 2. System Prompt (系统提示词)

**特点：每个 Agent 独立，动态构建**

```python
def _build_agent_prompt(self, agent: HandoffAgent) -> str:
    parts = []

    # 1. 基础 prompt（每个 Agent 不同）
    if agent.system_prompt:
        parts.append(agent.system_prompt)
    else:
        parts.append(f"你是 '{agent.name}' Agent。{agent.description}")

    # 2. 添加 handoff 工具说明
    if agent.handoffs:
        parts.append("\n## 可用的 Agent 委托")
        for h in agent.handoffs:
            parts.append(f"- `{h.tool_name}`: {h.description}")

    # 3. 添加 handoff 历史
    if self._handoff_history:
        parts.append("\n## 委托历史")
        for event in self._handoff_history[-5:]:
            parts.append(f"- {event.from_agent} → {event.to_agent}: ...")

    return "\n".join(parts)
```

```
┌─────────────────────────────────────────────────────────────────┐
│              Handoff 模式 System Prompt 处理                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Coder Agent 的 system_prompt:                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 你是代码编写专家...                                       │   │
│  │                                                         │   │
│  │ ## 可用的 Agent 委托                                     │   │
│  │ - `transfer_to_reviewer`: 当需要审查时                   │   │
│  │                                                         │   │
│  │ ## 委托历史                                              │   │
│  │ (首次为空)                                               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Reviewer Agent 的 system_prompt (切换后):                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 你是代码审查专家...                                       │   │
│  │                                                         │   │
│  │ ## 可用的 Agent 委托                                     │   │
│  │ - `transfer_to_coder`: 当需要修改代码时                  │   │
│  │                                                         │   │
│  │ ## 委托历史                                              │   │
│  │ - coder → reviewer: 请审查这段代码                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 3. Tools (工具集)

**特点：每个 Agent 可定义不同的工具 + 动态添加 handoff 工具**

```python
def get_handoff_tools(self) -> list[dict]:
    """将 HandoffTarget 转化为 LLM 可调用的工具 schema"""
    tools = []
    for h in self.handoffs:
        tools.append({
            "name": h.tool_name,
            "description": f"将任务委托给 '{h.agent_name}' Agent。",
            "input_schema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "传递给目标 Agent 的上下文"}
                },
                "required": ["message"],
            },
        })
    return tools
```

```
┌─────────────────────────────────────────────────────────────────┐
│                 Handoff 模式 Tools 处理                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Coder Agent 的 tools:                                          │
│  [                                                              │
│    run_shell, write_file, read_file,  # ← Agent 定义的普通工具  │
│    transfer_to_reviewer,              # ← 动态添加的 handoff 工具│
│  ]                                                              │
│                                                                 │
│  Reviewer Agent 的 tools:                                       │
│  [                                                              │
│    read_file, web_search,             # ← Agent 定义的普通工具  │
│    transfer_to_coder,                 # ← 动态添加的 handoff 工具│
│  ]                                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 4. Handoff History

**特点：Orchestrator 维护，注入到 system_prompt**

```python
@dataclass
class HandoffEvent:
    from_agent: str
    to_agent: str
    message: str
    timestamp: float

# 记录 handoff
event = HandoffEvent(
    from_agent=agent.name,
    to_agent=target_name,
    message=handoff_message,
)
self._handoff_history.append(event)
```

---

### Master-Worker 模式的上下文处理

#### 1. Messages (对话历史)

**特点：通过 TaskPayload 序列化传递**

```python
# Master 端：创建任务时序列化
task = TaskPayload(
    task_id=task_id,
    task_type="chat",
    content=message,
    session_id=session_id,
    context={
        "session_messages": session_messages or [],  # ← 序列化传递
        "has_session": session is not None,
        "has_gateway": gateway is not None,
    },
)

# Worker 端：接收任务时反序列化
session_messages = task.context.get("session_messages", [])
response = await self._agent.chat_with_session(
    message=task.content,
    session_messages=session_messages,
    session_id=session_id,
)
```

```
┌─────────────────────────────────────────────────────────────────┐
│              Master-Worker 模式 Messages 处理                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Master 进程                                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ SessionManager                                           │   │
│  │   └─ session.context.get_messages()                     │   │
│  │          │                                              │   │
│  │          ▼                                              │   │
│  │   session_messages = [                                  │   │
│  │     {role: "user", content: "..."},                     │   │
│  │     {role: "assistant", content: "..."},                │   │
│  │   ]                                                     │   │
│  │          │                                              │   │
│  │          ▼ 序列化为 JSON                                 │   │
│  │   TaskPayload(context={"session_messages": [...]})      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                         │                                       │
│                         │ ZMQ 消息传递                          │
│                         ▼                                       │
│  Worker 进程                                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ task.context.get("session_messages")                    │   │
│  │          │                                              │   │
│  │          ▼ 反序列化                                     │   │
│  │   agent.chat_with_session(messages=session_messages)    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 2. System Prompt 和 Tools

**特点：Worker 独立初始化，但加载相同配置**

```python
# worker.py:180-188
async def _init_agent(self):
    from ..core.agent import Agent
    self._agent = Agent()  # ← 创建新的 Agent 实例
    await self._agent.initialize()  # ← 从相同配置文件加载
```

```python
# agent.py:616-670 - Agent.initialize()
async def initialize(self, start_scheduler: bool = True):
    # 加载身份文档
    self.identity.load()  # ← 从 settings.identity_path 读取

    # 加载已安装的技能
    await self.skill_manager.load_installed_skills()  # ← 从 data/skills/ 读取

    # 加载 MCP 配置
    await self.mcp_manager.load_servers()  # ← 从 MCP 配置文件读取

    # 构建系统提示词
    base_prompt = self.identity.get_system_prompt()
    self._context.system = self._build_system_prompt(base_prompt)
```

```
┌─────────────────────────────────────────────────────────────────┐
│                      文件系统（共享）                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  settings.py (全局配置)                                          │
│  identity.md (身份文档)                                          │
│  data/skills/ (已安装技能)                                        │
│  mcp_config.json (MCP 配置)                                      │
│  data/memory/ (记忆存储)                                         │
│                                                                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            │                               │
            ▼                               ▼
┌─────────────────────┐           ┌─────────────────────┐
│   Master 进程        │           │   Worker 进程       │
│                     │           │                     │
│  _local_agent       │           │  _agent             │
│    └─ initialize()  │           │    └─ initialize()  │
│        │            │           │        │            │
│        ▼            │           │        ▼            │
│  加载相同的配置      │           │  加载相同的配置      │
│  加载相同的技能      │           │  加载相同的技能      │
│  加载相同的 MCP      │           │  加载相同的 MCP      │
│                     │           │                     │
│  system_prompt = A  │           │  system_prompt = A  │
│  tools = [x, y, z]  │           │  tools = [x, y, z]  │
└─────────────────────┘           └─────────────────────┘
```

#### 3. Session 和 Gateway（不可序列化对象）

**特点：不传递，Master 端保留引用**

```python
# Master 端：只传递标志位
context={
    "session_messages": session_messages or [],
    # 注意：session 和 gateway 不能序列化
    "has_session": session is not None,   # ← 只传递标志位
    "has_gateway": gateway is not None,
}
```

```
┌─────────────────────────────────────────────────────────────────┐
│           Master-Worker 不可序列化对象处理                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Master 进程                          Worker 进程               │
│  ┌──────────────────┐                ┌──────────────────┐      │
│  │ session 对象      │                │ 无 session 对象  │      │
│  │ gateway 对象      │  ──不可传──►   │ 无 gateway 对象  │      │
│  │                   │                │                  │      │
│  │ 保留引用，等待结果  │◄──返回结果──  │ 只处理消息内容   │      │
│  └──────────────────┘                └──────────────────┘      │
│                                                                 │
│  处理方式:                                                       │
│  1. Master 将 session_messages 序列化传递                        │
│  2. Worker 处理完成后返回文本结果                                 │
│  3. Master 收到结果后，再通过 session/gateway 发送响应            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 上下文处理对比总结

```
┌─────────────────┬─────────────────────┬─────────────────────────┐
│     上下文       │    Handoff 模式     │   Master-Worker 模式    │
├─────────────────┼─────────────────────┼─────────────────────────┤
│ messages        │ 共享，持续累积        │ 序列化传递，独立副本    │
│                 │ 切换时追加 handoff   │                         │
├─────────────────┼─────────────────────┼─────────────────────────┤
│ system_prompt   │ 每个 Agent 自己定义  │ 共享配置，独立初始化    │
│                 │ 动态构建（含历史）    │ 加载相同配置文件        │
├─────────────────┼─────────────────────┼─────────────────────────┤
│ tools           │ 每个 Agent 定义不同  │ 共享配置，独立初始化    │
│                 │ + 动态 handoff 工具  │ 加载相同工具集          │
├─────────────────┼─────────────────────┼─────────────────────────┤
│ handoff_history │ Orchestrator 维护   │ 不适用                  │
│                 │ 注入到 system_prompt │                         │
├─────────────────┼─────────────────────┼─────────────────────────┤
│ session/gateway │ 不适用              │ Master 端保留引用       │
│                 │                     │ 只传序列化数据          │
├─────────────────┼─────────────────────┼─────────────────────────┤
│ 内存模型        │ 共享内存            │ 进程隔离                │
│                 │ 同一 Python 对象    │ 需要序列化/反序列化     │
└─────────────────┴─────────────────────┴─────────────────────────┘
```

### 简单记忆

```
Handoff 模式 = "换人演戏"
┌─────────────────────────────────────────┐
│         共享一个 LLM (Brain)             │
│                                         │
│   Agent A          Agent B              │
│   自己的 prompt    自己的 prompt         │
│   自己的 tools     自己的 tools          │
│        │               │                │
│        └───────┬───────┘                │
│                ▼                        │
│           共享 messages                  │
└─────────────────────────────────────────┘

Master-Worker 模式 = "分身术"
┌─────────────────────────────────────────┐
│  Master 进程                             │
│    MasterAgent (加载配置 A)              │
└─────────────────────────────────────────┘
                │ 序列化 messages
                ▼
┌─────────────────────────────────────────┐
│  Worker 进程 (完全独立)                  │
│    WorkerAgent (加载配置 A)              │
│    独立实例，但加载相同配置               │
└─────────────────────────────────────────┘
```

**一句话总结：**
- **Handoff** = 每个 Agent 有自己的 prompt/tools，共享 messages
- **Master-Worker** = 每个进程独立初始化，加载相同配置，messages 需序列化传递

---

## 两种模式对比

### 架构对比

| 维度 | Handoff 模式 | Master-Worker 模式 |
|------|-------------|-------------------|
| **通信机制** | 进程内函数调用 | ZMQ 消息队列 |
| **进程模型** | 单进程 | 多进程 |
| **Agent 实体** | 虚拟角色（dataclass） | 真正的 Agent 实例 |
| **LLM 实例** | 共享一个 brain | 每个 Worker 独立 brain |
| **内存空间** | 共享 | 隔离 |
| **切换决策** | LLM 语义决策 | Master 调度算法 |

### 创建方式对比

| 问题 | Handoff 模式 | Master-Worker 模式 |
|------|-------------|-------------------|
| **创建时机** | 必须预先手动定义所有 Agent | Master 启动时自动创建 |
| **能否动态创建** | ❌ 不能 | ✅ 可以 `spawn_worker()` |
| **Agent 是否相同** | 可以完全不同 | 默认相同 |

### 适用场景对比

| 场景 | 推荐模式 | 原因 |
|------|---------|------|
| 流程编排 (A→B→C) | Handoff | LLM 自主决定切换时机 |
| 并行任务分发 | Master-Worker | 多进程并行执行 |
| 串行能力委托 | Handoff | 轻量级，无通信开销 |
| 高并发请求 | Master-Worker | Worker 池分担负载 |
| 需要进程隔离 | Master-Worker | 独立进程更安全 |

### 决策机制对比

**Handoff 决策点：LLM 输出**

```python
# 检测 LLM 是否调用了 handoff 工具
for block in tool_use_blocks:
    if block.name in handoff_tool_names:  # ← 决策点
        return {"type": "handoff", "target_agent": ...}
```

**Master-Worker 决策点：Master 调度算法**

```python
def _should_handle_locally(self, message):
    idle_worker = self.registry.find_idle_agent()

    if not idle_worker:                    # 决策点 1: 有空闲 Worker?
        if len(message) < 50:              # 决策点 2: 消息简单?
            return True                    # 本地处理
        return False                       # 等待 Worker

    if len(message) < 30:                  # 决策点 3: 消息很短?
        return True                        # 减少通信开销

    return False                           # 分发给 Worker
```

---

## 配置与使用

### 配置项

```python
# config.py
class Settings:
    # 多 Agent 协同配置
    orchestration_enabled: bool = Field(
        default=False,
        description="是否启用多 Agent 协同"
    )
    orchestration_mode: str = Field(
        default="single",
        description="编排模式: single | handoff | master-worker"
    )
    orchestration_bus_address: str = Field(
        default="tcp://127.0.0.1:5555",
        description="ZMQ 总线地址"
    )
    orchestration_pub_address: str = Field(
        default="tcp://127.0.0.1:5556",
        description="ZMQ 广播地址"
    )
    orchestration_min_workers: int = Field(
        default=1,
        description="最小 Worker 数量"
    )
    orchestration_max_workers: int = Field(
        default=5,
        description="最大 Worker 数量"
    )
    orchestration_heartbeat_interval: int = Field(
        default=5,
        description="Worker 心跳间隔（秒）"
    )
    orchestration_health_check_interval: int = Field(
        default=10,
        description="健康检查间隔（秒）"
    )
```

### 环境变量

```bash
# 启用多 Agent 协同
ORCHESTRATION_ENABLED=true

# 选择模式
ORCHESTRATION_MODE=master-worker  # 或 handoff

# Worker 数量
ORCHESTRATION_MIN_WORKERS=2
ORCHESTRATION_MAX_WORKERS=10
```

### 启动方式

```python
# main.py 中的判断逻辑
if is_orchestration_enabled():
    # 多 Agent 模式
    master = get_master_agent()
    await master.start()

    async def agent_handler(session, message):
        return await master.handle_request(
            session_id=session.id,
            message=message,
            ...
        )
else:
    # 单 Agent 模式
    agent = get_agent()
    await agent.initialize()

    async def agent_handler(session, message):
        return await agent.chat_with_session(
            message=message,
            session_id=session.id,
            ...
        )
```

---

## 核心组件参考

### 文件结构

```
src/openakita/orchestration/
├── __init__.py          # 模块导出
├── handoff.py           # Handoff 模式实现
│   ├── HandoffAgent     # Agent 角色定义
│   ├── HandoffTarget    # Handoff 目标定义
│   └── HandoffOrchestrator  # 编排器
├── master.py            # Master-Agent 实现
│   ├── MasterAgent      # 主协调器
│   └── _worker_process_entry()  # Worker 进程入口
├── worker.py            # Worker-Agent 实现
│   └── WorkerAgent      # 工作进程
├── bus.py               # ZMQ 通信总线
│   ├── AgentBus         # 通信总线
│   └── WorkerBus        # Worker 端便捷类
├── messages.py          # 消息协议
│   ├── AgentMessage     # 消息格式
│   ├── AgentInfo        # Agent 信息
│   ├── TaskPayload      # 任务负载
│   ├── TaskResult       # 任务结果
│   └── CommandType/EventType  # 枚举
├── registry.py          # Agent 注册中心
│   └── AgentRegistry    # 注册管理
└── monitor.py           # Agent 监控
    └── AgentMonitor     # 监控器
```

### 类图

```
┌─────────────────┐     ┌─────────────────┐
│  HandoffAgent   │     │   MasterAgent   │
│  (dataclass)    │     │                 │
├─────────────────┤     ├─────────────────┤
│ name            │     │ registry        │
│ description     │     │ bus             │
│ system_prompt   │     │ _local_agent    │
│ tools           │     │ _worker_processes│
│ handoffs        │     └────────┬────────┘
└────────┬────────┘              │
         │                       │ creates
         │                       ▼
         │              ┌─────────────────┐
         │              │   WorkerAgent   │
         │              │   (进程)        │
         │              ├─────────────────┤
         │              │ bus             │
         │              │ _agent          │
         │              └─────────────────┘
         │
         ▼
┌─────────────────┐
│HandoffOrchestrator│
├─────────────────┤
│ _agents         │
│ _entry_agent    │
│ _brain          │
│ _handoff_history│
└─────────────────┘
```

---

## 总结

OpenAkita 的多 Agent 架构提供了两种互补的协同模式：

1. **Handoff 模式**：通过 LLM 工具调用实现语义驱动的 Agent 切换，适合流程编排和串行协作。

2. **Master-Worker 模式**：通过 ZMQ 消息队列实现分布式任务调度，适合并行执行和高并发场景。

选择建议：
- 需要不同专业能力的 Agent 协作 → Handoff
- 需要并行处理多个请求 → Master-Worker
- 简单场景 → 单 Agent 模式（默认）