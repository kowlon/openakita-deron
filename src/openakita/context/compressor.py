"""
上下文压缩器

提供多种上下文压缩策略，在 Token 预算超限时压缩上下文。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CompressionStrategy(Enum):
    """压缩策略枚举"""

    SLIDING_WINDOW = "sliding_window"  # 滑动窗口（默认，确定性）
    SUMMARY = "summary"  # LLM 摘要压缩
    PRIORITY = "priority"  # 按优先级裁剪
    HYBRID = "hybrid"  # 混合策略


class ICompressor(ABC):
    """
    上下文压缩器抽象基类

    定义压缩器的接口，支持多种压缩策略。
    """

    @property
    @abstractmethod
    def strategy(self) -> CompressionStrategy:
        """当前压缩策略"""
        ...

    @abstractmethod
    def compress(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        target_tokens: int,
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        压缩上下文

        Args:
            system_prompt: 系统提示
            messages: 消息列表
            target_tokens: 目标 Token 数

        Returns:
            压缩后的 (system_prompt, messages)
        """
        ...

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """估算文本的 Token 数"""
        ...


class SlidingWindowCompressor(ICompressor):
    """
    滑动窗口压缩器

    使用确定性滑动窗口算法压缩消息历史。
    不调用 LLM，延迟 <10ms。

    特点：
    - 保留最近的对话轮次
    - 保持 tool_use/tool_result 配对
    - 优先保留系统消息
    """

    def __init__(
        self,
        chars_per_token: float = 4.0,
        min_keep_rounds: int = 4,
    ):
        """
        初始化滑动窗口压缩器。

        Args:
            chars_per_token: 每个 Token 的平均字符数
            min_keep_rounds: 最少保留轮数
        """
        self._chars_per_token = chars_per_token
        self._min_keep_rounds = min_keep_rounds

    @property
    def strategy(self) -> CompressionStrategy:
        return CompressionStrategy.SLIDING_WINDOW

    def compress(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        target_tokens: int,
    ) -> tuple[str, list[dict[str, Any]],]:
        """
        使用滑动窗口压缩消息历史。

        策略：
        1. 保留系统提示
        2. 从最早的消息开始裁剪
        3. 保持 min_keep_rounds 轮对话
        4. 保持 tool_use/tool_result 配对
        """
        current_tokens = self.estimate_tokens(system_prompt)
        for msg in messages:
            current_tokens += self._estimate_message_tokens(msg)

        if current_tokens <= target_tokens:
            return system_prompt, messages

        logger.info(
            f"[Compressor] SlidingWindow: {current_tokens} > {target_tokens}, "
            f"compressing {len(messages)} messages"
        )

        # 计算需要裁剪的消息数
        trimmed_messages = list(messages)
        rounds = self._count_rounds(trimmed_messages)

        while current_tokens > target_tokens and len(trimmed_messages) > 0:
            # 检查是否已达到最小保留轮数
            current_rounds = self._count_rounds(trimmed_messages)
            if current_rounds <= self._min_keep_rounds:
                break

            # 找到可以安全删除的消息
            remove_index = self._find_safe_remove_index(trimmed_messages)
            if remove_index is None:
                break

            removed_msg = trimmed_messages.pop(remove_index)
            current_tokens -= self._estimate_message_tokens(removed_msg)

        return system_prompt, trimmed_messages

    def estimate_tokens(self, text: str) -> int:
        """估算文本的 Token 数"""
        return int(len(text) / self._chars_per_token)

    def _estimate_message_tokens(self, message: dict[str, Any]) -> int:
        """估算消息的 Token 数"""
        content = message.get("content", "")
        if isinstance(content, str):
            return self.estimate_tokens(content) + 4  # 角色开销
        elif isinstance(content, list):
            total = 4
            for block in content:
                if isinstance(block, dict):
                    total += self.estimate_tokens(str(block.get("text", "")))
                    total += self.estimate_tokens(str(block.get("content", "")))
            return total
        return 100  # 未知格式估算

    def _count_rounds(self, messages: list[dict[str, Any]]) -> int:
        """统计对话轮数"""
        return sum(1 for m in messages if m.get("role") == "user")

    def _find_safe_remove_index(self, messages: list[dict[str, Any]]) -> int | None:
        """
        找到可以安全删除的消息索引。

        避免：
        - 删除 tool_result 导致 tool_use 孤立
        - 删除 tool_use 导致 tool_result 孤立
        """
        for i, msg in enumerate(messages):
            role = msg.get("role")

            # 跳过 tool 相关消息
            if role == "tool":
                continue

            # 检查下一条消息是否是 tool_result（需要配对保留）
            if i + 1 < len(messages) and messages[i + 1].get("role") == "tool":
                # 检查是否是 assistant 的 tool_use
                content = msg.get("content")
                if isinstance(content, list):
                    has_tool_use = any(
                        isinstance(b, dict) and b.get("type") == "tool_use"
                        for b in content
                    )
                    if has_tool_use:
                        continue  # 跳过，避免破坏配对

            return i

        return None


