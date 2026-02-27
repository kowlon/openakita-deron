"""
能力注册表

统一管理所有能力的注册、发现和调用。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from .types import CapabilityMeta, CapabilityStatus, CapabilityType

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class CapabilityRegistry:
    """
    能力注册表

    统一管理所有能力的注册、发现和调用。

    功能：
    - 注册/注销能力
    - 按类型、标签、名称搜索能力
    - 记录使用统计
    - 生成能力清单

    示例：
        registry = CapabilityRegistry()

        # 注册能力
        registry.register(CapabilityMeta(
            name="search",
            type=CapabilityType.TOOL,
            description="Search the web",
        ))

        # 获取能力
        capability = registry.get("search")

        # 搜索能力
        results = registry.search("web", tags=["search"])

        # 列出所有工具
        tools = registry.list_by_type(CapabilityType.TOOL)
    """

    # 核心存储
    _capabilities: dict[str, CapabilityMeta] = field(default_factory=dict)

    # 索引（加速查询）
    _type_index: dict[CapabilityType, set[str]] = field(default_factory=dict)
    _tag_index: dict[str, set[str]] = field(default_factory=dict)
    _status_index: dict[CapabilityStatus, set[str]] = field(default_factory=dict)

    # 使用统计
    _total_registrations: int = 0
    _total_unregistrations: int = 0

    def __post_init__(self):
        """初始化索引"""
        for cap_type in CapabilityType:
            self._type_index[cap_type] = set()
        for status in CapabilityStatus:
            self._status_index[status] = set()

    # ==================== CRUD 操作 ====================

    def register(self, capability: CapabilityMeta) -> bool:
        """
        注册能力。

        Args:
            capability: 能力元数据

        Returns:
            是否注册成功（如果已存在则覆盖并返回 True）
        """
        name = capability.name

        # 如果已存在，先注销旧的
        if name in self._capabilities:
            self._unregister_internal(name)

        # 注册到主存储
        self._capabilities[name] = capability

        # 更新类型索引
        self._type_index[capability.type].add(name)

        # 更新标签索引
        for tag in capability.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(name)

        # 更新状态索引
        self._status_index[capability.status].add(name)

        self._total_registrations += 1

        logger.info(f"[Registry] Registered capability: {name} ({capability.type.value})")
        return True

    def unregister(self, name: str) -> bool:
        """
        注销能力。

        Args:
            name: 能力名称

        Returns:
            是否注销成功
        """
        if name not in self._capabilities:
            return False

        self._unregister_internal(name)
        self._total_unregistrations += 1

        logger.info(f"[Registry] Unregistered capability: {name}")
        return True

    def _unregister_internal(self, name: str) -> None:
        """内部注销方法"""
        capability = self._capabilities.get(name)
        if not capability:
            return

        # 从主存储移除
        del self._capabilities[name]

        # 从类型索引移除
        self._type_index[capability.type].discard(name)

        # 从标签索引移除
        for tag in capability.tags:
            if tag in self._tag_index:
                self._tag_index[tag].discard(name)

        # 从状态索引移除
        self._status_index[capability.status].discard(name)

    def get(self, name: str) -> CapabilityMeta | None:
        """
        获取能力。

        Args:
            name: 能力名称

        Returns:
            能力元数据，不存在则返回 None
        """
        return self._capabilities.get(name)

    def get_or_raise(self, name: str) -> CapabilityMeta:
        """
        获取能力，不存在则抛出异常。

        Args:
            name: 能力名称

        Returns:
            能力元数据

        Raises:
            KeyError: 能力不存在
        """
        capability = self._capabilities.get(name)
        if capability is None:
            raise KeyError(f"Capability not found: {name}")
        return capability

    def has(self, name: str) -> bool:
        """检查能力是否存在"""
        return name in self._capabilities

    # ==================== 查询操作 ====================

    def list_all(self) -> list[CapabilityMeta]:
        """列出所有能力"""
        return list(self._capabilities.values())

    def list_names(self) -> list[str]:
        """列出所有能力名称"""
        return list(self._capabilities.keys())

    def list_by_type(self, cap_type: CapabilityType) -> list[CapabilityMeta]:
        """
        按类型列出能力。

        Args:
            cap_type: 能力类型

        Returns:
            该类型的所有能力
        """
        names = self._type_index.get(cap_type, set())
        return [self._capabilities[name] for name in names if name in self._capabilities]

    def list_by_tag(self, tag: str) -> list[CapabilityMeta]:
        """
        按标签列出能力。

        Args:
            tag: 标签

        Returns:
            包含该标签的所有能力
        """
        names = self._tag_index.get(tag, set())
        return [self._capabilities[name] for name in names if name in self._capabilities]

    def list_by_status(self, status: CapabilityStatus) -> list[CapabilityMeta]:
        """
        按状态列出能力。

        Args:
            status: 能力状态

        Returns:
            该状态的所有能力
        """
        names = self._status_index.get(status, set())
        return [self._capabilities[name] for name in names if name in self._capabilities]

    def list_available(self) -> list[CapabilityMeta]:
        """列出所有可用能力"""
        result = []
        for status in (CapabilityStatus.ACTIVE, CapabilityStatus.DEPRECATED):
            result.extend(self.list_by_status(status))
        return result

    def search(
        self,
        query: str | None = None,
        tags: list[str] | None = None,
        cap_type: CapabilityType | None = None,
        status: CapabilityStatus | None = None,
    ) -> list[CapabilityMeta]:
        """
        搜索能力。

        Args:
            query: 名称/描述搜索关键词
            tags: 标签过滤
            cap_type: 类型过滤
            status: 状态过滤

        Returns:
            匹配的能力列表
        """
        # 从全部能力开始
        candidates = set(self._capabilities.keys())

        # 按类型过滤
        if cap_type is not None:
            candidates &= self._type_index.get(cap_type, set())

        # 按标签过滤
        if tags:
            for tag in tags:
                candidates &= self._tag_index.get(tag, set())

        # 按状态过滤
        if status is not None:
            candidates &= self._status_index.get(status, set())

        # 按关键词过滤
        results = []
        query_lower = query.lower() if query else None

        for name in candidates:
            capability = self._capabilities.get(name)
            if capability is None:
                continue

            # 关键词匹配
            if query_lower:
                name_match = query_lower in capability.name.lower()
                desc_match = query_lower in capability.description.lower()
                tag_match = any(query_lower in tag.lower() for tag in capability.tags)

                if not (name_match or desc_match or tag_match):
                    continue

            results.append(capability)

        return results

    # ==================== 使用统计 ====================

    def record_usage(self, name: str, success: bool = True) -> bool:
        """
        记录能力使用。

        Args:
            name: 能力名称
            success: 是否成功

        Returns:
            是否记录成功
        """
        capability = self._capabilities.get(name)
        if capability is None:
            return False

        capability.record_usage(success=success)
        return True

    def get_usage_stats(self, name: str) -> dict[str, Any] | None:
        """
        获取能力使用统计。

        Args:
            name: 能力名称

        Returns:
            使用统计字典
        """
        capability = self._capabilities.get(name)
        if capability is None:
            return None

        return capability.get_usage_stats()

    def get_top_used(self, limit: int = 10) -> list[tuple[str, int]]:
        """
        获取最常用的能力。

        Args:
            limit: 返回数量

        Returns:
            [(name, usage_count), ...] 列表
        """
        usages = [
            (name, cap._usage_count)
            for name, cap in self._capabilities.items()
        ]
        usages.sort(key=lambda x: x[1], reverse=True)
        return usages[:limit]

    # ==================== 清单生成 ====================

    def generate_manifest(self, title: str = "Capability Manifest") -> str:
        """
        生成能力清单（Markdown 格式）。

        Args:
            title: 清单标题

        Returns:
            Markdown 格式的能力清单
        """
        lines = [
            f"# {title}",
            "",
            f"**Total Capabilities**: {len(self._capabilities)}",
            "",
        ]

        # 按类型分组
        for cap_type in CapabilityType:
            capabilities = self.list_by_type(cap_type)
            if not capabilities:
                continue

            lines.append(f"## {cap_type.value.upper()}S ({len(capabilities)})")
            lines.append("")

            # 按状态排序：ACTIVE -> DEPRECATED -> DISABLED -> ERROR
            status_order = [
                CapabilityStatus.ACTIVE,
                CapabilityStatus.DEPRECATED,
                CapabilityStatus.DISABLED,
                CapabilityStatus.ERROR,
            ]
            for status in status_order:
                status_caps = [c for c in capabilities if c.status == status]
                if not status_caps:
                    continue

                for cap in sorted(status_caps, key=lambda x: x.name):
                    lines.append(cap.to_manifest_entry())
                    lines.append("")

        return "\n".join(lines)

    def generate_compact_manifest(self) -> str:
        """
        生成紧凑格式的能力清单，适合注入 SystemPrompt。

        Returns:
            紧凑格式的清单字符串
        """
        lines = []

        # 按类型分组
        for cap_type in CapabilityType:
            capabilities = [c for c in self.list_by_type(cap_type) if c.is_available()]
            if not capabilities:
                continue

            lines.append(f"## {cap_type.value.upper()}S")

            for cap in sorted(capabilities, key=lambda x: x.name):
                # 紧凑格式：名称 - 描述
                desc = cap.description[:80] + "..." if len(cap.description) > 80 else cap.description
                if desc:
                    lines.append(f"- {cap.name}: {desc}")
                else:
                    lines.append(f"- {cap.name}")

            lines.append("")

        return "\n".join(lines)

    def generate_system_prompt_section(
        self,
        include_parameters: bool = False,
        include_examples: bool = False,
        only_available: bool = True,
    ) -> str:
        """
        生成适合注入到 SystemPrompt 的能力清单。

        这个方法生成的清单格式简洁，适合 LLM 理解和使用。

        Args:
            include_parameters: 是否包含参数说明
            include_examples: 是否包含使用示例
            only_available: 是否只包含可用能力

        Returns:
            适合 SystemPrompt 的能力清单
        """
        lines = ["# 可用能力", ""]

        for cap_type in CapabilityType:
            capabilities = self.list_by_type(cap_type)

            if only_available:
                capabilities = [c for c in capabilities if c.is_available()]

            if not capabilities:
                continue

            type_name = {
                CapabilityType.TOOL: "工具",
                CapabilityType.SKILL: "技能",
                CapabilityType.MCP: "MCP 工具",
                CapabilityType.BUILTIN: "内置能力",
            }.get(cap_type, cap_type.value)

            lines.append(f"## {type_name}")
            lines.append("")

            for cap in sorted(capabilities, key=lambda x: x.name):
                # 能力名称
                lines.append(f"### {cap.name}")

                # 描述
                if cap.description:
                    lines.append(f"{cap.description}")

                # 标签
                if cap.tags:
                    lines.append(f"标签: {', '.join(cap.tags)}")

                # 参数
                if include_parameters and cap.parameters:
                    lines.append("")
                    lines.append("参数:")
                    for param, schema in cap.parameters.items():
                        param_type = schema.get("type", "any")
                        required = schema.get("required", False)
                        req_mark = "*" if required else ""
                        param_desc = schema.get("description", "")
                        lines.append(f"  - {param}{req_mark} ({param_type}): {param_desc}")

                # 示例
                if include_examples and cap.examples:
                    lines.append("")
                    lines.append("示例:")
                    for i, example in enumerate(cap.examples[:2], 1):
                        if "input" in example:
                            lines.append(f"  {i}. 输入: {example['input']}")

                lines.append("")

        return "\n".join(lines)

    def generate_tool_list_for_prompt(self) -> str:
        """
        生成适合 LLM 工具调用格式的清单。

        返回一个简洁的格式，列出所有可用工具及其简要描述。

        Returns:
            工具列表字符串
        """
        tools = self.list_available()
        if not tools:
            return "当前没有可用的工具。"

        lines = ["可用工具列表:", ""]
        for tool in sorted(tools, key=lambda x: x.name):
            lines.append(f"- {tool.name}: {tool.description or '无描述'}")

        return "\n".join(lines)

    def generate_summary(self) -> dict[str, Any]:
        """
        生成能力摘要统计。

        Returns:
            摘要统计字典
        """
        type_counts = {}
        for cap_type in CapabilityType:
            type_counts[cap_type.value] = len(self.list_by_type(cap_type))

        status_counts = {}
        for status in CapabilityStatus:
            status_counts[status.value] = len(self.list_by_status(status))

        # 标签统计
        tag_counts = {
            tag: len(names)
            for tag, names in self._tag_index.items()
        }
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "total": len(self._capabilities),
            "available": len(self.list_available()),
            "by_type": type_counts,
            "by_status": status_counts,
            "top_tags": top_tags,
            "total_tags": len(self._tag_index),
            "registration_stats": {
                "total_registrations": self._total_registrations,
                "total_unregistrations": self._total_unregistrations,
            },
        }

    # ==================== 批量操作 ====================

    def clear(self) -> int:
        """
        清空所有能力。

        Returns:
            清空的能力数量
        """
        count = len(self._capabilities)
        self._capabilities.clear()

        for cap_type in CapabilityType:
            self._type_index[cap_type].clear()
        self._tag_index.clear()
        for status in CapabilityStatus:
            self._status_index[status].clear()

        logger.info(f"[Registry] Cleared {count} capabilities")
        return count

    def register_batch(self, capabilities: list[CapabilityMeta]) -> int:
        """
        批量注册能力。

        Args:
            capabilities: 能力列表

        Returns:
            成功注册的数量
        """
        count = 0
        for cap in capabilities:
            if self.register(cap):
                count += 1
        return count

    def unregister_batch(self, names: list[str]) -> int:
        """
        批量注销能力。

        Args:
            names: 能力名称列表

        Returns:
            成功注销的数量
        """
        count = 0
        for name in names:
            if self.unregister(name):
                count += 1
        return count


# 全局注册表实例（可选使用）
_global_registry: CapabilityRegistry | None = None


def get_global_registry() -> CapabilityRegistry:
    """获取全局注册表实例"""
    global _global_registry
    if _global_registry is None:
        _global_registry = CapabilityRegistry()
    return _global_registry


def reset_global_registry() -> None:
    """重置全局注册表"""
    global _global_registry
    _global_registry = None