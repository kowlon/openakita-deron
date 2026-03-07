"""
SubAgentWorker - 无状态步骤执行器

根据 JIT (Just-In-Time) 配置注入设计理念，Worker 不持有任务状态。
Orchestrator 通过 SubAgentPayload 动态注入配置和上下文，
Worker 执行完毕后返回 StepResult，可被其他任务复用。

设计说明:
- 无状态设计：Worker 不保存任务历史
- JIT 配置注入：每次执行时接收完整配置
- 可复用：执行完毕后可处理下一个步骤
- 资源隔离：每次执行创建独立的 Agent 实例
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from ..core.agent import Agent
from .models import SubAgentConfig, TaskStep

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================


@dataclass
class ArtifactReference:
    """
    制品引用

    用于引用大数据对象，避免直接传递内容。
    支持文件、图片、代码等类型的引用。
    """

    id: str  # 制品唯一 ID
    type: str  # 类型: "file" | "image" | "code" | "data"
    uri: str  # URI: "file://..." 或 "db://..."
    summary: str  # 简短摘要
    size: int | None = None  # 大小（字节）
    mime_type: str | None = None  # MIME 类型

    def to_dict(self) -> dict:
        """序列化为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ArtifactReference":
        """从字典反序列化"""
        return cls(**data)


@dataclass
class SubAgentPayload:
    """
    SubAgent 调用载荷

    包含执行步骤所需的全部上下文信息。
    由 Orchestrator 组装并传递给 Worker。
    """

    # 标识
    task_id: str  # 任务 ID
    step_id: str  # 步骤 ID
    step_index: int  # 步骤索引

    # 上下文
    previous_steps_summary: str = ""  # 前序步骤摘要
    task_context: dict[str, Any] = field(default_factory=dict)  # 任务级变量
    history_messages: list[dict] = field(default_factory=list)  # 聊天历史
    artifacts: list[ArtifactReference] = field(default_factory=list)  # 制品引用

    # 配置
    agent_config: SubAgentConfig | None = None  # 动态配置

    # 用户输入
    user_input: str = ""  # 用户输入文本

    # 执行参数
    timeout: float = 300.0  # 超时时间（秒）

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "task_id": self.task_id,
            "step_id": self.step_id,
            "step_index": self.step_index,
            "previous_steps_summary": self.previous_steps_summary,
            "task_context": self.task_context,
            "history_messages": self.history_messages,
            "artifacts": [a.to_dict() for a in self.artifacts],
            "agent_config": self.agent_config.to_dict() if self.agent_config else None,
            "user_input": self.user_input,
            "timeout": self.timeout,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SubAgentPayload":
        """从字典反序列化"""
        artifacts = [
            ArtifactReference.from_dict(a)
            for a in data.get("artifacts", [])
        ]
        agent_config = None
        if data.get("agent_config"):
            agent_config = SubAgentConfig.from_dict(data["agent_config"])

        return cls(
            task_id=data["task_id"],
            step_id=data["step_id"],
            step_index=data["step_index"],
            previous_steps_summary=data.get("previous_steps_summary", ""),
            task_context=data.get("task_context", {}),
            history_messages=data.get("history_messages", []),
            artifacts=artifacts,
            agent_config=agent_config,
            user_input=data.get("user_input", ""),
            timeout=data.get("timeout", 300.0),
        )


