"""
系统规则存储

管理跨任务持久化的系统级规则。
规则由管理员配置，AI 不可修改。

参考：
- docs/memory-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


class RuleCategory(Enum):
    """用于分类与筛选的规则类别"""

    COMPLIANCE = "compliance"  # 合规约束（例如：不存储 PII）
    SECURITY = "security"  # 安全约束（例如：禁止危险命令）
    BUSINESS = "business"  # 业务规则（例如：审批流程）
    CUSTOM = "custom"  # 自定义规则


@dataclass
class SystemRule:
    """
    系统规则定义。

    规则为永久存储，非任务级别。
    由管理员配置并注入系统提示词。

    属性：
        id: 规则唯一标识
        category: 用于分类的规则类别
        content: 规则内容/描述
        priority: 优先级 1-10（越高越重要）
        enabled: 规则是否启用
        created_by: 创建规则的管理员
        created_at: 创建时间戳
    """

    id: str
    category: RuleCategory
    content: str
    priority: int  # 1-10，数值越高越重要
    enabled: bool = True
    created_by: str = "system"
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """转换为用于序列化的字典"""
        return {
            "id": self.id,
            "category": self.category.value,
            "content": self.content,
            "priority": self.priority,
            "enabled": self.enabled,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SystemRule":
        """从字典创建"""
        return cls(
            id=data["id"],
            category=RuleCategory(data["category"]),
            content=data["content"],
            priority=data.get("priority", 5),
            enabled=data.get("enabled", True),
            created_by=data.get("created_by", "system"),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if "created_at" in data
                else datetime.now()
            ),
        )


class SystemRuleStore:
    """
    系统规则存储管理器。

    从 YAML/JSON 配置文件加载规则，并提供规则检索方法。

    YAML 示例格式：
        rules:
          - id: rule-001
            category: compliance
            content: "不要存储敏感信息"
            priority: 10
            enabled: true

    JSON 示例格式：
        {
            "rules": [
                {
                    "id": "rule-001",
                    "category": "compliance",
                    "content": "不要存储敏感信息",
                    "priority": 10,
                    "enabled": true
                }
            ]
        }

    使用示例：
        store = SystemRuleStore()
        store.load_from_yaml("config/rules.yaml")

        # 获取所有启用规则（按优先级排序）
        rules = store.get_enabled_rules()

        # 按类别获取规则
        compliance_rules = store.get_rules_by_category(RuleCategory.COMPLIANCE)
    """

    def __init__(self) -> None:
        """初始化空规则存储"""
        self._rules: list[SystemRule] = []

    def load_from_yaml(self, path: str) -> None:
        """
        从 YAML 文件加载规则。

        参数：
            path: YAML 文件路径

        异常：
            FileNotFoundError: 文件不存在
            yaml.YAMLError: YAML 解析失败
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Rules file not found: {path}")

        with open(file_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self._parse_rules_data(data)

    def load_from_json(self, path: str) -> None:
        """
        从 JSON 文件加载规则。

        参数：
            path: JSON 文件路径

        异常：
            FileNotFoundError: 文件不存在
            json.JSONDecodeError: JSON 解析失败
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Rules file not found: {path}")

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        self._parse_rules_data(data)

    def _parse_rules_data(self, data: dict[str, Any] | None) -> None:
        """
        解析已加载的数据中的规则。

        参数：
            data: 包含 "rules" 键的字典，值为规则字典列表
        """
        if not data or "rules" not in data:
            self._rules = []
            return

        self._rules = [SystemRule.from_dict(rule_data) for rule_data in data["rules"]]

    def get_enabled_rules(self) -> list[SystemRule]:
        """
        获取所有启用规则，按优先级降序排序。

        返回：
            启用的 SystemRule 列表，按优先级排序。
            优先级更高的规则排在前面。
        """
        enabled = [rule for rule in self._rules if rule.enabled]
        return sorted(enabled, key=lambda r: r.priority, reverse=True)

    def get_rules_by_category(self, category: RuleCategory) -> list[SystemRule]:
        """
        按类别获取规则，按优先级降序排序。

        参数：
            category: 用于筛选的 RuleCategory

        返回：
            匹配类别的 SystemRule 列表。
            仅返回启用规则。
            按优先级排序（高优先级在前）。
        """
        matching = [
            rule
            for rule in self._rules
            if rule.category == category and rule.enabled
        ]
        return sorted(matching, key=lambda r: r.priority, reverse=True)

    def get_rule_by_id(self, rule_id: str) -> SystemRule | None:
        """
        按 ID 获取规则。

        参数：
            rule_id: 规则标识

        返回：
            若找到则返回 SystemRule，否则为 None
        """
        for rule in self._rules:
            if rule.id == rule_id:
                return rule
        return None

    def add_rule(self, rule: SystemRule) -> None:
        """
        向存储中添加新规则。

        参数：
            rule: 要添加的 SystemRule
        """
        self._rules.append(rule)

    def remove_rule(self, rule_id: str) -> bool:
        """
        按 ID 移除规则。

        参数：
            rule_id: 规则标识

        返回：
            若移除成功则为 True，否则为 False
        """
        for i, rule in enumerate(self._rules):
            if rule.id == rule_id:
                self._rules.pop(i)
                return True
        return False

    def clear_rules(self) -> None:
        """清空存储中的所有规则。"""
        self._rules = []

    @property
    def rule_count(self) -> int:
        """获取规则总数（包含禁用规则）。"""
        return len(self._rules)

    def to_prompt(self) -> str:
        """
        生成启用规则的提示词格式字符串。

        返回：
            用于注入系统提示词的格式化字符串。
        """
        rules = self.get_enabled_rules()
        if not rules:
            return ""

        lines = ["## System Rules", ""]
        for rule in rules:
            lines.append(f"- [{rule.category.value}] {rule.content}")

        return "\n".join(lines)
