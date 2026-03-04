"""
Interrupt Manager - 处理任务中断、取消和跳过逻辑

从 agent.py 提取的中断管理功能，包括：
- 停止/跳过命令检测
- 任务取消状态管理
- 用户确认和消息插入
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from openakita.core.agent_state import AgentState
    from openakita.core.task_monitor import TaskStatus

logger = logging.getLogger(__name__)

# 停止任务的指令列表（用户发送这些指令时会立即停止当前任务）
STOP_COMMANDS = {
    "停止",
    "停",
    "stop",
    "停止执行",
    "取消",
    "取消任务",
    "算了",
    "不用了",
    "别做了",
    "停下",
    "暂停",
    "cancel",
    "abort",
    "quit",
    "停止当前任务",
    "中止",
    "终止",
    "不要了",
}

# 跳过当前步骤的指令列表
SKIP_COMMANDS = {
    "跳过",
    "skip",
    "下一步",
    "next",
    "跳过这步",
    "跳过当前",
    "skip this",
    "换个方法",
    "太慢了",
}


class InterruptManager:
    """
    中断管理器 - 处理任务的中断、取消和跳过

    职责:
    - 管理任务取消状态
    - 检测停止/跳过命令
    - 分类中断类型
    - 处理跳过和确认逻辑
    """

    def __init__(
        self,
        agent_state: AgentState,
        get_current_session_id: Callable[[], str | None] | None = None,
    ):
        """
        初始化中断管理器

        Args:
            agent_state: Agent 状态对象，用于访问任务状态
            get_current_session_id: 获取当前会话ID的回调函数
        """
        self._agent_state = agent_state
        self._get_current_session_id = get_current_session_id
        self._interrupt_enabled: bool = True

    @property
    def _task_cancelled(self) -> bool:
        """统一的取消状态查询（委托到 TaskState）"""
        return (
            hasattr(self, "_agent_state")
            and self._agent_state is not None
            and self._agent_state.is_task_cancelled
        )

    @property
    def _cancel_reason(self) -> str:
        """统一的取消原因查询（委托到 TaskState）"""
        if hasattr(self, "_agent_state") and self._agent_state:
            return self._agent_state.task_cancel_reason
        return ""

    def set_interrupt_enabled(self, enabled: bool) -> None:
        """
        设置是否启用中断检查

        Args:
            enabled: 是否启用
        """
        self._interrupt_enabled = enabled
        logger.info(f"Interrupt check {'enabled' if enabled else 'disabled'}")

    def cancel_current_task(self, reason: str = "用户请求停止", session_id: str | None = None) -> None:
        """
        取消正在执行的任务。

        如果指定 session_id，仅取消该会话的任务和计划；否则取消所有。

        Args:
            reason: 取消原因
            session_id: 可选会话 ID，实现跨通道隔离
        """
        _sid = session_id or (self._get_current_session_id() if self._get_current_session_id else None)

        if _sid:
            task = self._agent_state.get_task_for_session(_sid)
            task_status = task.status.value if task else "N/A"
            logger.info(
                f"[StopTask] cancel_current_task 被调用: reason={reason!r}, "
                f"session_id={_sid}, task_status={task_status}"
            )
            if task:
                self._agent_state.cancel_task(reason, session_id=_sid)
            else:
                logger.warning(
                    f"[StopTask] No task found for session {_sid}, "
                    f"falling back to cancel current_task"
                )
                self._agent_state.cancel_task(reason)
        else:
            has_task = self._agent_state.current_task is not None
            task_status = self._agent_state.current_task.status.value if has_task else "N/A"
            logger.info(
                f"[StopTask] cancel_current_task 被调用: reason={reason!r}, "
                f"has_task={has_task}, task_status={task_status}"
            )
            self._agent_state.cancel_task(reason)

        # 取消活跃的计划
        try:
            from openakita.tools.handlers.plan import cancel_plan

            if _sid:
                if cancel_plan(_sid):
                    logger.info(f"[StopTask] Cancelled active plan for session {_sid}")
            else:
                from openakita.tools.handlers.plan import _session_active_plans

                for sid in list(_session_active_plans.keys()):
                    if cancel_plan(sid):
                        logger.info(f"[StopTask] Cancelled active plan for session {sid}")
        except Exception as e:
            logger.warning(f"[StopTask] Failed to cancel plan: {e}")

        logger.info(f"[StopTask] Task cancellation completed: {reason}")

    def is_stop_command(self, message: str) -> bool:
        """
        检查消息是否为停止指令

        Args:
            message: 用户消息

        Returns:
            是否为停止指令
        """
        msg_lower = message.strip().lower()
        return msg_lower in STOP_COMMANDS or message.strip() in STOP_COMMANDS

    def is_skip_command(self, message: str) -> bool:
        """
        检查消息是否为跳过当前步骤指令

        Args:
            message: 用户消息

        Returns:
            是否为跳过指令
        """
        msg_lower = message.strip().lower()
        return msg_lower in SKIP_COMMANDS or message.strip() in SKIP_COMMANDS

    def classify_interrupt(self, message: str) -> str:
        """
        分类中断消息类型

        Args:
            message: 用户消息

        Returns:
            "stop" / "skip" / "insert"
        """
        if self.is_stop_command(message):
            return "stop"
        elif self.is_skip_command(message):
            return "skip"
        return "insert"

    def skip_current_step(self, reason: str = "用户请求跳过当前步骤", session_id: str | None = None) -> bool:
        """
        跳过当前正在执行的工具/步骤（不终止整个任务）

        Args:
            reason: 跳过原因
            session_id: 可选会话 ID，实现跨通道隔离

        Returns:
            是否成功设置 skip（False 表示无活跃任务）
        """
        _sid = session_id or (self._get_current_session_id() if self._get_current_session_id else None)
        task = (
            self._agent_state.get_task_for_session(_sid) if _sid else None
        ) or self._agent_state.current_task
        if task:
            self._agent_state.skip_current_step(reason, session_id=_sid)
            logger.info(f"[SkipStep] Step skip requested: {reason} (session={_sid})")
            return True
        logger.warning(f"[SkipStep] No active task to skip: {reason}")
        return False

    async def insert_user_message(self, text: str, session_id: str | None = None) -> bool:
        """
        向当前任务注入用户消息（任务执行期间的非指令消息）

        Args:
            text: 用户消息文本
            session_id: 可选会话 ID，实现跨通道隔离

        Returns:
            是否成功入队（False 表示无活跃任务，消息被丢弃）
        """
        _sid = session_id or (self._get_current_session_id() if self._get_current_session_id else None)
        task = (
            self._agent_state.get_task_for_session(_sid) if _sid else None
        ) or self._agent_state.current_task
        if task:
            await self._agent_state.insert_user_message(text, session_id=_sid)
            logger.info(f"[UserInsert] User message queued: {text[:50]}... (session={_sid})")
            return True
        logger.warning(f"[UserInsert] No active task, message dropped: {text[:50]}...")
        return False