@dataclass
class StepResult:
    """
    步骤执行结果

    Worker 执行步骤后返回的结果对象。
    """

    # 标识
    task_id: str  # 任务 ID
    step_id: str  # 步骤 ID

    # 状态
    success: bool  # 是否成功

    # 结果
    result: dict[str, Any] = field(default_factory=dict)  # 执行结果
    error: str | None = None  # 错误信息

    # 制品
    artifacts: list[dict] = field(default_factory=list)  # 新产生的制品

    # 建议
    suggested_next_action: str | None = None  # 下一步建议

    # 显示数据
    display_view: dict[str, Any] = field(default_factory=dict)  # 前端渲染数据

    # 元数据
    duration_ms: float | None = None  # 执行耗时（毫秒）
    tokens_used: int | None = None  # 使用的 token 数

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "task_id": self.task_id,
            "step_id": self.step_id,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "artifacts": self.artifacts,
            "suggested_next_action": self.suggested_next_action,
            "display_view": self.display_view,
            "duration_ms": self.duration_ms,
            "tokens_used": self.tokens_used,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StepResult":
        """从字典反序列化"""
        return cls(
            task_id=data["task_id"],
            step_id=data["step_id"],
            success=data["success"],
            result=data.get("result", {}),
            error=data.get("error"),
            artifacts=data.get("artifacts", []),
            suggested_next_action=data.get("suggested_next_action"),
            display_view=data.get("display_view", {}),
            duration_ms=data.get("duration_ms"),
            tokens_used=data.get("tokens_used"),
        )

    @classmethod
    def success_result(
        cls,
        task_id: str,
        step_id: str,
        result: dict[str, Any],
        artifacts: list[dict] | None = None,
        duration_ms: float | None = None,
    ) -> "StepResult":
        """创建成功结果"""
        return cls(
            task_id=task_id,
            step_id=step_id,
            success=True,
            result=result,
            artifacts=artifacts or [],
            duration_ms=duration_ms,
        )

    @classmethod
    def error_result(
        cls,
        task_id: str,
        step_id: str,
        error: str,
    ) -> "StepResult":
        """创建错误结果"""
        return cls(
            task_id=task_id,
            step_id=step_id,
            success=False,
            error=error,
        )


# ==================== SubAgentWorker ====================


