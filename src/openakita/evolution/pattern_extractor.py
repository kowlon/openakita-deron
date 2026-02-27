"""
模式提取器

从执行追踪中提取有价值的模式，用于自我进化。
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .models import (
    ExecutionStatus,
    ExecutionTrace,
    ExecutionStep,
    OutcomeLabel,
    PatternObservation,
    StepType,
)
from .experience_store import ExperienceStore

logger = logging.getLogger(__name__)


@dataclass
class PatternConfig:
    """模式提取配置"""
    min_frequency: int = 3  # 最小出现次数
    min_confidence: float = 0.7  # 最小置信度
    analysis_window_days: int = 7  # 分析时间窗口
    max_patterns: int = 100  # 最大模式数量


class PatternExtractor:
    """
    模式提取器

    从执行追踪中提取模式：
    - 成功模式：高效完成任务的策略
    - 失败模式：常见错误和失败原因
    - 优化模式：性能改进机会
    """

    def __init__(
        self,
        store: ExperienceStore,
        config: PatternConfig | None = None,
    ):
        """
        初始化模式提取器。

        Args:
            store: 经验存储
            config: 提取配置
        """
        self._store = store
        self._config = config or PatternConfig()
        self._patterns: list[PatternObservation] = []

    # ==================== 模式提取 ====================

    def extract_patterns(self) -> list[PatternObservation]:
        """
        提取所有模式。

        Returns:
            提取的模式列表
        """
        self._patterns = []

        # 获取时间窗口内的追踪
        start_date = datetime.now() - timedelta(days=self._config.analysis_window_days)
        traces = self._store.query(start_date=start_date, limit=1000)

        if len(traces) < self._config.min_frequency:
            logger.warning(f"[PatternExtractor] Not enough traces: {len(traces)}")
            return []

        # 提取各类模式
        self._extract_success_patterns(traces)
        self._extract_failure_patterns(traces)
        self._extract_capability_patterns(traces)
        self._extract_performance_patterns(traces)

        # 按频率和置信度排序
        self._patterns.sort(key=lambda p: (p.frequency, p.confidence), reverse=True)

        # 限制数量
        self._patterns = self._patterns[:self._config.max_patterns]

        logger.info(f"[PatternExtractor] Extracted {len(self._patterns)} patterns")
        return self._patterns

    def _extract_success_patterns(self, traces: list[ExecutionTrace]) -> None:
        """提取成功模式"""
        successful = [t for t in traces if t.outcome == OutcomeLabel.SUCCESS]
        if len(successful) < self._config.min_frequency:
            return

        # 分析成功追踪的能力组合
        capability_combos: Counter[tuple[str, ...]] = Counter()
        for trace in successful:
            if trace.capabilities_used:
                combo = tuple(sorted(trace.capabilities_used))
                capability_combos[combo] += 1

        # 提取高频成功组合
        for combo, count in capability_combos.most_common(10):
            if count >= self._config.min_frequency:
                confidence = count / len(successful)
                if confidence >= self._config.min_confidence:
                    pattern = PatternObservation(
                        pattern_type="success_pattern",
                        description=f"Capability combination {' + '.join(combo)} often leads to success",
                        frequency=count,
                        confidence=confidence,
                        examples=[f"Used in {count} successful tasks"],
                        suggested_action=f"Consider promoting this capability combination",
                    )
                    self._patterns.append(pattern)

        # 分析成功追踪的步骤序列
        step_sequences: Counter[tuple[str, ...]] = Counter()
        for trace in successful:
            if len(trace.steps) >= 2:
                sequence = tuple(s.name for s in trace.steps[:5] if s.name)
                if len(sequence) >= 2:
                    step_sequences[sequence] += 1

        for sequence, count in step_sequences.most_common(10):
            if count >= self._config.min_frequency:
                confidence = count / len(successful)
                if confidence >= self._config.min_confidence:
                    pattern = PatternObservation(
                        pattern_type="success_pattern",
                        description=f"Step sequence {' -> '.join(sequence)} often succeeds",
                        frequency=count,
                        confidence=confidence,
                        examples=[f"Observed in {count} traces"],
                        suggested_action="Consider documenting this as a best practice",
                    )
                    self._patterns.append(pattern)

    def _extract_failure_patterns(self, traces: list[ExecutionTrace]) -> None:
        """提取失败模式"""
        failed = [t for t in traces if t.outcome == OutcomeLabel.FAILURE]
        if len(failed) < self._config.min_frequency:
            return

        # 分析失败原因
        error_counter: Counter[str] = Counter()
        for trace in failed:
            if trace.error_summary:
                # 简化错误描述
                error_key = self._simplify_error(trace.error_summary)
                error_counter[error_key] += 1

        for error, count in error_counter.most_common(10):
            if count >= self._config.min_frequency:
                confidence = count / len(failed)
                pattern = PatternObservation(
                    pattern_type="failure_pattern",
                    description=f"Common failure: {error}",
                    frequency=count,
                    confidence=confidence,
                    examples=[f"Occurred in {count} failed tasks"],
                    suggested_action=f"Investigate and add error handling for: {error}",
                )
                self._patterns.append(pattern)

        # 分析失败前的能力使用
        pre_failure_capabilities: Counter[str] = Counter()
        for trace in failed:
            for cap in trace.capabilities_used:
                pre_failure_capabilities[cap] += 1

        for cap, count in pre_failure_capabilities.most_common(5):
            if count >= self._config.min_frequency:
                # 计算该能力的失败率
                all_with_cap = len(self._store.query(capability=cap))
                if all_with_cap > 0:
                    failure_rate = count / all_with_cap
                    if failure_rate > 0.3:  # 失败率超过30%
                        pattern = PatternObservation(
                            pattern_type="failure_pattern",
                            description=f"Capability '{cap}' has high failure rate ({failure_rate:.1%})",
                            frequency=count,
                            confidence=failure_rate,
                            examples=[f"Failed {count} out of {all_with_cap} times"],
                            suggested_action=f"Review and improve capability '{cap}'",
                        )
                        self._patterns.append(pattern)

        # 分析失败步骤
        failed_steps: Counter[str] = Counter()
        for trace in failed:
            for step in trace.get_failed_steps():
                failed_steps[step.name] += 1

        for step_name, count in failed_steps.most_common(5):
            if count >= self._config.min_frequency:
                pattern = PatternObservation(
                    pattern_type="failure_pattern",
                    description=f"Step '{step_name}' frequently fails",
                    frequency=count,
                    confidence=count / len(failed),
                    examples=[f"Failed {count} times"],
                    suggested_action=f"Add error handling or fallback for step '{step_name}'",
                )
                self._patterns.append(pattern)

    def _extract_capability_patterns(self, traces: list[ExecutionTrace]) -> None:
        """提取能力使用模式"""
        # 分析能力使用频率
        capability_usage: Counter[str] = Counter()
        for trace in traces:
            for cap in trace.capabilities_used:
                capability_usage[cap] += 1

        # 高频使用的能力
        for cap, count in capability_usage.most_common(10):
            if count >= self._config.min_frequency:
                # 计算成功率
                success_rate = self._store.get_success_rate(capability=cap)
                if success_rate >= 0.9:  # 成功率超过90%
                    pattern = PatternObservation(
                        pattern_type="success_pattern",
                        description=f"Capability '{cap}' is reliable ({success_rate:.1%} success rate)",
                        frequency=count,
                        confidence=success_rate,
                        examples=[f"Used {count} times"],
                        suggested_action=f"Consider promoting '{cap}' as a primary capability",
                    )
                    self._patterns.append(pattern)

        # 分析能力协同
        capability_pairs: Counter[tuple[str, str]] = Counter()
        for trace in traces:
            caps = trace.capabilities_used
            for i, cap1 in enumerate(caps):
                for cap2 in caps[i+1:]:
                    pair = tuple(sorted([cap1, cap2]))
                    capability_pairs[pair] += 1

        for (cap1, cap2), count in capability_pairs.most_common(10):
            if count >= self._config.min_frequency:
                confidence = count / len(traces)
                if confidence >= self._config.min_confidence:
                    pattern = PatternObservation(
                        pattern_type="optimization_pattern",
                        description=f"Capabilities '{cap1}' and '{cap2}' are often used together",
                        frequency=count,
                        confidence=confidence,
                        examples=[f"Co-occurred in {count} traces"],
                        suggested_action="Consider creating a combined skill for this workflow",
                    )
                    self._patterns.append(pattern)

    def _extract_performance_patterns(self, traces: list[ExecutionTrace]) -> None:
        """提取性能模式"""
        # 分析执行时间
        durations = [(t, t.total_duration_ms) for t in traces if t.total_duration_ms > 0]
        if len(durations) < self._config.min_frequency:
            return

        # 计算平均和标准差
        avg_duration = sum(d for _, d in durations) / len(durations)
        variance = sum((d - avg_duration) ** 2 for _, d in durations) / len(durations)
        std_dev = variance ** 0.5

        # 识别慢任务
        slow_threshold = avg_duration + 2 * std_dev
        slow_traces = [t for t, d in durations if d > slow_threshold]

        if len(slow_traces) >= self._config.min_frequency:
            # 分析慢任务的共同特征
            slow_capabilities: Counter[str] = Counter()
            for trace in slow_traces:
                for cap in trace.capabilities_used:
                    slow_capabilities[cap] += 1

            for cap, count in slow_capabilities.most_common(3):
                if count >= self._config.min_frequency:
                    pattern = PatternObservation(
                        pattern_type="optimization_pattern",
                        description=f"Capability '{cap}' is associated with slow executions",
                        frequency=count,
                        confidence=count / len(slow_traces),
                        examples=[f"Found in {count} slow tasks"],
                        suggested_action=f"Optimize capability '{cap}' for better performance",
                    )
                    self._patterns.append(pattern)

        # 识别快任务
        fast_threshold = avg_duration / 2
        fast_traces = [t for t, d in durations if d < fast_threshold]

        if len(fast_traces) >= self._config.min_frequency:
            # 分析快任务的共同特征
            fast_capabilities: Counter[str] = Counter()
            for trace in fast_traces:
                for cap in trace.capabilities_used:
                    fast_capabilities[cap] += 1

            for cap, count in fast_capabilities.most_common(3):
                if count >= self._config.min_frequency:
                    confidence = count / len(fast_traces)
                    pattern = PatternObservation(
                        pattern_type="success_pattern",
                        description=f"Capability '{cap}' is associated with fast executions",
                        frequency=count,
                        confidence=confidence,
                        examples=[f"Found in {count} fast tasks"],
                        suggested_action="Study this capability's efficiency patterns",
                    )
                    self._patterns.append(pattern)

    # ==================== 辅助方法 ====================

    def _simplify_error(self, error: str) -> str:
        """简化错误描述"""
        # 移除具体路径和数值
        import re
        simplified = error

        # 移除文件路径
        simplified = re.sub(r'/[\w/.-]+', '[PATH]', simplified)

        # 移除数字
        simplified = re.sub(r'\b\d+\b', '[NUM]', simplified)

        # 截断
        if len(simplified) > 100:
            simplified = simplified[:100] + "..."

        return simplified

    # ==================== 查询方法 ====================

    def get_patterns(self) -> list[PatternObservation]:
        """获取已提取的模式"""
        return self._patterns

    def get_patterns_by_type(self, pattern_type: str) -> list[PatternObservation]:
        """按类型获取模式"""
        return [p for p in self._patterns if p.pattern_type == pattern_type]

    def get_success_patterns(self) -> list[PatternObservation]:
        """获取成功模式"""
        return self.get_patterns_by_type("success_pattern")

    def get_failure_patterns(self) -> list[PatternObservation]:
        """获取失败模式"""
        return self.get_patterns_by_type("failure_pattern")

    def get_optimization_patterns(self) -> list[PatternObservation]:
        """获取优化模式"""
        return self.get_patterns_by_type("optimization_pattern")

    def get_top_patterns(self, n: int = 10) -> list[PatternObservation]:
        """获取最重要的N个模式"""
        return self._patterns[:n]