"""
Token 预算控制器

动态管理 Token 预算分配，在上下文构建时检查和调整预算。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from .config import TokenBudget
from .exceptions import TokenBudgetExceeded

if TYPE_CHECKING:
    from .interfaces import ICompressor

logger = logging.getLogger(__name__)


class BudgetState(Enum):
    """预算状态"""
    HEALTHY = "healthy"      # 预算充足
    WARNING = "warning"       # 预算紧张
    CRITICAL = "critical"     # 预算即将耗尽
    EXCEEDED = "exceeded"    # 预算超限


@dataclass
class BudgetAllocation:
    """
    预算分配记录

    记录各层上下文的 Token 分配情况。
    """

    system_tokens: int = 0
    task_tokens: int = 0
    conversation_tokens: int = 0
    reserved_tokens: int = 0

    @property
    def total_used(self) -> int:
        """总使用量"""
        return self.system_tokens + self.task_tokens + self.conversation_tokens

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "system_tokens": self.system_tokens,
            "task_tokens": self.task_tokens,
            "conversation_tokens": self.conversation_tokens,
            "reserved_tokens": self.reserved_tokens,
            "total_used": self.total_used,
        }


@dataclass
class BudgetCheckResult:
    """
    预算检查结果

    包含当前状态和建议。
    """

    state: BudgetState
    allocation: BudgetAllocation
    remaining_tokens: int
    message: str
    needs_compression: bool = False
    suggested_action: str | None = None

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "state": self.state.value,
            "allocation": self.allocation.to_dict(),
            "remaining_tokens": self.remaining_tokens,
            "message": self.message,
            "needs_compression": self.needs_compression,
            "suggested_action": self.suggested_action,
        }


class BudgetController:
    """
    Token 预算控制器

    负责动态预算分配和检查。

    功能：
    - 检查当前 Token 使用量
    - 动态分配各层预算
    - 触发压缩策略
    - 预警机制
    """

    # 预警阈值
    WARNING_THRESHOLD = 0.75   # 75% 使用时警告
    CRITICAL_THRESHOLD = 0.90  # 90% 使用时严重警告

    def __init__(
        self,
        budget: TokenBudget | None = None,
        compressor: ICompressor | None = None,
    ):
        """
        初始化预算控制器。

        Args:
            budget: Token 预算配置
            compressor: 压缩器实例（可选）
        """
        self._budget = budget or TokenBudget()
        self._compressor = compressor
        self._allocation = BudgetAllocation()

    @property
    def budget(self) -> TokenBudget:
        """获取预算配置"""
        return self._budget

    @property
    def allocation(self) -> BudgetAllocation:
        """获取当前分配"""
        return self._allocation

    @property
    def available_for_context(self) -> int:
        """可用于上下文的 Token 数"""
        return self._budget.available_for_context

    def check_budget(
        self,
        system_tokens: int = 0,
        task_tokens: int = 0,
        conversation_tokens: int = 0,
    ) -> BudgetCheckResult:
        """
        检查预算状态。

        Args:
            system_tokens: 系统层 Token 数
            task_tokens: 任务层 Token 数
            conversation_tokens: 会话层 Token 数

        Returns:
            预算检查结果
        """
        # 更新分配记录
        self._allocation = BudgetAllocation(
            system_tokens=system_tokens,
            task_tokens=task_tokens,
            conversation_tokens=conversation_tokens,
            reserved_tokens=self._budget.response_reserve + self._budget.buffer,
        )

        total_used = self._allocation.total_used
        remaining = self.available_for_context - total_used
        usage_ratio = total_used / self.available_for_context if self.available_for_context > 0 else 0

        # 判断状态
        if total_used > self.available_for_context:
            return BudgetCheckResult(
                state=BudgetState.EXCEEDED,
                allocation=self._allocation,
                remaining_tokens=remaining,
                message=f"预算超限: 使用 {total_used} > 可用 {self.available_for_context}",
                needs_compression=True,
                suggested_action="immediate_compression",
            )

        if usage_ratio >= self.CRITICAL_THRESHOLD:
            return BudgetCheckResult(
                state=BudgetState.CRITICAL,
                allocation=self._allocation,
                remaining_tokens=remaining,
                message=f"预算紧张: 已使用 {usage_ratio:.1%}",
                needs_compression=True,
                suggested_action="compress_conversation",
            )

        if usage_ratio >= self.WARNING_THRESHOLD:
            return BudgetCheckResult(
                state=BudgetState.WARNING,
                allocation=self._allocation,
                remaining_tokens=remaining,
                message=f"预算警告: 已使用 {usage_ratio:.1%}",
                needs_compression=False,
                suggested_action="monitor",
            )

        return BudgetCheckResult(
            state=BudgetState.HEALTHY,
            allocation=self._allocation,
            remaining_tokens=remaining,
            message=f"预算正常: 已使用 {usage_ratio:.1%}",
            needs_compression=False,
            suggested_action=None,
        )

    def allocate(
        self,
        priority: str = "balanced",
    ) -> dict[str, int]:
        """
        动态分配各层预算。

        Args:
            priority: 优先级策略
                - "balanced": 平衡分配（默认）
                - "system": 优先系统层
                - "conversation": 优先会话层

        Returns:
            各层预算分配字典
        """
        available = self.available_for_context

        if priority == "system":
            # 优先系统层：增加系统层预算
            return {
                "system": min(self._budget.system_reserve * 2, available // 3),
                "task": self._budget.task_reserve,
                "conversation": available - self._budget.system_reserve * 2 - self._budget.task_reserve,
            }
        elif priority == "conversation":
            # 优先会话层：增加会话层预算
            return {
                "system": self._budget.system_reserve,
                "task": self._budget.task_reserve,
                "conversation": available - self._budget.system_reserve - self._budget.task_reserve,
            }
        else:
            # 平衡分配
            return {
                "system": self._budget.system_reserve,
                "task": self._budget.task_reserve,
                "conversation": self._budget.conversation_reserve,
            }

    def should_compress(self, current_tokens: int) -> bool:
        """
        判断是否需要压缩。

        Args:
            current_tokens: 当前 Token 数

        Returns:
            是否需要压缩
        """
        return current_tokens > self.available_for_context * self.WARNING_THRESHOLD

    def get_target_tokens(self, current_tokens: int) -> int:
        """
        获取压缩目标 Token 数。

        Args:
            current_tokens: 当前 Token 数

        Returns:
            目标 Token 数
        """
        # 目标为可用预算的 70%，留出缓冲空间
        target = int(self.available_for_context * 0.70)
        return min(target, current_tokens)

    def estimate_capacity(
        self,
        avg_message_tokens: int = 200,
    ) -> dict[str, int]:
        """
        估算容量。

        Args:
            avg_message_tokens: 平均每条消息的 Token 数

        Returns:
            容量估算字典
        """
        allocation = self.allocate()
        return {
            "max_messages": allocation["conversation"] // avg_message_tokens,
            "system_capacity": allocation["system"],
            "task_capacity": allocation["task"],
            "conversation_capacity": allocation["conversation"],
        }

    def reset(self) -> None:
        """重置分配记录"""
        self._allocation = BudgetAllocation()

    def update_budget(self, new_budget: TokenBudget) -> None:
        """
        更新预算配置。

        Args:
            new_budget: 新的预算配置
        """
        self._budget = new_budget
        logger.info(f"预算已更新: total={new_budget.total}")

    def get_status_report(self) -> dict:
        """
        获取状态报告。

        Returns:
            状态报告字典
        """
        return {
            "budget": self._budget.to_dict(),
            "allocation": self._allocation.to_dict(),
            "available_for_context": self.available_for_context,
            "thresholds": {
                "warning": self.WARNING_THRESHOLD,
                "critical": self.CRITICAL_THRESHOLD,
            },
        }