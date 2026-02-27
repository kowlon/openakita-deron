"""
进化系统集成帮助器

提供 Agent 与自我进化系统的集成支持。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ...evolution import (
    EvolutionOrchestrator,
    OrchestratorConfig,
    OutcomeLabel,
)

if TYPE_CHECKING:
    from ...core.agent import Agent

logger = logging.getLogger(__name__)


def setup_evolution_system(
    agent: "Agent",
    auto_evolve: bool = False,
    evolution_interval_hours: int = 24,
    min_traces_for_evolution: int = 10,
) -> EvolutionOrchestrator:
    """
    为 Agent 设置自我进化系统。

    这个函数初始化进化编排器，用于：
    - 收集执行追踪
    - 分析成功/失败模式
    - 生成进化提案
    - 执行技能进化

    Args:
        agent: Agent 实例
        auto_evolve: 是否自动执行进化
        evolution_interval_hours: 进化间隔（小时）
        min_traces_for_evolution: 触发进化的最小追踪数

    Returns:
        配置好的 EvolutionOrchestrator 实例
    """
    config = OrchestratorConfig(
        auto_evolve=auto_evolve,
        evolution_interval_hours=evolution_interval_hours,
        min_traces_for_evolution=min_traces_for_evolution,
    )

    orchestrator = EvolutionOrchestrator(config)

    # 尝试加载已有状态
    try:
        count = orchestrator.load()
        if count > 0:
            logger.info(f"[EvolutionSystem] Loaded {count} existing traces")
    except Exception as e:
        logger.debug(f"[EvolutionSystem] No existing traces to load: {e}")

    # 存储到 Agent
    agent.evolution_orchestrator = orchestrator

    logger.info(
        f"[EvolutionSystem] Initialized with auto_evolve={auto_evolve}, "
        f"interval={evolution_interval_hours}h, min_traces={min_traces_for_evolution}"
    )

    return orchestrator


def record_task_execution(
    agent: "Agent",
    task_id: str,
    session_id: str,
    task_description: str,
    outcome: str,
    tools_executed: list[str] | None = None,
    steps: list[dict] | None = None,
    error_summary: str | None = None,
    duration_seconds: float | None = None,
) -> str | None:
    """
    记录任务执行到进化系统。

    这是 Agent 记录执行追踪的主要入口。
    追踪数据用于后续的模式分析和进化提案生成。

    Args:
        agent: Agent 实例
        task_id: 任务 ID
        session_id: 会话 ID
        task_description: 任务描述
        outcome: 结果 (success, failure, partial)
        tools_executed: 执行的工具列表
        steps: 步骤列表
        error_summary: 错误摘要
        duration_seconds: 执行时长（秒）

    Returns:
        追踪 ID，如果进化系统未初始化则返回 None
    """
    if not hasattr(agent, "evolution_orchestrator") or agent.evolution_orchestrator is None:
        logger.debug("[EvolutionSystem] Not initialized, skipping trace recording")
        return None

    try:
        trace_id = agent.evolution_orchestrator.record_execution(
            task_id=task_id,
            session_id=session_id,
            task_description=task_description,
            outcome=outcome,
            steps=steps,
            capabilities_used=tools_executed,
            error_summary=error_summary,
        )

        logger.debug(
            f"[EvolutionSystem] Recorded trace {trace_id}: "
            f"task={task_id[:20]}..., outcome={outcome}"
        )

        return trace_id

    except Exception as e:
        logger.warning(f"[EvolutionSystem] Failed to record trace: {e}")
        return None


def build_execution_steps_from_trace(
    react_trace: list[dict],
    tools_executed: list[str],
    tool_results: dict[str, Any] | None = None,
) -> list[dict]:
    """
    从 ReAct 追踪构建执行步骤。

    将 ReasoningEngine 的 react_trace 转换为
    进化系统可用的 ExecutionStep 格式。

    Args:
        react_trace: ReAct 追踪列表
        tools_executed: 执行的工具名称列表
        tool_results: 工具结果映射

    Returns:
        步骤字典列表
    """
    steps = []

    for i, trace_item in enumerate(react_trace):
        step_type = "reasoning"
        tool_calls = trace_item.get("tool_calls", [])

        if tool_calls:
            step_type = "action"

            for tc in tool_calls:
                tool_name = tc.get("name", "unknown")
                tool_input = tc.get("input_preview", "")
                result = ""
                success = True

                if tool_results:
                    result = str(tool_results.get(tool_name, ""))[:500]
                    # 简单的成功/失败判断
                    success = not any(
                        marker in result.lower()
                        for marker in ["error", "failed", "exception", "❌"]
                    )

                steps.append({
                    "type": "action",
                    "name": tool_name,
                    "description": f"Execute {tool_name}",
                    "status": "success" if success else "failure",
                    "output": result[:200] if result else None,
                    "error": None if success else result[:100],
                })

        elif trace_item.get("thinking"):
            steps.append({
                "type": "reasoning",
                "name": f"think_{i}",
                "description": "LLM reasoning step",
                "status": "success",
                "output": trace_item.get("text", "")[:200] if trace_item.get("text") else None,
            })

        elif trace_item.get("text"):
            steps.append({
                "type": "reasoning",
                "name": f"respond_{i}",
                "description": "LLM response",
                "status": "success",
                "output": trace_item.get("text", "")[:200],
            })

    return steps


def check_and_trigger_evolution(agent: "Agent") -> dict[str, Any] | None:
    """
    检查并触发进化循环。

    如果满足进化条件（追踪数足够 + 时间间隔），
    则运行进化循环。

    Args:
        agent: Agent 实例

    Returns:
        进化结果，如果未触发则返回 None
    """
    if not hasattr(agent, "evolution_orchestrator") or agent.evolution_orchestrator is None:
        return None

    orchestrator = agent.evolution_orchestrator

    if not orchestrator.should_evolve():
        return None

    logger.info("[EvolutionSystem] Triggering evolution cycle")

    try:
        result = orchestrator.run_evolution_cycle()

        if result.get("status") == "success":
            logger.info(
                f"[EvolutionSystem] Evolution cycle completed: "
                f"patterns={result.get('patterns_found', 0)}, "
                f"proposals={result.get('proposals_generated', 0)}"
            )
        else:
            logger.debug(f"[EvolutionSystem] Evolution cycle: {result.get('message', 'skipped')}")

        return result

    except Exception as e:
        logger.error(f"[EvolutionSystem] Evolution cycle failed: {e}")
        return {"status": "error", "error": str(e)}


def get_evolution_summary(agent: "Agent") -> dict[str, Any]:
    """
    获取进化系统摘要。

    Args:
        agent: Agent 实例

    Returns:
        进化系统摘要字典
    """
    if not hasattr(agent, "evolution_orchestrator") or agent.evolution_orchestrator is None:
        return {"enabled": False, "reason": "Evolution system not initialized"}

    orchestrator = agent.evolution_orchestrator
    stats = orchestrator.get_statistics()

    return {
        "enabled": True,
        "store_stats": stats.get("store", {}),
        "evolution_stats": stats.get("evolution", {}),
        "last_evolution": stats.get("last_evolution"),
        "evolution_count": stats.get("evolution_count", 0),
        "should_evolve": orchestrator.should_evolve(),
    }


def save_evolution_state(agent: "Agent") -> bool:
    """
    保存进化系统状态。

    Args:
        agent: Agent 实例

    Returns:
        是否成功保存
    """
    if not hasattr(agent, "evolution_orchestrator") or agent.evolution_orchestrator is None:
        return False

    try:
        agent.evolution_orchestrator.save()
        logger.debug("[EvolutionSystem] State saved")
        return True
    except Exception as e:
        logger.warning(f"[EvolutionSystem] Failed to save state: {e}")
        return False