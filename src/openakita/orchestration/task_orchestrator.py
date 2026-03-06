"""
TaskOrchestrator - 任务编排核心组件

负责任务的创建、恢复、执行和状态管理。
协调 SessionTasks、TaskStorage 和 Transport 各层组件，
实现完整的任务生命周期管理。
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from .models import (
    BestPracticeConfig,
    OrchestrationTask,
    SessionTasks,
    StepStatus,
    SubAgentConfig,
    TaskStatus,
    TaskStep,
    TriggerType,
)
from .session_tasks import RouteResult, SessionTasks as SessionTasksManager
from .storage import TaskStorage
from .transport import (
    AgentTransport,
    Command,
    CommandType,
    Event,
    EventType,
    MemoryTransport,
    Response,
)

logger = logging.getLogger(__name__)


# ==================== 异常类 ====================


class TaskOrchestratorError(Exception):
    """任务编排器错误"""

    pass


class TaskNotFoundError(TaskOrchestratorError):
    """任务不存在错误"""

    pass


class TaskExecutionError(TaskOrchestratorError):
    """任务执行错误"""

    pass


class TemplateNotFoundError(TaskOrchestratorError):
    """模板不存在错误"""

    pass


# ==================== 路由决策 ====================


class RouteDecision(Enum):
    """路由决策类型"""

    TO_TASK = "to_task"  # 路由到任务
    TO_NORMAL_CHAT = "to_normal_chat"  # 普通对话
    TASK_SUSPENDED = "task_suspended"  # 任务已暂停


@dataclass
class RouteOutput:
    """路由输出"""

    decision: RouteDecision
    task_id: str | None = None
    step_id: str | None = None
    message: str | None = None


# ==================== TaskOrchestrator ====================


class TaskOrchestrator:
    """
    任务编排核心组件

    负责任务的创建、恢复、执行和状态管理。
    MainAgent 通过 TaskOrchestrator 与 SubAgent 进行交互。

    特性:
    - 任务创建与恢复
    - 步骤执行循环
    - 输入路由
    - 自动暂停机制
    - 最佳实践管理
    """

    def __init__(
        self,
        storage: TaskStorage | None = None,
        transport: AgentTransport | None = None,
    ):
        """
        初始化任务编排器

        Args:
            storage: 任务存储实例（可选，默认创建新实例）
            transport: 通信传输实例（可选，默认使用 MemoryTransport）
        """
        self._storage = storage or TaskStorage()
        self._transport = transport or MemoryTransport("orchestrator")

        # 会话任务管理器缓存
        self._session_tasks: dict[str, SessionTasksManager] = {}

        # 最佳实践注册表
        self._templates: dict[str, BestPracticeConfig] = {}

        # 运行状态
        self._running = False

        # 执行回调
        self._on_task_event: Callable[[Event], Any] | None = None

    # ==================== 生命周期 ====================

    async def start(self) -> None:
        """启动编排器"""
        if self._running:
            return

        # 连接存储
        if not self._storage._connection:
            await self._storage.connect()

        # 启动传输
        await self._transport.start()

        self._running = True
        logger.info("TaskOrchestrator started")

    async def stop(self) -> None:
        """停止编排器"""
        if not self._running:
            return

        # 停止传输
        await self._transport.stop()

        # 关闭存储
        await self._storage.close()

        self._running = False
        logger.info("TaskOrchestrator stopped")

    # ==================== 最佳实践管理 ====================

    def register_template(self, template: BestPracticeConfig) -> None:
        """
        注册最佳实践模板

        Args:
            template: 最佳实践配置
        """
        self._templates[template.id] = template
        logger.info(f"Registered template: {template.id}")

    def unregister_template(self, template_id: str) -> bool:
        """
        注销最佳实践模板

        Args:
            template_id: 模板 ID

        Returns:
            是否注销成功
        """
        if template_id in self._templates:
            del self._templates[template_id]
            logger.info(f"Unregistered template: {template_id}")
            return True
        return False

    def get_template(self, template_id: str) -> BestPracticeConfig | None:
        """获取最佳实践模板"""
        return self._templates.get(template_id)

    def list_templates(self) -> list[BestPracticeConfig]:
        """列出所有最佳实践模板"""
        return list(self._templates.values())

    # ==================== 会话管理 ====================

    async def get_session_tasks(self, session_id: str) -> SessionTasksManager:
        """
        获取会话任务管理器

        优先从内存缓存获取，否则从数据库加载。

        Args:
            session_id: 会话 ID

        Returns:
            SessionTasksManager 对象
        """
        if session_id not in self._session_tasks:
            # 从数据库加载
            session_tasks = await self._storage.load_session_tasks(session_id)
            # 转换为 SessionTasksManager
            manager = SessionTasksManager(session_id=session_id)
            for task_id, task in session_tasks.tasks.items():
                manager.add_task(task)
            if session_tasks.active_task_id:
                manager.activate_task(session_tasks.active_task_id)
            self._session_tasks[session_id] = manager

        return self._session_tasks[session_id]

    def clear_session_cache(self, session_id: str) -> None:
        """清除会话缓存"""
        self._session_tasks.pop(session_id, None)

    # ==================== 任务创建 ====================

    async def create_task(
        self,
        session_id: str,
        template_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        input_payload: dict[str, Any] | None = None,
        trigger_type: str = TriggerType.CONTEXT.value,
    ) -> OrchestrationTask:
        """
        创建新任务

        Args:
            session_id: 会话 ID
            template_id: 最佳实践模板 ID（可选）
            name: 任务名称
            description: 任务描述
            input_payload: 初始输入数据
            trigger_type: 触发类型

        Returns:
            创建的任务对象

        Raises:
            TemplateNotFoundError: 模板不存在
        """
        task_id = str(uuid.uuid4())
        steps: list[TaskStep] = []

        # 如果指定了模板，从模板创建步骤
        if template_id:
            template = self._templates.get(template_id)
            if not template:
                raise TemplateNotFoundError(f"Template not found: {template_id}")

            name = name or template.name
            description = description or template.description

            # 从模板创建步骤
            for idx, step_template in enumerate(template.steps):
                step = TaskStep(
                    id=str(uuid.uuid4()),
                    task_id=task_id,
                    index=idx,
                    name=step_template.name,
                    description=step_template.description,
                    sub_agent_config=step_template.sub_agent_config,
                )
                steps.append(step)

        # 创建任务
        task = OrchestrationTask(
            id=task_id,
            session_id=session_id,
            template_id=template_id,
            trigger_type=trigger_type,
            name=name or "New Task",
            description=description or "",
            input_payload=input_payload or {},
            steps=steps,
        )

        # 持久化
        await self._storage.save_task(task)

        # 添加到会话
        session_tasks = await self.get_session_tasks(session_id)
        session_tasks.add_task(task)

        # 发布事件
        await self._publish_event(Event.create(
            event_type=EventType.TASK_CREATED,
            payload={"task_id": task_id, "name": task.name},
        ))

        logger.info(f"Task created: {task_id}")
        return task

    # ==================== 任务恢复 ====================

    async def resume_task(self, task_id: str) -> OrchestrationTask:
        """
        恢复任务

        Args:
            task_id: 任务 ID

        Returns:
            恢复的任务对象

        Raises:
            TaskNotFoundError: 任务不存在
        """
        # 从数据库加载
        task = await self._storage.load_task(task_id)
        if not task:
            raise TaskNotFoundError(f"Task not found: {task_id}")

        # 重置无关计数
        task.irrelevant_turn_count = 0

        # 设置为运行状态
        if task.status == TaskStatus.PAUSED.value:
            task.status = TaskStatus.RUNNING.value
            task.suspend_reason = None

        # 更新数据库
        await self._storage.save_task(task)

        # 添加到会话并激活
        session_tasks = await self.get_session_tasks(task.session_id)
        if task_id not in session_tasks.tasks:
            session_tasks.add_task(task)
        session_tasks.activate_task(task_id)

        # 发布事件
        await self._publish_event(Event.create(
            event_type=EventType.TASK_STARTED,
            payload={"task_id": task_id},
        ))

        logger.info(f"Task resumed: {task_id}")
        return task

    # ==================== 任务控制 ====================

    async def pause_task(
        self,
        task_id: str,
        reason: str = "user_requested",
    ) -> None:
        """
        暂停任务

        Args:
            task_id: 任务 ID
            reason: 暂停原因
        """
        task = await self._storage.load_task(task_id)
        if not task:
            raise TaskNotFoundError(f"Task not found: {task_id}")

        task.status = TaskStatus.PAUSED.value
        task.suspend_reason = reason
        await self._storage.save_task(task)

        # 取消会话中的活跃状态
        session_tasks = await self.get_session_tasks(task.session_id)
        session_tasks.deactivate_task()

        # 发布事件
        await self._publish_event(Event.create(
            event_type=EventType.TASK_PAUSED,
            payload={"task_id": task_id, "reason": reason},
        ))

        logger.info(f"Task paused: {task_id}")

    async def cancel_task(self, task_id: str) -> None:
        """
        取消任务

        Args:
            task_id: 任务 ID
        """
        task = await self._storage.load_task(task_id)
        if not task:
            raise TaskNotFoundError(f"Task not found: {task_id}")

        task.status = TaskStatus.CANCELLED.value
        await self._storage.save_task(task)

        # 从会话中移除
        session_tasks = await self.get_session_tasks(task.session_id)
        session_tasks.remove_task(task_id)

        # 发布事件
        await self._publish_event(Event.create(
            event_type=EventType.TASK_CANCELLED,
            payload={"task_id": task_id},
        ))

        logger.info(f"Task cancelled: {task_id}")

    # ==================== 执行循环 ====================

    async def execute_step(
        self,
        task: OrchestrationTask,
        step: TaskStep,
    ) -> Response:
        """
        执行单个步骤

        Args:
            task: 任务对象
            step: 步骤对象

        Returns:
            执行结果
        """
        # 更新步骤状态
        step.set_status(StepStatus.RUNNING)
        await self._storage.save_step(step)

        # 发布步骤开始事件
        await self._publish_event(Event.create(
            event_type=EventType.STEP_STARTED,
            payload={
                "task_id": task.id,
                "step_id": step.id,
                "step_name": step.name,
            },
        ))

        try:
            # 构建执行命令
            command = Command.create(
                command_type=CommandType.EXECUTE_STEP,
                payload={
                    "task_id": task.id,
                    "step_id": step.id,
                    "step_index": step.index,
                    "input_args": step.input_args,
                    "sub_agent_config": step.sub_agent_config.to_dict(),
                    "context_variables": task.context_variables,
                },
                sender_id="orchestrator",
                target_id="worker",
            )

            # 发送命令并等待响应
            # TODO: 实际发送到 SubAgent Worker
            # 这里先返回模拟响应
            response = Response.success_response(
                command_id=command.command_id,
                result={"status": "completed"},
            )

            # 更新步骤状态
            step.set_status(StepStatus.COMPLETED)
            step.output_result = response.result or {}
            await self._storage.save_step(step)

            # 发布步骤完成事件
            await self._publish_event(Event.create(
                event_type=EventType.STEP_COMPLETED,
                payload={
                    "task_id": task.id,
                    "step_id": step.id,
                },
            ))

            return response

        except Exception as e:
            # 更新步骤状态为失败
            step.set_status(StepStatus.FAILED)
            await self._storage.save_step(step)

            # 发布步骤失败事件
            await self._publish_event(Event.create(
                event_type=EventType.STEP_FAILED,
                payload={
                    "task_id": task.id,
                    "step_id": step.id,
                    "error": str(e),
                },
            ))

            raise TaskExecutionError(f"Step execution failed: {e}") from e

    async def advance_task(self, task: OrchestrationTask) -> bool:
        """
        推进任务到下一步

        Args:
            task: 任务对象

        Returns:
            是否还有下一步
        """
        has_next = task.advance_step()
        await self._storage.save_task(task)
        return has_next

    async def complete_task(self, task: OrchestrationTask) -> None:
        """
        完成任务

        Args:
            task: 任务对象
        """
        task.status = TaskStatus.COMPLETED.value
        await self._storage.save_task(task)

        # 取消会话中的活跃状态
        session_tasks = await self.get_session_tasks(task.session_id)
        session_tasks.deactivate_task()

        # 发布任务完成事件
        await self._publish_event(Event.create(
            event_type=EventType.TASK_COMPLETED,
            payload={"task_id": task.id, "name": task.name},
        ))

        logger.info(f"Task completed: {task.id}")

    # ==================== 路由逻辑 ====================

    async def route_input(
        self,
        session_id: str,
        user_input: str,
    ) -> RouteOutput:
        """
        路由用户输入

        Args:
            session_id: 会话 ID
            user_input: 用户输入

        Returns:
            RouteOutput 路由输出
        """
        session_tasks = await self.get_session_tasks(session_id)
        route_result = session_tasks.route_input(user_input)

        if route_result.routed:
            return RouteOutput(
                decision=RouteDecision.TO_TASK,
                task_id=route_result.task_id,
                step_id=route_result.step_id,
                message=route_result.reason,
            )

        # 检查是否触发自动暂停
        if route_result.reason == "Auto-suspend triggered":
            active_task = session_tasks.get_active_task()
            if active_task:
                await self.pause_task(active_task.id, "auto_suspend")

            return RouteOutput(
                decision=RouteDecision.TASK_SUSPENDED,
                message="Task auto-suspended due to irrelevant input",
            )

        return RouteOutput(
            decision=RouteDecision.TO_NORMAL_CHAT,
            message=route_result.reason,
        )

    # ==================== 自动暂停 ====================

    async def handle_irrelevant_input(
        self,
        session_id: str,
        task_id: str,
    ) -> bool:
        """
        处理无关输入

        递增无关计数，超过阈值时触发自动暂停。

        Args:
            session_id: 会话 ID
            task_id: 任务 ID

        Returns:
            是否触发自动暂停
        """
        session_tasks = await self.get_session_tasks(session_id)
        task = session_tasks.get_task(task_id)

        if not task:
            return False

        should_suspend = session_tasks.increment_irrelevant_count(task)
        await self._storage.update_task_meta(
            task_id,
            irrelevant_turn_count=task.irrelevant_turn_count,
        )

        if should_suspend:
            await self.pause_task(task_id, "auto_suspend")
            logger.info(f"Task auto-suspended: {task_id}")

        return should_suspend

    # ==================== 事件发布 ====================

    def set_event_handler(
        self,
        handler: Callable[[Event], Any],
    ) -> None:
        """
        设置事件处理器

        Args:
            handler: 事件处理函数
        """
        self._on_task_event = handler

    async def _publish_event(self, event: Event) -> None:
        """发布事件"""
        # 调用回调
        if self._on_task_event:
            try:
                result = self._on_task_event(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Event handler error: {e}")

        # 通过传输层广播
        try:
            await self._transport.publish_event(event)
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")

    # ==================== 统计信息 ====================

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "running": self._running,
            "templates_count": len(self._templates),
            "sessions_cached": len(self._session_tasks),
            "template_ids": list(self._templates.keys()),
        }