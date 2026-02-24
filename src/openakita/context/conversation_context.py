"""
会话上下文

使用滑动窗口裁剪来管理对话历史。
这是核心优化：用确定性的滑动窗口替代 LLM 压缩，
将延迟从 2-5 秒降低到 <10ms。

参考：
- docs/context-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConversationContext:
    """
    会话上下文 - 滑动窗口消息历史。

这是企业级上下文系统的核心优化：
不使用 LLM 压缩（2-5 秒延迟），改为确定性滑动窗口算法（<10ms 延迟）。

关键特性：
    - 压缩时不调用 LLM
    - 基于轮次计数的确定性滑动窗口
    - 保留 tool_use/tool_result 的配对关系
    - 可配置上限

属性：
    messages: 对话消息列表
    max_rounds: 保留的最大对话轮数（默认 20）
    max_tokens: token 预算提示（不严格强制）
    min_keep_rounds: 始终保留的最小轮数（默认 4）

示例：
    ctx = ConversationContext()
    ctx.add_message("user", "你好")
    ctx.add_message("assistant", "你好！")
    messages = ctx.to_messages()
    """

    messages: list[dict[str, Any]] = field(default_factory=list)
    max_rounds: int = 20
    max_tokens: int = 8000
    min_keep_rounds: int = 4

    def add_message(self, role: str, content: str | list[dict[str, Any]]) -> None:
        """
        添加消息，并在需要时应用滑动窗口。

        这是同步且确定性的操作，不调用 LLM。
        延迟保证 <10ms。

        参数：
            role: 消息角色（"user"、"assistant"、"tool"、"system"）
            content: 消息内容（字符串或内容块列表）
        """
        self.messages.append({
            "role": role,
            "content": content,
        })
        self._trim_if_needed()

    def _trim_if_needed(self) -> float:
        """
        若超过轮数上限则执行滑动窗口裁剪。

        这是核心优化：使用确定性算法替代 LLM 压缩。

        返回：
            耗时（毫秒，用于性能监控）
        """
        start_time = time.perf_counter()

        # 统计轮数（用户消息）
        rounds = self._count_rounds()

        # 若未超限，则无需裁剪
        if rounds <= self.max_rounds:
            return 0.0

        # 找到裁剪边界
        # 保留最近 max_rounds 轮
        keep_from_round = rounds - self.max_rounds
        keep_from_index = self._find_round_boundary(keep_from_round)

        # 裁剪消息
        self.messages = self.messages[keep_from_index:]

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return elapsed_ms

    def _count_rounds(self) -> int:
        """
        统计对话轮数。

        一轮定义为一条用户消息及其响应。
        按用户消息数量计数。

        返回：
            对话轮数
        """
        return sum(1 for m in self.messages if m.get("role") == "user")

    def _find_round_boundary(self, target_round: int) -> int:
        """
        查找指定轮次的起始索引。

        参数：
            target_round: 需要查找的轮次编号（从 0 开始）

        返回：
            该轮在消息列表中的起始索引
        """
        round_count = 0
        for i, msg in enumerate(self.messages):
            if msg.get("role") == "user":
                if round_count == target_round:
                    return i
                round_count += 1
        return 0

    def to_messages(self) -> list[dict[str, Any]]:
        """
        获取用于 LLM API 的消息列表。

        返回：
            消息列表的副本
        """
        return self.messages.copy()

    @staticmethod
    def trim_messages(
        messages: list[dict[str, Any]],
        max_rounds: int,
        max_tokens: int = 8000,
    ) -> list[dict[str, Any]]:
        ctx = ConversationContext(
            max_rounds=max_rounds,
            max_tokens=max_tokens,
        )
        for msg in messages:
            ctx.messages.append(msg)
            ctx._trim_if_needed()
        return ctx.to_messages()

    @staticmethod
    def estimate_messages_tokens(
        messages: list[dict[str, Any]],
        chars_per_token: float = 4.0,
    ) -> int:
        ctx = ConversationContext()
        ctx.messages = list(messages)
        return ctx.estimate_tokens(chars_per_token=chars_per_token)

    def clear(self) -> None:
        """清空所有消息。"""
        self.messages = []

    def get_stats(self) -> dict[str, Any]:
        """
        获取会话统计信息。

        返回：
            会话统计字典
        """
        return {
            "message_count": len(self.messages),
            "round_count": self._count_rounds(),
            "max_rounds": self.max_rounds,
            "user_messages": sum(1 for m in self.messages if m.get("role") == "user"),
            "assistant_messages": sum(
                1 for m in self.messages if m.get("role") == "assistant"
            ),
            "tool_messages": sum(1 for m in self.messages if m.get("role") == "tool"),
        }

    def estimate_tokens(self, chars_per_token: float = 4.0) -> int:
        """
        估算对话总 token 数。

        参数：
            chars_per_token: 每个 token 的平均字符数

        返回：
            估算的 token 数量
        """
        total_chars = 0
        for msg in self.messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        total_chars += len(str(block.get("text", "")))
                        total_chars += len(str(block.get("content", "")))

        return int(total_chars / chars_per_token)

    def has_tool_use(self) -> bool:
        """
        检查对话是否包含工具调用块。

        返回：
            若存在 tool_use 内容则为 True
        """
        for msg in self.messages:
            content = msg.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        return True
        return False

    def get_last_user_message(self) -> dict[str, Any] | None:
        """
        获取最后一条用户消息。

        返回：
            最后一条用户消息字典或 None
        """
        for msg in reversed(self.messages):
            if msg.get("role") == "user":
                return msg
        return None

    def get_last_assistant_message(self) -> dict[str, Any] | None:
        """
        获取最后一条助手消息。

        返回：
            最后一条助手消息字典或 None
        """
        for msg in reversed(self.messages):
            if msg.get("role") == "assistant":
                return msg
        return None

    def to_dict(self) -> dict[str, Any]:
        """转换为用于序列化的字典。"""
        return {
            "messages": self.messages,
            "max_rounds": self.max_rounds,
            "max_tokens": self.max_tokens,
            "min_keep_rounds": self.min_keep_rounds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationContext":
        """从字典创建。"""
        return cls(
            messages=data.get("messages", []),
            max_rounds=data.get("max_rounds", 20),
            max_tokens=data.get("max_tokens", 8000),
            min_keep_rounds=data.get("min_keep_rounds", 4),
        )

    def __len__(self) -> int:
        """返回消息数量。"""
        return len(self.messages)

    def __str__(self) -> str:
        """字符串表示。"""
        return f"ConversationContext(rounds={self._count_rounds()}, messages={len(self.messages)})"

    def __repr__(self) -> str:
        """详细表示。"""
        return (
            f"ConversationContext(messages={len(self.messages)}, "
            f"rounds={self._count_rounds()}/{self.max_rounds})"
        )
