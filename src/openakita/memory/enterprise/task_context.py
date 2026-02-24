"""
任务上下文存储

管理任务级上下文存储，包含步骤摘要、关键变量和错误记录。
支持多租户隔离。

参考：
- docs/memory-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ErrorEntry:
    """
    错误记录条目。

    记录任务执行过程中遇到的错误，用于调试与错误跟踪。

    属性：
        step_id: 出错的步骤 ID
        error_type: 错误类型（如 "NetworkError"、"TimeoutError"）
        error_message: 详细错误信息
        retry_count: 重试次数
        resolution: 解决方式（未解决则为 None）
        timestamp: 错误发生时间
    """

    step_id: str
    error_type: str
    error_message: str
    retry_count: int = 0
    resolution: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """转换为用于序列化的字典。"""
        return {
            "step_id": self.step_id,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "resolution": self.resolution,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ErrorEntry":
        """从字典创建。"""
        return cls(
            step_id=data["step_id"],
            error_type=data["error_type"],
            error_message=data["error_message"],
            retry_count=data.get("retry_count", 0),
            resolution=data.get("resolution"),
            timestamp=(
                datetime.fromisoformat(data["timestamp"])
                if "timestamp" in data
                else datetime.now()
            ),
        )


@dataclass
class TaskMemory:
    """
    任务记忆上下文。

    存储任务级信息，包括步骤摘要、关键变量和错误记录。
    任务记忆是临时的，任务结束后应清理。

    属性：
        task_id: 任务唯一标识
        tenant_id: 多租户隔离的租户 ID
        task_type: 任务类型（如 "search"、"analysis"）
        task_description: 任务目标的简要描述
        step_summaries: 步骤完成摘要列表（最多 20 条）
        key_variables: 任务过程中的关键变量（最多 50 项）
        errors: 错误记录列表
        created_at: 任务创建时间
        updated_at: 最后更新时间
    """

    task_id: str
    tenant_id: str
    task_type: str
    task_description: str
    step_summaries: list[str] = field(default_factory=list)
    key_variables: dict[str, Any] = field(default_factory=dict)
    errors: list[ErrorEntry] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # 限制
    MAX_STEP_SUMMARIES = 20
    MAX_KEY_VARIABLES = 50

    def add_step_summary(self, step_name: str, summary: str) -> None:
        """
        添加步骤摘要（带滑动窗口限制）。

        超过 MAX_STEP_SUMMARIES 时，移除最早条目。
        """
        entry = f"{step_name}: {summary}"
        self.step_summaries.append(entry)

        # 使用滑动窗口强制限制
        if len(self.step_summaries) > self.MAX_STEP_SUMMARIES:
            self.step_summaries = self.step_summaries[-self.MAX_STEP_SUMMARIES :]

        self.updated_at = datetime.now()

    def add_variable(self, key: str, value: Any) -> None:
        """
        添加关键变量。

        超过 MAX_KEY_VARIABLES 时，移除最早条目。
        """
        # 达到上限且新增 key 时，移除最早条目
        if len(self.key_variables) >= self.MAX_KEY_VARIABLES and key not in self.key_variables:
            # 删除第一个 key（Python 3.7+ 保持插入顺序）
            first_key = next(iter(self.key_variables))
            del self.key_variables[first_key]

        self.key_variables[key] = value
        self.updated_at = datetime.now()

    def add_variables(self, variables: dict[str, Any]) -> None:
        """添加多个变量。"""
        for key, value in variables.items():
            self.add_variable(key, value)

    def add_error(self, error: ErrorEntry) -> None:
        """添加错误记录。"""
        self.errors.append(error)
        self.updated_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """转换为用于序列化的字典。"""
        return {
            "task_id": self.task_id,
            "tenant_id": self.tenant_id,
            "task_type": self.task_type,
            "task_description": self.task_description,
            "step_summaries": self.step_summaries,
            "key_variables": self.key_variables,
            "errors": [e.to_dict() for e in self.errors],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskMemory":
        """从字典创建。"""
        return cls(
            task_id=data["task_id"],
            tenant_id=data["tenant_id"],
            task_type=data["task_type"],
            task_description=data["task_description"],
            step_summaries=data.get("step_summaries", []),
            key_variables=data.get("key_variables", {}),
            errors=[ErrorEntry.from_dict(e) for e in data.get("errors", [])],
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


class TaskContextStore:
    """
    任务上下文存储管理器。

    提供任务上下文的内存存储，支持：
    - 多租户隔离
    - 步骤摘要跟踪（最多 20 条）
    - 关键变量存储（最多 50 项）
    - 错误记录
    - 提示词上下文生成

    示例用法：
        store = TaskContextStore()

        # 启动任务
        store.start_task("task-001", "tenant-001", "search", "Search for info")

        # 记录进展
        store.record_step_completion(
            "task-001", "step-001", "Web Search",
            "Found 5 results", {"query": "info"}
        )

        # 获取用于提示词注入的上下文
        context = store.to_prompt("task-001")

        # 结束任务（清理记忆）
        store.end_task("task-001")
    """

    def __init__(self) -> None:
        """初始化空的上下文存储。"""
        self._contexts: dict[str, TaskMemory] = {}

    def start_task(
        self,
        task_id: str,
        tenant_id: str,
        task_type: str,
        description: str,
    ) -> TaskMemory:
        """
        启动新的任务上下文。

        参数：
            task_id: 任务唯一标识
            tenant_id: 用于隔离的租户 ID
            task_type: 任务类型
            description: 任务描述/目标

        返回：
            创建的 TaskMemory 对象
        """
        context = TaskMemory(
            task_id=task_id,
            tenant_id=tenant_id,
            task_type=task_type,
            task_description=description,
        )
        self._contexts[task_id] = context
        return context

    def end_task(self, task_id: str) -> bool:
        """
        结束任务并移除其上下文。

        参数：
            task_id: 任务标识

        返回：
            若找到并移除任务则为 True，否则为 False
        """
        if task_id in self._contexts:
            del self._contexts[task_id]
            return True
        return False

    def get_context(self, task_id: str) -> TaskMemory | None:
        """
        通过 ID 获取任务上下文。

        参数：
            task_id: 任务标识

        返回：
            若找到则返回 TaskMemory，否则为 None
        """
        return self._contexts.get(task_id)

    def record_step_completion(
        self,
        task_id: str,
        step_id: str,
        step_name: str,
        summary: str,
        variables: dict[str, Any],
    ) -> bool:
        """
        记录任务步骤完成情况。

        参数：
            task_id: 任务标识
            step_id: 步骤标识
            step_name: 步骤名称
            summary: 完成摘要
            variables: 本步骤的关键变量

        返回：
            若任务存在且记录成功则为 True，否则为 False
        """
        context = self._contexts.get(task_id)
        if not context:
            return False

        context.add_step_summary(step_name, summary)
        context.add_variables(variables)
        return True

    def record_error(
        self,
        task_id: str,
        step_id: str,
        error_type: str,
        error_message: str,
        resolution: str | None = None,
    ) -> bool:
        """
        记录任务错误。

        参数：
            task_id: 任务标识
            step_id: 出错的步骤
            error_type: 错误类型
            error_message: 错误信息
            resolution: 解决方式（可选）

        返回：
            若任务存在且记录成功则为 True，否则为 False
        """
        context = self._contexts.get(task_id)
        if not context:
            return False

        error = ErrorEntry(
            step_id=step_id,
            error_type=error_type,
            error_message=error_message,
            resolution=resolution,
        )
        context.add_error(error)
        return True

    def to_prompt(self, task_id: str) -> str:
        """
        生成提示词格式的上下文字符串。

        参数：
            task_id: 任务标识

        返回：
            用于提示词注入的格式化字符串。
            若任务不存在则返回空字符串。
        """
        context = self._contexts.get(task_id)
        if not context:
            return ""

        lines = ["## Task Context", ""]

        # 任务描述
        lines.append(f"**Task**: {context.task_description}")
        lines.append(f"**Type**: {context.task_type}")
        lines.append("")

        # 步骤摘要
        if context.step_summaries:
            lines.append("**Completed Steps**:")
            for i, summary in enumerate(context.step_summaries, 1):
                lines.append(f"  {i}. {summary}")
            lines.append("")

        # 关键变量
        if context.key_variables:
            lines.append("**Key Variables**:")
            for key, value in context.key_variables.items():
                lines.append(f"  - {key}: {value}")
            lines.append("")

        # 错误（如有）
        if context.errors:
            lines.append("**Errors Encountered**:")
            for error in context.errors:
                resolution = f" (resolved: {error.resolution})" if error.resolution else ""
                lines.append(f"  - [{error.error_type}] {error.error_message}{resolution}")
            lines.append("")

        return "\n".join(lines)

    def get_stats(self, task_id: str) -> dict[str, Any]:
        """
        获取任务统计信息。

        参数：
            task_id: 任务标识

        返回：
            任务统计信息字典。
            若任务不存在则返回空字典。
        """
        context = self._contexts.get(task_id)
        if not context:
            return {}

        return {
            "task_id": context.task_id,
            "tenant_id": context.tenant_id,
            "task_type": context.task_type,
            "step_count": len(context.step_summaries),
            "variable_count": len(context.key_variables),
            "error_count": len(context.errors),
            "created_at": context.created_at.isoformat(),
            "updated_at": context.updated_at.isoformat(),
        }

    def get_tasks_by_tenant(self, tenant_id: str) -> list[TaskMemory]:
        """
        获取指定租户的全部任务。

        参数：
            tenant_id: 租户标识

        返回：
            该租户的 TaskMemory 对象列表
        """
        return [
            ctx for ctx in self._contexts.values() if ctx.tenant_id == tenant_id
        ]

    def clear_all(self) -> None:
        """清空所有任务上下文。"""
        self._contexts.clear()

    @property
    def task_count(self) -> int:
        """获取活跃任务总数。"""
        return len(self._contexts)
