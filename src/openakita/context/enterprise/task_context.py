"""
任务上下文

管理用于构建上下文的任务级信息，重点是为 LLM 提示词生成上下文，
与记忆模块中偏向存储的 TaskMemory 相区分。

参考：
- docs/context-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TaskContext:
    """
    任务上下文 - 用于构建提示词的任务级上下文。

    包含任务定义、步骤摘要和关键变量。
    由 EnterpriseContextManager 用于构建任务层上下文。

    生命周期：
    - 任务开始时创建
    - 步骤完成时更新
    - 任务结束时销毁

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

    # 约束
    MAX_STEP_SUMMARIES = 20
    MAX_KEY_VARIABLES = 50
    MAX_TOKENS = 16000

    def add_step_summary(self, step_name: str, summary: str) -> None:
        """
        添加步骤摘要（带滑动窗口限制）。

        参数：
            step_name: 步骤名称
            summary: 完成内容的简要摘要
        """
        # 将摘要截断到 100 字符
        truncated = summary[:100] if len(summary) > 100 else summary
        entry = f"[{step_name}] {truncated}"

        self.step_summaries.append(entry)

        # 强制滑动窗口限制
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
        # 达到上限且新增 key 时，移除最早条目
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

    def to_prompt(self) -> str:
        """
        生成任务上下文提示词字符串。

        返回：
            用于注入系统提示词的格式化字符串。
        """
        parts = []

        # 任务描述
        parts.append(f"# Current Task\n{self.task_description}")

        # 进度指示
        if self.total_steps > 0:
            parts.append(f"\nProgress: Step {self.current_step}/{self.total_steps}")
        elif self.current_step > 0:
            parts.append(f"\nProgress: Step {self.current_step}")

        # 步骤摘要
        if self.step_summaries:
            parts.append("\n# Completed Steps")
            for i, summary in enumerate(self.step_summaries, 1):
                parts.append(f"{i}. {summary}")

        # 关键变量
        if self.key_variables:
            parts.append("\n# Key Variables")
            for key, value in self.key_variables.items():
                # 截断过长的值
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
            若估算 token 数 <= MAX_TOKENS 则为 True
        """
        return self.estimate_tokens() <= self.MAX_TOKENS

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
            "estimated_tokens": self.estimate_tokens(),
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
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskContext":
        """从字典创建。"""
        return cls(
            task_id=data["task_id"],
            tenant_id=data["tenant_id"],
            task_type=data["task_type"],
            task_description=data["task_description"],
            step_summaries=data.get("step_summaries", []),
            key_variables=data.get("key_variables", {}),
            current_step=data.get("current_step", 0),
            total_steps=data.get("total_steps", 0),
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
        )

    def __str__(self) -> str:
        """字符串表示。"""
        return f"TaskContext({self.task_id}, type={self.task_type}, steps={len(self.step_summaries)})"

    def __repr__(self) -> str:
        """详细表示。"""
        return (
            f"TaskContext(task_id='{self.task_id}', tenant_id='{self.tenant_id}', "
            f"task_type='{self.task_type}', steps={len(self.step_summaries)}, "
            f"variables={len(self.key_variables)})"
        )
