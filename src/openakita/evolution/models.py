"""
执行追踪数据模型

用于记录和分析 Agent 执行过程中的各种事件，
支持自我进化闭环。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class StepType(Enum):
    """步骤类型"""
    REASONING = "reasoning"      # 推理步骤
    TOOL_CALL = "tool_call"      # 工具调用
    SKILL_CALL = "skill_call"    # 技能调用
    MCP_CALL = "mcp_call"        # MCP 调用
    DECISION = "decision"        # 决策点
    ERROR = "error"              # 错误处理
    RETRY = "retry"              # 重试
    FALLBACK = "fallback"        # 降级


class OutcomeLabel(Enum):
    """结果标签"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    ERROR = "error"


@dataclass
class ExecutionStep:
    """
    执行步骤

    记录单个执行步骤的详细信息。
    """
    step_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    step_type: StepType = StepType.REASONING
    name: str = ""
    description: str = ""
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float = 0.0
    error: str | None = None
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def start(self) -> None:
        """标记步骤开始"""
        self.started_at = datetime.now()
        self.status = ExecutionStatus.RUNNING

    def complete(self, output: dict[str, Any] | None = None) -> None:
        """标记步骤完成"""
        self.completed_at = datetime.now()
        self.status = ExecutionStatus.SUCCESS
        if output:
            self.output_data = output
        if self.started_at:
            self.duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000

    def fail(self, error: str) -> None:
        """标记步骤失败"""
        self.completed_at = datetime.now()
        self.status = ExecutionStatus.FAILURE
        self.error = error
        if self.started_at:
            self.duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "step_id": self.step_id,
            "step_type": self.step_type.value,
            "name": self.name,
            "description": self.description,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "retry_count": self.retry_count,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionStep":
        """从字典创建"""
        return cls(
            step_id=data.get("step_id", str(uuid.uuid4())[:8]),
            step_type=StepType(data.get("step_type", "reasoning")),
            name=data.get("name", ""),
            description=data.get("description", ""),
            input_data=data.get("input_data", {}),
            output_data=data.get("output_data", {}),
            status=ExecutionStatus(data.get("status", "pending")),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            duration_ms=data.get("duration_ms", 0.0),
            error=data.get("error"),
            retry_count=data.get("retry_count", 0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ExecutionTrace:
    """
    执行追踪

    记录一次完整任务执行的轨迹。
    """
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    session_id: str = ""
    task_description: str = ""
    steps: list[ExecutionStep] = field(default_factory=list)
    status: ExecutionStatus = ExecutionStatus.PENDING
    outcome: OutcomeLabel | None = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    total_duration_ms: float = 0.0
    token_usage: dict[str, int] = field(default_factory=dict)
    capabilities_used: list[str] = field(default_factory=list)
    error_summary: str | None = None
    user_feedback: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_step(self, step: ExecutionStep) -> str:
        """
        添加执行步骤。

        Args:
            step: 执行步骤

        Returns:
            步骤 ID
        """
        self.steps.append(step)
        return step.step_id

    def create_step(
        self,
        step_type: StepType,
        name: str,
        description: str = "",
        input_data: dict[str, Any] | None = None,
    ) -> ExecutionStep:
        """
        创建并添加新步骤。

        Args:
            step_type: 步骤类型
            name: 步骤名称
            description: 步骤描述
            input_data: 输入数据

        Returns:
            新创建的步骤
        """
        step = ExecutionStep(
            step_type=step_type,
            name=name,
            description=description,
            input_data=input_data or {},
        )
        self.add_step(step)
        return step

    def complete(self, outcome: OutcomeLabel = OutcomeLabel.SUCCESS) -> None:
        """
        标记执行完成。

        Args:
            outcome: 结果标签
        """
        self.completed_at = datetime.now()
        self.status = ExecutionStatus.SUCCESS if outcome == OutcomeLabel.SUCCESS else ExecutionStatus.FAILURE
        self.outcome = outcome
        self.total_duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000

    def fail(self, error_summary: str) -> None:
        """
        标记执行失败。

        Args:
            error_summary: 错误摘要
        """
        self.completed_at = datetime.now()
        self.status = ExecutionStatus.FAILURE
        self.outcome = OutcomeLabel.FAILURE
        self.error_summary = error_summary
        self.total_duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000

    def get_step_by_id(self, step_id: str) -> ExecutionStep | None:
        """根据 ID 获取步骤"""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def get_steps_by_type(self, step_type: StepType) -> list[ExecutionStep]:
        """根据类型获取步骤"""
        return [s for s in self.steps if s.step_type == step_type]

    def get_failed_steps(self) -> list[ExecutionStep]:
        """获取所有失败的步骤"""
        return [s for s in self.steps if s.status == ExecutionStatus.FAILURE]

    def get_retry_steps(self) -> list[ExecutionStep]:
        """获取所有重试过的步骤"""
        return [s for s in self.steps if s.retry_count > 0]

    def get_statistics(self) -> dict[str, Any]:
        """
        获取执行统计。

        Returns:
            统计数据字典
        """
        total_steps = len(self.steps)
        successful_steps = len([s for s in self.steps if s.status == ExecutionStatus.SUCCESS])
        failed_steps = len([s for s in self.steps if s.status == ExecutionStatus.FAILURE])

        steps_by_type: dict[str, int] = {}
        for step in self.steps:
            type_key = step.step_type.value
            steps_by_type[type_key] = steps_by_type.get(type_key, 0) + 1

        total_duration = sum(s.duration_ms for s in self.steps)
        avg_step_duration = total_duration / total_steps if total_steps > 0 else 0

        return {
            "trace_id": self.trace_id,
            "total_steps": total_steps,
            "successful_steps": successful_steps,
            "failed_steps": failed_steps,
            "success_rate": successful_steps / total_steps if total_steps > 0 else 0,
            "steps_by_type": steps_by_type,
            "total_duration_ms": total_duration,
            "avg_step_duration_ms": avg_step_duration,
            "capabilities_used": self.capabilities_used,
            "retry_count": len(self.get_retry_steps()),
            "outcome": self.outcome.value if self.outcome else None,
        }

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "trace_id": self.trace_id,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "task_description": self.task_description,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status.value,
            "outcome": self.outcome.value if self.outcome else None,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_duration_ms": self.total_duration_ms,
            "token_usage": self.token_usage,
            "capabilities_used": self.capabilities_used,
            "error_summary": self.error_summary,
            "user_feedback": self.user_feedback,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionTrace":
        """从字典创建"""
        return cls(
            trace_id=data.get("trace_id", str(uuid.uuid4())),
            task_id=data.get("task_id", ""),
            session_id=data.get("session_id", ""),
            task_description=data.get("task_description", ""),
            steps=[ExecutionStep.from_dict(s) for s in data.get("steps", [])],
            status=ExecutionStatus(data.get("status", "pending")),
            outcome=OutcomeLabel(data["outcome"]) if data.get("outcome") else None,
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else datetime.now(),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            total_duration_ms=data.get("total_duration_ms", 0.0),
            token_usage=data.get("token_usage", {}),
            capabilities_used=data.get("capabilities_used", []),
            error_summary=data.get("error_summary"),
            user_feedback=data.get("user_feedback"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PatternObservation:
    """
    模式观察

    从执行追踪中提取的模式观察。
    """
    pattern_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    pattern_type: str = ""  # success_pattern, failure_pattern, optimization_pattern
    description: str = ""
    frequency: int = 1
    confidence: float = 0.0
    examples: list[str] = field(default_factory=list)
    suggested_action: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "description": self.description,
            "frequency": self.frequency,
            "confidence": self.confidence,
            "examples": self.examples,
            "suggested_action": self.suggested_action,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PatternObservation":
        """从字典创建"""
        return cls(
            pattern_id=data.get("pattern_id", str(uuid.uuid4())[:8]),
            pattern_type=data.get("pattern_type", ""),
            description=data.get("description", ""),
            frequency=data.get("frequency", 1),
            confidence=data.get("confidence", 0.0),
            examples=data.get("examples", []),
            suggested_action=data.get("suggested_action", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
        )


@dataclass
class EvolutionProposal:
    """
    进化提案

    基于模式分析提出的改进建议。
    """
    proposal_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    description: str = ""
    rationale: str = ""
    proposal_type: str = ""  # new_skill, skill_improvement, process_change
    affected_capabilities: list[str] = field(default_factory=list)
    expected_benefit: str = ""
    risk_level: str = "low"  # low, medium, high
    implementation_steps: list[str] = field(default_factory=list)
    status: str = "proposed"  # proposed, approved, implemented, rejected
    created_at: datetime = field(default_factory=datetime.now)
    implemented_at: datetime | None = None

    def approve(self) -> None:
        """批准提案"""
        self.status = "approved"

    def implement(self) -> None:
        """实现提案"""
        self.status = "implemented"
        self.implemented_at = datetime.now()

    def reject(self, reason: str | None = None) -> None:
        """拒绝提案"""
        self.status = "rejected"
        if reason:
            self.rationale += f"\nRejected: {reason}"

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "proposal_id": self.proposal_id,
            "title": self.title,
            "description": self.description,
            "rationale": self.rationale,
            "proposal_type": self.proposal_type,
            "affected_capabilities": self.affected_capabilities,
            "expected_benefit": self.expected_benefit,
            "risk_level": self.risk_level,
            "implementation_steps": self.implementation_steps,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "implemented_at": self.implemented_at.isoformat() if self.implemented_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvolutionProposal":
        """从字典创建"""
        return cls(
            proposal_id=data.get("proposal_id", str(uuid.uuid4())[:8]),
            title=data.get("title", ""),
            description=data.get("description", ""),
            rationale=data.get("rationale", ""),
            proposal_type=data.get("proposal_type", ""),
            affected_capabilities=data.get("affected_capabilities", []),
            expected_benefit=data.get("expected_benefit", ""),
            risk_level=data.get("risk_level", "low"),
            implementation_steps=data.get("implementation_steps", []),
            status=data.get("status", "proposed"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            implemented_at=datetime.fromisoformat(data["implemented_at"]) if data.get("implemented_at") else None,
        )