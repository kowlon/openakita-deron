"""
任务上下文

管理用于构建上下文的任务级信息，重点是为 LLM 提示词生成上下文，
与记忆模块中偏向存储的 TaskMemory 相区分。

支持检查点和回滚功能，允许在任务执行过程中保存状态并在需要时恢复。

参考：
- docs/context-refactoring-enterprise.md
- docs/refactor/20260226_enterprise_self_evolution_agent.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from openakita.context.exceptions import CheckpointNotFoundError


@dataclass
class Checkpoint:
    """
    检查点数据结构。

    属性：
        id: 检查点唯一标识
        state: 检查点状态数据
        created_at: 创建时间
    """

    id: str
    state: dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class TaskContext:
    """
    任务上下文 - 用于构建提示词的任务级上下文。

    包含任务定义、步骤摘要、关键变量和检查点。
    由 EnterpriseContextManager 用于构建任务层上下文。

    生命周期：
    - 任务开始时创建
    - 步骤完成时更新
    - 任务结束时销毁

    检查点支持：
    - save_checkpoint(): 保存当前状态
    - rollback(): 恢复到指定检查点

    属性：
        task_id: 任务唯一标识
        tenant_id: 多租户隔离的租户 ID
        task_type: 任务类型（如 "search"、"analysis"）
        task_description: 任务目标的简要描述
        step_summaries: 步骤完成摘要列表（最多 20 条）
        key_variables: 任务过程中的关键变量（最多 50 项）
        current_step: 当前步骤编号
        total_steps: 预计总步骤数（未知则为 0）
        created_at: 任务创建时间戳
        updated_at: 最后更新时间戳
        checkpoints: 检查点列表
        max_tokens: 任务上下文的最大 token 预算
    """

    task_id: str
    tenant_id: str
    task_type: str
    task_description: str
    step_summaries: list[str] = field(default_factory=list)
    key_variables: dict[str, Any] = field(default_factory=dict)
    current_step: int = 0
    total_steps: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    checkpoints: list[Checkpoint] = field(default_factory=list)
    max_tokens: int = 4000

    MAX_STEP_SUMMARIES = 20
    MAX_KEY_VARIABLES = 50
    MAX_CHECKPOINTS = 10

    def add_step_summary(self, step_name: str, summary: str) -> None:
        """
        添加步骤摘要（带滑动窗口限制）。

        参数：
            step_name: 步骤名称
            summary: 完成内容的简要摘要
        """
        truncated = summary[:100] if len(summary) > 100 else summary
        entry = f"[{step_name}] {truncated}"

        self.step_summaries.append(entry)

        if len(self.step_summaries) > self.MAX_STEP_SUMMARIES:
            self.step_summaries = self.step_summaries[-self.MAX_STEP_SUMMARIES:]

        self.current_step += 1
        self.updated_at = datetime.now()

    def add_variable(self, key: str, value: Any) -> None:
        """
        添加关键变量。

        参数：
            key: 变量名
            value: 变量值
        """
        if (
            len(self.key_variables) >= self.MAX_KEY_VARIABLES
            and key not in self.key_variables
        ):
            first_key = next(iter(self.key_variables))
            del self.key_variables[first_key]

        self.key_variables[key] = value
        self.updated_at = datetime.now()

    def add_variables(self, variables: dict[str, Any]) -> None:
        """
        添加多个变量。

        参数：
            variables: 要添加的变量字典
        """
        for key, value in variables.items():
            self.add_variable(key, value)

    def save_checkpoint(self, state: dict[str, Any] | None = None) -> str:
        """
        保存检查点。

        创建当前状态的快照，包括 step_summaries、key_variables 和 current_step。
        可选地保存额外的状态数据。

        参数：
            state: 可选的额外状态数据

        返回：
            检查点 ID（格式：cp_N）
        """
        checkpoint_id = f"cp_{len(self.checkpoints)}"

        # 创建当前状态快照
        checkpoint_state = {
            "step_summaries": list(self.step_summaries),
            "key_variables": dict(self.key_variables),
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "timestamp": datetime.now().isoformat(),
        }

        # 合并额外状态
        if state:
            checkpoint_state["extra"] = state

        checkpoint = Checkpoint(
            id=checkpoint_id,
            state=checkpoint_state,
        )

        self.checkpoints.append(checkpoint)

        # 限制检查点数量
        if len(self.checkpoints) > self.MAX_CHECKPOINTS:
            self.checkpoints = self.checkpoints[-self.MAX_CHECKPOINTS :]

        self.updated_at = datetime.now()
        return checkpoint_id

    def rollback(self, checkpoint_id: str) -> dict[str, Any] | None:
        """
        回滚到指定检查点。

        恢复 step_summaries、key_variables 和 current_step 到检查点状态。
        不删除检查点，只恢复状态。

        参数：
            checkpoint_id: 检查点 ID

        返回：
            检查点状态字典，如果检查点不存在则返回 None

        异常：
            CheckpointNotFoundError: 检查点不存在时抛出
        """
        for checkpoint in self.checkpoints:
            if checkpoint.id == checkpoint_id:
                # 恢复状态
                self.step_summaries = list(checkpoint.state.get("step_summaries", []))
                self.key_variables = dict(checkpoint.state.get("key_variables", {}))
                self.current_step = checkpoint.state.get("current_step", 0)
                self.total_steps = checkpoint.state.get("total_steps", 0)
                self.updated_at = datetime.now()
                return checkpoint.state

        raise CheckpointNotFoundError(checkpoint_id, self.task_id)

    def get_checkpoint(self, checkpoint_id: str) -> Checkpoint | None:
        """
        获取指定检查点。

        参数：
            checkpoint_id: 检查点 ID

        返回：
            检查点对象，如果不存在则返回 None
        """
        for checkpoint in self.checkpoints:
            if checkpoint.id == checkpoint_id:
                return checkpoint
        return None

    def list_checkpoints(self) -> list[dict[str, Any]]:
        """
        列出所有检查点摘要。

        返回：
            检查点摘要列表
        """
        return [
            {
                "id": cp.id,
                "created_at": cp.created_at.isoformat(),
                "step": cp.state.get("current_step", 0),
                "has_extra": "extra" in cp.state,
            }
            for cp in self.checkpoints
        ]

    def clear_checkpoints(self) -> None:
        """清空所有检查点。"""
        self.checkpoints = []
        self.updated_at = datetime.now()

    def to_prompt(self) -> str:
        """
        生成任务上下文提示词字符串。

        返回：
            用于注入系统提示词的格式化字符串。
        """
        parts = []

        parts.append(f"# 任务目标\n{self.task_description}")

        if self.total_steps > 0:
            parts.append(f"\n进度: 步骤 {self.current_step}/{self.total_steps}")
        elif self.current_step > 0:
            parts.append(f"\n进度: 步骤 {self.current_step}")

        if self.step_summaries:
            parts.append("\n# 已完成步骤")
            for i, summary in enumerate(self.step_summaries, 1):
                parts.append(f"{i}. {summary}")

        if self.key_variables:
            parts.append("\n# 关键变量")
            for key, value in self.key_variables.items():
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:100] + "..."
                parts.append(f"- {key}: {value_str}")

        return "\n".join(parts)

    def estimate_tokens(self, chars_per_token: float = 4.0) -> int:
        """
        估算任务上下文的 token 数量。

        参数：
            chars_per_token: 每个 token 的平均字符数

        返回：
            估算的 token 数量
        """
        return int(len(self.to_prompt()) / chars_per_token)

    def is_within_budget(self) -> bool:
        """
        检查上下文是否在 token 预算内。

        返回：
            若估算 token 数 <= max_tokens 则为 True
        """
        return self.estimate_tokens() <= self.max_tokens

    def clear(self) -> None:
        """清空任务上下文。"""
        self.step_summaries = []
        self.key_variables = {}
        self.current_step = 0
        self.checkpoints = []
        self.updated_at = datetime.now()

    def get_stats(self) -> dict[str, Any]:
        """
        获取任务上下文的统计信息。

        返回：
            任务统计信息字典
        """
        return {
            "task_id": self.task_id,
            "tenant_id": self.tenant_id,
            "task_type": self.task_type,
            "step_count": len(self.step_summaries),
            "variable_count": len(self.key_variables),
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "checkpoint_count": len(self.checkpoints),
            "estimated_tokens": self.estimate_tokens(),
            "max_tokens": self.max_tokens,
            "within_budget": self.is_within_budget(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def to_dict(self) -> dict[str, Any]:
        """转换为用于序列化的字典。"""
        return {
            "task_id": self.task_id,
            "tenant_id": self.tenant_id,
            "task_type": self.task_type,
            "task_description": self.task_description,
            "step_summaries": self.step_summaries,
            "key_variables": self.key_variables,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "max_tokens": self.max_tokens,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "checkpoints": [
                {
                    "id": cp.id,
                    "state": cp.state,
                    "created_at": cp.created_at.isoformat(),
                }
                for cp in self.checkpoints
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskContext":
        """从字典创建。"""
        checkpoints = []
        for cp_data in data.get("checkpoints", []):
            checkpoints.append(
                Checkpoint(
                    id=cp_data["id"],
                    state=cp_data["state"],
                    created_at=(
                        datetime.fromisoformat(cp_data["created_at"])
                        if "created_at" in cp_data
                        else datetime.now()
                    ),
                )
            )

        return cls(
            task_id=data["task_id"],
            tenant_id=data["tenant_id"],
            task_type=data["task_type"],
            task_description=data["task_description"],
            step_summaries=data.get("step_summaries", []),
            key_variables=data.get("key_variables", {}),
            current_step=data.get("current_step", 0),
            total_steps=data.get("total_steps", 0),
            max_tokens=data.get("max_tokens", 4000),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if "created_at" in data
                else datetime.now()
            ),
            updated_at=(
                datetime.fromisoformat(data["updated_at"])
                if "updated_at" in data
                else datetime.now()
            ),
            checkpoints=checkpoints,
        )

    def __str__(self) -> str:
        """字符串表示。"""
        return f"TaskContext({self.task_id}, type={self.task_type}, steps={len(self.step_summaries)})"

    def __repr__(self) -> str:
        """详细表示。"""
        return (
            f"TaskContext(task_id='{self.task_id}', tenant_id='{self.tenant_id}', "
            f"task_type='{self.task_type}', steps={len(self.step_summaries)}, "
            f"variables={len(self.key_variables)}, checkpoints={len(self.checkpoints)})"
        )
