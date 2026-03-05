"""
多任务编排核心数据结构

定义多任务编排系统所需的核心数据类型和数据结构。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ==================== 枚举类型 ====================


class TaskStatus(Enum):
    """任务状态"""

    PENDING = "pending"  # 等待开始
    RUNNING = "running"  # 执行中
    WAITING_USER = "waiting_user"  # 等待用户确认
    COMPLETED = "completed"  # 已完成
    CANCELLED = "cancelled"  # 已取消
    FAILED = "failed"  # 失败


class StepStatus(Enum):
    """步骤状态"""

    PENDING = "pending"  # 等待开始
    RUNNING = "running"  # 执行中
    WAITING_USER = "waiting_user"  # 等待用户确认
    COMPLETED = "completed"  # 已完成
    SKIPPED = "skipped"  # 已跳过
    FAILED = "failed"  # 失败


class ProcessMode(Enum):
    """进程模式"""

    WORKER = "worker"  # 独立进程 Worker 模式
    INLINE = "inline"  # 内联模式（同进程）


class BrainMode(Enum):
    """Brain 模式"""

    SHARED_PROXY = "shared_proxy"  # 共享模型配置/代理
    INDEPENDENT = "independent"  # 独立 Brain


class TriggerType(Enum):
    """触发类型"""

    REGEX = "regex"  # 正则匹配
    KEYWORD = "keyword"  # 关键词匹配
    MANUAL = "manual"  # 手动触发


# ==================== 配置结构 ====================


@dataclass
class CapabilitiesConfig:
    """能力限制配置"""

    allow_shell: bool = False  # 是否允许 shell 命令
    allow_write: bool = False  # 是否允许写入文件
    allow_network: bool = True  # 是否允许网络访问

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "allow_shell": self.allow_shell,
            "allow_write": self.allow_write,
            "allow_network": self.allow_network,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CapabilitiesConfig":
        """从字典反序列化"""
        return cls(
            allow_shell=data.get("allow_shell", False),
            allow_write=data.get("allow_write", False),
            allow_network=data.get("allow_network", True),
        )


@dataclass
class RuntimeConfig:
    """运行时配置"""

    max_iterations: int = 20  # 最大迭代次数
    session_type: str = "cli"  # 会话类型 (cli/im/web)
    memory_policy: str = "task_scoped"  # 记忆策略 (task_scoped/persistent)
    prompt_budget: str = "standard"  # 提示词预算 (minimal/standard/extended)
    timeout_seconds: int = 300  # 超时时间（秒）

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "max_iterations": self.max_iterations,
            "session_type": self.session_type,
            "memory_policy": self.memory_policy,
            "prompt_budget": self.prompt_budget,
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RuntimeConfig":
        """从字典反序列化"""
        return cls(
            max_iterations=data.get("max_iterations", 20),
            session_type=data.get("session_type", "cli"),
            memory_policy=data.get("memory_policy", "task_scoped"),
            prompt_budget=data.get("prompt_budget", "standard"),
            timeout_seconds=data.get("timeout_seconds", 300),
        )


@dataclass
class TriggerPattern:
    """触发模式"""

    type: TriggerType  # 触发类型
    pattern: str | None = None  # 正则模式
    keywords: list[str] = field(default_factory=list)  # 关键词列表
    priority: int = 0  # 优先级（数字越小越高）

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "type": self.type.value,
            "pattern": self.pattern,
            "keywords": self.keywords,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TriggerPattern":
        """从字典反序列化"""
        return cls(
            type=TriggerType(data["type"]),
            pattern=data.get("pattern"),
            keywords=data.get("keywords", []),
            priority=data.get("priority", 0),
        )


@dataclass
class ToolsConfig:
    """工具配置"""

    system_tools: list[str] = field(default_factory=list)  # 系统工具
    mcp_tools: list[str] = field(default_factory=list)  # MCP 工具

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "system_tools": self.system_tools,
            "mcp_tools": self.mcp_tools,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ToolsConfig":
        """从字典反序列化"""
        return cls(
            system_tools=data.get("system_tools", []),
            mcp_tools=data.get("mcp_tools", []),
        )


# ==================== SubAgent 配置 ====================


@dataclass
class SubAgentConfig:
    """SubAgent 运行时配置"""

    subagent_id: str  # SubAgent 唯一标识
    name: str  # SubAgent 名称
    description: str = ""  # 描述
    system_prompt: str = ""  # 系统提示词
    allowed_tools: list[str] = field(default_factory=list)  # 合并后的可执行工具列表
    skills: list[str] = field(default_factory=list)  # 提示词侧能力约束
    capabilities: CapabilitiesConfig = field(default_factory=CapabilitiesConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    process_mode: ProcessMode = ProcessMode.WORKER
    brain_mode: BrainMode = BrainMode.SHARED_PROXY
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "subagent_id": self.subagent_id,
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "allowed_tools": self.allowed_tools,
            "skills": self.skills,
            "capabilities": self.capabilities.to_dict(),
            "runtime": self.runtime.to_dict(),
            "process_mode": self.process_mode.value,
            "brain_mode": self.brain_mode.value,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SubAgentConfig":
        """从字典反序列化"""
        return cls(
            subagent_id=data["subagent_id"],
            name=data["name"],
            description=data.get("description", ""),
            system_prompt=data.get("system_prompt", ""),
            allowed_tools=data.get("allowed_tools", []),
            skills=data.get("skills", []),
            capabilities=CapabilitiesConfig.from_dict(data.get("capabilities", {})),
            runtime=RuntimeConfig.from_dict(data.get("runtime", {})),
            process_mode=ProcessMode(data.get("process_mode", "worker")),
            brain_mode=BrainMode(data.get("brain_mode", "shared_proxy")),
            metadata=data.get("metadata", {}),
        )


# ==================== 场景定义 ====================


@dataclass
class StepDefinition:
    """步骤定义"""

    step_id: str  # 步骤标识
    name: str  # 步骤名称
    description: str = ""  # 描述
    output_key: str = ""  # 输出键名（用于上下文传递）
    tools: ToolsConfig = field(default_factory=ToolsConfig)  # 工具配置
    skills: list[str] = field(default_factory=list)  # 技能列表
    system_prompt: str = ""  # 系统提示词
    requires_confirmation: bool = True  # 是否需要用户确认
    dependencies: list[str] = field(default_factory=list)  # 依赖的步骤 ID
    timeout_seconds: int = 300  # 超时时间

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "step_id": self.step_id,
            "name": self.name,
            "description": self.description,
            "output_key": self.output_key,
            "tools": self.tools.to_dict(),
            "skills": self.skills,
            "system_prompt": self.system_prompt,
            "requires_confirmation": self.requires_confirmation,
            "dependencies": self.dependencies,
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StepDefinition":
        """从字典反序列化"""
        tools_data = data.get("tools", {})
        if isinstance(tools_data, dict):
            tools = ToolsConfig.from_dict(tools_data)
        else:
            tools = ToolsConfig()

        return cls(
            step_id=data["step_id"],
            name=data["name"],
            description=data.get("description", ""),
            output_key=data.get("output_key", ""),
            tools=tools,
            skills=data.get("skills", []),
            system_prompt=data.get("system_prompt", ""),
            requires_confirmation=data.get("requires_confirmation", True),
            dependencies=data.get("dependencies", []),
            timeout_seconds=data.get("timeout_seconds", 300),
        )


@dataclass
class ScenarioDefinition:
    """场景定义（最佳实践）"""

    scenario_id: str  # 场景唯一标识
    name: str  # 场景名称
    description: str = ""  # 描述
    category: str = "general"  # 分类
    version: str = "1.0"  # 版本
    trigger_patterns: list[TriggerPattern] = field(default_factory=list)  # 触发模式
    steps: list[StepDefinition] = field(default_factory=list)  # 步骤定义列表
    metadata: dict[str, Any] = field(default_factory=dict)  # 元数据

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "trigger_patterns": [p.to_dict() for p in self.trigger_patterns],
            "steps": [s.to_dict() for s in self.steps],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScenarioDefinition":
        """从字典反序列化"""
        trigger_patterns = []
        for p in data.get("trigger_patterns", []):
            if isinstance(p, dict):
                trigger_patterns.append(TriggerPattern.from_dict(p))

        steps = []
        for s in data.get("steps", []):
            if isinstance(s, dict):
                steps.append(StepDefinition.from_dict(s))

        return cls(
            scenario_id=data["scenario_id"],
            name=data["name"],
            description=data.get("description", ""),
            category=data.get("category", "general"),
            version=data.get("version", "1.0"),
            trigger_patterns=trigger_patterns,
            steps=steps,
            metadata=data.get("metadata", {}),
        )

    def get_step(self, step_id: str) -> StepDefinition | None:
        """获取步骤定义"""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def get_step_index(self, step_id: str) -> int:
        """获取步骤索引"""
        for i, step in enumerate(self.steps):
            if step.step_id == step_id:
                return i
        return -1


# ==================== 任务状态 ====================


@dataclass
class StepSession:
    """
    步骤会话

    管理单个步骤的执行状态和对话历史
    """

    step_id: str  # 步骤标识
    status: StepStatus = StepStatus.PENDING  # 步骤状态
    sub_agent_id: str | None = None  # SubAgent 进程标识
    messages: list[dict[str, Any]] = field(default_factory=list)  # 对话历史快照
    output: dict[str, Any] = field(default_factory=dict)  # 步骤输出
    started_at: str | None = None  # 开始时间
    completed_at: str | None = None  # 完成时间
    error_message: str | None = None  # 错误信息

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "step_id": self.step_id,
            "status": self.status.value,
            "sub_agent_id": self.sub_agent_id,
            "messages": self.messages,
            "output": self.output,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StepSession":
        """从字典反序列化"""
        return cls(
            step_id=data["step_id"],
            status=StepStatus(data.get("status", "pending")),
            sub_agent_id=data.get("sub_agent_id"),
            messages=data.get("messages", []),
            output=data.get("output", {}),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            error_message=data.get("error_message"),
        )

    def start(self) -> None:
        """标记步骤开始"""
        self.status = StepStatus.RUNNING
        self.started_at = datetime.now().isoformat()

    def complete(self, output: dict[str, Any] | None = None) -> None:
        """标记步骤完成"""
        self.status = StepStatus.COMPLETED
        self.completed_at = datetime.now().isoformat()
        if output:
            self.output = output

    def wait_for_user(self) -> None:
        """标记等待用户确认"""
        self.status = StepStatus.WAITING_USER

    def fail(self, error: str) -> None:
        """标记步骤失败"""
        self.status = StepStatus.FAILED
        self.completed_at = datetime.now().isoformat()
        self.error_message = error

    def add_message(self, role: str, content: str) -> None:
        """添加消息到历史"""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })


@dataclass
class TaskState:
    """
    任务状态

    管理任务的完整状态信息
    """

    task_id: str  # 任务唯一标识
    scenario_id: str  # 场景标识
    session_id: str | None = None  # 关联的会话 ID
    status: TaskStatus = TaskStatus.PENDING  # 任务状态
    current_step_id: str | None = None  # 当前步骤 ID
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: str | None = None
    completed_at: str | None = None
    error_message: str | None = None

    # 输入输出
    initial_message: str = ""  # 初始用户消息
    context: dict[str, Any] = field(default_factory=dict)  # 步骤间上下文
    final_output: dict[str, Any] = field(default_factory=dict)  # 最终输出

    # 统计
    total_steps: int = 0  # 总步骤数
    completed_steps: int = 0  # 已完成步骤数

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "task_id": self.task_id,
            "scenario_id": self.scenario_id,
            "session_id": self.session_id,
            "status": self.status.value,
            "current_step_id": self.current_step_id,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
            "initial_message": self.initial_message,
            "context": self.context,
            "final_output": self.final_output,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskState":
        """从字典反序列化"""
        return cls(
            task_id=data["task_id"],
            scenario_id=data["scenario_id"],
            session_id=data.get("session_id"),
            status=TaskStatus(data.get("status", "pending")),
            current_step_id=data.get("current_step_id"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            error_message=data.get("error_message"),
            initial_message=data.get("initial_message", ""),
            context=data.get("context", {}),
            final_output=data.get("final_output", {}),
            total_steps=data.get("total_steps", 0),
            completed_steps=data.get("completed_steps", 0),
        )

    def start(self) -> None:
        """标记任务开始"""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now().isoformat()

    def complete(self, output: dict[str, Any] | None = None) -> None:
        """标记任务完成"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now().isoformat()
        if output:
            self.final_output = output

    def cancel(self) -> None:
        """标记任务取消"""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.now().isoformat()

    def fail(self, error: str) -> None:
        """标记任务失败"""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now().isoformat()
        self.error_message = error

    def wait_for_user(self) -> None:
        """标记等待用户"""
        self.status = TaskStatus.WAITING_USER

    def get_progress(self) -> tuple[int, int]:
        """获取进度 (已完成, 总数)"""
        return (self.completed_steps, self.total_steps)

    def get_progress_percent(self) -> float:
        """获取进度百分比"""
        if self.total_steps == 0:
            return 0.0
        return (self.completed_steps / self.total_steps) * 100