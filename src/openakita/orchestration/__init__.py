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

3. 多任务编排 (Multi-Task Orchestration): 最佳实践场景的步骤编排
   - TaskOrchestrator: 任务编排器，管理任务创建和协调
   - TaskSession: 任务会话，管理任务生命周期
   - SubAgentManager: SubAgent 管理器，管理步骤执行进程
   - ScenarioRegistry: 场景注册表，管理最佳实践场景
   - ContextManager: 上下文管理器，管理步骤间上下文传递

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

from .bus import AgentBus, BusConfig
from .config_loader import SubAgentConfigLoader
from .context_manager import ContextManager, ContextInjector, OutputExtractor
from .handoff import HandoffAgent, HandoffOrchestrator, HandoffTarget
from .master import MasterAgent
from .messages import (
    AgentInfo,
    AgentMessage,
    AgentStatus,
    CommandType,
    MessageType,
    StepRequest,
    StepResponse,
)
from .models import (
    BrainMode,
    CapabilitiesConfig,
    ProcessMode,
    RuntimeConfig,
    ScenarioDefinition,
    StepDefinition,
    StepSession,
    StepStatus,
    SubAgentConfig,
    TaskState,
    TaskStatus,
    ToolsConfig,
    TriggerPattern,
    TriggerType,
)
from .monitor import AgentMonitor
from .registry import AgentRegistry
from .scenario_registry import ScenarioRegistry, ScenarioMatchResult
from .subagent_manager import SubAgentManager
from .task_orchestrator import OrchestratorConfig, TaskOrchestrator
from .task_session import TaskSession, TaskSessionConfig
from .worker import WorkerAgent

__all__ = [
    # 消息协议
    "AgentMessage",
    "MessageType",
    "CommandType",
    "AgentStatus",
    "AgentInfo",
    "StepRequest",
    "StepResponse",
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
    # 多任务编排
    "TaskOrchestrator",
    "OrchestratorConfig",
    "TaskSession",
    "TaskSessionConfig",
    "SubAgentManager",
    "ScenarioRegistry",
    "ScenarioMatchResult",
    "ContextManager",
    "ContextInjector",
    "OutputExtractor",
    "SubAgentConfigLoader",
    # 数据模型
    "TaskState",
    "TaskStatus",
    "StepSession",
    "StepStatus",
    "ScenarioDefinition",
    "StepDefinition",
    "SubAgentConfig",
    "CapabilitiesConfig",
    "RuntimeConfig",
    "ToolsConfig",
    "TriggerPattern",
    "TriggerType",
    "ProcessMode",
    "BrainMode",
]
