"""
记忆后端协议

定义记忆后端（Legacy/Enterprise）的抽象协议接口。

参考：
- docs/memory-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MemoryBackend(Protocol):
    """
    记忆后端协议。

这是定义记忆系统接口的抽象协议。
支持多种后端实现：
    - LegacyMemoryBackend: 包装现有 MemoryManager 以向后兼容
    - EnterpriseMemoryRouter: 企业级三层存储实现

示例：
    def process_with_memory(backend: MemoryBackend):
        backend.start_task("task-001", "tenant-001", "search", "搜索任务")
        context = await backend.get_injection_context("task-001", "search", "query")
        backend.end_task("task-001")
    """

    async def get_injection_context(
        self, task_id: str, task_type: str, query: str
    ) -> str:
        """
        获取用于注入系统提示词的记忆上下文。

        这是记忆系统的核心读取方法。返回可直接注入 LLM 系统提示词的格式化上下文字符串。

        对于 Enterprise 后端，返回内容包括：
        1. 系统规则 - 永久业务约束
        2. 任务上下文 - 当前任务的步骤摘要与关键变量
        3. 技能缓存 - 匹配任务类型的技能模式（可选）

        参数：
            task_id: 关联任务上下文的任务唯一标识
            task_type: 任务类型（例如 "search"、"analysis"、"generation"）
                      用于匹配技能缓存
            query: 用于语义匹配的用户查询内容（Legacy 后端使用）

        返回：
            str: 用于注入系统提示词的格式化上下文字符串。
                 若无相关上下文则返回空字符串。

        示例：
            context = await backend.get_injection_context(
                task_id="task-001",
                task_type="search",
                query="John Doe 是谁"
            )
        """
        ...

    def record_step_completion(
        self,
        task_id: str,
        step_id: str,
        step_name: str,
        summary: str,
        variables: dict[str, Any],
    ) -> None:
        """
        记录步骤完成情况。

        当 Agent 完成步骤时调用。记录内容用于：
        1. 构建任务上下文（供后续步骤参考）
        2. 生成步骤摘要（用于上下文注入）
        3. 提取关键变量（用于任务跟踪）

        注意：这是“规则写入”模式，无需 AI 自动提取，
        调用方显式传入值。

        参数：
            task_id: 任务唯一标识
            step_id: 步骤唯一标识
            step_name: 步骤名称（例如 "网页搜索"、"数据整理"）
            summary: 步骤完成摘要（建议少于 100 字符）
            variables: 本步骤提取/产出的关键变量

        示例：
            backend.record_step_completion(
                task_id="task-001",
                step_id="step-001",
                step_name="网页搜索",
                summary="搜索完成，找到 5 条相关结果",
                variables={"query": "John Doe", "result_count": 5}
            )
        """
        ...

    def record_error(
        self,
        task_id: str,
        step_id: str,
        error_type: str,
        error_message: str,
        resolution: str | None,
    ) -> None:
        """
        记录错误。

        当步骤失败或出现异常时调用。记录的错误用于：
        1. 错误跟踪与调试
        2. 生成错误报告
        3. 供后续步骤参考已知错误

        参数：
            task_id: 任务唯一标识
            step_id: 发生错误的步骤 ID
            error_type: 错误类型（例如 "NetworkError"、"TimeoutError"）
            error_message: 详细错误信息
            resolution: 若已解决则为解决方式，未解决则为 None

        示例：
            backend.record_error(
                task_id="task-001",
                step_id="step-002",
                error_type="NetworkError",
                error_message="请求超时，连接失败",
                resolution=None  # 未解决
            )

            # 成功重试后更新
            backend.record_error(
                task_id="task-001",
                step_id="step-002",
                error_type="NetworkError",
                error_message="请求超时",
                resolution="提高超时时间后重试成功"
            )
        """
        ...

    def start_task(
        self, task_id: str, tenant_id: str, task_type: str, description: str
    ) -> None:
        """
        启动任务。

        启动新任务时调用，将会：
        1. 创建任务上下文（Enterprise 后端）
        2. 初始化与任务相关的存储结构
        3. 设置 TTL（支持过期的后端）

        参数：
            task_id: 任务唯一标识
            tenant_id: 多租户隔离的租户 ID
            task_type: 任务类型（例如 "search"、"analysis"、"generation"）
            description: 简要描述任务目标

        示例：
            backend.start_task(
                task_id="task-001",
                tenant_id="tenant-001",
                task_type="search",
                description="搜索 John Doe 并生成摘要"
            )
        """
        ...

    def end_task(self, task_id: str) -> None:
        """
        结束任务。

        任务完成或中止时调用，将会：
        1. 标记任务结束
        2. 清理任务上下文（Enterprise 后端释放任务级存储）
        3. 归档任务记录（如需要）

        注意：调用该方法后，任务上下文将不再可访问
        （除非存在归档机制）。

        参数：
            task_id: 任务唯一标识

        示例：
            # 任务完成后
            backend.end_task("task-001")
        """
        ...

    def get_stats(self, task_id: str) -> dict[str, Any]:
        """
        获取统计信息。

        返回任务统计信息，用于监控与调试。

        参数：
            task_id: 任务唯一标识

        返回：
            dict：统计信息字典（具体字段因后端而异）：
                - step_count: 已完成步骤数
                - error_count: 错误数量
                - variable_count: 变量数量
                - context_size: 上下文字符数
                - created_at: 任务创建时间
                - updated_at: 最近更新时间

        示例：
            stats = backend.get_stats("task-001")
            print(f"已完成 {stats['step_count']} 步")
            print(f"遇到 {stats['error_count']} 个错误")
        """
        ...
