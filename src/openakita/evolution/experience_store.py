"""
经验存储核心

存储和管理执行追踪记录，支持模式分析。
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .models import (
    ExecutionStatus,
    ExecutionTrace,
    OutcomeLabel,
    PatternObservation,
)

logger = logging.getLogger(__name__)


@dataclass
class StoreConfig:
    """存储配置"""
    storage_path: Path = field(default_factory=lambda: Path("data/evolution/experience"))
    max_traces: int = 1000
    max_age_days: int = 30
    auto_save: bool = True
    save_interval: int = 10  # 每N条记录保存一次


class ExperienceStore:
    """
    经验存储

    存储、索引和查询执行追踪记录。
    支持按时间、任务类型、结果类型等多维度查询。
    """

    def __init__(self, config: StoreConfig | None = None):
        """
        初始化经验存储。

        Args:
            config: 存储配置
        """
        self._config = config or StoreConfig()
        self._traces: dict[str, ExecutionTrace] = {}
        self._trace_index: dict[str, list[str]] = defaultdict(list)  # task_id -> trace_ids
        self._session_index: dict[str, list[str]] = defaultdict(list)  # session_id -> trace_ids
        self._outcome_index: dict[str, list[str]] = defaultdict(list)  # outcome -> trace_ids
        self._capability_index: dict[str, list[str]] = defaultdict(list)  # capability -> trace_ids
        self._date_index: dict[str, list[str]] = defaultdict(list)  # date -> trace_ids
        self._pending_saves = 0
        self._loaded = False

        # 确保存储目录存在
        if self._config.storage_path:
            self._config.storage_path.mkdir(parents=True, exist_ok=True)

    # ==================== 存储操作 ====================

    def store(self, trace: ExecutionTrace) -> str:
        """
        存储执行追踪。

        Args:
            trace: 执行追踪

        Returns:
            追踪 ID
        """
        trace_id = trace.trace_id

        # 如果已存在，先删除旧的索引
        if trace_id in self._traces:
            self._remove_from_indexes(self._traces[trace_id])

        # 存储追踪
        self._traces[trace_id] = trace

        # 更新索引
        self._add_to_indexes(trace)

        # 自动保存
        self._pending_saves += 1
        if self._config.auto_save and self._pending_saves >= self._config.save_interval:
            self.save()
            self._pending_saves = 0

        logger.debug(f"[ExperienceStore] Stored trace {trace_id}")
        return trace_id

    def get(self, trace_id: str) -> ExecutionTrace | None:
        """
        获取执行追踪。

        Args:
            trace_id: 追踪 ID

        Returns:
            执行追踪，不存在则返回 None
        """
        return self._traces.get(trace_id)

    def delete(self, trace_id: str) -> bool:
        """
        删除执行追踪。

        Args:
            trace_id: 追踪 ID

        Returns:
            是否删除成功
        """
        if trace_id not in self._traces:
            return False

        trace = self._traces[trace_id]
        self._remove_from_indexes(trace)
        del self._traces[trace_id]

        logger.debug(f"[ExperienceStore] Deleted trace {trace_id}")
        return True

    def clear(self) -> int:
        """
        清空所有存储。

        Returns:
            清空的记录数
        """
        count = len(self._traces)
        self._traces.clear()
        self._trace_index.clear()
        self._session_index.clear()
        self._outcome_index.clear()
        self._capability_index.clear()
        self._date_index.clear()
        logger.info(f"[ExperienceStore] Cleared {count} traces")
        return count

    # ==================== 查询操作 ====================

    def query(
        self,
        task_id: str | None = None,
        session_id: str | None = None,
        outcome: OutcomeLabel | None = None,
        capability: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[ExecutionTrace]:
        """
        查询执行追踪。

        Args:
            task_id: 任务 ID 过滤
            session_id: 会话 ID 过滤
            outcome: 结果标签过滤
            capability: 能力名称过滤
            start_date: 开始日期过滤
            end_date: 结束日期过滤
            limit: 最大返回数量

        Returns:
            匹配的执行追踪列表
        """
        # 从最具体的索引开始
        trace_ids: set[str] | None = None

        if task_id:
            trace_ids = set(self._trace_index.get(task_id, []))
        if session_id:
            session_ids = set(self._session_index.get(session_id, []))
            trace_ids = session_ids if trace_ids is None else trace_ids & session_ids
        if outcome:
            outcome_ids = set(self._outcome_index.get(outcome.value, []))
            trace_ids = outcome_ids if trace_ids is None else trace_ids & outcome_ids
        if capability:
            cap_ids = set(self._capability_index.get(capability, []))
            trace_ids = cap_ids if trace_ids is None else trace_ids & cap_ids

        # 如果没有索引条件，使用所有追踪
        if trace_ids is None:
            trace_ids = set(self._traces.keys())

        # 日期过滤
        if start_date or end_date:
            date_filtered = set()
            for trace_id in trace_ids:
                trace = self._traces.get(trace_id)
                if trace:
                    trace_date = trace.started_at
                    if start_date and trace_date < start_date:
                        continue
                    if end_date and trace_date > end_date:
                        continue
                    date_filtered.add(trace_id)
            trace_ids = date_filtered

        # 获取并排序
        traces = [self._traces[tid] for tid in trace_ids if tid in self._traces]
        traces.sort(key=lambda t: t.started_at, reverse=True)

        return traces[:limit]

    def get_by_task(self, task_id: str) -> list[ExecutionTrace]:
        """获取任务的所有追踪"""
        trace_ids = self._trace_index.get(task_id, [])
        return [self._traces[tid] for tid in trace_ids if tid in self._traces]

    def get_by_session(self, session_id: str) -> list[ExecutionTrace]:
        """获取会话的所有追踪"""
        trace_ids = self._session_index.get(session_id, [])
        return [self._traces[tid] for tid in trace_ids if tid in self._traces]

    def get_recent(self, limit: int = 10) -> list[ExecutionTrace]:
        """获取最近的追踪"""
        traces = sorted(self._traces.values(), key=lambda t: t.started_at, reverse=True)
        return traces[:limit]

    def get_failed(self, limit: int = 10) -> list[ExecutionTrace]:
        """获取失败的追踪"""
        trace_ids = self._outcome_index.get(OutcomeLabel.FAILURE.value, [])
        traces = [self._traces[tid] for tid in trace_ids if tid in self._traces]
        traces.sort(key=lambda t: t.started_at, reverse=True)
        return traces[:limit]

    def get_successful(self, limit: int = 10) -> list[ExecutionTrace]:
        """获取成功的追踪"""
        trace_ids = self._outcome_index.get(OutcomeLabel.SUCCESS.value, [])
        traces = [self._traces[tid] for tid in trace_ids if tid in self._traces]
        traces.sort(key=lambda t: t.started_at, reverse=True)
        return traces[:limit]

    # ==================== 统计操作 ====================

    def get_statistics(self) -> dict[str, Any]:
        """
        获取存储统计。

        Returns:
            统计数据
        """
        total = len(self._traces)
        if total == 0:
            return {
                "total_traces": 0,
                "by_outcome": {},
                "by_capability": {},
                "avg_duration_ms": 0,
            }

        # 按结果统计
        by_outcome = {
            outcome: len(trace_ids)
            for outcome, trace_ids in self._outcome_index.items()
        }

        # 按能力统计
        by_capability = {
            cap: len(trace_ids)
            for cap, trace_ids in self._capability_index.items()
        }

        # 平均持续时间
        durations = [t.total_duration_ms for t in self._traces.values() if t.total_duration_ms > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            "total_traces": total,
            "by_outcome": by_outcome,
            "by_capability": by_capability,
            "avg_duration_ms": avg_duration,
            "oldest_trace": min(t.started_at for t in self._traces.values()).isoformat(),
            "newest_trace": max(t.started_at for t in self._traces.values()).isoformat(),
        }

    def get_success_rate(self, capability: str | None = None) -> float:
        """
        获取成功率。

        Args:
            capability: 能力名称（可选）

        Returns:
            成功率 (0.0 - 1.0)
        """
        if capability:
            trace_ids = self._capability_index.get(capability, [])
        else:
            trace_ids = list(self._traces.keys())

        if not trace_ids:
            return 0.0

        success_count = 0
        for trace_id in trace_ids:
            trace = self._traces.get(trace_id)
            if trace and trace.outcome == OutcomeLabel.SUCCESS:
                success_count += 1

        return success_count / len(trace_ids)

    def get_capability_usage(self) -> dict[str, int]:
        """获取能力使用统计"""
        return {
            cap: len(trace_ids)
            for cap, trace_ids in self._capability_index.items()
        }

    # ==================== 持久化操作 ====================

    def save(self) -> None:
        """保存到文件"""
        if not self._config.storage_path:
            return

        file_path = self._config.storage_path / "traces.json"

        data = {
            "traces": [t.to_dict() for t in self._traces.values()],
            "saved_at": datetime.now().isoformat(),
        }

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"[ExperienceStore] Saved {len(self._traces)} traces to {file_path}")

    def load(self) -> int:
        """
        从文件加载。

        Returns:
            加载的记录数
        """
        if not self._config.storage_path:
            return 0

        file_path = self._config.storage_path / "traces.json"
        if not file_path.exists():
            return 0

        with open(file_path) as f:
            data = json.load(f)

        count = 0
        for trace_data in data.get("traces", []):
            trace = ExecutionTrace.from_dict(trace_data)
            self.store(trace)
            count += 1

        self._loaded = True
        logger.info(f"[ExperienceStore] Loaded {count} traces from {file_path}")
        return count

    # ==================== 维护操作 ====================

    def cleanup_old(self, max_age_days: int | None = None) -> int:
        """
        清理过期记录。

        Args:
            max_age_days: 最大保留天数

        Returns:
            清理的记录数
        """
        max_age = max_age_days or self._config.max_age_days
        cutoff = datetime.now() - timedelta(days=max_age)

        to_delete = [
            trace_id for trace_id, trace in self._traces.items()
            if trace.started_at < cutoff
        ]

        for trace_id in to_delete:
            self.delete(trace_id)

        if to_delete:
            logger.info(f"[ExperienceStore] Cleaned up {len(to_delete)} old traces")

        return len(to_delete)

    def trim_to_size(self, max_traces: int | None = None) -> int:
        """
        修剪到指定大小。

        Args:
            max_traces: 最大记录数

        Returns:
            清理的记录数
        """
        max_size = max_traces or self._config.max_traces
        if len(self._traces) <= max_size:
            return 0

        # 按时间排序，删除最旧的
        sorted_traces = sorted(self._traces.values(), key=lambda t: t.started_at)
        to_delete = sorted_traces[:len(self._traces) - max_size]

        for trace in to_delete:
            self.delete(trace.trace_id)

        logger.info(f"[ExperienceStore] Trimmed {len(to_delete)} traces to reach max size {max_size}")
        return len(to_delete)

    # ==================== 内部方法 ====================

    def _add_to_indexes(self, trace: ExecutionTrace) -> None:
        """添加到索引"""
        trace_id = trace.trace_id

        # 任务索引
        if trace.task_id:
            self._trace_index[trace.task_id].append(trace_id)

        # 会话索引
        if trace.session_id:
            self._session_index[trace.session_id].append(trace_id)

        # 结果索引
        if trace.outcome:
            self._outcome_index[trace.outcome.value].append(trace_id)

        # 能力索引
        for cap in trace.capabilities_used:
            self._capability_index[cap].append(trace_id)

        # 日期索引
        date_key = trace.started_at.strftime("%Y-%m-%d")
        self._date_index[date_key].append(trace_id)

    def _remove_from_indexes(self, trace: ExecutionTrace) -> None:
        """从索引中移除"""
        trace_id = trace.trace_id

        # 任务索引
        if trace.task_id and trace_id in self._trace_index.get(trace.task_id, []):
            self._trace_index[trace.task_id].remove(trace_id)

        # 会话索引
        if trace.session_id and trace_id in self._session_index.get(trace.session_id, []):
            self._session_index[trace.session_id].remove(trace_id)

        # 结果索引
        if trace.outcome and trace_id in self._outcome_index.get(trace.outcome.value, []):
            self._outcome_index[trace.outcome.value].remove(trace_id)

        # 能力索引
        for cap in trace.capabilities_used:
            if trace_id in self._capability_index.get(cap, []):
                self._capability_index[cap].remove(trace_id)

        # 日期索引
        date_key = trace.started_at.strftime("%Y-%m-%d")
        if trace_id in self._date_index.get(date_key, []):
            self._date_index[date_key].remove(trace_id)


class MockExperienceStore(ExperienceStore):
    """
    模拟经验存储

    用于测试，不进行持久化。
    """

    def __init__(self):
        super().__init__(StoreConfig(storage_path=None, auto_save=False))