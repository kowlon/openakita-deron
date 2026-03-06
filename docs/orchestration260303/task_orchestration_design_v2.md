# 任务编排技术设计文档

## 1. 设计原则与技术规范

### 1.1 架构原则

| 原则 | 应用 |
|------|------|
| **高内聚** | 每个 SubAgent 专注单一职责，配置、执行、状态管理分离 |
| **低耦合** | 通过 Transport 抽象解耦通信；Worker 无状态设计 |
| **单一职责** | MainAgent 负责编排，SubAgent 负责执行，Storage 负责持久化 |
| **开闭原则** | 新增最佳实践无需修改核心代码；Transport 可扩展 |

### 1.2 设计模式

| 模式 | 应用场景 |
|------|----------|
| **策略模式** | Transport 抽象（MemoryTransport / ZMQTransport） |
| **模板方法** | BestPracticeConfig 定义任务模板 |
| **状态模式** | Task/Step 状态机管理 |
| **依赖注入** | SubAgentConfig 运行时注入 Worker |

### 1.3 技术约束

- **单机部署**：所有组件运行在同一机器
- **进程内通信优先**：默认使用 MemoryTransport
- **无状态 Worker**：Worker 不持有任务状态，由 MainAgent 统一管理

---

## 2. 核心数据模型

### 2.1 模型关系图

```
BestPracticeConfig (模板)
        │
        │ 实例化
        ▼
OrchestrationTask (任务)
        │
        │ 包含
        ▼
    TaskStep[] (步骤)
        │
        │ 关联
        ▼
  SubAgentConfig (配置)
```

### 2.2 最佳实践配置

```python
@dataclass
class BestPracticeConfig:
    """可复用的任务模板配置"""
    id: str                          # 唯一标识 (e.g., "code-review-v1")
    name: str                        # 显示名称
    description: str                 # 任务描述（含适用场景，供 LLM 判定）
    steps: list[StepTemplate]        # 步骤模板列表

@dataclass
class StepTemplate:
    """步骤模板定义"""
    name: str                        # 步骤名称
    description: str                 # 步骤描述
    sub_agent_config: SubAgentConfig # SubAgent 配置
```

### 2.3 任务模型

```python
@dataclass
class OrchestrationTask:
    """运行时任务对象"""
    # 标识
    id: str                          # UUID
    session_id: str                  # 所属会话
    template_id: str | None          # 关联的最佳实践 ID

    # 触发信息
    trigger_type: str                # "best_practice" | "context" | "plan"
    trigger_message_id: str          # 触发消息 ID

    # 状态
    status: TaskStatus               # 任务状态
    suspend_reason: str | None       # 暂停原因
    current_step_index: int          # 当前步骤索引
    irrelevant_turn_count: int       # 连续无关对话计数

    # 数据
    name: str
    description: str
    input_payload: dict              # 初始输入
    result_payload: dict             # 最终结果
    context_variables: dict          # 跨步骤共享变量

    # 时间戳
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
```

### 2.4 步骤模型

```python
@dataclass
class TaskStep:
    """任务执行单元"""
    # 标识
    id: str                          # UUID
    task_id: str                     # 所属任务
    index: int                       # 执行顺序

    # 元数据
    name: str
    description: str

    # 配置
    sub_agent_config: SubAgentConfig # SubAgent 完整配置

    # 状态
    status: StepStatus
    retry_count: int

    # 输入输出
    input_args: dict
    output_result: dict
    artifacts: list[str]             # 制品 ID 列表

    # 用户交互
    user_feedback: str | None

    # 时间戳
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
```

### 2.5 SubAgent 配置

```python
@dataclass
class SubAgentConfig:
    """SubAgent 运行时配置"""
    # 身份
    name: str                        # Agent 名称
    role: str                        # 角色描述
    system_prompt: str               # 系统提示词

    # 能力
    skills: list[str]                # Skills 列表
    mcps: list[str]                  # MCP Server 列表
    tools: list[str]                 # 系统工具列表
```

### 2.6 会话任务管理器

```python
class SessionTasks:
    """会话级任务管理"""
    session_id: str
    active_task_id: str | None       # 当前活跃任务（仅一个）
    tasks: dict[str, OrchestrationTask]

    def get_active_task() -> OrchestrationTask | None
    def activate_task(task_id: str)
    def deactivate_task()
    def route_input(user_input: str) -> RouteResult
```

---

## 3. 存储层设计

### 3.1 设计原则

- **实时持久化**：状态变更立即落盘
- **原子操作**：Task 与 Step 状态一致性保证
- **快照恢复**：支持从任意状态点恢复

