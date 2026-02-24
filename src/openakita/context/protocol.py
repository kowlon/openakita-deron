"""
上下文后端协议

定义上下文后端的抽象协议接口。
上下文系统管理对话历史，并为 LLM 交互组装上下文。

参考：
- docs/context-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ContextBackend(Protocol):
    """
    上下文后端协议。

这是定义上下文系统接口的抽象协议。
支持多种后端实现：
    - EnterpriseContextManager: 企业级三层上下文实现
    - 自定义后端：实现本协议即可扩展

上下文系统提供：
    1. 系统上下文（身份、规则、工具清单）- 永久层
    2. 任务上下文（步骤摘要、关键变量）- 任务生命周期层
    3. 会话上下文（消息历史）- 滑动窗口层

关键优化：使用滑动窗口替代 LLM 压缩，
将上下文构建延迟从 2-5 秒降低到 <50ms。

示例：
    def process_with_context(backend: ContextBackend):
        backend.initialize(identity="我是一个助手", rules=["保持有帮助"])
        backend.start_task("task-001", "tenant-001", "search", "搜索任务")
        backend.add_message("session-001", "user", "你好")

        system_prompt, messages = backend.build_context("task-001", "session-001")

        backend.end_task("task-001")
        backend.clear_session("session-001")
    """

    def build_context(
        self, task_id: str, session_id: str
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        构建用于 LLM 交互的完整上下文。

        从三层组装上下文：
        1. 系统上下文（身份、规则、工具）
        2. 任务上下文（步骤摘要、变量）
        3. 会话上下文（滑动窗口的消息历史）

        参数：
            task_id: 任务级上下文的任务标识
            session_id: 对话历史的会话标识

        返回：
            包含以下内容的元组：
            - str: 包含身份、规则与任务上下文的系统提示词
            - list[dict]: 含 role 与 content 的消息字典列表

        示例：
            system_prompt, messages = backend.build_context("task-001", "session-001")
            # system_prompt 包含：身份 + 规则 + 任务上下文
            # messages 包含：对话历史（最多 20 轮）
        """
        ...

    def add_message(
        self, session_id: str, role: str, content: str | list[dict[str, Any]]
    ) -> None:
        """
        向会话历史添加消息。

        消息按会话存储，并会被包含在 build_context 调用中。
        滑动窗口会限制对话轮数（默认：20 轮）。

        参数：
            session_id: 会话标识
            role: 消息角色（"user"、"assistant"、"tool"、"system"）
            content: 消息内容（字符串或内容块列表）

        示例：
            backend.add_message("session-001", "user", "你好")
            backend.add_message("session-001", "assistant", [
                {"type": "text", "text": "你好！"},
                {"type": "tool_use", "id": "tool-1", "name": "search", "input": {}}
            ])
            backend.add_message("session-001", "tool", {
                "tool_call_id": "tool-1",
                "content": "搜索结果..."
            })
        """
        ...

    def get_stats(self, task_id: str, session_id: str) -> dict[str, Any]:
        """
        获取上下文统计信息。

        返回当前上下文状态的统计数据，用于监控与调试。

        参数：
            task_id: 任务标识
            session_id: 会话标识

        返回：
            dict：包含以下统计信息：
                - system_tokens: 系统上下文的估算 token 数
                - task_tokens: 任务上下文的估算 token 数
                - conversation_tokens: 会话的估算 token 数
                - conversation_rounds: 对话轮数
                - step_count: 记录的任务步骤数
                - variable_count: 关键变量数量

        示例：
            stats = backend.get_stats("task-001", "session-001")
            print(f"上下文大小: {stats['system_tokens'] + stats['conversation_tokens']} tokens")
        """
        ...

    def clear_session(self, session_id: str) -> None:
        """
        清空会话数据。

        移除指定会话的所有对话历史。
        在开始新会话或清理时调用。

        参数：
            session_id: 要清理的会话标识

        示例：
            backend.clear_session("session-001")
        """
        ...

    def initialize(
        self,
        identity: str,
        rules: list[str] | None = None,
        tools_manifest: str | None = None,
    ) -> None:
        """
        初始化系统上下文。

        设置永久的系统上下文层，包括 Agent 身份、规则与可用工具。
        必须在使用其他方法之前调用。

        参数：
            identity: Agent 身份描述（我是谁）
            rules: 行为规则/约束列表
            tools_manifest: 可用工具描述

        示例：
            backend.initialize(
                identity="我是一个有帮助的 AI 助手",
                rules=[
                    "始终保持尊重",
                    "不要分享敏感信息"
                ],
                tools_manifest="可用工具：search、calculator、file_reader"
            )
        """
        ...

    def start_task(
        self, task_id: str, tenant_id: str, task_type: str, description: str
    ) -> None:
        """
        启动任务上下文。

        为指定任务初始化任务级上下文。
        任务上下文包含步骤摘要与关键变量，并在任务执行中累积。

        参数：
            task_id: 任务唯一标识
            tenant_id: 多租户隔离的租户 ID
            task_type: 任务类型（例如 "search"、"analysis"）
            description: 任务目标的简要描述

        示例：
            backend.start_task(
                task_id="task-001",
                tenant_id="tenant-001",
                task_type="search",
                description="搜索关于 X 的信息"
            )
        """
        ...

    def end_task(self, task_id: str) -> None:
        """
        结束任务上下文。

        清理任务级上下文。在任务完成或取消时调用。

        参数：
            task_id: 要结束的任务标识

        示例：
            backend.end_task("task-001")
        """
        ...

    def record_step(
        self,
        task_id: str,
        step_id: str,
        step_name: str,
        summary: str,
        variables: dict[str, Any],
    ) -> None:
        """
        在任务上下文中记录步骤完成。

        将步骤信息添加到任务上下文，用于后续的上下文构建。

        参数：
            task_id: 任务标识
            step_id: 步骤标识
            step_name: 可读的步骤名称
            summary: 该步骤完成内容的简要摘要
            variables: 本步骤提取/使用的关键变量

        示例：
            backend.record_step(
                task_id="task-001",
                step_id="step-001",
                step_name="网页搜索",
                summary="找到 5 条相关结果",
                variables={"query": "test", "result_count": 5}
            )
        """
        ...
