"""
性能监控模块

记录 LLM 交互各阶段的耗时，包括:
- Prompt 构建各阶段耗时
- LLM 调用首 Token 时间
- 总响应时间

使用方式:
    from openakita.infra.performance import PerformanceTracker

    tracker = PerformanceTracker()
    tracker.start_stage("prompt_build")
    # ... do work ...
    tracker.end_stage("prompt_build")

    tracker.log_summary()  # 打印耗时统计
"""

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class StageMetrics:
    """单个阶段的性能指标"""
    name: str
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "duration_ms": round(self.duration_ms, 2),
            "metadata": self.metadata,
        }


@dataclass
class LLMCallMetrics:
    """LLM 调用性能指标"""
    provider: str = ""
    model: str = ""
    call_start_time: float = 0.0
    first_token_time: float = 0.0
    end_time: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def ttfb_ms(self) -> float:
        """Time to First Token (首 Token 时间)"""
        if self.first_token_time > 0 and self.call_start_time > 0:
            return (self.first_token_time - self.call_start_time) * 1000
        return 0.0

    @property
    def total_ms(self) -> float:
        """总响应时间"""
        if self.end_time > 0 and self.call_start_time > 0:
            return (self.end_time - self.call_start_time) * 1000
        return 0.0

    @property
    def tokens_per_second(self) -> float:
        """输出 Token 速率"""
        if self.output_tokens > 0 and self.total_ms > 0:
            return self.output_tokens / (self.total_ms / 1000)
        return 0.0

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "ttfb_ms": round(self.ttfb_ms, 2),
            "total_ms": round(self.total_ms, 2),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "tokens_per_second": round(self.tokens_per_second, 2),
        }


