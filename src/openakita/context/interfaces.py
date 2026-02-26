"""
上下文模块接口定义

定义上下文系统的抽象接口，支持多种实现。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class ContextPriority(Enum):
    """上下文优先级"""
    CRITICAL = 100  # 系统核心信息，不可裁剪
    HIGH = 80       # 重要上下文，优先保留
    MEDIUM = 50     # 一般上下文
    LOW = 20        # 可选上下文，可被裁剪


class CompressionStrategy(Enum):
    """压缩策略"""
    SLIDING_WINDOW = "sliding_window"  # 滑动窗口
    SUMMARY = "summary"                 # LLM 摘要压缩
    PRIORITY = "priority"               # 按优先级裁剪
    HYBRID = "hybrid"                   # 混合策略


@runtime_checkable
class IContext(Protocol):
    """
    上下文接口协议

    所有上下文类型都应实现此接口。
    """

    def to_prompt(self) -> str:
        """将上下文转换为提示词格式"""
        ...

    def estimate_tokens(self) -> int:
        """估算上下文的 Token 数量"""
        ...

    def clear(self) -> None:
        """清空上下文"""
        ...


class ISystemContext(IContext, Protocol):
    """
    系统上下文协议

    永久层上下文，包含身份、规则、能力清单。
    启动时初始化一次，运行时只读（除能力清单可刷新）。
    """

    @property
    def identity(self) -> str:
        """Agent 身份描述"""
        ...

    @property
    def rules(self) -> list[str]:
        """行为规则列表"""
        ...

    @property
    def capabilities_manifest(self) -> str:
        """能力清单"""
        ...

    @property
    def policies(self) -> list[str]:
        """策略列表"""
        ...

    def refresh_capabilities(self, manifest: str) -> None:
        """刷新能力清单"""
        ...


class ITaskContext(IContext, Protocol):
    """
    任务上下文协议

    任务生命周期层上下文，包含目标、进度、变量。
    支持检查点和回滚。
    """

    @property
    def task_id(self) -> str:
        """任务 ID"""
        ...

    @property
    def tenant_id(self) -> str:
        """租户 ID"""
        ...

    @property
    def task_description(self) -> str:
        """任务描述"""
        ...

    def add_step_summary(self, step_name: str, summary: str) -> None:
        """添加步骤摘要"""
        ...

    def add_variables(self, variables: dict[str, Any]) -> None:
        """添加任务变量"""
        ...

    def save_checkpoint(self, state: dict) -> str:
        """保存检查点，返回检查点 ID"""
        ...

    def rollback(self, checkpoint_id: str) -> dict | None:
        """回滚到检查点，返回检查点状态"""
        ...


class IConversationContext(IContext, Protocol):
    """
    会话上下文协议

    滑动窗口层上下文，包含消息历史。
    支持 Token 预算和压缩策略。
    """

    @property
    def max_rounds(self) -> int:
        """最大轮数"""
        ...

    @property
    def max_tokens(self) -> int:
        """最大 Token 预算"""
        ...

    def add_message(self, role: str, content: str | list[dict]) -> None:
        """添加消息，自动执行限制策略"""
        ...

    def get_messages(self) -> list[dict]:
        """获取消息列表"""
        ...


class ICompressor(ABC):
    """
    上下文压缩器抽象基类

    支持多种压缩策略。
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
        messages: list[dict],
        target_tokens: int,
    ) -> tuple[str, list[dict]]:
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


class IContextOrchestrator(ABC):
    """
    上下文编排器抽象基类

    协调三层上下文，动态分配 Token 预算。
    """

    @abstractmethod
    def create_task(
        self,
        task_id: str,
        tenant_id: str,
        description: str,
        **kwargs,
    ) -> ITaskContext:
        """创建任务上下文"""
        ...

    @abstractmethod
    def get_or_create_conversation(self, session_id: str) -> IConversationContext:
        """获取或创建会话上下文"""
        ...

    @abstractmethod
    def build_context(
        self,
        task_id: str,
        session_id: str,
    ) -> tuple[str, list[dict]]:
        """
        构建完整上下文

        Returns:
            (system_prompt, messages)
        """
        ...

    @abstractmethod
    def end_task(self, task_id: str) -> None:
        """结束任务，清理任务上下文"""
        ...

    @abstractmethod
    def clear_session(self, session_id: str) -> None:
        """清空会话"""
        ...