"""
任务编排核心数据模型

定义任务编排系统的核心数据结构：
- TaskStatus / StepStatus: 状态枚举
- TriggerType: 触发类型枚举
- RouterPromptConfig: 路由器 Prompt 配置
- SubAgentConfig: SubAgent 配置
- StepTemplate / BestPracticeConfig: 任务模板
- BestPracticeTriggerConfig: 最佳实践触发器配置
- TaskStep / OrchestrationTask: 运行时任务和步骤
- SessionTasks: 会话任务管理
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ==================== 枚举类型 ====================


class TaskStatus(Enum):
    """任务状态"""

    PENDING = "pending"  # 已创建，等待执行
    RUNNING = "running"  # 正在执行中
    PAUSED = "paused"  # 已暂停（自动或手动）
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 执行失败
    CANCELLED = "cancelled"  # 已取消


class StepStatus(Enum):
    """步骤状态"""

    PENDING = "pending"  # 等待执行
    RUNNING = "running"  # 正在执行
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 执行失败
    SKIPPED = "skipped"  # 已跳过


class TriggerType(Enum):
    """任务触发类型"""

    BEST_PRACTICE = "best_practice"  # 从最佳实践入口触发
    CONTEXT = "context"  # 从对话上下文触发（LLM 判定）
    PLAN = "plan"  # 从 Plan 转任务


# ==================== 路由 Prompt 配置 ====================


@dataclass
class RouterPromptConfig:
    """
    路由器 Prompt 配置

    用于 LLM 智能路由判断的配置，包含系统提示词、判断示例和置信度阈值。
    支持 YAML 文件加载和序列化/反序列化。
    """

    # 路由器标识
    router_name: str = ""  # 路由器名称 (e.g., "task_router", "agent_router")
    description: str = ""  # 路由器用途描述

    # LLM 判断配置
    system_prompt: str = ""  # LLM 判断用的系统提示词
    user_prompt_template: str = ""  # 用户提示词模板（支持变量占位符）
    output_format: str = ""  # 输出格式说明

    # 示例
    examples: list[dict[str, str]] = field(default_factory=list)  # 判断示例 (input -> output)

    # 配置
    threshold: float = 0.7  # 置信度阈值 (0.0 - 1.0)
    enabled: bool = True  # 是否启用 LLM 路由

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "router_name": self.router_name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "user_prompt_template": self.user_prompt_template,
            "output_format": self.output_format,
            "examples": self.examples,
            "threshold": self.threshold,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RouterPromptConfig":
        """从字典反序列化"""
        return cls(
            router_name=data.get("router_name", ""),
            description=data.get("description", ""),
            system_prompt=data.get("system_prompt", ""),
            user_prompt_template=data.get("user_prompt_template", ""),
            output_format=data.get("output_format", ""),
            examples=data.get("examples", []),
            threshold=data.get("threshold", 0.7),
            enabled=data.get("enabled", True),
        )

    def format_user_prompt(
        self,
        user_input: str,
        task_name: str = "",
        task_description: str = "",
        step_name: str = "",
        step_description: str = "",
    ) -> str:
        """
        格式化用户提示词

        Args:
            user_input: 用户输入
            task_name: 任务名称
            task_description: 任务描述
            step_name: 当前步骤名称
            step_description: 当前步骤描述

        Returns:
            格式化后的提示词
        """
        return self.user_prompt_template.format(
            user_input=user_input,
            task_name=task_name,
            task_description=task_description,
            step_name=step_name,
            step_description=step_description,
        )


# ==================== SubAgent 配置 ====================


@dataclass
class SubAgentConfig:
    """
    SubAgent 运行时配置

    定义 SubAgent 的身份、能力和运行参数。
    通过 JIT 配置注入给 Worker 使用。
    """

    # 身份
    name: str  # Agent 名称
    role: str  # 角色描述
    system_prompt: str  # 系统提示词

    # 能力
    skills: list[str] = field(default_factory=list)  # Skills 列表
    mcps: list[str] = field(default_factory=list)  # MCP Server 列表
    tools: list[str] = field(default_factory=list)  # 系统工具列表

    def to_dict(self) -> dict:
        """序列化为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SubAgentConfig":
        """从字典反序列化"""
        return cls(**data)


