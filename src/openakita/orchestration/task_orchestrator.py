"""
TaskOrchestrator - 任务编排器

负责任务的创建、管理和协调。

核心功能:
- 从对话或手动触发创建任务
- 任务状态管理
- 协调 TaskSession 和 SubAgentManager
"""

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .context_manager import ContextManager, OutputExtractor
from .messages import StepRequest, StepResponse
from .models import ScenarioDefinition, TaskState, TaskStatus
from .scenario_registry import ScenarioRegistry, ScenarioMatchResult
from .subagent_manager import SubAgentManager
from .task_session import TaskSession, TaskSessionConfig

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """编排器配置"""

    auto_register_scenarios: bool = True  # 自动注册场景
    scenario_directories: list[str] | None = None  # 场景配置目录
    max_concurrent_tasks: int = 10  # 最大并发任务数
    default_session_config: TaskSessionConfig | None = None  # 默认会话配置


class TaskOrchestrator:
    """
    任务编排器

    管理任务的完整生命周期，从创建到完成。

    核心职责:
    - 场景匹配与任务创建
    - 任务会话管理
    - 状态协调与持久化
    - 与 MainAgent 集成
    """

    def __init__(
        self,
        scenario_registry: ScenarioRegistry,
        sub_agent_manager: SubAgentManager,
        config: OrchestratorConfig | None = None,
        data_dir: Path | None = None,
    ):
        """
        初始化任务编排器

        Args:
            scenario_registry: 场景注册表
            sub_agent_manager: SubAgent 管理器
            config: 编排器配置
            data_dir: 数据目录
        """
        self.scenario_registry = scenario_registry
        self._sub_agent_manager = sub_agent_manager
        self._config = config or OrchestratorConfig()
        self._data_dir = data_dir

        # 活跃任务映射: task_id -> TaskSession
        self._active_tasks: dict[str, TaskSession] = {}
        # 会话任务映射: session_id -> task_id
        self._session_tasks: dict[str, str] = {}

    # ==================== 初始化 ====================

    async def initialize(self) -> None:
        """初始化编排器"""
        # 启动 SubAgent 管理器
        await self._sub_agent_manager.start()

        # 加载场景配置
        if self._config.scenario_directories:
            for directory in self._config.scenario_directories:
                self.scenario_registry.load_from_directory(directory)

        logger.info(f"TaskOrchestrator initialized with {self.scenario_registry.count()} scenarios")

    async def shutdown(self) -> None:
        """关闭编排器"""
        # 取消所有活跃任务
        for task_session in list(self._active_tasks.values()):
            await task_session.cancel()

        # 停止 SubAgent 管理器
        await self._sub_agent_manager.stop()

        logger.info("TaskOrchestrator shutdown")

    # ==================== 任务创建 ====================

    async def create_task_from_dialog(
        self,
        message: str,
        session_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> TaskSession | None:
        """
        从对话消息创建任务

        Args:
            message: 用户消息
            session_id: 会话 ID
            context: 额外上下文

        Returns:
            创建的任务会话，无匹配则返回 None
        """
        # 场景匹配
        match_result = self.scenario_registry.match_from_dialog(message)
        if not match_result:
            logger.debug(f"No scenario matched for message: {message[:50]}...")
            return None

        return await self._create_task(
            scenario=match_result.scenario,
            session_id=session_id,
            initial_message=message,
            context=context or {},
            match_result=match_result,
        )

    async def create_task_manual(
        self,
        scenario_id: str,
        session_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> TaskSession | None:
        """
        手动创建任务

        Args:
            scenario_id: 场景 ID
            session_id: 会话 ID
            context: 初始上下文

        Returns:
            创建的任务会话
        """
        scenario = self.scenario_registry.get(scenario_id)
        if not scenario:
            logger.warning(f"Scenario not found: {scenario_id}")
            return None

        return await self._create_task(
            scenario=scenario,
            session_id=session_id,
            initial_message="",
            context=context or {},
        )

    async def _create_task(
        self,
        scenario: ScenarioDefinition,
        session_id: str | None = None,
        initial_message: str = "",
        context: dict[str, Any] | None = None,
        match_result: ScenarioMatchResult | None = None,
    ) -> TaskSession:
        """
        创建任务

        Args:
            scenario: 场景定义
            session_id: 会话 ID
            initial_message: 初始消息
            context: 上下文
            match_result: 匹配结果

        Returns:
            任务会话
        """
        # 生成任务 ID
        task_id = f"task-{uuid.uuid4().hex[:8]}"

        # 创建任务状态
        state = TaskState(
            task_id=task_id,
            scenario_id=scenario.scenario_id,
            session_id=session_id,
            status=TaskStatus.PENDING,
            initial_message=initial_message,
            context=context or {},
            total_steps=len(scenario.steps),
        )

        # 创建任务会话
        session_config = self._config.default_session_config or TaskSessionConfig()
        task_session = TaskSession(
            state=state,
            scenario=scenario,
            sub_agent_manager=self._sub_agent_manager,
            config=session_config,
        )

        # 注册任务
        self._active_tasks[task_id] = task_session
        if session_id:
            self._session_tasks[session_id] = task_id

        logger.info(f"Created task {task_id} for scenario {scenario.scenario_id}")

        return task_session

    # ==================== 任务管理 ====================

    async def start_task(self, task_id: str) -> bool:
        """
        启动任务

        Args:
            task_id: 任务 ID

        Returns:
            是否成功
        """
        task_session = self._active_tasks.get(task_id)
        if not task_session:
            logger.warning(f"Task not found: {task_id}")
            return False

        await task_session.start()
        return True

    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务 ID

        Returns:
            是否成功
        """
        task_session = self._active_tasks.get(task_id)
        if not task_session:
            return False

        await task_session.cancel()

        # 清理
        self._active_tasks.pop(task_id, None)
        if task_session.state.session_id:
            self._session_tasks.pop(task_session.state.session_id, None)

        return True

    async def confirm_step(
        self,
        task_id: str,
        step_id: str,
        edited_output: dict[str, Any] | None = None,
    ) -> bool:
        """
        确认步骤

        Args:
            task_id: 任务 ID
            step_id: 步骤 ID
            edited_output: 编辑后的输出

        Returns:
            是否成功
        """
        task_session = self._active_tasks.get(task_id)
        if not task_session:
            return False

        return await task_session.confirm_step(step_id, edited_output)

    async def switch_step(self, task_id: str, step_id: str) -> bool:
        """
        切换步骤

        Args:
            task_id: 任务 ID
            step_id: 目标步骤 ID

        Returns:
            是否成功
        """
        task_session = self._active_tasks.get(task_id)
        if not task_session:
            return False

        return await task_session.switch_to_step(step_id)

    # ==================== 消息分发 ====================

    async def dispatch_message(
        self,
        session_id: str,
        message: str,
    ) -> str | None:
        """
        分发消息到活跃任务

        Args:
            session_id: 会话 ID
            message: 用户消息

        Returns:
            响应内容，无活跃任务返回 None
        """
        task_id = self._session_tasks.get(session_id)
        if not task_id:
            return None

        task_session = self._active_tasks.get(task_id)
        if not task_session:
            return None

        # 检查任务状态
        if task_session.state.status == TaskStatus.WAITING_USER:
            # 等待用户确认，尝试确认当前步骤
            current_step = task_session.get_current_step()
            if current_step:
                # 用户消息可能表示确认或编辑请求
                if message.lower() in ["确认", "confirm", "ok", "好的"]:
                    await task_session.confirm_step(current_step.step_id)
                    return "步骤已确认，继续执行..."
                else:
                    # 将消息转发给当前步骤
                    return await task_session.dispatch_step(message)

        elif task_session.state.status == TaskStatus.RUNNING:
            # 运行中，转发消息到当前步骤
            return await task_session.dispatch_step(message)

        elif task_session.state.status == TaskStatus.COMPLETED:
            # 任务已完成，清理
            self._active_tasks.pop(task_id, None)
            self._session_tasks.pop(session_id, None)
            return None

        return None

    # ==================== 查询 ====================

    def get_task(self, task_id: str) -> TaskSession | None:
        """获取任务会话"""
        return self._active_tasks.get(task_id)

    def get_active_task(self, session_id: str) -> TaskSession | None:
        """获取会话的活跃任务"""
        task_id = self._session_tasks.get(session_id)
        if task_id:
            return self._active_tasks.get(task_id)
        return None

    def get_task_state(self, task_id: str) -> TaskState | None:
        """获取任务状态"""
        task_session = self._active_tasks.get(task_id)
        return task_session.state if task_session else None

    def list_active_tasks(self) -> list[TaskSession]:
        """列出所有活跃任务"""
        return list(self._active_tasks.values())

    def list_tasks_by_status(self, status: TaskStatus) -> list[TaskSession]:
        """按状态列出任务"""
        return [
            ts for ts in self._active_tasks.values()
            if ts.state.status == status
        ]

    def has_active_task(self, session_id: str) -> bool:
        """检查会话是否有活跃任务"""
        return session_id in self._session_tasks

    # ==================== 统计 ====================

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        status_counts = {}
        for status in TaskStatus:
            status_counts[status.value] = len(self.list_tasks_by_status(status))

        return {
            "active_tasks": len(self._active_tasks),
            "session_tasks": len(self._session_tasks),
            "status_counts": status_counts,
            "scenarios": self.scenario_registry.count(),
        }

    # ==================== 工具方法 ====================

    def _cleanup_completed_tasks(self) -> int:
        """清理已完成的任务"""
        completed_ids = [
            task_id for task_id, ts in self._active_tasks.items()
            if ts.state.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED)
        ]

        for task_id in completed_ids:
            task_session = self._active_tasks.pop(task_id)
            if task_session.state.session_id:
                self._session_tasks.pop(task_session.state.session_id, None)

        if completed_ids:
            logger.info(f"Cleaned up {len(completed_ids)} completed tasks")

        return len(completed_ids)