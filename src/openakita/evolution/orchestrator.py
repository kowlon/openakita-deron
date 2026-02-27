"""
进化编排器

协调自我进化的完整闭环：收集 -> 分析 -> 生成 -> 验证。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .models import ExecutionTrace, EvolutionProposal
from .experience_store import ExperienceStore, StoreConfig
from .pattern_extractor import PatternExtractor, PatternConfig
from .proposal_generator import ProposalGenerator, ProposalConfig
from .skill_evolver import SkillEvolver, EvolverConfig, EvolutionResult

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """编排器配置"""
    # 存储配置
    store_config: StoreConfig = field(default_factory=StoreConfig)
    # 模式提取配置
    pattern_config: PatternConfig = field(default_factory=PatternConfig)
    # 提案生成配置
    proposal_config: ProposalConfig = field(default_factory=ProposalConfig)
    # 进化器配置
    evolver_config: EvolverConfig = field(default_factory=EvolverConfig)
    # 运行配置
    auto_evolve: bool = False  # 是否自动执行进化
    evolution_interval_hours: int = 24  # 进化间隔（小时）
    min_traces_for_evolution: int = 10  # 触发进化的最小追踪数


class EvolutionOrchestrator:
    """
    进化编排器

    协调自我进化的完整闭环：
    1. 收集执行追踪
    2. 分析模式
    3. 生成提案
    4. 执行进化
    5. 验证结果
    """

    def __init__(self, config: OrchestratorConfig | None = None):
        """
        初始化进化编排器。

        Args:
            config: 编排器配置
        """
        self._config = config or OrchestratorConfig()

        # 初始化组件
        self._store = ExperienceStore(self._config.store_config)
        self._extractor = PatternExtractor(self._store, self._config.pattern_config)
        self._generator = ProposalGenerator(self._store, self._extractor, self._config.proposal_config)
        self._evolver = SkillEvolver(self._store, self._generator, self._config.evolver_config)

        # 状态
        self._last_evolution: datetime | None = None
        self._evolution_count = 0

    # ==================== 追踪收集 ====================

    def record_trace(self, trace: ExecutionTrace) -> str:
        """
        记录执行追踪。

        Args:
            trace: 执行追踪

        Returns:
            追踪 ID
        """
        trace_id = self._store.store(trace)
        logger.debug(f"[Orchestrator] Recorded trace {trace_id}")
        return trace_id

    def record_execution(
        self,
        task_id: str,
        session_id: str,
        task_description: str,
        outcome: str,
        steps: list[dict] | None = None,
        capabilities_used: list[str] | None = None,
        error_summary: str | None = None,
    ) -> str:
        """
        便捷方法：记录执行。

        Args:
            task_id: 任务 ID
            session_id: 会话 ID
            task_description: 任务描述
            outcome: 结果 (success, failure, partial)
            steps: 步骤列表
            capabilities_used: 使用的能力
            error_summary: 错误摘要

        Returns:
            追踪 ID
        """
        from .models import OutcomeLabel, ExecutionStep, StepType

        trace = ExecutionTrace(
            task_id=task_id,
            session_id=session_id,
            task_description=task_description,
            capabilities_used=capabilities_used or [],
        )

        # 设置结果
        outcome_map = {
            "success": OutcomeLabel.SUCCESS,
            "failure": OutcomeLabel.FAILURE,
            "partial": OutcomeLabel.PARTIAL,
            "error": OutcomeLabel.ERROR,
        }
        trace.outcome = outcome_map.get(outcome.lower(), OutcomeLabel.SUCCESS)

        if error_summary:
            trace.error_summary = error_summary

        # 添加步骤
        if steps:
            for step_data in steps:
                step = trace.create_step(
                    step_type=StepType(step_data.get("type", "reasoning")),
                    name=step_data.get("name", ""),
                    description=step_data.get("description", ""),
                )
                if step_data.get("status") == "success":
                    step.complete(step_data.get("output"))
                elif step_data.get("status") == "failure":
                    step.fail(step_data.get("error", ""))

        trace.complete(trace.outcome)
        return self.record_trace(trace)

    # ==================== 进化循环 ====================

    def run_evolution_cycle(self, force: bool = False) -> dict[str, Any]:
        """
        运行进化循环。

        Args:
            force: 是否强制运行（忽略间隔检查）

        Returns:
            进化结果摘要
        """
        logger.info("[Orchestrator] Starting evolution cycle")

        result = {
            "started_at": datetime.now().isoformat(),
            "traces_analyzed": 0,
            "patterns_found": 0,
            "proposals_generated": 0,
            "evolutions_executed": 0,
            "evolutions_successful": 0,
            "errors": [],
        }

        try:
            # 检查是否有足够的追踪
            stats = self._store.get_statistics()
            result["traces_analyzed"] = stats["total_traces"]

            if stats["total_traces"] < self._config.min_traces_for_evolution:
                result["status"] = "skipped"
                result["message"] = f"Not enough traces ({stats['total_traces']} < {self._config.min_traces_for_evolution})"
                return result

            # 1. 提取模式
            patterns = self._extractor.extract_patterns()
            result["patterns_found"] = len(patterns)
            logger.info(f"[Orchestrator] Found {len(patterns)} patterns")

            # 2. 生成提案
            proposals = self._generator.generate_proposals()
            result["proposals_generated"] = len(proposals)
            logger.info(f"[Orchestrator] Generated {len(proposals)} proposals")

            # 3. 执行进化（如果启用）
            if self._config.auto_evolve or force:
                results = self._evolver.evolve_all_approved()
                result["evolutions_executed"] = len(results)
                result["evolutions_successful"] = len([r for r in results if r.success])
                logger.info(f"[Orchestrator] Executed {len(results)} evolutions")

            self._last_evolution = datetime.now()
            self._evolution_count += 1
            result["status"] = "success"

        except Exception as e:
            logger.error(f"[Orchestrator] Evolution cycle failed: {e}")
            result["status"] = "error"
            result["errors"].append(str(e))

        result["completed_at"] = datetime.now().isoformat()
        return result

    def should_evolve(self) -> bool:
        """
        检查是否应该运行进化。

        Returns:
            是否应该运行进化
        """
        # 检查追踪数量
        stats = self._store.get_statistics()
        if stats["total_traces"] < self._config.min_traces_for_evolution:
            return False

        # 检查间隔
        if self._last_evolution:
            elapsed = datetime.now() - self._last_evolution
            if elapsed < timedelta(hours=self._config.evolution_interval_hours):
                return False

        return True

    # ==================== 查询方法 ====================

    def get_statistics(self) -> dict[str, Any]:
        """
        获取进化系统统计。

        Returns:
            统计数据
        """
        store_stats = self._store.get_statistics()
        evolution_stats = self._evolver.get_evolution_stats()

        return {
            "store": store_stats,
            "evolution": evolution_stats,
            "last_evolution": self._last_evolution.isoformat() if self._last_evolution else None,
            "evolution_count": self._evolution_count,
        }

    def get_pending_proposals(self) -> list[EvolutionProposal]:
        """获取待处理的提案"""
        return self._generator.get_pending_proposals()

    def get_recent_patterns(self) -> list:
        """获取最近的模式"""
        return self._extractor.get_top_patterns(10)

    def get_recent_traces(self, limit: int = 10) -> list[ExecutionTrace]:
        """获取最近的追踪"""
        return self._store.get_recent(limit)

    # ==================== 组件访问 ====================

    @property
    def store(self) -> ExperienceStore:
        """获取存储实例"""
        return self._store

    @property
    def extractor(self) -> PatternExtractor:
        """获取模式提取器"""
        return self._extractor

    @property
    def generator(self) -> ProposalGenerator:
        """获取提案生成器"""
        return self._generator

    @property
    def evolver(self) -> SkillEvolver:
        """获取技能进化器"""
        return self._evolver

    # ==================== 持久化 ====================

    def save(self) -> None:
        """保存状态"""
        self._store.save()
        logger.info("[Orchestrator] State saved")

    def load(self) -> int:
        """
        加载状态。

        Returns:
            加载的追踪数量
        """
        count = self._store.load()
        logger.info(f"[Orchestrator] Loaded {count} traces")
        return count