# ==================== 任务模板 ====================


@dataclass
class StepTemplate:
    """
    步骤模板定义

    定义任务中单个步骤的配置，用于 BestPracticeConfig。
    """

    name: str  # 步骤名称
    description: str  # 步骤描述
    sub_agent_config: SubAgentConfig  # SubAgent 配置

    def to_dict(self) -> dict:
        """序列化为字典"""
        result = {
            "name": self.name,
            "description": self.description,
            "sub_agent_config": self.sub_agent_config.to_dict(),
        }
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "StepTemplate":
        """从字典反序列化"""
        sub_agent_config = SubAgentConfig.from_dict(data["sub_agent_config"])
        return cls(
            name=data["name"],
            description=data["description"],
            sub_agent_config=sub_agent_config,
        )


@dataclass
class BestPracticeTriggerConfig:
    """
    最佳实践触发器配置

    定义 LLM 判断是否应该触发最佳实践的配置。
    独立于 BestPracticeConfig，专注于触发判断逻辑。

    Attributes:
        trigger_name: 触发器名称（用于标识和日志）
        description: 触发器用途描述
        system_prompt: LLM 判断用的系统提示词，包含判断逻辑和输出格式要求
        best_practice_descriptions: 各最佳实践的描述字典 {bp_id: description}，供 LLM 匹配
        confidence_threshold: 触发置信度阈值，范围 [0.0, 1.0]，默认 0.7
    """

    trigger_name: str  # 触发器名称
    description: str  # 触发器用途描述
    system_prompt: str  # LLM 判断用的系统提示词
    best_practice_descriptions: dict[str, str] = field(
        default_factory=dict
    )  # {bp_id: description}
    confidence_threshold: float = 0.7  # 触发置信度阈值

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "trigger_name": self.trigger_name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "best_practice_descriptions": self.best_practice_descriptions,
            "confidence_threshold": self.confidence_threshold,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BestPracticeTriggerConfig":
        """从字典反序列化"""
        return cls(
            trigger_name=data["trigger_name"],
            description=data["description"],
            system_prompt=data["system_prompt"],
            best_practice_descriptions=data.get("best_practice_descriptions", {}),
            confidence_threshold=data.get("confidence_threshold", 0.7),
        )

    def update_best_practice_descriptions(
        self, descriptions: dict[str, str]
    ) -> None:
        """
        动态更新最佳实践描述列表

        Args:
            descriptions: 新的最佳实践描述字典 {bp_id: description}
        """
        self.best_practice_descriptions.update(descriptions)

    def remove_best_practice(self, bp_id: str) -> bool:
        """
        移除指定最佳实践描述

        Args:
            bp_id: 最佳实践 ID

        Returns:
            是否成功移除
        """
        if bp_id in self.best_practice_descriptions:
            del self.best_practice_descriptions[bp_id]
            return True
        return False

    def get_formatted_descriptions(self) -> str:
        """
        获取格式化的最佳实践描述列表，用于 LLM prompt

        Returns:
            格式化的描述文本
        """
        if not self.best_practice_descriptions:
            return "当前没有可用的最佳实践。"

        lines = ["可用的最佳实践列表："]
        for bp_id, desc in self.best_practice_descriptions.items():
            lines.append(f"- {bp_id}: {desc}")
        return "\n".join(lines)


