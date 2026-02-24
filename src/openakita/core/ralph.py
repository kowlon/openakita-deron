"""
Ralph Wiggum 循环引擎

参考来源:
- https://github.com/anthropics/claude-code/tree/main/plugins/ralph-wiggum
- https://claytonfarr.github.io/ralph-playbook/

核心理念:
- 任务未完成，绝不终止
- 通过文件持久化状态
- 每次迭代 fresh context
- 通过 backpressure（测试验证）强制自我修正
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import settings
from ..core.agent_state import TaskState, TaskStatus

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """任务执行结果"""

    success: bool
    data: Any = None
    error: str | None = None
    iterations: int = 0
    duration_seconds: float = 0


class StopHook:
    """
    Stop Hook - 拦截退出尝试

    当 Agent 试图退出但任务未完成时，拦截并继续
    """

    def __init__(self, task: TaskState):
        self.task = task
        self.intercepted_count = 0

    def should_stop(self) -> bool:
        """检查是否应该停止"""
        if self.task.status == TaskStatus.COMPLETED:
            return True

        if self.task.status in (TaskStatus.FAILED, TaskStatus.CANCELLED):
            logger.warning(f"Task {self.task.task_id} is in terminal state: {self.task.status}")
            return True

        return False

    def intercept(self) -> bool:
        """
        拦截退出尝试

        Returns:
            True 如果拦截成功（应继续执行），False 如果应该停止
        """
        if self.should_stop():
            return False

        self.intercepted_count += 1
        logger.info(
            f"Stop hook intercepted exit attempt #{self.intercepted_count} for task {self.task.task_id}"
        )
        return True


class RalphLoop:
    """
    Ralph Wiggum 循环引擎

    核心循环逻辑:
    while not task.is_complete and iteration < max_iterations:
        1. 从 MEMORY.md 加载状态
        2. 执行一次迭代
        3. 检查结果
        4. 如果失败，分析原因并调整策略
        5. 保存进度到 MEMORY.md
        6. 继续下一次迭代
    """

    def __init__(
        self,
        max_iterations: int = 100,
        memory_path: Path | None = None,
        on_iteration: Callable[[int, TaskState], None] | None = None,
        on_error: Callable[[str, TaskState], None] | None = None,
    ):
        self.max_iterations = max_iterations
        self.memory_path = memory_path or settings.memory_path
        self.on_iteration = on_iteration
        self.on_error = on_error

        self._current_task: TaskState | None = None
        self._iteration = 0
        self._stop_hook: StopHook | None = None

    async def run(
        self,
        task: TaskState,
        execute_fn: Callable[[TaskState], Any],
    ) -> TaskResult:
        """
        运行 Ralph 循环

        Args:
            task: 要执行的任务 (TaskState)
            execute_fn: 执行函数，执行一步或整个任务。
                       如果是多步任务，函数应更新 task.status。
                       如果任务完成，应返回结果。

        Returns:
            TaskResult
        """
        self._current_task = task
        self._iteration = 0
        self._stop_hook = StopHook(task)

        start_time = datetime.now()

        logger.info(f"Ralph loop starting for task: {task.task_id}")
        logger.info(f"Max iterations: {self.max_iterations}")

        while self._iteration < self.max_iterations:
            self._iteration += 1
            task.iteration = self._iteration

            # 检查是否应该停止
            if self._stop_hook.should_stop():
                break

            # 加载进度
            await self._load_progress()

            # 通知迭代开始
            if self.on_iteration:
                self.on_iteration(self._iteration, task)

            logger.info(f"Iteration {self._iteration}/{self.max_iterations}")

            # 标记任务进行中
            if task.status == TaskStatus.IDLE:
                try:
                    task.transition(TaskStatus.REASONING)
                except ValueError:
                    pass  # 已经在其它状态

            try:
                # 执行任务（一步或全部）
                result = await execute_fn(task)

                # 检查是否应该停止（例如任务被取消或失败）
                if self._stop_hook.should_stop():
                    break

                # 如果任务已完成
                if task.status == TaskStatus.COMPLETED or result is not None:
                    if task.status != TaskStatus.COMPLETED:
                         try:
                             task.transition(TaskStatus.COMPLETED)
                         except ValueError:
                             pass
                    
                    logger.info(f"Task {task.task_id} completed successfully")
                    
                    # 保存进度
                    await self._save_progress()

                    duration = (datetime.now() - start_time).total_seconds()
                    return TaskResult(
                        success=True,
                        data=result,
                        iterations=self._iteration,
                        duration_seconds=duration,
                    )
                
                # 任务未完成，继续循环
                # 保存进度
                await self._save_progress()

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Iteration {self._iteration} failed: {error_msg}")

                # 标记失败（由 execute_fn 决定是否致命，或者在这里统一处理）
                # 这里假设异常意味着当前步骤失败，但不一定是整个任务失败
                # task.transition(TaskStatus.FAILED) # 不轻易标记失败

                # 通知错误
                if self.on_error:
                    self.on_error(error_msg, task)

                # 保存进度
                await self._save_progress()

                # 尝试拦截退出
                if not self._stop_hook.intercept():
                    break

                # 分析错误并调整策略（Placeholder）
                # await self._analyze_and_adapt(error_msg)

        # 循环结束但任务未完成
        duration = (datetime.now() - start_time).total_seconds()

        if task.status == TaskStatus.COMPLETED:
            return TaskResult(
                success=True,
                data=None, # result might be lost if not returned by execute_fn
                iterations=self._iteration,
                duration_seconds=duration,
            )
        else:
            return TaskResult(
                success=False,
                error="Max iterations reached" if task.status != TaskStatus.FAILED else "Task failed",
                iterations=self._iteration,
                duration_seconds=duration,
            )

    async def _load_progress(self) -> None:
        """从 MEMORY.md 加载进度（在线程池中执行，避免阻塞事件循环）"""
        import asyncio

        await asyncio.to_thread(self._load_progress_sync)

    def _load_progress_sync(self) -> None:
        """同步加载进度"""
        try:
            if self.memory_path.exists():
                self.memory_path.read_text(encoding="utf-8")
                logger.debug("Progress loaded from MEMORY.md")
        except Exception as e:
            logger.warning(f"Failed to load progress: {e}")

    async def _save_progress(self) -> None:
        """保存进度到 MEMORY.md（在线程池中执行，避免阻塞事件循环）"""
        import asyncio

        if not self._current_task:
            return
        await asyncio.to_thread(self._save_progress_sync)

    def _save_progress_sync(self) -> None:
        """同步保存进度"""
        if not self._current_task:
            return

        try:
            content = ""
            if self.memory_path.exists():
                content = self.memory_path.read_text(encoding="utf-8")

            task = self._current_task
            session_line = f"- **Session**: {task.session_id}\n" if task.session_id else ""
            task_info = f"""### Active Task

