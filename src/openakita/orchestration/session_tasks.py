"""
SessionTasks - 会话任务管理器

管理单个会话内所有任务的状态：
- 维护任务集合与活跃任务
- 提供路由索引与上下文管理
- 确保同一时刻仅一个活跃任务（单活跃任务原则）
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

from .models import OrchestrationTask, TaskStatus

logger = logging.getLogger(__name__)


@dataclass
class RouteResult:
    """
    路由判断结果

    描述用户输入应该被路由到哪个任务/步骤。
    """

    routed: bool  # 是否路由到任务
    task_id: str | None = None  # 目标任务 ID
    step_id: str | None = None  # 目标步骤 ID
    reason: str | None = None  # 路由原因


class SessionTasks:
    """
    会话级任务管理

    管理单个会话内所有任务的状态，确保同一时刻仅一个活跃任务。

    特性:
    - 单活跃任务原则
    - 任务路由判断
    - 自动暂停检测
    - 线程安全
    """

    # 自动暂停阈值（连续无关对话次数）
    AUTO_SUSPEND_THRESHOLD = 5

    def __init__(self, session_id: str):
        """
        初始化会话任务管理器

        Args:
            session_id: 会话 ID
        """
        self._session_id = session_id
        self._active_task_id: str | None = None
        self._tasks: dict[str, OrchestrationTask] = {}
        self._lock = threading.Lock()

    # ==================== 属性 ====================

    @property
    def session_id(self) -> str:
        """会话 ID"""
        return self._session_id

    @property
    def active_task_id(self) -> str | None:
        """当前活跃任务 ID"""
        return self._active_task_id

    @property
    def tasks(self) -> dict[str, OrchestrationTask]:
        """所有任务（只读）"""
        return self._tasks.copy()

    # ==================== 任务管理 ====================

    def get_active_task(self) -> OrchestrationTask | None:
        """
        获取当前活跃任务

        Returns:
            活跃任务对象，无活跃任务则返回 None
        """
        with self._lock:
            if self._active_task_id and self._active_task_id in self._tasks:
                return self._tasks[self._active_task_id]
            return None

    def activate_task(self, task_id: str) -> bool:
        """
        激活指定任务

        Args:
            task_id: 要激活的任务 ID

        Returns:
            是否激活成功
        """
        with self._lock:
            if task_id not in self._tasks:
                logger.warning(f"Cannot activate non-existent task: {task_id}")
                return False

            # 如果已有活跃任务，先取消
            if self._active_task_id and self._active_task_id != task_id:
                logger.info(f"Deactivating previous task: {self._active_task_id}")

            self._active_task_id = task_id
            logger.info(f"Activated task: {task_id}")
            return True

    def deactivate_task(self) -> str | None:
        """
        取消当前活跃任务

        Returns:
            被取消的任务 ID，无活跃任务则返回 None
        """
        with self._lock:
            if self._active_task_id:
                task_id = self._active_task_id
                self._active_task_id = None
                logger.info(f"Deactivated task: {task_id}")
                return task_id
            return None

    def add_task(self, task: OrchestrationTask) -> None:
        """
        添加新任务

        Args:
            task: 要添加的任务对象
        """
        with self._lock:
            self._tasks[task.id] = task
            logger.debug(f"Added task: {task.id}")

    def remove_task(self, task_id: str) -> bool:
        """
        移除任务

        Args:
            task_id: 要移除的任务 ID

        Returns:
            是否移除成功
        """
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]

                # 如果移除的是活跃任务，清除活跃状态
                if self._active_task_id == task_id:
                    self._active_task_id = None
                    logger.info(f"Removed active task: {task_id}")
                else:
                    logger.debug(f"Removed task: {task_id}")

                return True
            return False

    def get_task(self, task_id: str) -> OrchestrationTask | None:
        """
        获取指定任务

        Args:
            task_id: 任务 ID

        Returns:
            任务对象，不存在则返回 None
        """
        with self._lock:
            return self._tasks.get(task_id)

    def has_active_task(self) -> bool:
        """检查是否有活跃任务"""
        with self._lock:
            return self._active_task_id is not None and self._active_task_id in self._tasks

    def get_all_tasks(self) -> list[OrchestrationTask]:
        """获取所有任务列表"""
        with self._lock:
            return list(self._tasks.values())

    # ==================== 路由判断 ====================

    def route_input(self, user_input: str) -> RouteResult:
        """
        判断用户输入路由目标

        Args:
            user_input: 用户输入文本

        Returns:
            RouteResult 路由判断结果
        """
        with self._lock:
            # 没有活跃任务，不路由
            if not self._active_task_id:
                return RouteResult(
                    routed=False,
                    reason="No active task"
                )

            # 获取活跃任务
            task = self._tasks.get(self._active_task_id)
            if not task:
                return RouteResult(
                    routed=False,
                    reason="Active task not found"
                )

            # 任务不在运行状态，不路由
            if task.status != TaskStatus.RUNNING.value:
                return RouteResult(
                    routed=False,
                    reason=f"Task not running: {task.status}"
                )

            # 获取当前步骤
            current_step = task.get_current_step()
            if not current_step:
                return RouteResult(
                    routed=False,
                    reason="No current step"
                )

            # 检查输入是否与任务相关
            if self.is_irrelevant(user_input, task):
                # 递增无关计数
                should_suspend = self.increment_irrelevant_count(task)

                if should_suspend:
                    return RouteResult(
                        routed=False,
                        reason="Auto-suspend triggered"
                    )

                return RouteResult(
                    routed=False,
                    reason="Input irrelevant to task"
                )

            # 重置无关计数（输入相关）
            task.irrelevant_turn_count = 0

            return RouteResult(
                routed=True,
                task_id=task.id,
                step_id=current_step.id,
                reason="Routed to active task"
            )

    def is_irrelevant(self, user_input: str, task: OrchestrationTask) -> bool:
        """
        判断输入是否与任务无关

        当前使用简单关键词匹配，未来可接入 LLM 判断。

        Args:
            user_input: 用户输入文本
            task: 任务对象

        Returns:
            是否与任务无关
        """
        # 简单实现：检查是否包含任务相关关键词
        # TODO: 未来可接入 LLM 进行智能判断

        input_lower = user_input.lower()

        # 空输入视为无关
        if not input_lower.strip():
            return True

        # 任务名称相关关键词
        task_keywords = [
            task.name.lower(),
            task.description.lower(),
        ]

        # 当前步骤相关关键词
        current_step = task.get_current_step()
        if current_step:
            task_keywords.extend([
                current_step.name.lower(),
                current_step.description.lower(),
            ])

        # 检查是否匹配任何关键词
        for keyword in task_keywords:
            if keyword and keyword in input_lower:
                return False

        # 检查常见的任务相关词汇
        task_related_words = [
            "继续", "continue", "next", "下一步", "下一个",
            "跳过", "skip", "暂停", "pause", "恢复", "resume",
            "取消", "cancel", "停止", "stop", "完成", "done",
            "是的", "yes", "不是", "no", "好的", "ok",
        ]

        for word in task_related_words:
            if word in input_lower:
                return False

        return True

    def increment_irrelevant_count(self, task: OrchestrationTask) -> bool:
        """
        递增无关对话计数

        Args:
            task: 任务对象

        Returns:
            是否触发自动暂停
        """
        task.irrelevant_turn_count += 1
        logger.debug(
            f"Task {task.id} irrelevant count: {task.irrelevant_turn_count}"
        )

        if task.irrelevant_turn_count >= self.AUTO_SUSPEND_THRESHOLD:
            logger.info(
                f"Task {task.id} auto-suspend triggered: "
                f"{task.irrelevant_turn_count} irrelevant turns"
            )
            return True

        return False

    # ==================== 序列化 ====================

    def to_dict(self) -> dict:
        """序列化为字典"""
        with self._lock:
            return {
                "session_id": self._session_id,
                "active_task_id": self._active_task_id,
                "tasks": {k: v.to_dict() for k, v in self._tasks.items()},
            }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionTasks":
        """从字典反序列化"""
        tasks = {
            k: OrchestrationTask.from_dict(v)
            for k, v in data.get("tasks", {}).items()
        }

        instance = cls(session_id=data["session_id"])
        instance._active_task_id = data.get("active_task_id")
        instance._tasks = tasks

        return instance

    # ==================== 统计信息 ====================

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            status_counts: dict[str, int] = {}
            for task in self._tasks.values():
                status = task.status
                status_counts[status] = status_counts.get(status, 0) + 1

            return {
                "session_id": self._session_id,
                "total_tasks": len(self._tasks),
                "active_task_id": self._active_task_id,
                "status_counts": status_counts,
            }