@dataclass
class BestPracticeConfig:
    """
    可复用的任务模板配置

    定义了任务的元数据（名称、描述、适用场景）、触发条件描述和步骤序列。
    用户触发最佳实践时，系统加载配置并实例化为运行时任务。
    """

    id: str  # 唯一标识 (e.g., "code-review-v1")
    name: str  # 显示名称
    description: str  # 任务描述（含适用场景，供 LLM 判定）
    steps: list[StepTemplate] = field(default_factory=list)  # 步骤模板列表
    trigger_config: BestPracticeTriggerConfig | None = None  # 触发配置

    def to_dict(self) -> dict:
        """序列化为字典"""
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
        }
        if self.trigger_config:
            result["trigger_config"] = self.trigger_config.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "BestPracticeConfig":
        """从字典反序列化"""
        steps = [StepTemplate.from_dict(s) for s in data.get("steps", [])]
        trigger_config = None
        if "trigger_config" in data:
            trigger_config = BestPracticeTriggerConfig.from_dict(data["trigger_config"])
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            steps=steps,
            trigger_config=trigger_config,
        )


# ==================== 运行时任务模型 ====================


@dataclass
class TaskStep:
    """
    任务执行单元

    步骤是任务的执行单元，对应一次 SubAgent 调用。
    拥有独立的输入/输出，支持状态追踪，可产生制品。
    """

    # 标识
    id: str  # UUID
    task_id: str  # 所属任务
    index: int  # 执行顺序

    # 元数据
    name: str
    description: str

    # 配置
    sub_agent_config: SubAgentConfig  # SubAgent 完整配置

    # 状态
    status: str = StepStatus.PENDING.value  # StepStatus 值
    retry_count: int = 0

    # 输入输出
    input_args: dict[str, Any] = field(default_factory=dict)
    output_result: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)  # 制品 ID 列表

    # 用户交互
    user_feedback: str | None = None

    # 时间戳
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: str | None = None
    finished_at: str | None = None

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "index": self.index,
            "name": self.name,
            "description": self.description,
            "sub_agent_config": self.sub_agent_config.to_dict(),
            "status": self.status,
            "retry_count": self.retry_count,
            "input_args": self.input_args,
            "output_result": self.output_result,
            "artifacts": self.artifacts,
            "user_feedback": self.user_feedback,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskStep":
        """从字典反序列化"""
        sub_agent_config = SubAgentConfig.from_dict(data["sub_agent_config"])
        return cls(
            id=data["id"],
            task_id=data["task_id"],
            index=data["index"],
            name=data["name"],
            description=data["description"],
            sub_agent_config=sub_agent_config,
            status=data.get("status", StepStatus.PENDING.value),
            retry_count=data.get("retry_count", 0),
            input_args=data.get("input_args", {}),
            output_result=data.get("output_result", {}),
            artifacts=data.get("artifacts", []),
            user_feedback=data.get("user_feedback"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
        )

    def set_status(self, status: StepStatus) -> None:
        """设置状态"""
        self.status = status.value
        if status == StepStatus.RUNNING:
            self.started_at = datetime.now().isoformat()
        elif status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED):
            self.finished_at = datetime.now().isoformat()