- **ID**: {task.task_id}
{session_line}- **描述**: {task.task_query or task.task_definition}
- **状态**: {task.status.value}
- **尝试次数**: {task.iteration}
- **最后更新**: {datetime.now().isoformat()}
"""

            if "### Active Task" in content:
                start = content.find("### Active Task")
                end = content.find("###", start + 1)
                if end == -1:
                    end = content.find("\n## ", start + 1)
                if end == -1:
                    end = len(content)
                content = content[:start] + task_info + content[end:]
            else:
                insert_pos = content.find("## Current Task Progress")
                if insert_pos != -1:
                    insert_pos = content.find("\n", insert_pos) + 1
                    content = content[:insert_pos] + "\n" + task_info + content[insert_pos:]

            self.memory_path.write_text(content, encoding="utf-8")
            logger.debug("Progress saved to MEMORY.md")

        except Exception as e:
            logger.warning(f"Failed to save progress: {e}")

    async def _analyze_and_adapt(self, error: str) -> None:
        """
        分析错误并调整策略

        这是 Ralph 模式的核心:
        - 分析失败原因
        - 搜索解决方案
        - 调整策略
        """
        logger.info("Analyzing error and adapting strategy...")

        # TODO: 实现更智能的错误分析
        # 1. 使用 Brain 分析错误
        # 2. 搜索 GitHub 找解决方案
        # 3. 如果需要新能力，安装它
        # 4. 更新执行策略

        # 暂时简单等待后重试
        import asyncio

        await asyncio.sleep(1)

    @property
    def iteration(self) -> int:
        """当前迭代次数"""
        return self._iteration

    @property
    def current_task(self) -> TaskState | None:
        """当前任务"""
        return self._current_task