### 3.2 数据库 Schema

#### orchestration_tasks 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PK | UUID |
| session_id | TEXT | 关联会话 |
| template_id | TEXT | 模板 ID |
| status | TEXT | 任务状态 |
| name | TEXT | 任务名称 |
| context_json | TEXT | JSON: input, result, variables |
| meta_json | TEXT | JSON: trigger_info, description |
| created_at | TEXT | ISO8601 |
| updated_at | TEXT | ISO8601 |
| completed_at | TEXT | ISO8601 |

#### orchestration_steps 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PK | UUID |
| task_id | TEXT FK | 关联任务 |
| step_index | INTEGER | 步骤顺序 |
| name | TEXT | 步骤名称 |
| status | TEXT | 步骤状态 |
| io_json | TEXT | JSON: input_args, output_result |
| config_json | TEXT | JSON: SubAgentConfig |
| created_at | TEXT | ISO8601 |
| started_at | TEXT | ISO8601 |
| finished_at | TEXT | ISO8601 |

### 3.3 存储管理器

```python
class TaskStorage:
    """任务存储管理器"""

    async def save_task(self, task: OrchestrationTask) -> None:
        """保存任务（含步骤）"""

    async def load_task(self, task_id: str) -> OrchestrationTask | None:
        """加载单个任务"""

    async def load_session_tasks(self, session_id: str) -> SessionTasks:
        """加载会话所有任务"""

    async def update_step_status(
        self, step_id: str, status: StepStatus, result: dict | None = None
    ) -> None:
        """更新步骤状态"""
```

---

## 4. 通信层设计

### 4.1 设计原则

- **抽象解耦**：通过 Transport 接口隔离通信实现
- **默认高效**：单机场景使用进程内通信
- **可扩展**：支持未来分布式部署

### 4.2 Transport 接口

```python
class AgentTransport(ABC):
    """通信传输抽象"""

    @abstractmethod
    async def send_command(self, target: str, command: Command) -> Response:
        """发送命令"""

    @abstractmethod
    async def publish_event(self, event: Event) -> None:
        """发布事件"""

    @abstractmethod
    async def subscribe(self, topic: str, handler: Callable) -> None:
        """订阅主题"""
```

### 4.3 实现方案

| 实现 | 机制 | 适用场景 |
|------|------|----------|
| **MemoryTransport** | asyncio.Queue | 单机部署（默认） |
| **ZMQTransport** | ZeroMQ | 分布式部署（可选） |

### 4.4 MemoryTransport 特性

- **零拷贝**：Python 对象引用传递
- **无序列化**：避免 JSON/Pickle 开销
- **调试友好**：直接访问内存对象

---

## 5. 运行时逻辑

### 5.1 核心设计：结构与数据分离

| 阶段 | 输入 | 动作 | 输出 |
|------|------|------|------|
| **Create** | BestPracticeConfig | 实例化空任务结构 | PENDING 状态任务 |
| **Resume** | Task ID | 加载数据填充结构 | RUNNING 状态任务 |
| **Execute** | 活跃任务 | 按步骤执行 | 步骤结果 |

### 5.2 任务创建流程

```
BestPracticeConfig
       │
       ▼
┌─────────────────┐
│ 实例化 Task     │
│ 实例化 Steps    │
│ 加载 SubAgent   │
│ Configs         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 状态: PENDING   │
│ 持久化到 DB     │
└────────┬────────┘
         │
         ▼
    激活任务
```

### 5.3 任务恢复流程

```
Task ID
    │
    ▼
┌─────────────────┐
│ 从 DB 加载      │
│ Task + Steps    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 填充数据:       │
│ - 步骤输出      │
│ - 上下文变量    │
│ - 聊天历史      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 重置计数器      │
│ 状态: RUNNING   │
└─────────────────┘
```

### 5.4 执行循环

```python
async def execute_task(self, task: OrchestrationTask):
    """统一执行入口"""
    self.session_tasks.activate_task(task.id)

    while task.current_step_index < len(task.steps):
        step = task.steps[task.current_step_index]

        # 跳过已完成步骤
        if step.status == StepStatus.COMPLETED:
            task.current_step_index += 1
            continue

        # 执行当前步骤
        step.status = StepStatus.RUNNING
        self.storage.save_task(task)

        result = await self.run_step(step)

        if result.success:
            step.status = StepStatus.COMPLETED
            task.current_step_index += 1
        else:
            step.status = StepStatus.FAILED
            task.status = TaskStatus.PAUSED
            self.storage.save_task(task)
            break
```

### 5.5 路由逻辑