@dataclass
class OrchestrationTask:
    """
    运行时任务对象

    任务是用户的高级意图实例，由多个步骤按顺序组成。
    具有唯一 ID，支持路由与恢复，可关联最佳实践模板。
    """

    # 标识
    id: str  # UUID
    session_id: str  # 所属会话
    template_id: str | None = None  # 关联的最佳实践 ID

    # 触发信息
    trigger_type: str = TriggerType.CONTEXT.value  # TriggerType 值
    trigger_message_id: str | None = None  # 触发消息 ID

    # 状态
    status: str = TaskStatus.PENDING.value  # TaskStatus 值
    suspend_reason: str | None = None  # 暂停原因
    current_step_index: int = 0  # 当前步骤索引
    irrelevant_turn_count: int = 0  # 连续无关对话计数

    # 数据
    name: str = ""
    description: str = ""
    input_payload: dict[str, Any] = field(default_factory=dict)  # 初始输入
    result_payload: dict[str, Any] = field(default_factory=dict)  # 最终结果
    context_variables: dict[str, Any] = field(default_factory=dict)  # 跨步骤共享变量

    # 步骤
    steps: list[TaskStep] = field(default_factory=list)

    # 时间戳
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str | None = None

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "template_id": self.template_id,
            "trigger_type": self.trigger_type,
            "trigger_message_id": self.trigger_message_id,
            "status": self.status,
            "suspend_reason": self.suspend_reason,
            "current_step_index": self.current_step_index,
            "irrelevant_turn_count": self.irrelevant_turn_count,
            "name": self.name,
            "description": self.description,
            "input_payload": self.input_payload,
            "result_payload": self.result_payload,
            "context_variables": self.context_variables,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OrchestrationTask":
        """从字典反序列化"""
        steps = [TaskStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            id=data["id"],
            session_id=data["session_id"],
            template_id=data.get("template_id"),
            trigger_type=data.get("trigger_type", TriggerType.CONTEXT.value),
            trigger_message_id=data.get("trigger_message_id"),
            status=data.get("status", TaskStatus.PENDING.value),
            suspend_reason=data.get("suspend_reason"),
            current_step_index=data.get("current_step_index", 0),
            irrelevant_turn_count=data.get("irrelevant_turn_count", 0),
            name=data.get("name", ""),
            description=data.get("description", ""),
            input_payload=data.get("input_payload", {}),
            result_payload=data.get("result_payload", {}),
            context_variables=data.get("context_variables", {}),
            steps=steps,
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            completed_at=data.get("completed_at"),
        )

    def set_status(self, status: TaskStatus) -> None:
        """设置状态"""
        self.status = status.value
        self.updated_at = datetime.now().isoformat()
        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            self.completed_at = datetime.now().isoformat()

    def get_current_step(self) -> TaskStep | None:
        """获取当前步骤"""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    def advance_step(self) -> bool:
        """推进到下一步，返回是否还有下一步"""
        self.current_step_index += 1
        self.updated_at = datetime.now().isoformat()
        return self.current_step_index < len(self.steps)


# ==================== 会话任务管理 ====================


@dataclass
class SessionTasks:
    """
    会话级任务管理

    管理单个会话内所有任务的状态：
    - 维护任务集合与活跃任务
    - 提供路由索引与上下文管理
    - 确保同一时刻仅一个活跃任务
    """

    session_id: str
    active_task_id: str | None = None  # 当前活跃任务（仅一个）
    tasks: dict[str, OrchestrationTask] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "session_id": self.session_id,
            "active_task_id": self.active_task_id,
            "tasks": {k: v.to_dict() for k, v in self.tasks.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionTasks":
        """从字典反序列化"""
        tasks = {
            k: OrchestrationTask.from_dict(v)
            for k, v in data.get("tasks", {}).items()
        }
        return cls(
            session_id=data["session_id"],
            active_task_id=data.get("active_task_id"),
            tasks=tasks,
        )

    def get_active_task(self) -> OrchestrationTask | None:
        """获取当前活跃任务"""
        if self.active_task_id and self.active_task_id in self.tasks:
            return self.tasks[self.active_task_id]
        return None

    def activate_task(self, task_id: str) -> None:
        """激活指定任务"""
        if task_id in self.tasks:
            self.active_task_id = task_id

    def deactivate_task(self) -> None:
        """取消当前活跃任务"""
        self.active_task_id = None

    def add_task(self, task: OrchestrationTask) -> None:
        """添加新任务"""
        self.tasks[task.id] = task

    def remove_task(self, task_id: str) -> bool:
        """移除任务，返回是否成功"""
        if task_id in self.tasks:
            del self.tasks[task_id]
            if self.active_task_id == task_id:
                self.active_task_id = None
            return True
        return False

    def has_active_task(self) -> bool:
        """检查是否有活跃任务"""
        return self.active_task_id is not None and self.active_task_id in self.tasks