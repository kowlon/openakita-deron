"""
能力类型系统

定义能力的类型枚举和元数据结构。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CapabilityType(Enum):
    """
    能力类型枚举

    定义系统中所有能力的类型分类：
    - TOOL: 内置工具，由 ToolCatalog 提供
    - SKILL: 技能，由 SkillManager 管理
    - MCP: MCP 服务器提供的工具
    - BUILTIN: 内置能力，直接实现
    """
    TOOL = "tool"
    SKILL = "skill"
    MCP = "mcp"
    BUILTIN = "builtin"

    def __str__(self) -> str:
        return self.value


class CapabilityStatus(Enum):
    """
    能力状态枚举

    - ACTIVE: 可用
    - DEPRECATED: 已废弃但仍可用
    - DISABLED: 已禁用
    - ERROR: 加载错误
    """
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"
    ERROR = "error"

    def __str__(self) -> str:
        return self.value


@dataclass
class CapabilityMeta:
    """
    能力元数据

    描述一个能力的完整信息，用于注册、发现和调用。

    属性:
        name: 能力唯一标识符（如 "search", "calculator"）
        type: 能力类型
        description: 能力描述
        version: 版本号
        tags: 标签列表，用于分类和搜索
        parameters: 参数 schema（JSON Schema 格式）
        returns: 返回值 schema
        examples: 使用示例
        status: 当前状态
        source: 来源标识（如文件路径、MCP 服务器名）
        priority: 优先级（用于冲突解决）
        metadata: 额外元数据
    """
    name: str
    type: CapabilityType
    description: str = ""
    version: str = "1.0.0"
    tags: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    returns: dict[str, Any] = field(default_factory=dict)
    examples: list[dict[str, Any]] = field(default_factory=list)
    status: CapabilityStatus = CapabilityStatus.ACTIVE
    source: str = ""
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    # 使用统计（运行时更新）
    _usage_count: int = field(default=0, repr=False)
    _last_used: float | None = field(default=None, repr=False)
    _success_count: int = field(default=0, repr=False)
    _error_count: int = field(default=0, repr=False)

    def __post_init__(self):
        """初始化后处理"""
        # 确保 type 是枚举类型
        if isinstance(self.type, str):
            self.type = CapabilityType(self.type)
        if isinstance(self.status, str):
            self.status = CapabilityStatus(self.status)

    def is_available(self) -> bool:
        """检查能力是否可用"""
        return self.status in (CapabilityStatus.ACTIVE, CapabilityStatus.DEPRECATED)

    def record_usage(self, success: bool = True, timestamp: float | None = None) -> None:
        """
        记录使用情况。

        Args:
            success: 是否成功执行
            timestamp: 时间戳（默认使用当前时间）
        """
        import time
        self._usage_count += 1
        self._last_used = timestamp or time.time()
        if success:
            self._success_count += 1
        else:
            self._error_count += 1

    def get_usage_stats(self) -> dict[str, Any]:
        """获取使用统计"""
        return {
            "usage_count": self._usage_count,
            "success_count": self._success_count,
            "error_count": self._error_count,
            "success_rate": (
                self._success_count / self._usage_count
                if self._usage_count > 0 else 0.0
            ),
            "last_used": self._last_used,
        }

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "type": self.type.value,
            "description": self.description,
            "version": self.version,
            "tags": self.tags,
            "parameters": self.parameters,
            "returns": self.returns,
            "examples": self.examples,
            "status": self.status.value,
            "source": self.source,
            "priority": self.priority,
            "metadata": self.metadata,
            "usage_stats": self.get_usage_stats(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapabilityMeta":
        """从字典创建"""
        return cls(
            name=data["name"],
            type=CapabilityType(data.get("type", "tool")),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            tags=data.get("tags", []),
            parameters=data.get("parameters", {}),
            returns=data.get("returns", {}),
            examples=data.get("examples", []),
            status=CapabilityStatus(data.get("status", "active")),
            source=data.get("source", ""),
            priority=data.get("priority", 0),
            metadata=data.get("metadata", {}),
        )

    def to_manifest_entry(self) -> str:
        """
        生成能力清单条目（Markdown 格式）。

        Returns:
            Markdown 格式的条目字符串
        """
        lines = [
            f"### {self.name}",
            "",
            f"- **类型**: {self.type.value}",
            f"- **版本**: {self.version}",
            f"- **状态**: {self.status.value}",
        ]

        if self.description:
            lines.append(f"- **描述**: {self.description}")

        if self.tags:
            lines.append(f"- **标签**: {', '.join(self.tags)}")

        if self.parameters:
            lines.append("")
            lines.append("**参数**:")
            for param, schema in self.parameters.items():
                param_type = schema.get("type", "any")
                required = schema.get("required", False)
                req_mark = "*" if required else ""
                lines.append(f"- `{param}{req_mark}` ({param_type}): {schema.get('description', '')}")

        return "\n".join(lines)

    def __hash__(self) -> int:
        """支持作为 dict key 或 set 成员"""
        return hash((self.name, self.type))

    def __eq__(self, other: object) -> bool:
        """相等比较"""
        if not isinstance(other, CapabilityMeta):
            return False
        return self.name == other.name and self.type == other.type


@dataclass
class CapabilityCategory:
    """
    能力分类

    用于组织和展示能力。
    """
    name: str
    description: str = ""
    capabilities: list[str] = field(default_factory=list)  # capability names
    subcategories: list["CapabilityCategory"] = field(default_factory=list)

    def add_capability(self, name: str) -> None:
        """添加能力"""
        if name not in self.capabilities:
            self.capabilities.append(name)

    def remove_capability(self, name: str) -> bool:
        """移除能力"""
        if name in self.capabilities:
            self.capabilities.remove(name)
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": self.capabilities,
            "subcategories": [s.to_dict() for s in self.subcategories],
        }