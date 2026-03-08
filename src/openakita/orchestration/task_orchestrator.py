"""
TaskOrchestrator - 任务编排核心组件

负责任务的创建、恢复、执行和状态管理。
协调 SessionTasks、TaskStorage 和 Transport 各层组件，
实现完整的任务生命周期管理。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from .models import (
    BestPracticeConfig,
    BestPracticeTriggerConfig,
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
from .subagent_worker import SubAgentPayload, SubAgentWorker
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
        worker: SubAgentWorker | None = None,
        llm_client: Any | None = None,
    ):
        """
        初始化任务编排器

        Args:
            storage: 任务存储实例（可选，默认创建新实例）
            transport: 通信传输实例（可选，默认使用 MemoryTransport）
            worker: SubAgentWorker 实例（可选，默认创建新实例）
            llm_client: LLM 客户端实例（可选，用于智能路由判断）
        """
        self._storage = storage or TaskStorage()
        self._transport = transport or MemoryTransport("orchestrator")
        self._worker = worker or SubAgentWorker("orchestrator-worker")

        # LLM 客户端（用于智能路由判断）
        self._llm_client = llm_client

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

        # 启动 Worker
        await self._worker.start()

        self._running = True
        logger.info("TaskOrchestrator started")

    async def stop(self) -> None:
        """停止编排器"""
        if not self._running:
            return

        # 停止 Worker
        await self._worker.stop()

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

    async def execute_task_stream(
        self,
        task: OrchestrationTask,
    ) -> AsyncIterator[dict]:
        """
        流式执行任务，yield 步骤事件

        用于最佳实践任务的多步骤执行。

        Args:
            task: 任务对象

        Yields:
            SSE 事件字典
        """
        # 更新任务状态
        task.status = TaskStatus.RUNNING.value
        await self._storage.save_task(task)

        # 发布任务开始事件
        yield {
            "type": "task_started",
            "task_id": task.id,
            "task_name": task.name,
            "total_steps": len(task.steps),
        }

        try:
            for step in task.steps:
                # 发布步骤开始事件
                yield {
                    "type": "step_started",
                    "task_id": task.id,
                    "step_id": step.id,
                    "step_name": step.name,
                    "step_index": step.index,
                }

                # 执行步骤（流式）
                async for event in self._execute_step_stream(task, step):
                    yield event

                # 检查步骤状态
                if step.status == StepStatus.FAILED.value:
                    # 发布步骤完成事件
                    yield {
                        "type": "step_completed",
                        "task_id": task.id,
                        "step_id": step.id,
                        "success": False,
                    }
                    break

                # 发布步骤完成事件
                yield {
                    "type": "step_completed",
                    "task_id": task.id,
                    "step_id": step.id,
                    "success": True,
                }

            # 更新任务状态
            if step.status == StepStatus.FAILED.value:
                task.status = TaskStatus.FAILED.value
            else:
                task.status = TaskStatus.COMPLETED.value
            await self._storage.save_task(task)

            # 发布任务完成事件
            yield {
                "type": "task_completed",
                "task_id": task.id,
                "success": task.status == TaskStatus.COMPLETED.value,
            }

        except Exception as e:
            # 更新任务状态为失败
            task.status = TaskStatus.FAILED.value
            await self._storage.save_task(task)

            yield {
                "type": "task_failed",
                "task_id": task.id,
                "error": str(e),
            }

    async def _execute_step_stream(
        self,
        task: OrchestrationTask,
        step: TaskStep,
    ) -> AsyncIterator[dict]:
        """
        流式执行单个步骤

        Args:
            task: 任务对象
            step: 步骤对象

        Yields:
            步骤执行事件
        """
        # 更新步骤状态
        step.set_status(StepStatus.RUNNING)
        await self._storage.save_step(step)

        try:
            # 发布步骤执行中事件
            yield {
                "type": "step_progress",
                "task_id": task.id,
                "step_id": step.id,
                "status": "executing",
            }

            # 构建执行载荷
            payload = SubAgentPayload(
                task_id=task.id,
                step_id=step.id,
                step_index=step.index,
                agent_config=step.sub_agent_config,
                task_context=task.context_variables,
                user_input="",  # 从 input_args 或其他来源获取
                timeout=300.0,  # 默认超时
            )

            # 从 input_args 获取用户输入（如果存在）
            if step.input_args and isinstance(step.input_args, dict):
                payload.user_input = step.input_args.get("user_input", "")

            # 调用 Worker.execute_stream()
            step_completed = False
            async for event in self._worker.execute_stream(payload):
                # 检查是否为步骤完成事件
                if event.get("type") == "step_complete":
                    step_completed = event.get("success", True)

                yield event

            # 更新步骤状态
            if step_completed:
                step.set_status(StepStatus.COMPLETED)
                step.output_result = {"status": "completed"}
            else:
                step.set_status(StepStatus.FAILED)
                step.output_result = {"status": "failed"}

            await self._storage.save_step(step)

        except Exception as e:
            # 更新步骤状态为失败
            step.set_status(StepStatus.FAILED)
            await self._storage.save_step(step)

            yield {
                "type": "step_failed",
                "task_id": task.id,
                "step_id": step.id,
                "error": str(e),
            }

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
        check_best_practices: bool = True,
    ) -> RouteOutput:
        """
        路由用户输入

        Args:
            session_id: 会话 ID
            user_input: 用户输入
            check_best_practices: 是否检查最佳实践触发（默认 True）

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

        # 检查是否触发最佳实践
        if check_best_practices and not session_tasks.has_active_task():
            matched_template = await self.should_trigger_best_practice(user_input)
            if matched_template:
                # 创建最佳实践任务
                task = await self.create_task(
                    session_id=session_id,
                    template_id=matched_template.id,
                    name=matched_template.name,
                    description=matched_template.description,
                    input_payload={"user_input": user_input},
                    trigger_type=TriggerType.BEST_PRACTICE.value,
                )
                return RouteOutput(
                    decision=RouteDecision.TO_TASK,
                    task_id=task.id,
                    message=f"Triggered best practice: {matched_template.name}",
                )

        return RouteOutput(
            decision=RouteDecision.TO_NORMAL_CHAT,
            message=route_result.reason,
        )

    async def should_trigger_best_practice(
        self,
        user_input: str,
    ) -> BestPracticeConfig | None:
        """
        判断用户输入是否触发最佳实践

        优先使用 LLM 智能判断，失败时回退到关键词匹配。

        Args:
            user_input: 用户输入

        Returns:
            匹配的最佳实践模板，无匹配返回 None
        """
        if not self._templates:
            return None

        # 获取启用了 LLM 触发的模板
        templates_with_llm = []
        templates_fallback = []

        for template in self._templates.values():
            if template.trigger_config and template.trigger_config.enabled:
                templates_with_llm.append(template)
            else:
                templates_fallback.append(template)

        # 尝试 LLM 匹配
        matched_template = None
        if templates_with_llm and self._llm_client:
            try:
                matched_template = await self._llm_match_best_practice(
                    user_input,
                    templates_with_llm,
                )
                if matched_template:
                    logger.info(f"LLM matched best practice: {matched_template.id}")
                    return matched_template
            except Exception as e:
                logger.warning(f"LLM matching failed, falling back to keywords: {e}")

        # 回退到关键词匹配
        for template in templates_with_llm:
            if self._keyword_match_best_practice(user_input, template):
                logger.info(f"Keyword matched best practice: {template.id}")
                return template

        for template in templates_fallback:
            if self._keyword_match_best_practice(user_input, template):
                logger.info(f"Keyword matched best practice (fallback): {template.id}")
                return template

        return None

    async def _llm_match_best_practice(
        self,
        user_input: str,
        templates: list[BestPracticeConfig],
    ) -> BestPracticeConfig | None:
        """
        使用 LLM 判断用户输入匹配哪个最佳实践

        Args:
            user_input: 用户输入
            templates: 候选最佳实践模板列表

        Returns:
            匹配的最佳实践模板，无匹配返回 None
        """
        if not self._llm_client or not templates:
            return None

        # 获取第一个模板的触发配置（作为默认配置）
        trigger_config = templates[0].trigger_config
        if not trigger_config:
            trigger_config = BestPracticeTriggerConfig()

        # 限制检查的模板数量
        max_templates = trigger_config.max_templates_to_check
        templates_to_check = templates[:max_templates]

        # 构建 prompt
        template_descriptions = []
        for i, template in enumerate(templates_to_check):
            template_descriptions.append(
                f"{i + 1}. {template.name}: {template.description}"
            )

        prompt = trigger_config.trigger_prompt or self._get_default_trigger_prompt()
        prompt = prompt.replace(
            "{templates}", "\n".join(template_descriptions)
        ).replace("{user_input}", user_input)

        try:
            # 调用 LLM
            from ..llm.types import LLMRequest, Message, TextBlock

            request = LLMRequest(
                messages=[Message(role="user", content=[TextBlock(text=prompt)])],
                temperature=trigger_config.llm_temperature,
                max_tokens=100,  # 简短回复即可
            )

            response = await self._llm_client.generate(request)

            # 解析结果
            response_text = response.content[0].text if response.content else ""

            # 尝试解析 JSON 格式的返回
            import json
            try:
                result = json.loads(response_text)
                if isinstance(result, dict):
                    matched_id = result.get("matched_template_id")
                    if matched_id:
                        for template in templates_to_check:
                            if template.id == matched_id:
                                return template
                    # 也支持索引匹配
                    matched_index = result.get("matched_index")
                    if matched_index and 0 < matched_index <= len(templates_to_check):
                        return templates_to_check[matched_index - 1]
            except json.JSONDecodeError:
                pass

            # 尝试从文本中提取模板名称或 ID
            for template in templates_to_check:
                if template.id in response_text or template.name in response_text:
                    return template

            # 检查是否明确表示不匹配
            if "none" in response_text.lower() or "无匹配" in response_text:
                return None

            # 尝试匹配数字索引
            import re
            match = re.search(r"\b([1-9])\b", response_text)
            if match:
                idx = int(match.group(1))
                if 0 < idx <= len(templates_to_check):
                    return templates_to_check[idx - 1]

            return None

        except Exception as e:
            logger.error(f"LLM matching error: {e}")
            raise

    def _keyword_match_best_practice(
        self,
        user_input: str,
        template: BestPracticeConfig,
    ) -> bool:
        """
        使用关键词匹配判断用户输入是否触发最佳实践

        Args:
            user_input: 用户输入
            template: 最佳实践模板

        Returns:
            是否匹配
        """
        input_lower = user_input.lower()

        # 检查模板名称和描述中的关键词
        keywords = [
            template.name.lower(),
            template.id.lower(),
        ]

        # 从描述中提取关键词（简单的空格分割）
        desc_words = template.description.lower().split()
        keywords.extend([w for w in desc_words if len(w) > 3])

        for keyword in keywords:
            if keyword and keyword in input_lower:
                return True

        return False

    @staticmethod
    def _get_default_trigger_prompt() -> str:
        """获取默认的 LLM 触发判断 prompt"""
        return """你是一个任务路由助手。根据用户的输入判断是否应该触发以下最佳实践流程。

最佳实践列表:
{templates}

用户输入: {user_input}

请判断用户输入是否匹配某个最佳实践。如果匹配，请返回 JSON 格式：
{"matched_template_id": "模板ID"} 或 {"matched_index": 数字索引}

如果不匹配任何最佳实践，请返回：
{"matched_template_id": null}

只返回 JSON，不要其他解释。"""

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