class SubAgentWorker:
    """
    无状态步骤执行器

    负责执行单个步骤，不持有任务状态。
    通过 JIT 配置注入获取执行所需的所有信息。

    特性:
    - JIT 配置注入：每次执行时接收完整配置
    - 无状态设计：不保存任务历史
    - 可复用：执行完毕后可处理下一个步骤
    - 资源隔离：每次执行创建独立的 Agent 实例
    """

    def __init__(self, worker_id: str = "worker"):
        """
        初始化 Worker

        Args:
            worker_id: Worker 唯一标识
        """
        self.worker_id = worker_id

        # 运行状态
        self._running = False
        self._current_task_id: str | None = None

        # 统计
        self._tasks_completed = 0
        self._tasks_failed = 0

    @property
    def is_busy(self) -> bool:
        """是否正在执行任务"""
        return self._running and self._current_task_id is not None

    # ==================== 生命周期 ====================

    async def start(self) -> None:
        """启动 Worker"""
        if self._running:
            return

        self._running = True
        logger.info(f"SubAgentWorker started: {self.worker_id}")

    async def stop(self) -> None:
        """停止 Worker"""
        if not self._running:
            return

        self._running = False
        logger.info(f"SubAgentWorker stopped: {self.worker_id}")

    # ==================== JIT 配置注入 ====================

    def _build_system_prompt(
        self,
        agent_config: SubAgentConfig,
        payload: SubAgentPayload,
    ) -> str:
        """
        构建系统提示词

        将 SubAgentConfig 与执行上下文组合成完整的系统提示词。

        Args:
            agent_config: SubAgent 配置
            payload: 执行载荷

        Returns:
            完整的系统提示词
        """
        parts = []

        # 1. 基础角色定义
        parts.append(f"# 角色定义\n你是 {agent_config.name}，{agent_config.role}")
        parts.append("")

        # 2. 原始系统提示词
        if agent_config.system_prompt:
            parts.append("# 核心指令")
            parts.append(agent_config.system_prompt)
            parts.append("")

        # 3. 任务上下文
        parts.append("# 当前任务")
        parts.append(f"- 任务 ID: {payload.task_id}")
        parts.append(f"- 步骤索引: {payload.step_index}")

        if payload.previous_steps_summary:
            parts.append("")
            parts.append("## 前序步骤摘要")
            parts.append(payload.previous_steps_summary)

        if payload.task_context:
            parts.append("")
            parts.append("## 任务变量")
            for key, value in payload.task_context.items():
                parts.append(f"- {key}: {value}")

        # 4. 制品引用
        if payload.artifacts:
            parts.append("")
            parts.append("## 可用制品")
            for artifact in payload.artifacts:
                parts.append(f"- [{artifact.type}] {artifact.summary} ({artifact.uri})")

        return "\n".join(parts)

    def _build_chat_messages(
        self,
        payload: SubAgentPayload,
        system_prompt: str,
    ) -> list[dict]:
        """
        构建聊天消息列表

        将历史消息与新输入组合。

        Args:
            payload: 执行载荷
            system_prompt: 系统提示词

        Returns:
            聊天消息列表
        """
        messages = []

        # 系统消息
        messages.append({
            "role": "system",
            "content": system_prompt,
        })

        # 历史消息（如果有）
        for msg in payload.history_messages:
            # 过滤掉旧的 system 消息，使用新的
            if msg.get("role") != "system":
                messages.append(msg)

        # 用户输入
        if payload.user_input:
            messages.append({
                "role": "user",
                "content": payload.user_input,
            })

        return messages

    # ==================== 执行 ====================

    async def execute(
        self,
        payload: SubAgentPayload,
    ) -> StepResult:
        """
        执行步骤

        这是 Worker 的核心方法，接收载荷并返回结果。

        Args:
            payload: 执行载荷

        Returns:
            StepResult 执行结果
        """
        if not self._running:
            await self.start()

        if self.is_busy:
            return StepResult.error_result(
                task_id=payload.task_id,
                step_id=payload.step_id,
                error="Worker is busy with another task",
            )

        self._current_task_id = payload.task_id
        start_time = time.time()

        try:
            logger.info(
                f"Worker {self.worker_id}: executing step "
                f"{payload.step_id} of task {payload.task_id}"
            )

            # 验证配置
            if not payload.agent_config:
                raise ValueError("Missing agent_config in payload")

            # 执行步骤
            result = await self._execute_step(payload)

            # 更新统计
            self._tasks_completed += 1

            duration_ms = (time.time() - start_time) * 1000
            result.duration_ms = duration_ms

            logger.info(
                f"Worker {self.worker_id}: step {payload.step_id} completed "
                f"(success={result.success}, duration={duration_ms:.0f}ms)"
            )

            return result

        except asyncio.TimeoutError:
            logger.error(
                f"Worker {self.worker_id}: step {payload.step_id} timeout"
            )
            self._tasks_failed += 1
            return StepResult.error_result(
                task_id=payload.task_id,
                step_id=payload.step_id,
                error=f"Execution timeout after {payload.timeout}s",
            )

        except Exception as e:
            logger.error(
                f"Worker {self.worker_id}: step {payload.step_id} failed: {e}",
                exc_info=True,
            )
            self._tasks_failed += 1
            return StepResult.error_result(
                task_id=payload.task_id,
                step_id=payload.step_id,
                error=str(e),
            )

        finally:
            self._current_task_id = None

    async def _execute_step(self, payload: SubAgentPayload) -> StepResult:
        """
        内部执行步骤

        创建 Agent 实例并执行。

        Args:
            payload: 执行载荷

        Returns:
            StepResult 执行结果
        """
        agent_config = payload.agent_config

        # 构建系统提示词
        system_prompt = self._build_system_prompt(agent_config, payload)

        # 构建消息
        messages = self._build_chat_messages(payload, system_prompt)

        # 创建 Agent 实例
        agent = Agent(name=agent_config.name)

        try:
            # 初始化 Agent
            await agent.initialize(start_scheduler=False)

            # 执行对话
            # 使用超时保护
            response = await asyncio.wait_for(
                agent.chat_with_session(
                    message=payload.user_input,
                    session_messages=messages,
                    session_id=f"task-{payload.task_id}-step-{payload.step_id}",
                ),
                timeout=payload.timeout,
            )

            # 构建结果
            return StepResult.success_result(
                task_id=payload.task_id,
                step_id=payload.step_id,
                result={
                    "response": response,
                    "message": "Step executed successfully",
                },
                artifacts=self._extract_artifacts(response),
            )

        finally:
            # 清理资源
            await agent.shutdown()

    async def execute_stream(
        self,
        payload: SubAgentPayload,
    ) -> AsyncIterator[dict]:
        """
        流式执行步骤，yield 事件

        使用 Agent.chat_with_session_stream() 实现流式输出。

        Args:
            payload: 执行载荷

        Yields:
            流式事件字典
        """
        if not self._running:
            await self.start()

        if self.is_busy:
            yield {"type": "error", "message": "Worker is busy with another task"}
            return

        self._current_task_id = payload.task_id

        agent_config = payload.agent_config
        if not agent_config:
            yield {"type": "error", "message": "Missing agent_config in payload"}
            self._current_task_id = None
            return

        # 构建系统提示词和消息
        system_prompt = self._build_system_prompt(agent_config, payload)
        messages = self._build_chat_messages(payload, system_prompt)

        # 创建 Agent 实例
        agent = Agent(name=agent_config.name)

        try:
            # 初始化 Agent
            await agent.initialize(start_scheduler=False)

            # 流式执行
            async for event in agent.chat_with_session_stream(
                message=payload.user_input,
                session_messages=messages,
                session_id=f"task-{payload.task_id}-step-{payload.step_id}",
            ):
                yield event

            # 发送步骤完成事件
            yield {
                "type": "step_complete",
                "task_id": payload.task_id,
                "step_id": payload.step_id,
            }

        except Exception as e:
            logger.error(f"Stream execution error: {e}", exc_info=True)
            yield {"type": "error", "message": str(e)}

        finally:
            # 清理资源
            await agent.shutdown()
            self._current_task_id = None

    def _extract_artifacts(self, response: Any) -> list[dict]:
        """
        从响应中提取制品

        Args:
            response: Agent 响应

        Returns:
            制品列表
        """
        artifacts = []

        # 简单实现：从响应中提取文件引用
        if isinstance(response, str):
            # TODO: 实现更智能的制品提取
            pass
        elif isinstance(response, dict):
            if "files" in response:
                for file_path in response["files"]:
                    artifacts.append({
                        "id": f"artifact-{len(artifacts)}",
                        "type": "file",
                        "uri": f"file://{file_path}",
                        "summary": f"Generated file: {file_path}",
                    })

        return artifacts

    # ==================== 便捷方法 ====================

    async def execute_step_from_command(
        self,
        step: TaskStep,
        task_context: dict[str, Any] | None = None,
        user_input: str = "",
    ) -> StepResult:
        """
        从 TaskStep 执行步骤

        便捷方法，将 TaskStep 转换为 SubAgentPayload 并执行。

        Args:
            step: 任务步骤
            task_context: 任务上下文
            user_input: 用户输入

        Returns:
            StepResult 执行结果
        """
        payload = SubAgentPayload(
            task_id=step.task_id,
            step_id=step.id,
            step_index=step.index,
            agent_config=step.sub_agent_config,
            task_context=task_context or {},
            user_input=user_input,
            previous_steps_summary="",  # TODO: 从存储加载
        )

        return await self.execute(payload)

    # ==================== 统计 ====================

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "worker_id": self.worker_id,
            "running": self._running,
            "busy": self.is_busy,
            "current_task_id": self._current_task_id,
            "tasks_completed": self._tasks_completed,
            "tasks_failed": self._tasks_failed,
        }


