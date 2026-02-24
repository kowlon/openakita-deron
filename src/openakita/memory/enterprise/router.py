"""
企业级记忆路由器

统一的记忆路由器，协调三层存储：
1. 系统规则 - 永久业务约束
2. 任务上下文 - 任务级步骤摘要与变量
3. 技能 - 可选的技能模式缓存

该路由器实现 MemoryBackend 协议，为 Agent 提供与记忆系统交互的
统一接口。

参考：
- docs/memory-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

from typing import Any

from openakita.memory.enterprise.config import EnterpriseMemoryConfig
from openakita.memory.enterprise.rules import SystemRuleStore
from openakita.memory.enterprise.task_context import TaskContextStore


class EnterpriseMemoryRouter:
    """
    企业级记忆路由器。

    这是企业级记忆系统的主要入口。
    它协调三层存储并实现 MemoryBackend 协议。

    第一层 - 系统规则（永久）：
        从配置文件加载规则。这些业务约束适用于所有任务，
        且不能被 AI 修改。

    第二层 - 任务上下文（任务生命周期）：
        当前任务的步骤摘要与关键变量。
        在任务开始时创建，任务结束时销毁。

    第三层 - 技能（可选）：
        与任务类型匹配的技能模式缓存。
        本版本未实现。

    示例：
        config = EnterpriseMemoryConfig(rules_path="config/rules.yaml")
        router = EnterpriseMemoryRouter(config)

        # 开始任务
        router.start_task("task-001", "tenant-001", "search", "Search for info")

        # 记录进展
        router.record_step_completion(
            "task-001", "step-001", "Web Search",
            "Found 5 results", {"query": "info"}
        )

        # 获取用于提示词注入的上下文
        context = await router.get_injection_context("task-001", "search", "query")

        # 结束任务（清理任务上下文）
        router.end_task("task-001")
    """

    def __init__(self, config: EnterpriseMemoryConfig | None = None) -> None:
        """
        初始化记忆路由器。

        参数：
            config: 路由器配置。如为 None，则使用默认值。
        """
        self._config = config or EnterpriseMemoryConfig()

        # 第一层：系统规则（永久）
        self._rule_store = SystemRuleStore()
        if self._config.rules_path:
            self._load_rules(self._config.rules_path)

        # 第二层：任务上下文（任务生命周期）
        self._task_store = TaskContextStore()

        # 第三层：技能（可选，尚未实现）
        # self._skill_store = SkillStore() if config.skills_path else None
        self._skill_store = None

    def _load_rules(self, path: str) -> None:
        """
        从配置文件加载系统规则。

        参数：
            path: YAML 或 JSON 文件路径
        """
        if path.endswith(".yaml") or path.endswith(".yml"):
            self._rule_store.load_from_yaml(path)
        elif path.endswith(".json"):
            self._rule_store.load_from_json(path)
        else:
            raise ValueError(f"Unsupported rules file format: {path}")

    # ========== MemoryBackend 协议实现 ==========

    async def get_injection_context(
        self, task_id: str, task_type: str, query: str
    ) -> str:
        """
        获取用于系统提示词注入的记忆上下文。

        上下文来自三层汇总：
        1. 系统规则（若存在则始终包含）
        2. 任务上下文（若任务存在则包含）
        3. 技能（可选，按任务类型匹配）

        参数：
            task_id: 任务唯一标识
            task_type: 用于技能匹配的任务类型
            query: 用户查询（未来用于语义匹配）

        返回：
            用于系统提示词注入的格式化上下文字符串
        """
        sections: list[str] = []

        # 第一层：系统规则
        rules_prompt = self._rule_store.to_prompt()
        if rules_prompt:
            sections.append(rules_prompt)

        # 第二层：任务上下文
        task_prompt = self._task_store.to_prompt(task_id)
        if task_prompt:
            sections.append(task_prompt)

        # 第三层：技能（可选）
        # if self._skill_store:
        #     skills_prompt = self._skill_store.to_prompt(task_type)
        #     if skills_prompt:
        #         sections.append(skills_prompt)

        return "\n\n".join(sections) if sections else ""

    def record_step_completion(
        self,
        task_id: str,
        step_id: str,
        step_name: str,
        summary: str,
        variables: dict[str, Any],
    ) -> None:
        """
        记录任务的步骤完成情况。

        参数：
            task_id: 任务唯一标识
            step_id: 步骤唯一标识
            step_name: 步骤名称
            summary: 步骤完成摘要
            variables: 本步骤提取的关键变量
        """
        self._task_store.record_step_completion(
            task_id, step_id, step_name, summary, variables
        )

    def record_error(
        self,
        task_id: str,
        step_id: str,
        error_type: str,
        error_message: str,
        resolution: str | None,
    ) -> None:
        """
        记录任务错误。

        参数：
            task_id: 任务唯一标识
            step_id: 出错的步骤
            error_type: 错误类型
            error_message: 错误信息
            resolution: 若已解决则为解决方案，否则为 None
        """
        self._task_store.record_error(
            task_id, step_id, error_type, error_message, resolution
        )

    def start_task(
        self, task_id: str, tenant_id: str, task_type: str, description: str
    ) -> None:
        """
        启动新任务。

        参数：
            task_id: 任务唯一标识
            tenant_id: 多租户隔离的租户 ID
            task_type: 任务类型
            description: 任务描述/目标
        """
        self._task_store.start_task(task_id, tenant_id, task_type, description)

    def end_task(self, task_id: str) -> None:
        """
        结束任务并清理其上下文。

        参数：
            task_id: 任务唯一标识
        """
        self._task_store.end_task(task_id)

    def get_stats(self, task_id: str) -> dict[str, Any]:
        """
        获取任务统计信息。

        参数：
            task_id: 任务唯一标识

        返回：
            任务统计信息字典
        """
        task_stats = self._task_store.get_stats(task_id)

        # 增加规则数量
        task_stats["rule_count"] = self._rule_store.rule_count

        # 若任务存在则增加上下文大小
        if task_stats:
            context = self._task_store.to_prompt(task_id)
            task_stats["context_size"] = len(context)

        return task_stats

    # ========== 额外辅助方法 ==========

    @property
    def rule_store(self) -> SystemRuleStore:
        """获取底层规则存储以便直接操作。"""
        return self._rule_store

    @property
    def task_store(self) -> TaskContextStore:
        """获取底层任务存储以便直接操作。"""
        return self._task_store

    def get_tasks_by_tenant(self, tenant_id: str) -> list[Any]:
        """
        获取某租户的全部活跃任务。

        参数：
            tenant_id: 租户标识

        返回：
            该租户的任务记忆对象列表
        """
        return self._task_store.get_tasks_by_tenant(tenant_id)

    @property
    def active_task_count(self) -> int:
        """获取活跃任务数量。"""
        return self._task_store.task_count

    def clear_all_tasks(self) -> None:
        """清理所有任务上下文。"""
        self._task_store.clear_all()

    def clear_all_rules(self) -> None:
        """清理所有系统规则。"""
        self._rule_store.clear_rules()

    def reload_rules(self, path: str | None = None) -> None:
        """
        从配置文件重新加载系统规则。

        参数：
            path: 规则文件路径。如为 None，则使用 config.rules_path。
        """
        rules_path = path or self._config.rules_path
        if rules_path:
            self._rule_store.clear_rules()
            self._load_rules(rules_path)
            # 更新配置，记录路径以便后续重载
            self._config.rules_path = rules_path
