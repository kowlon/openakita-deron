"""
多 Agent 协同工作框架

本模块提供两种 Agent 协同模式:

1. Master-Worker (ZMQ 重量级): 基于 ZeroMQ 的跨进程/跨机器协同
   - AgentRegistry: Agent 注册中心，管理所有活跃 Agent
   - AgentBus: ZMQ 通信总线，处理进程间通信
   - MasterAgent: 主协调器，任务分发和监督
   - WorkerAgent: 工作进程，执行具体任务

2. Handoff (轻量级): 进程内 Agent 切换，参考 OpenAI Agents SDK 设计
   - HandoffAgent: 具有特定能力的 Agent 角色
   - HandoffTarget: 描述何时以及如何委托给其他 Agent
   - HandoffOrchestrator: 管理 Agent 间的切换和消息路由

架构:
    ┌─────────────────────────────────────────┐
    │              主进程                       │
    │  ┌─────────┐  ┌─────────┐  ┌─────────┐  │
    │  │   CLI   │  │ Gateway │  │Scheduler│  │
    │  └────┬────┘  └────┬────┘  └────┬────┘  │
    │       │            │            │        │
    │       └────────────┼────────────┘        │
    │                    ▼                     │
    │            ┌──────────────┐              │
    │            │ MasterAgent  │              │
    │            │  (协调器)    │              │
    │            └──────┬───────┘              │
    │                   │                      │
    │            ┌──────┴───────┐              │
    │            │  AgentBus    │              │
    │            │   (ZMQ)      │              │
    │            └──────┬───────┘              │
    │                   │                      │
    │            ┌──────┴───────┐              │
    │            │AgentRegistry │              │
    │            └──────────────┘              │
    └─────────────────────────────────────────┘
                        │
           ┌────────────┼────────────┐
           ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ Worker 1 │ │ Worker 2 │ │ Worker N │
    │  (进程)  │ │  (进程)  │ │  (进程)  │
    └──────────┘ └──────────┘ └──────────┘
"""

from .best_practice_manager import (
    BestPracticeManager,
    BestPracticeManagerError,
)
from .bus import AgentBus, BusConfig
from .handoff import HandoffAgent, HandoffOrchestrator, HandoffTarget
from .master import MasterAgent
from .messages import (
    AgentInfo,
    AgentMessage,
    AgentStatus,
    CommandType,
    MessageType,
)
from .models import (
    BestPracticeConfig,
    OrchestrationTask,
    SessionTasks,
    StepStatus,
    StepTemplate,
    SubAgentConfig,
    TaskStatus,
    TaskStep,
    TriggerType,
)
from .monitor import AgentMonitor
from .registry import AgentRegistry
from .payload import (
    PayloadAssembler,
    PayloadAssemblerConfig,
    assemble_payload,
)
from .session_tasks import RouteResult, SessionTasks as SessionTasksManager
from .storage import TaskStorage, get_task_storage, close_task_storage
from .subagent_worker import (
    ArtifactReference,
    StepResult,
    SubAgentPayload,
    SubAgentWorker,
    WorkerPool,
)
from .task_orchestrator import (
    RouteDecision,
    RouteOutput,
    TaskOrchestrator,
    TaskExecutionError,
    TaskNotFoundError,
    TemplateNotFoundError,
)
from .transport import (
    AgentTransport,
    Command,
    CommandType as TransportCommandType,
    Event,
    EventType,
    MemoryTransport,
    Response,
    TransportError,
    TransportTimeoutError,
)
from .worker import WorkerAgent

__all__ = [
    # 消息协议
    "AgentMessage",
    "MessageType",
    "CommandType",
    "AgentStatus",
    "AgentInfo",
    # 核心组件
    "AgentRegistry",
    "AgentBus",
    "BusConfig",
    "MasterAgent",
    "WorkerAgent",
    "AgentMonitor",
    # Handoff 模式
    "HandoffAgent",
    "HandoffTarget",
    "HandoffOrchestrator",
    # 最佳实践模板
    "BestPracticeManager",
    "BestPracticeManagerError",
    # 任务编排模型
    "TaskStatus",
    "StepStatus",
    "TriggerType",
    "SubAgentConfig",
    "StepTemplate",
    "BestPracticeConfig",
    "TaskStep",
    "OrchestrationTask",
    "SessionTasks",
    "SessionTasksManager",
    "RouteResult",
    # 任务编排存储
    "TaskStorage",
    "get_task_storage",
    "close_task_storage",
    # 任务编排核心
    "TaskOrchestrator",
    "RouteDecision",
    "RouteOutput",
    "TaskNotFoundError",
    "TaskExecutionError",
    "TemplateNotFoundError",
    # Transport
    "AgentTransport",
    "MemoryTransport",
    "Command",
    "TransportCommandType",
    "Response",
    "Event",
    "EventType",
    "TransportError",
    "TransportTimeoutError",
    # SubAgent Worker
    "SubAgentWorker",
    "SubAgentPayload",
    "StepResult",
    "ArtifactReference",
    "WorkerPool",
    # Payload Assembler
    "PayloadAssembler",
    "PayloadAssemblerConfig",
    "assemble_payload",
]
