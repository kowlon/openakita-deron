"""
系统上下文

管理永久的系统级上下文，包括身份、规则和工具清单。
该上下文在初始化后只读。

参考：
- docs/context-refactoring-enterprise.md
- autonomous-coder/enterprise_refactor_plan.md
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SystemContext:
    """
    系统上下文 - 永久只读的上下文层。

    包含身份、规则与工具清单，跨任务与会话保持不变。
    启动时初始化一次。

    属性：
        identity: Agent 身份描述（我是谁）
        rules: 行为规则/约束列表
        tools_manifest: 可用工具描述
        max_tokens: 系统上下文的最大 token 预算

    示例：
        system_ctx = SystemContext(
            identity="我是一个有帮助的 AI 助手",
            rules=["始终保持尊重", "不要分享敏感信息"],
            tools_manifest="可用工具：search、calculator、file_reader"
        )

        prompt = system_ctx.to_prompt()
        tokens = system_ctx.estimate_tokens()
    """

    identity: str = ""
    rules: list[str] = field(default_factory=list)
    tools_manifest: str = ""
    max_tokens: int = 8000

    def to_prompt(self) -> str:
        """
        生成系统提示词字符串。

        返回：
            包含身份、规则与工具的格式化系统提示词。

        示例输出：
            # 身份
            我是一个有帮助的 AI 助手。

            # 规则
            - 始终保持尊重
            - 不要分享敏感信息

            # 可用工具
            search: 用于搜索网络信息
            calculator: 执行计算
        """
        parts = []

        # 身份区块
        if self.identity:
            parts.append("# Identity\n" + self.identity)

        # 规则区块
        if self.rules:
            rules_text = "\n".join(f"- {rule}" for rule in self.rules)
            parts.append("# Rules\n" + rules_text)

        # 工具区块
        if self.tools_manifest:
            parts.append("# Available Tools\n" + self.tools_manifest)

        return "\n\n".join(parts)

    def estimate_tokens(self, chars_per_token: float = 4.0) -> int:
        """
        估算系统上下文的 token 数量。

        使用简单的基于字符的估算。更准确的估算请使用分词器库。

        参数：
            chars_per_token: 每个 token 的平均字符数（默认 4）

        返回：
            估算的 token 数量
        """
        prompt = self.to_prompt()
        return int(len(prompt) / chars_per_token)

    def is_within_budget(self) -> bool:
        """
        检查上下文是否在 token 预算内。

        返回：
            若估算 token 数 <= max_tokens 则为 True
        """
        return self.estimate_tokens() <= self.max_tokens

    def get_stats(self) -> dict[str, Any]:
        """
        获取系统上下文的统计信息。

        返回：
            上下文统计信息字典
        """
        return {
            "identity_length": len(self.identity),
            "rules_count": len(self.rules),
            "tools_manifest_length": len(self.tools_manifest),
            "estimated_tokens": self.estimate_tokens(),
            "max_tokens": self.max_tokens,
            "within_budget": self.is_within_budget(),
        }

    def add_rule(self, rule: str) -> None:
        """
        向上下文添加规则。

        参数：
            rule: 要添加的规则文本
        """
        self.rules.append(rule)

    def set_identity(self, identity: str) -> None:
        """
        设置 Agent 身份。

        参数：
            identity: 身份描述
        """
        self.identity = identity

    def set_tools_manifest(self, manifest: str) -> None:
        """
        设置工具清单。

        参数：
            manifest: 工具描述
        """
        self.tools_manifest = manifest

    def clear_rules(self) -> None:
        """清空所有规则。"""
        self.rules = []

    def to_dict(self) -> dict[str, Any]:
        """
        转换为用于序列化的字典。

        返回：
            字典表示
        """
        return {
            "identity": self.identity,
            "rules": self.rules,
            "tools_manifest": self.tools_manifest,
            "max_tokens": self.max_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SystemContext":
        """
        从字典创建。

        参数：
            data: 包含上下文数据的字典

        返回：
            SystemContext 实例
        """
        return cls(
            identity=data.get("identity", ""),
            rules=data.get("rules", []),
            tools_manifest=data.get("tools_manifest", ""),
            max_tokens=data.get("max_tokens", 8000),
        )

    def __str__(self) -> str:
        """字符串表示。"""
        return f"SystemContext(identity={len(self.identity)} chars, rules={len(self.rules)}, tokens~{self.estimate_tokens()})"

    def __repr__(self) -> str:
        """详细表示。"""
        return (
            f"SystemContext(identity='{self.identity[:50]}...', "
            f"rules={len(self.rules)}, tools_manifest={len(self.tools_manifest)} chars, "
            f"max_tokens={self.max_tokens})"
        )
