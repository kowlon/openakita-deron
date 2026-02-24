"""
企业级上下文管理器

统一的上下文管理器，负责协调三层上下文：
1. SystemContext - 永久层（身份、规则、工具）
2. TaskContext - 任务生命周期层（步骤摘要、变量）
3. ConversationContext - 滑动窗口层（消息历史）

参考：
- docs/context-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

from typing import Any

from openakita.context.enterprise.config import ContextConfig
from openakita.context.enterprise.conversation_context import ConversationContext
from openakita.context.enterprise.system_context import SystemContext
from openakita.context.enterprise.task_context import TaskContext


class EnterpriseContextManager:
    """
    企业级上下文管理器 - 统一的上下文协调器。

管理三层上下文：
    - SystemContext: 永久层，启动时初始化一次
    - TaskContext: 任务级生命周期，随任务创建/销毁
    - ConversationContext: 会话级滑动窗口

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
        self.system_ctx: SystemContext | None = None
        self.task_contexts: dict[str, TaskContext] = {}
        self.conversation_contexts: dict[str, ConversationContext] = {}

    # ========== 初始化 ==========

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
        self.system_ctx = SystemContext(
            identity=identity,
            rules=rules or [],
            tools_manifest=tools_manifest or "",
            max_tokens=self.config.max_system_tokens,
        )

    # ========== 任务管理 ==========

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
        ctx = TaskContext(
            task_id=task_id,
            tenant_id=tenant_id,
            task_type=task_type,
            task_description=description,
            total_steps=total_steps,
        )
        self.task_contexts[task_id] = ctx
        return ctx

    def end_task(self, task_id: str) -> bool:
        """
        结束任务并清理其上下文。

        参数：
            task_id: 任务标识

        返回：
            若找到并移除任务则为 True
        """
        if task_id in self.task_contexts:
            del self.task_contexts[task_id]
            # 清理关联的会话上下文
            to_remove = [
                sid
                for sid in self.conversation_contexts
                if sid.startswith(f"{task_id}:")
            ]
            for sid in to_remove:
                del self.conversation_contexts[sid]
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
        return self.task_contexts.get(task_id)

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
        ctx = self.task_contexts.get(task_id)
        if not ctx:
            return False

        ctx.add_step_summary(step_name, summary)
        if variables:
            ctx.add_variables(variables)
        return True

    # ========== 会话管理 ==========

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
        if session_id not in self.conversation_contexts:
            self.conversation_contexts[session_id] = ConversationContext(
                max_rounds=self.config.max_conversation_rounds,
                max_tokens=self.config.max_conversation_tokens,
            )

        self.conversation_contexts[session_id].add_message(role, content)

    def get_conversation(self, session_id: str) -> ConversationContext | None:
        """
        根据会话 ID 获取会话上下文。

        参数：
            session_id: 会话标识

        返回：
            若存在则返回 ConversationContext，否则为 None
        """
        return self.conversation_contexts.get(session_id)

    def clear_session(self, session_id: str) -> bool:
        """
        清理会话内容。

        参数：
            session_id: 会话标识

        返回：
            若找到并清理则为 True
        """
        if session_id in self.conversation_contexts:
            self.conversation_contexts[session_id].clear()
            return True
        return False

    # ========== 上下文构建 ==========

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
        parts = []

        # 第 1 层：系统上下文
        if self.system_ctx:
            parts.append(self.system_ctx.to_prompt())

        # 第 2 层：任务上下文
        task_ctx = self.task_contexts.get(task_id)
        if task_ctx:
            parts.append(task_ctx.to_prompt())

        # 合并系统部分
        system_prompt = "\n\n---\n\n".join(parts) if parts else ""

        # 第 3 层：会话上下文
        conv_ctx = self.conversation_contexts.get(session_id)
        messages = conv_ctx.to_messages() if conv_ctx else []

        return system_prompt, messages

    # ========== 统计信息 ==========

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

        # 系统统计
        if self.system_ctx:
            stats["system"] = self.system_ctx.get_stats()
            stats["total_estimated_tokens"] += stats["system"]["estimated_tokens"]

        # 任务统计
        task_ctx = self.task_contexts.get(task_id)
        if task_ctx:
            stats["task"] = task_ctx.get_stats()
            stats["total_estimated_tokens"] += stats["task"]["estimated_tokens"]

        # 会话统计
        conv_ctx = self.conversation_contexts.get(session_id)
        if conv_ctx:
            stats["conversation"] = conv_ctx.get_stats()
            stats["total_estimated_tokens"] += conv_ctx.estimate_tokens()

        return stats

    def get_task_count(self) -> int:
        """获取活跃任务数量。"""
        return len(self.task_contexts)

    def get_session_count(self) -> int:
        """获取活跃会话数量。"""
        return len(self.conversation_contexts)

    def clear_all(self) -> None:
        """清空所有任务与会话上下文（保留系统上下文）。"""
        self.task_contexts.clear()
        self.conversation_contexts.clear()
