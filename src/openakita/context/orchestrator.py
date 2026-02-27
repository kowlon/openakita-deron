"""
上下文编排器

协调三层上下文，动态分配 Token 预算，构建完整的 LLM 上下文。

参考：
- docs/refactor/20260226_enterprise_self_evolution_agent.md
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .budget_controller import BudgetController, BudgetState
from .config import ContextConfig, TokenBudget
from .conversation_context import ConversationContext
from .exceptions import (
    ContextError,
    SessionContextNotFoundError,
    TaskContextNotFoundError,
)
from .interfaces import IContextOrchestrator, IConversationContext, ITaskContext
from .system_context import SystemContext
from .task_context import TaskContext
from .compressor import CompressionStrategy, create_compressor

if TYPE_CHECKING:
    from .interfaces import ICompressor

logger = logging.getLogger(__name__)


@dataclass
class ContextOrchestrator(IContextOrchestrator):
    """
    上下文编排器

    协调三层上下文：
    - SystemContext: 永久层（身份、规则、能力）
    - TaskContext: 任务层（目标、进度、变量）
    - ConversationContext: 会话层（消息历史）

    功能：
    - 创建和管理任务/会话上下文
    - 动态分配 Token 预算
    - 组装完整上下文供 LLM 使用
    - 触发压缩策略

    属性：
        system_context: 系统上下文（永久层）
        config: 上下文配置
        budget_controller: 预算控制器
        compressor: 压缩器实例
    """

    system_context: SystemContext
    config: ContextConfig = field(default_factory=ContextConfig)
    budget_controller: BudgetController = field(default_factory=BudgetController)
    compressor: ICompressor | None = None

    # 运行时状态
    _tasks: dict[str, TaskContext] = field(default_factory=dict)
    _conversations: dict[str, ConversationContext] = field(default_factory=dict)

    def __post_init__(self):
        """初始化后处理"""
        if self.compressor is None:
            self.compressor = create_compressor(CompressionStrategy.SLIDING_WINDOW)

    # ==================== IContextOrchestrator 接口实现 ====================

    def create_task(
        self,
        task_id: str,
        tenant_id: str,
        description: str,
        **kwargs,
    ) -> ITaskContext:
        """
        创建任务上下文。

        Args:
            task_id: 任务 ID
            tenant_id: 租户 ID
            description: 任务描述
            **kwargs: 额外参数（task_type, total_steps 等）

        Returns:
            创建的任务上下文
        """
        if task_id in self._tasks:
            logger.warning(f"[Orchestrator] Task {task_id} already exists, returning existing")
            return self._tasks[task_id]

        task = TaskContext(
            task_id=task_id,
            tenant_id=tenant_id,
            task_type=kwargs.get("task_type", "general"),
            task_description=description,
            total_steps=kwargs.get("total_steps", 0),
            max_tokens=self.config.max_task_tokens,
        )

        self._tasks[task_id] = task
        logger.info(f"[Orchestrator] Created task: {task_id}")

        return task

    def get_or_create_conversation(self, session_id: str) -> IConversationContext:
        """
        获取或创建会话上下文。

        Args:
            session_id: 会话 ID

        Returns:
            会话上下文
        """
        if session_id not in self._conversations:
            self._conversations[session_id] = ConversationContext(
                max_rounds=self.config.max_conversation_rounds,
                max_tokens=self.config.max_conversation_tokens,
            )
            logger.info(f"[Orchestrator] Created conversation: {session_id}")

        return self._conversations[session_id]

    def build_context(
        self,
        task_id: str,
        session_id: str,
    ) -> tuple[str, list[dict]]:
        """
        构建完整上下文。

        组装三层上下文，检查预算，必要时触发压缩。

        Args:
            task_id: 任务 ID
            session_id: 会话 ID

        Returns:
            (system_prompt, messages) 元组
        """
        # 获取各层上下文
        task = self._tasks.get(task_id)
        conversation = self._conversations.get(session_id)

        # 构建系统提示
        system_parts = [self.system_context.to_prompt()]

        if task:
            task_prompt = task.to_prompt()
            if task_prompt:
                system_parts.append(task_prompt)

        system_prompt = "\n\n".join(system_parts)

        # 获取消息历史
        messages = conversation.to_messages() if conversation else []

        # 检查预算
        system_tokens = self._estimate_tokens(system_prompt)
        conversation_tokens = sum(
            self._estimate_message_tokens(m) for m in messages
        )

        budget_result = self.budget_controller.check_budget(
            system_tokens=system_tokens,
            conversation_tokens=conversation_tokens,
        )

        # 根据预算状态处理
        if budget_result.needs_compression and self.compressor:
            logger.info(
                f"[Orchestrator] Budget {budget_result.state.value}, "
                f"triggering compression"
            )

            target_tokens = self.budget_controller.get_target_tokens(
                system_tokens + conversation_tokens
            )

            system_prompt, messages = self.compressor.compress(
                system_prompt=system_prompt,
                messages=messages,
                target_tokens=target_tokens,
            )

        return system_prompt, messages

    def end_task(self, task_id: str) -> None:
        """
        结束任务，清理任务上下文。

        Args:
            task_id: 任务 ID
        """
        if task_id in self._tasks:
            del self._tasks[task_id]
            logger.info(f"[Orchestrator] Ended task: {task_id}")

    def clear_session(self, session_id: str) -> None:
        """
        清空会话。

        Args:
            session_id: 会话 ID
        """
        if session_id in self._conversations:
            self._conversations[session_id].clear()
            logger.info(f"[Orchestrator] Cleared session: {session_id}")

    # ==================== 扩展方法 ====================

    def get_task(self, task_id: str) -> TaskContext:
        """
        获取任务上下文。

        Args:
            task_id: 任务 ID

        Returns:
            任务上下文

        Raises:
            TaskContextNotFoundError: 任务不存在
        """
        if task_id not in self._tasks:
            raise TaskContextNotFoundError(task_id)
        return self._tasks[task_id]

    def get_conversation(self, session_id: str) -> ConversationContext:
        """
        获取会话上下文。

        Args:
            session_id: 会话 ID

        Returns:
            会话上下文

        Raises:
            SessionContextNotFoundError: 会话不存在
        """
        if session_id not in self._conversations:
            raise SessionContextNotFoundError(session_id)
        return self._conversations[session_id]

    def has_task(self, task_id: str) -> bool:
        """检查任务是否存在"""
        return task_id in self._tasks

    def has_conversation(self, session_id: str) -> bool:
        """检查会话是否存在"""
        return session_id in self._conversations

    def list_tasks(self) -> list[str]:
        """列出所有任务 ID"""
        return list(self._tasks.keys())

    def list_conversations(self) -> list[str]:
        """列出所有会话 ID"""
        return list(self._conversations.keys())

    def add_message_to_conversation(
        self,
        session_id: str,
        role: str,
        content: str | list[dict],
    ) -> None:
        """
        向会话添加消息。

        Args:
            session_id: 会话 ID
            role: 角色
            content: 内容
        """
        conversation = self.get_or_create_conversation(session_id)
        conversation.add_message(role, content)

    def get_stats(self) -> dict[str, Any]:
        """
        获取编排器统计信息。

        Returns:
            统计信息字典
        """
        return {
            "tasks_count": len(self._tasks),
            "conversations_count": len(self._conversations),
            "system_context_stats": self.system_context.get_stats(),
            "budget_status": self.budget_controller.get_status_report(),
            "config": {
                "max_conversation_rounds": self.config.max_conversation_rounds,
                "max_task_summaries": self.config.max_task_summaries,
            },
        }

    def _estimate_tokens(self, text: str) -> int:
        """估算文本 Token 数"""
        return int(len(text) / 4.0)

    def _estimate_message_tokens(self, message: dict) -> int:
        """估算消息 Token 数"""
        content = message.get("content", "")
        if isinstance(content, str):
            return self._estimate_tokens(content) + 4
        elif isinstance(content, list):
            total = 4
            for block in content:
                if isinstance(block, dict):
                    total += self._estimate_tokens(str(block.get("text", "")))
            return total
        return 100

    @classmethod
    def create_default(
        cls,
        identity: str = "AI Assistant",
        rules: list[str] | None = None,
        config: ContextConfig | None = None,
    ) -> "ContextOrchestrator":
        """
        创建默认的编排器实例。

        Args:
            identity: Agent 身份
            rules: 行为规则
            config: 上下文配置

        Returns:
            编排器实例
        """
        system_context = SystemContext(
            identity=identity,
            rules=rules or [],
        )

        return cls(
            system_context=system_context,
            config=config or ContextConfig(),
        )


# 便捷工厂函数
def create_orchestrator(
    identity: str = "AI Assistant",
    rules: list[str] | None = None,
    config: ContextConfig | None = None,
) -> ContextOrchestrator:
    """
    创建上下文编排器。

    Args:
        identity: Agent 身份
        rules: 行为规则
        config: 上下文配置

    Returns:
        编排器实例
    """
    return ContextOrchestrator.create_default(
        identity=identity,
        rules=rules,
        config=config,
    )