# ==================== Worker 池 ====================


class WorkerPool:
    """
    Worker 池

    管理多个 Worker 实例，支持负载均衡。
    """

    def __init__(self, pool_size: int = 3):
        """
        初始化 Worker 池

        Args:
            pool_size: Worker 数量
        """
        self.pool_size = pool_size
        self._workers: list[SubAgentWorker] = []
        self._current_index = 0

    async def start(self) -> None:
        """启动所有 Worker"""
        for i in range(self.pool_size):
            worker = SubAgentWorker(worker_id=f"worker-{i}")
            await worker.start()
            self._workers.append(worker)

        logger.info(f"WorkerPool started with {self.pool_size} workers")

    async def stop(self) -> None:
        """停止所有 Worker"""
        for worker in self._workers:
            await worker.stop()

        self._workers.clear()
        logger.info("WorkerPool stopped")

    def get_available_worker(self) -> SubAgentWorker | None:
        """
        获取可用 Worker

        使用轮询策略选择 Worker。

        Returns:
            可用的 Worker，如果没有则返回 None
        """
        # 尝试找到空闲的 Worker
        for _ in range(self.pool_size):
            worker = self._workers[self._current_index]
            self._current_index = (self._current_index + 1) % self.pool_size

            if not worker.is_busy:
                return worker

        return None

    async def execute(self, payload: SubAgentPayload) -> StepResult:
        """
        使用池中的 Worker 执行步骤

        如果所有 Worker 都忙，则等待。

        Args:
            payload: 执行载荷

        Returns:
            StepResult 执行结果
        """
        worker = self.get_available_worker()
        if worker:
            return await worker.execute(payload)

        # 所有 Worker 都忙，等待第一个可用的
        logger.warning("All workers busy, waiting...")
        await asyncio.sleep(0.1)

        worker = self.get_available_worker()
        if worker:
            return await worker.execute(payload)

        # 超时错误
        return StepResult.error_result(
            task_id=payload.task_id,
            step_id=payload.step_id,
            error="No available worker",
        )

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "pool_size": self.pool_size,
            "workers": [w.get_stats() for w in self._workers],
        }