class PriorityCompressor(ICompressor):
    """
    优先级压缩器

    按消息优先级裁剪。优先保留：
    1. 系统消息
    2. 包含关键信息的消息
    3. 最近的用户消息
    """

    # 消息优先级权重
    PRIORITY_WEIGHTS = {
        "system": 100,  # 系统消息最高优先
        "user": 80,  # 用户消息高优先
        "assistant": 50,  # 助手消息中等优先
        "tool": 30,  # 工具结果较低优先
    }

    def __init__(self, chars_per_token: float = 4.0):
        self._chars_per_token = chars_per_token

    @property
    def strategy(self) -> CompressionStrategy:
        return CompressionStrategy.PRIORITY

    def compress(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        target_tokens: int,
    ) -> tuple[str, list[dict[str, Any]],]:
        """按优先级压缩消息"""
        current_tokens = self.estimate_tokens(system_prompt)
        message_tokens = []

        for i, msg in enumerate(messages):
            tokens = self._estimate_message_tokens(msg)
            message_tokens.append((i, msg, tokens))
            current_tokens += tokens

        if current_tokens <= target_tokens:
            return system_prompt, messages

        # 计算优先级分数（低分数优先删除）
        scored_messages = []
        for i, msg, tokens in message_tokens:
            role = msg.get("role", "user")
            base_score = self.PRIORITY_WEIGHTS.get(role, 50)

            # 最近的消息加分
            recency_bonus = (i / len(messages)) * 20

            # 包含关键信息的消息加分
            content = msg.get("content", "")
            if isinstance(content, str):
                if any(kw in content for kw in ["错误", "error", "失败", "重要", "重要"]):
                    base_score += 30

            scored_messages.append((i, msg, tokens, base_score + recency_bonus))

        # 按分数升序排序（低分数优先删除）
        scored_messages.sort(key=lambda x: x[3])

        # 删除消息直到满足预算
        removed_indices = set()
        for i, msg, tokens, score in scored_messages:
            if current_tokens <= target_tokens:
                break
            # 不删除最后一条用户消息
            if i == len(messages) - 1 and msg.get("role") == "user":
                continue
            removed_indices.add(i)
            current_tokens -= tokens

        # 重建消息列表
        trimmed_messages = [
            msg for i, msg in enumerate(messages) if i not in removed_indices
        ]

        return system_prompt, trimmed_messages

    def estimate_tokens(self, text: str) -> int:
        return int(len(text) / self._chars_per_token)

    def _estimate_message_tokens(self, message: dict[str, Any]) -> int:
        """估算消息的 Token 数"""
        content = message.get("content", "")
        if isinstance(content, str):
            return self.estimate_tokens(content) + 4
        elif isinstance(content, list):
            total = 4
            for block in content:
                if isinstance(block, dict):
                    total += self.estimate_tokens(str(block.get("text", "")))
            return total
        return 100


class HybridCompressor(ICompressor):
    """
    混合压缩器

    结合多种策略：
    1. 首先尝试滑动窗口
    2. 如果仍超限，使用优先级裁剪
    """

    def __init__(
        self,
        chars_per_token: float = 4.0,
        min_keep_rounds: int = 4,
    ):
        self._sliding_window = SlidingWindowCompressor(
            chars_per_token=chars_per_token,
            min_keep_rounds=min_keep_rounds,
        )
        self._priority = PriorityCompressor(chars_per_token=chars_per_token)

    @property
    def strategy(self) -> CompressionStrategy:
        return CompressionStrategy.HYBRID

    def compress(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        target_tokens: int,
    ) -> tuple[str, list[dict[str, Any]],]:
        """先滑动窗口，再优先级裁剪"""
        # 第一阶段：滑动窗口
        system_prompt, messages = self._sliding_window.compress(
            system_prompt, messages, target_tokens
        )

        current_tokens = self.estimate_tokens(system_prompt)
        for msg in messages:
            current_tokens += self._estimate_message_tokens(msg)

        if current_tokens <= target_tokens:
            return system_prompt, messages

        # 第二阶段：优先级裁剪
        return self._priority.compress(system_prompt, messages, target_tokens)

    def estimate_tokens(self, text: str) -> int:
        return self._sliding_window.estimate_tokens(text)

    def _estimate_message_tokens(self, message: dict[str, Any]) -> int:
        return self._sliding_window._estimate_message_tokens(message)


def create_compressor(
    strategy: CompressionStrategy = CompressionStrategy.SLIDING_WINDOW,
    chars_per_token: float = 4.0,
    min_keep_rounds: int = 4,
) -> ICompressor:
    """
    创建压缩器实例

    Args:
        strategy: 压缩策略
        chars_per_token: 每个 Token 的平均字符数
        min_keep_rounds: 最少保留轮数（滑动窗口策略）

    Returns:
        压缩器实例
    """
    if strategy == CompressionStrategy.SLIDING_WINDOW:
        return SlidingWindowCompressor(
            chars_per_token=chars_per_token,
            min_keep_rounds=min_keep_rounds,
        )
    elif strategy == CompressionStrategy.PRIORITY:
        return PriorityCompressor(chars_per_token=chars_per_token)
    elif strategy == CompressionStrategy.HYBRID:
        return HybridCompressor(
            chars_per_token=chars_per_token,
            min_keep_rounds=min_keep_rounds,
        )
    else:
        raise ValueError(f"Unknown compression strategy: {strategy}")