class PerformanceTracker:
    """
    性能追踪器

    追踪用户请求从接收到 LLM 响应的完整链路耗时。

    Example:
        tracker = PerformanceTracker()
        tracker.start_request("你好")

        with tracker.stage("identity"):
            # 构建身份层
            pass

        with tracker.stage("runtime"):
            # 构建运行时层
            pass

        tracker.start_llm_call("anthropic", "claude-3-opus")
        # ... 在收到第一个 token 时调用 tracker.record_first_token()
        tracker.end_llm_call(100, 50)  # input_tokens, output_tokens

        tracker.end_request()
        tracker.log_summary()
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """重置所有追踪数据"""
        self._request_start_time: float = 0.0
        self._request_end_time: float = 0.0
        self._user_query: str = ""
        self._stages: dict[str, StageMetrics] = {}
        self._llm_calls: list[LLMCallMetrics] = []
        self._current_llm_call: LLMCallMetrics | None = None
        self._current_stage: str | None = None

    def start_request(self, user_query: str = ""):
        """开始追踪一个用户请求"""
        self.reset()
        self._request_start_time = time.time()
        self._user_query = user_query[:100]  # 截断长查询
        logger.info(f"[PERF] 🔵 Request started: '{self._user_query}'")

    def end_request(self):
        """结束当前请求追踪"""
        self._request_end_time = time.time()
        total_ms = (self._request_end_time - self._request_start_time) * 1000
        logger.info(f"[PERF] 🟢 Request completed in {total_ms:.0f}ms")

    def start_stage(self, name: str):
        """开始一个阶段"""
        self._stages[name] = StageMetrics(
            name=name,
            start_time=time.time(),
        )
        self._current_stage = name

    def end_stage(self, name: str, metadata: dict[str, Any] | None = None):
        """结束一个阶段"""
        if name in self._stages:
            stage = self._stages[name]
            stage.end_time = time.time()
            stage.duration_ms = (stage.end_time - stage.start_time) * 1000
            if metadata:
                stage.metadata.update(metadata)
            logger.debug(f"[PERF]   ⏱️ {name}: {stage.duration_ms:.1f}ms")
        self._current_stage = None

    @contextmanager
    def stage(self, name: str, metadata: dict[str, Any] | None = None):
        """上下文管理器方式追踪阶段"""
        self.start_stage(name)
        try:
            yield
        finally:
            self.end_stage(name, metadata)

    def start_llm_call(self, provider: str, model: str):
        """开始 LLM 调用追踪"""
        self._current_llm_call = LLMCallMetrics(
            provider=provider,
            model=model,
            call_start_time=time.time(),
        )
        logger.debug(f"[PERF]   🤖 LLM call started: {provider}/{model}")

    def record_first_token(self):
        """记录首 Token 时间"""
        if self._current_llm_call:
            self._current_llm_call.first_token_time = time.time()
            ttfb = self._current_llm_call.ttfb_ms
            logger.info(f"[PERF]   ⚡ First token received: TTFB={ttfb:.0f}ms")

    def end_llm_call(self, input_tokens: int = 0, output_tokens: int = 0):
        """结束 LLM 调用追踪"""
        if self._current_llm_call:
            self._current_llm_call.end_time = time.time()
            self._current_llm_call.input_tokens = input_tokens
            self._current_llm_call.output_tokens = output_tokens
            self._llm_calls.append(self._current_llm_call)

            metrics = self._current_llm_call
            logger.info(
                f"[PERF]   🏁 LLM call completed: "
                f"total={metrics.total_ms:.0f}ms, "
                f"TTFB={metrics.ttfb_ms:.0f}ms, "
                f"tokens={input_tokens}→{output_tokens}, "
                f"speed={metrics.tokens_per_second:.1f} tok/s"
            )
            self._current_llm_call = None

    def get_summary(self) -> dict[str, Any]:
        """获取性能摘要"""
        total_ms = 0
        if self._request_end_time > 0 and self._request_start_time > 0:
            total_ms = (self._request_end_time - self._request_start_time) * 1000

        # 计算各阶段耗时
        prompt_build_ms = sum(s.duration_ms for s in self._stages.values())
        llm_total_ms = sum(call.total_ms for call in self._llm_calls)
        avg_ttfb_ms = (
            sum(call.ttfb_ms for call in self._llm_calls) / len(self._llm_calls)
            if self._llm_calls else 0
        )

        return {
            "timestamp": datetime.now().isoformat(),
            "user_query": self._user_query,
            "total_ms": round(total_ms, 2),
            "breakdown": {
                "prompt_build_ms": round(prompt_build_ms, 2),
                "llm_total_ms": round(llm_total_ms, 2),
                "other_ms": round(total_ms - prompt_build_ms - llm_total_ms, 2),
            },
            "stages": {name: stage.to_dict() for name, stage in self._stages.items()},
            "llm_calls": [call.to_dict() for call in self._llm_calls],
            "metrics": {
                "avg_ttfb_ms": round(avg_ttfb_ms, 2),
                "total_llm_calls": len(self._llm_calls),
                "total_input_tokens": sum(c.input_tokens for c in self._llm_calls),
                "total_output_tokens": sum(c.output_tokens for c in self._llm_calls),
            },
        }

    def log_summary(self):
        """打印性能摘要"""
        summary = self.get_summary()

        logger.info("=" * 60)
        logger.info("[PERF] 📊 Performance Summary")
        logger.info("=" * 60)
        logger.info(f"  Query: '{summary['user_query']}'")
        logger.info(f"  Total Time: {summary['total_ms']:.0f}ms")
        logger.info("")
        logger.info("  Breakdown:")

        bd = summary["breakdown"]
        total = summary["total_ms"]
        if total > 0:
            prompt_pct = bd["prompt_build_ms"] / total * 100
            llm_pct = bd["llm_total_ms"] / total * 100
            other_pct = bd["other_ms"] / total * 100
            logger.info(f"    Prompt Build: {bd['prompt_build_ms']:.0f}ms ({prompt_pct:.1f}%)")
            logger.info(f"    LLM Calls:    {bd['llm_total_ms']:.0f}ms ({llm_pct:.1f}%)")
            logger.info(f"    Other:        {bd['other_ms']:.0f}ms ({other_pct:.1f}%)")

        if summary["stages"]:
            logger.info("")
            logger.info("  Stage Details:")
            for name, stage in summary["stages"].items():
                logger.info(f"    {name}: {stage['duration_ms']:.1f}ms")

        if summary["llm_calls"]:
            logger.info("")
            logger.info("  LLM Calls:")
            for i, call in enumerate(summary["llm_calls"], 1):
                logger.info(
                    f"    #{i} {call['provider']}/{call['model']}: "
                    f"TTFB={call['ttfb_ms']:.0f}ms, "
                    f"total={call['total_ms']:.0f}ms, "
                    f"tokens={call['input_tokens']}→{call['output_tokens']}"
                )

        metrics = summary["metrics"]
        logger.info("")
        logger.info(
            f"  Metrics: Avg TTFB={metrics['avg_ttfb_ms']:.0f}ms, "
            f"Total Tokens={metrics['total_input_tokens']}+{metrics['total_output_tokens']}"
        )
        logger.info("=" * 60)


# 全局性能追踪器实例
_global_tracker: PerformanceTracker | None = None


def get_performance_tracker() -> PerformanceTracker:
    """获取全局性能追踪器"""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = PerformanceTracker()
    return _global_tracker


def reset_performance_tracker():
    """重置全局性能追踪器"""
    global _global_tracker
    if _global_tracker:
        _global_tracker.reset()


def start_request_tracking(user_query: str = ""):
    """开始追踪一个请求"""
    tracker = get_performance_tracker()
    tracker.start_request(user_query)
    return tracker


def end_request_tracking():
    """结束当前请求追踪"""
    tracker = get_performance_tracker()
    tracker.end_request()
    return tracker.get_summary()
