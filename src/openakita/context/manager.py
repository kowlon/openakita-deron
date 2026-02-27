"""
企业级上下文管理器

统一的上下文管理器，负责协调三层上下文：
1. SystemContext - 永久层（身份、规则、工具）
2. TaskContext - 任务生命周期层（步骤摘要、变量）
3. ConversationContext - 滑动窗口层（消息历史）

内部使用 ContextOrchestrator 进行上下文协调。

参考：
- docs/context-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""
from __future__ import annotations

from typing import Any

from openakita.context.config import ContextConfig
from openakita.context.orchestrator import ContextOrchestrator
from openakita.context.conversation_context import ConversationContext
from openakita.context.system_context import SystemContext
from openakita.context.task_context import TaskContext


class EnterpriseContextManager:
    """
    企业级上下文管理器 - 统一的上下文协调器。

    管理三层上下文：
        - SystemContext: 永久层，启动时初始化一次
        - TaskContext: 任务级生命周期，随任务创建/销毁
        - ConversationContext: 会话级滑动窗口

    内部使用 ContextOrchestrator 进行：
        - 上下文协调
        - Token 预算控制
        - 优先级调度
        - 自动压缩

    该管理器提供 build_context() 方法，将三层内容组装为 LLM API 所需格式。

    示例：
        config = ContextConfig(max_conversation_rounds=20)
        manager = EnterpriseContextManager(config)

        # 初始化系统上下文（启动时一次）
        manager.initialize(
            identity="我是一个有帮助的助手",
            rules=["保持有帮助", "确保安全"],
            tools_manifest="search, calculator"
        )

        # 启动任务
        manager.start_task("task-001", "tenant-001", "search", "搜索信息")

        # 添加对话
        manager.add_message("session-001", "user", "你好")

        # 构建用于 LLM 的上下文
        system_prompt, messages = manager.build_context("task-001", "session-001")

        # 结束任务
        manager.end_task("task-001")
    """

    def __init__(self, config: ContextConfig | None = None):
        """
        初始化上下文管理器。

        参数：
            config: 配置对象。未提供则使用默认值。
        """
        self.config = config or ContextConfig()

        # 创建 SystemContext（稍后通过 initialize() 配置）
        self.system_ctx = SystemContext()

        # 创建 ContextOrchestrator
        self._orchestrator = ContextOrchestrator(
            system_context=self.system_ctx,
            config=self.config,
        )

    def initialize(
        self,
        identity: str,
        rules: list[str] | None = None,
        tools_manifest: str | None = None,
    ) -> None:
        """
        初始化系统上下文。

        应在应用启动时调用一次。

        参数：
            identity: Agent 身份描述
            rules: 行为规则列表
            tools_manifest: 可用工具描述
        """
        self.system_ctx.identity = identity
        self.system_ctx.rules = rules or []
        self.system_ctx.capabilities_manifest = tools_manifest or ""

    def start_task(
        self,
        task_id: str,
        tenant_id: str,
        task_type: str,
        description: str,
        total_steps: int = 0,
    ) -> TaskContext:
        """
        启动新的任务上下文。

        参数：
            task_id: 任务唯一标识
            tenant_id: 多租户隔离的租户 ID
            task_type: 任务类型
            description: 任务描述/目标
            total_steps: 预计步骤数量（未知则为 0）

        返回：
            创建的 TaskContext
        """
        return self._orchestrator.create_task(
            task_id=task_id,
            tenant_id=tenant_id,
            description=description,
            task_type=task_type,
            total_steps=total_steps,
        )

    def end_task(self, task_id: str) -> bool:
        """
        结束任务并清理其上下文。

        参数：
            task_id: 任务标识

        返回：
            若找到并移除任务则为 True
        """
        if self._orchestrator.has_task(task_id):
            self._orchestrator.end_task(task_id)
            return True
        return False

    def get_task(self, task_id: str) -> TaskContext | None:
        """
        根据 ID 获取任务上下文。

        参数：
            task_id: 任务标识

        返回：
            若存在则返回 TaskContext，否则为 None
        """
        try:
            return self._orchestrator.get_task(task_id)
        except Exception:
            return None

    def record_step(
        self,
        task_id: str,
        step_id: str,
        step_name: str,
        summary: str,
        variables: dict[str, Any] | None = None,
    ) -> bool:
        """
        在任务上下文中记录步骤完成。

        参数：
            task_id: 任务标识
            step_id: 步骤标识
            step_name: 步骤名称
            summary: 完成摘要
            variables: 本步骤的关键变量

        返回：
            若任务存在且记录成功则为 True
        """
        task = self.get_task(task_id)
        if not task:
            return False

        task.add_step_summary(step_name, summary)
        if variables:
            task.add_variables(variables)
        return True

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str | list[dict[str, Any]],
    ) -> None:
        """
        向会话上下文添加消息。

        参数：
            session_id: 会话标识
            role: 消息角色
            content: 消息内容
        """
        self._orchestrator.add_message_to_conversation(session_id, role, content)

    def get_conversation(self, session_id: str) -> ConversationContext | None:
        """
        根据会话 ID 获取会话上下文。

        参数：
            session_id: 会话标识

        返回：
            若存在则返回 ConversationContext，否则为 None
        """
        try:
            return self._orchestrator.get_conversation(session_id)
        except Exception:
            return None

    def clear_session(self, session_id: str) -> bool:
        """
        清理会话内容。

        参数：
            session_id: 会话标识

        返回：
            若找到并清理则为 True
        """
        if self._orchestrator.has_conversation(session_id):
            self._orchestrator.clear_session(session_id)
            return True
        return False

    def build_context(
        self, task_id: str, session_id: str
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        构建用于 LLM API 调用的完整上下文。

        组装三层内容：
        1. 系统上下文（身份、规则、工具）
        2. 任务上下文（描述、步骤、变量）
        3. 会话上下文（消息历史）

        参数：
            task_id: 任务标识
            session_id: 会话标识

        返回：
            (system_prompt, messages) 元组
        """
        return self._orchestrator.build_context(task_id, session_id)

    def build_context_with_priority(
        self, task_id: str, session_id: str
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        带优先级感知的上下文构建。

        参数：
            task_id: 任务标识
            session_id: 会话标识

        返回：
            (system_prompt, messages) 元组
        """
        return self._orchestrator.build_context_with_priority(task_id, session_id)

    def get_stats(self, task_id: str, session_id: str) -> dict[str, Any]:
        """
        获取上下文统计信息。

        参数：
            task_id: 任务标识
            session_id: 会话标识

        返回：
            包含各层统计的字典
        """
        stats = {
            "system": None,
            "task": None,
            "conversation": None,
            "total_estimated_tokens": 0,
        }

        if self.system_ctx:
            stats["system"] = self.system_ctx.get_stats()
            stats["total_estimated_tokens"] += stats["system"]["estimated_tokens"]

        task = self.get_task(task_id)
        if task:
            stats["task"] = task.get_stats()
            stats["total_estimated_tokens"] += stats["task"]["estimated_tokens"]

        conv = self.get_conversation(session_id)
        if conv:
            stats["conversation"] = conv.get_stats()
            stats["total_estimated_tokens"] += conv.estimate_tokens()

        return stats

    def get_task_count(self) -> int:
        """获取活跃任务数量。"""
        return len(self._orchestrator.list_tasks())

    def get_session_count(self) -> int:
        """获取活跃会话数量。"""
        return len(self._orchestrator.list_conversations())

    def clear_all(self) -> None:
        """清空所有任务与会话上下文（保留系统上下文）。"""
        # 先结束所有任务
        for task_id in self._orchestrator.list_tasks():
            self._orchestrator.end_task(task_id)

        # 清空并删除所有会话
        for session_id in self._orchestrator.list_conversations():
            conv = self._orchestrator.get_conversation(session_id)
            if conv:
                conv.clear()
            # 从内部字典中删除会话
            if session_id in self._orchestrator._conversations:
                del self._orchestrator._conversations[session_id]

    def get_orchestrator(self) -> ContextOrchestrator:
        """
        获取内部的 ContextOrchestrator 实例。

        用于高级操作，如设置任务优先级。

        返回：
            ContextOrchestrator 实例
        """
        return self._orchestrator