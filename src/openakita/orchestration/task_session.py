"""
TaskSession - 任务会话

管理单个任务实例的生命周期、步骤调度和上下文传递。

关键设计:
- 每个步骤的 SubAgent 以独立进程运行
- 维护独立的对话历史快照
- 支持步骤间上下文自动注入
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .messages import StepRequest, StepResponse, create_step_request
from .models import (
    ScenarioDefinition,
    StepDefinition,
    StepSession,
    StepStatus,
    TaskState,
    TaskStatus,
)
from .subagent_manager import SubAgentManager

logger = logging.getLogger(__name__)


@dataclass
class TaskSessionConfig:
    """任务会话配置"""

    auto_start_next_step: bool = True  # 确认后自动开始下一步
    enable_edit_mode: bool = True  # 启用编辑模式
    context_injection_enabled: bool = True  # 启用上下文注入


class TaskSession:
    """
    任务会话

    管理任务的生命周期、步骤调度和上下文传递。

    核心职责:
    - 步骤会话管理
    - 消息路由到 SubAgent
    - 上下文传递与存储
    - 状态管理
    """

    def __init__(
        self,
        state: TaskState,
        scenario: ScenarioDefinition,
        sub_agent_manager: SubAgentManager,
        config: TaskSessionConfig | None = None,
    ):
        """
        初始化任务会话

        Args:
            state: 任务状态
            scenario: 场景定义
            sub_agent_manager: SubAgent 管理器
            config: 会话配置
        """
        self.state = state
        self.scenario = scenario
        self._sub_agent_manager = sub_agent_manager
        self._config = config or TaskSessionConfig()

        # 步骤会话映射
        self.step_sessions: dict[str, StepSession] = {}

        # 当前模式: "step" 或 "free"
        self.mode: str = "step"

        # 步骤间上下文
        self.context: dict[str, Any] = {}

        # 初始化步骤会话
        self._init_step_sessions()

    def _init_step_sessions(self) -> None:
        """初始化所有步骤会话"""
        for step_def in self.scenario.steps:
            self.step_sessions[step_def.step_id] = StepSession(step_id=step_def.step_id)
            # 存储步骤配置到 output 字段（临时）
            self.step_sessions[step_def.step_id].output = {"step_def": step_def}

        # 设置总步骤数
        self.state.total_steps = len(self.scenario.steps)

    # ==================== 生命周期 ====================

    async def start(self) -> None:
        """启动任务"""
        if self.state.status != TaskStatus.PENDING:
            logger.warning(f"Task {self.state.task_id} already started")
            return

        logger.info(f"Starting task {self.state.task_id}")
        self.state.start()

        # 获取第一个步骤
        if self.scenario.steps:
            first_step = self.scenario.steps[0]
            self.state.current_step_id = first_step.step_id
            logger.info(f"Task {self.state.task_id}: first step is {first_step.step_id}, requires_confirmation={first_step.requires_confirmation}")

            # 启动第一个 SubAgent
            await self._start_step_agent(first_step.step_id)

            # 如果步骤不需要确认，立即执行
            if not first_step.requires_confirmation:
                logger.info(f"Task {self.state.task_id}: executing step {first_step.step_id}")
                await self._execute_step(first_step.step_id)
            else:
                logger.info(f"Task {self.state.task_id}: step {first_step.step_id} requires confirmation, waiting")

        logger.info(f"Task {self.state.task_id} started")

    async def _execute_step(self, step_id: str) -> None:
        """执行步骤"""
        step_def = self._get_step_definition(step_id)
        if not step_def:
            raise ValueError(f"Step definition not found: {step_id}")

        # 使用初始消息或系统提示词作为输入
        message = self.state.initial_message or "请执行任务"

        # 构建系统提示词
        system_prompt = self._build_system_prompt(step_def)

        # 创建步骤请求
        request = create_step_request(
            step_id=step_id,
            task_id=self.state.task_id,
            message=message,
            context=self.context.copy() if self._config.context_injection_enabled else {},
            system_prompt_override=system_prompt,
        )

        # 更新步骤状态
        step_session = self.step_sessions.get(step_id)
        if step_session and step_session.status == StepStatus.PENDING:
            step_session.start()

        # 发送请求
        response = await self._sub_agent_manager.dispatch_request(step_id, request)

        # 处理响应
        if response.success:
            if step_session:
                step_session.add_message("assistant", response.output or "")

            # 检查是否需要确认
            if response.requires_confirmation:
                step_session.wait_for_user()
                self.state.wait_for_user()
            else:
                # 自动完成步骤
                await self._complete_step(step_id, response.output_data or {"output": response.output})
        else:
            if step_session:
                step_session.fail(response.error or "Unknown error")
            logger.error(f"Step {step_id} failed: {response.error}")

    async def cancel(self) -> None:
        """取消任务"""
        if self.state.status == TaskStatus.COMPLETED:
            logger.warning(f"Task {self.state.task_id} already completed")
            return

        self.state.cancel()

        # 销毁所有 SubAgent
        for step_id in list(self.step_sessions.keys()):
            await self._sub_agent_manager.destroy_sub_agent(step_id)

        logger.info(f"Task {self.state.task_id} cancelled")

    async def complete(self, output: dict[str, Any] | None = None) -> None:
        """完成任务"""
        self.state.complete(output)

        # 销毁所有 SubAgent
        for step_id in list(self.step_sessions.keys()):
            await self._sub_agent_manager.destroy_sub_agent(step_id)

        logger.info(f"Task {self.state.task_id} completed")

    # ==================== 步骤调度 ====================

    async def dispatch_step(self, message: str) -> str:
        """
        向当前步骤发送消息

        Args:
            message: 用户消息

        Returns:
            响应内容
        """
        step_id = self.state.current_step_id
        if not step_id:
            raise ValueError("No current step")

        return await self.dispatch_step_to(step_id, message)

    async def dispatch_step_to(self, step_id: str, message: str) -> str:
        """
        向指定步骤发送消息

        Args:
            step_id: 步骤 ID
            message: 用户消息

        Returns:
            响应内容
        """
        # 获取或创建步骤会话
        step_session = self.step_sessions.get(step_id)
        if not step_session:
            raise ValueError(f"Step session not found: {step_id}")

        # 获取步骤定义
        step_def = self._get_step_definition(step_id)
        if not step_def:
            raise ValueError(f"Step definition not found: {step_id}")

        # 确保 SubAgent 已启动
        sub_agent_id = self._sub_agent_manager.get_sub_agent(step_id)
        if not sub_agent_id:
            await self._start_step_agent(step_id)

        # 构建系统提示词（注入上下文）
        system_prompt = self._build_system_prompt(step_def)

        # 创建步骤请求
        request = create_step_request(
            step_id=step_id,
            task_id=self.state.task_id,
            message=message,
            context=self.context.copy() if self._config.context_injection_enabled else {},
            system_prompt_override=system_prompt,
        )

        # 更新步骤状态
        if step_session.status == StepStatus.PENDING:
            step_session.start()

        # 添加用户消息到历史
        step_session.add_message("user", message)

        # 发送请求
        response = await self._sub_agent_manager.dispatch_request(step_id, request)

        # 处理响应
        if response.success:
            step_session.add_message("assistant", response.output or "")

            # 检查是否需要确认
            if response.requires_confirmation:
                step_session.wait_for_user()
                self.state.wait_for_user()
            else:
                # 自动完成步骤
                await self._complete_step(step_id, response.output_data or {"output": response.output})

            return response.output or ""
        else:
            step_session.fail(response.error or "Unknown error")
            return f"步骤执行失败: {response.error}"

    async def confirm_step(self, step_id: str, edited_output: dict[str, Any] | None = None) -> bool:
        """
        确认步骤输出

        Args:
            step_id: 步骤 ID
            edited_output: 编辑后的输出（可选）

        Returns:
            是否成功
        """
        step_session = self.step_sessions.get(step_id)
        if not step_session:
            return False

        if step_session.status != StepStatus.WAITING_USER:
            logger.warning(f"Step {step_id} is not waiting for confirmation")
            return False

        # 使用编辑后的输出或原始输出
        output = edited_output or step_session.output

        # 完成步骤
        await self._complete_step(step_id, output)

        return True

    async def _complete_step(self, step_id: str, output: dict[str, Any]) -> None:
        """完成步骤"""
        step_session = self.step_sessions.get(step_id)
        step_def = self._get_step_definition(step_id)

        if step_session:
            step_session.complete(output)

        # 更新上下文
        if step_def and step_def.output_key:
            self.context[step_def.output_key] = output
            self.state.context[step_def.output_key] = output

        # 更新进度
        self.state.completed_steps += 1

        # 检查是否有下一步
        next_step = self._get_next_step(step_id)
        if next_step:
            self.state.current_step_id = next_step.step_id
            self.state.status = TaskStatus.RUNNING

            # 自动启动下一步的 SubAgent 并执行
            if self._config.auto_start_next_step:
                await self._start_step_agent(next_step.step_id)
                # 如果下一步不需要确认，立即执行
                if not next_step.requires_confirmation:
                    await self._execute_step(next_step.step_id)
        else:
            # 任务完成
            await self.complete(output)

        logger.info(f"Step {step_id} completed in task {self.state.task_id}")

    async def _start_step_agent(self, step_id: str) -> None:
        """启动步骤的 SubAgent"""
        step_def = self._get_step_definition(step_id)
        if not step_def:
            raise ValueError(f"Step definition not found: {step_id}")

        # 从步骤定义创建 SubAgent 配置
        from .config_loader import SubAgentConfigLoader
        loader = SubAgentConfigLoader()
        config = loader.create_step_config(step_def)

        # 启动 SubAgent
        await self._sub_agent_manager.spawn_sub_agent(step_id, config)

    # ==================== 步骤切换 ====================

    async def switch_to_step(self, step_id: str) -> bool:
        """
        切换到指定步骤

        Args:
            step_id: 目标步骤 ID

        Returns:
            是否成功
        """
        # 检查步骤是否存在
        step_def = self._get_step_definition(step_id)
        if not step_def:
            logger.warning(f"Step {step_id} not found")
            return False

        # 检查依赖
        if not self._check_step_dependencies(step_id):
            logger.warning(f"Step {step_id} dependencies not satisfied")
            return False

        # 更新当前步骤
        self.state.current_step_id = step_id

        # 确保 SubAgent 已启动
        sub_agent_id = self._sub_agent_manager.get_sub_agent(step_id)
        if not sub_agent_id:
            await self._start_step_agent(step_id)

        logger.info(f"Switched to step {step_id} in task {self.state.task_id}")
        return True

    def _check_step_dependencies(self, step_id: str) -> bool:
        """检查步骤依赖是否满足"""
        step_def = self._get_step_definition(step_id)
        if not step_def:
            return False

        for dep_id in step_def.dependencies:
            dep_session = self.step_sessions.get(dep_id)
            if not dep_session or dep_session.status != StepStatus.COMPLETED:
                return False

        return True

    # ==================== 模式切换 ====================

    def switch_to_step_mode(self) -> None:
        """切换到步骤模式"""
        self.mode = "step"
        logger.debug(f"Task {self.state.task_id} switched to step mode")

    def switch_to_free_mode(self) -> None:
        """切换到自由模式"""
        self.mode = "free"
        logger.debug(f"Task {self.state.task_id} switched to free mode")

    # ==================== 辅助方法 ====================

    def _get_step_definition(self, step_id: str) -> StepDefinition | None:
        """获取步骤定义"""
        return self.scenario.get_step(step_id)

    def _get_next_step(self, current_step_id: str) -> StepDefinition | None:
        """获取下一个步骤"""
        current_index = self.scenario.get_step_index(current_step_id)
        if current_index < 0:
            return None

        next_index = current_index + 1
        if next_index < len(self.scenario.steps):
            return self.scenario.steps[next_index]

        return None

    def _build_system_prompt(self, step_def: StepDefinition) -> str:
        """构建系统提示词"""
        prompt = step_def.system_prompt

        # 注入上下文
        if self._config.context_injection_enabled and self.context:
            context_str = self._format_context()
            if context_str:
                prompt = f"{prompt}\n\n## 前置步骤输出\n{context_str}"

        return prompt

    def _format_context(self) -> str:
        """格式化上下文用于提示词"""
        lines = []
        for key, value in self.context.items():
            if value:
                lines.append(f"### {key}")
                if isinstance(value, dict):
                    # 格式化字典
                    for k, v in value.items():
                        lines.append(f"- {k}: {v}")
                else:
                    lines.append(str(value))
                lines.append("")
        return "\n".join(lines)

    # ==================== 查询 ====================

    def get_current_step(self) -> StepSession | None:
        """获取当前步骤会话"""
        if not self.state.current_step_id:
            return None
        return self.step_sessions.get(self.state.current_step_id)

    def get_progress(self) -> tuple[int, int]:
        """获取进度"""
        return self.state.get_progress()

    def get_progress_percent(self) -> float:
        """获取进度百分比"""
        return self.state.get_progress_percent()

    def get_step_output(self, step_id: str) -> dict[str, Any] | None:
        """获取步骤输出"""
        step_session = self.step_sessions.get(step_id)
        if step_session:
            return step_session.output
        return None

    def is_step_completed(self, step_id: str) -> bool:
        """检查步骤是否完成"""
        step_session = self.step_sessions.get(step_id)
        return step_session is not None and step_session.status == StepStatus.COMPLETED

    def to_dict(self) -> dict[str, Any]:
        """导出为字典"""
        return {
            "state": self.state.to_dict(),
            "scenario_id": self.scenario.scenario_id,
            "mode": self.mode,
            "context": self.context,
            "step_sessions": {
                sid: ss.to_dict() for sid, ss in self.step_sessions.items()
            },
        }