```
用户消息
    │
    ▼
┌─────────────────┐
│ 检查活跃任务    │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
 有活跃    无活跃
    │         │
    ▼         ▼
┌───────┐ ┌───────┐
│LLM判定│ │标准   │
│路由   │ │对话   │
└───┬───┘ └───────┘
    │
┌───┴───┐
│       │
▼       ▼
命中    未命中
│       │
▼       ▼
路由到  递增计数
SubAgent │
        ▼
    计数>=5?
        │
    ┌───┴───┐
    │       │
    ▼       ▼
   是      否
    │       │
    ▼       ▼
Auto-   普通对话
Suspend
```

### 5.6 自动暂停机制

```python
async def handle_irrelevant_input(self, task: OrchestrationTask):
    """处理无关输入"""
    task.irrelevant_turn_count += 1

    if task.irrelevant_turn_count >= 5:
        # 触发自动暂停
        task.status = TaskStatus.PAUSED
        task.suspend_reason = "auto_suspend"
        self.storage.save_task(task)

        # 销毁内存实例
        self.session_tasks.deactivate_task()

        # 通知用户
        await self.notify_user(f"任务 [{task.name}] 已自动暂停")
```

---

## 6. 无状态 Worker 设计

### 6.1 核心理念

**Orchestrator（大脑）** vs **Worker（手脚）**：

| 角色 | 职责 | 状态 |
|------|------|------|
| Orchestrator | 持有完整状态、调度决策 | 有状态 |
| Worker | 执行计算、返回结果 | 无状态 |

### 6.2 JIT 配置注入

```
Orchestrator                    Worker
    │                             │
    │  ASSIGN_TASK                │
    │  ┌─────────────────────┐    │
    │  │ SubAgentConfig      │    │
    │  │ TaskContext         │────┼──▶ 接收配置
    │  │ HistoryMessages     │    │     初始化 Agent
    │  │ ArtifactsRef        │    │     执行任务
    │  └─────────────────────┘    │
    │                             │
    │                   TASK_RESULT
    │◀────────────────────────────│
    │                             │
```

### 6.3 优势

- **资源效率**：Worker 池共享，无需预分配
- **动态调整**：运行时可修改后续步骤配置
- **容错能力**：Worker 故障可切换到其他 Worker

---

## 7. 数据传输优化

### 7.1 引用传递机制

```python
@dataclass
class ArtifactReference:
    """制品引用（非原始内容）"""
    id: str
    type: str          # "file" | "image" | "code"
    uri: str           # "file://..." 或 "db://..."
    summary: str       # 简短摘要
```

### 7.2 优化策略

| 策略 | 说明 |
|------|------|
| **引用传递** | 大数据仅传元数据，按需加载 |
| **延迟加载** | Worker 仅在需要时读取内容 |
| **上下文剪枝** | 根据窗口限制智能裁剪历史 |

### 7.3 Payload 结构

```python
@dataclass
class SubAgentPayload:
    """SubAgent 调用载荷"""
    # 标识
    task_id: str
    step_id: str
    step_index: int

    # 上下文
    previous_steps_summary: str    # 前序步骤摘要
    task_context: dict             # 任务级变量
    history_messages: list[dict]   # 聊天历史
    artifacts: list[ArtifactReference]  # 制品引用

    # 配置
    agent_config: SubAgentConfig   # 动态配置
```

---

## 8. 通信协议

### 8.1 步骤结果

```python
@dataclass
class StepResult:
    """步骤执行结果"""
    task_id: str
    step_id: str
    success: bool
    result: dict
    error: str | None
    artifacts: list[dict]          # 新产生的制品
    suggested_next_action: str     # 下一步建议
    display_view: dict             # 前端渲染数据
```

---

## 9. 实施路线

### Phase 1: 存储层与模型
- [ ] 定义数据类（OrchestrationTask, TaskStep, SubAgentConfig）
- [ ] 实现 SQLite Schema
- [ ] 实现 TaskStorage

### Phase 2: 通信层
- [ ] 定义 Transport 接口
- [ ] 实现 MemoryTransport
- [ ] 重构 AgentBus

### Phase 3: 编排逻辑
- [ ] 实现 SessionTasks 管理器
- [ ] 实现任务创建/恢复流程
- [ ] 实现路由逻辑
- [ ] 实现自动暂停机制

### Phase 4: Worker 集成
- [ ] 实现 JIT 配置注入
- [ ] 实现 Payload 组装
- [ ] 实现结果处理

### Phase 5: API 与前端
- [ ] 实现 `/api/tasks/{id}/resume`
- [ ] 实现任务看板组件
- [ ] 实现步骤输出编辑