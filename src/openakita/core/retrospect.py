"""
Retrospect Manager - 任务复盘和思维链摘要

从 agent.py 提取的复盘功能，包括：
- 任务复盘分析
- 思维链摘要构建
- 后台复盘执行
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openakita.core.task_monitor import TaskMonitor
    from openakita.llm.brain import Brain
    from openakita.memory import MemoryManager

logger = logging.getLogger(__name__)


class RetrospectManager:
    """
    复盘管理器 - 处理任务复盘和思维链摘要

    职责:
    - 构建思维链摘要
    - 执行任务复盘分析
    - 后台复盘执行和存储
    """

    def __init__(
        self,
        brain: Brain,
        memory_manager: MemoryManager,
    ):
        """
        初始化复盘管理器

        Args:
            brain: Brain 实例，用于 LLM 调用
            memory_manager: 记忆管理器，用于保存复盘结果
        """
        self.brain = brain
        self.memory_manager = memory_manager

    def build_chain_summary(self, react_trace: list[dict]) -> list[dict] | None:
        """
        从 ReAct trace 构建思维链摘要（用于 IM 消息 metadata）。

        每个迭代生成一个摘要项，包含 thinking 预览和工具调用列表。

        Args:
            react_trace: ReAct 执行轨迹

        Returns:
            摘要列表，如果输入为空则返回 None
        """
        if not react_trace:
            return None
        return [
            {
                "iteration": t.get("iteration", 0),
                "thinking_preview": (t.get("thinking") or "")[:150],
                "thinking_duration_ms": t.get("thinking_duration_ms", 0),
                "tools": [
                    {
                        "name": tc.get("name", ""),
                        "input_preview": str(tc.get("input_preview", ""))[:80],
                    }
                    for tc in t.get("tool_calls", [])
                ],
                **({"context_compressed": t["context_compressed"]} if t.get("context_compressed") else {}),
            }
            for t in react_trace
        ]

    async def do_task_retrospect(self, task_monitor: TaskMonitor) -> str:
        """
        执行任务复盘分析

        当任务耗时过长时，让 LLM 分析原因，找出可以改进的地方。

        Args:
            task_monitor: 任务监控器

        Returns:
            复盘分析结果
        """
        from .response_handler import strip_thinking_tags
        from .task_monitor import RETROSPECT_PROMPT

        try:
            context = task_monitor.get_retrospect_context()
            prompt = RETROSPECT_PROMPT.format(context=context)

            # 使用 Brain 进行复盘分析（独立上下文）
            response = await self.brain.think(
                prompt=prompt,
                system="你是一个任务执行分析专家。请简洁地分析任务执行情况，找出耗时原因和改进建议。",
            )

            result = strip_thinking_tags(response.content).strip() if response.content else ""

            # 保存复盘结果到监控器
            task_monitor.metrics.retrospect_result = result

            # 如果发现明显的重复错误模式，记录到记忆中
            if "重复" in result or "无效" in result or "弯路" in result:
                try:
                    from openakita.memory.types import Memory, MemoryPriority, MemoryType

                    memory = Memory(
                        type=MemoryType.ERROR,
                        priority=MemoryPriority.LONG_TERM,
                        content=f"任务执行复盘发现问题：{result}",
                        source="retrospect",
                        importance_score=0.7,
                    )
                    self.memory_manager.add_memory(memory)
                except Exception as e:
                    logger.warning(f"Failed to save retrospect to memory: {e}")

            return result

        except Exception as e:
            logger.warning(f"Task retrospect failed: {e}")
            return ""

    async def do_task_retrospect_background(
        self, task_monitor: TaskMonitor, session_id: str
    ) -> None:
        """
        后台执行任务复盘分析

        这个方法在后台异步执行，不阻塞主响应。
        复盘结果会保存到文件，供每日自检系统读取汇总。

        Args:
            task_monitor: 任务监控器
            session_id: 会话 ID
        """
        try:
            # 执行复盘分析
            retrospect_result = await self.do_task_retrospect(task_monitor)

            if not retrospect_result:
                return

            # 保存到复盘存储
            from .task_monitor import RetrospectRecord, get_retrospect_storage

            record = RetrospectRecord(
                task_id=task_monitor.metrics.task_id,
                session_id=session_id,
                description=task_monitor.metrics.description,
                duration_seconds=task_monitor.metrics.total_duration_seconds,
                iterations=task_monitor.metrics.total_iterations,
                model_switched=task_monitor.metrics.model_switched,
                initial_model=task_monitor.metrics.initial_model,
                final_model=task_monitor.metrics.final_model,
                retrospect_result=retrospect_result,
            )

            storage = get_retrospect_storage()
            storage.save(record)

            logger.info(f"[Session:{session_id}] Retrospect saved: {task_monitor.metrics.task_id}")

        except Exception as e:
            logger.error(f"[Session:{session_id}] Background retrospect failed: {e}")
