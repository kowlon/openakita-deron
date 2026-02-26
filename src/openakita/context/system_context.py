"""
系统上下文

管理永久的系统级上下文，包括身份、规则、能力清单和策略。
该上下文在初始化后只读（除能力清单可刷新）。

参考：
- docs/context-refactoring-enterprise.md
- docs/refactor/20260226_enterprise_self_evolution_agent.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SystemContext:
    """
    系统上下文 - 永久只读的上下文层。

    包含身份、规则、能力清单和策略，跨任务与会话保持不变。
    启动时初始化一次。

    特点：
    - 启动时初始化一次
    - 身份、规则、能力清单
    - Token 预算固定或仅手动调整
    - 能力清单可通过 refresh_capabilities() 刷新

    属性：
        identity: Agent 身份描述（我是谁）
        rules: 行为规则/约束列表
        capabilities_manifest: 能力清单 (Tools + Skills + MCP)
        policies: 策略约束
        max_tokens: 系统上下文的最大 token 预算

    示例：
        system_ctx = SystemContext(
            identity="我是一个有帮助的 AI 助手",
            rules=["始终保持尊重", "不要分享敏感信息"],
            capabilities_manifest="## 可用能力\\n### TOOLS\\n- search: 搜索"
        )

        prompt = system_ctx.to_prompt()
        tokens = system_ctx.estimate_tokens()
    """

    identity: str = ""
    rules: list[str] = field(default_factory=list)
    capabilities_manifest: str = ""
    policies: list[str] = field(default_factory=list)
    max_tokens: int = 16000

    # 缓存编译后的提示词
    _compiled_prompt: str = field(default="", repr=False)

    def to_prompt(self) -> str:
        """
        生成系统提示词字符串。

        使用缓存避免重复编译。

        返回：
            包含身份、规则、能力和策略的格式化系统提示词。
        """
        if not self._compiled_prompt:
            self._compile()
        return self._compiled_prompt

    def _compile(self) -> None:
        """编译系统提示词到缓存。"""
        parts = []

        # 身份区块
        if self.identity:
            parts.append("# 身份\n" + self.identity)

        # 规则区块
        if self.rules:
            rules_text = "\n".join(f"- {rule}" for rule in self.rules)
            parts.append("# 规则\n" + rules_text)

        # 能力区块
        if self.capabilities_manifest:
            parts.append(self.capabilities_manifest)

        # 策略区块
        if self.policies:
            policies_text = "\n".join(f"- {policy}" for policy in self.policies)
            parts.append("# 策略\n" + policies_text)

        self._compiled_prompt = "\n\n".join(parts)

    def refresh_capabilities(self, manifest: str) -> None:
        """
        刷新能力清单（安装新技能时调用）。

        清除缓存，下次调用 to_prompt() 时重新编译。

        参数：
            manifest: 新的能力清单
        """
        self.capabilities_manifest = manifest
        self._compiled_prompt = ""  # 清除缓存

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
            "capabilities_manifest_length": len(self.capabilities_manifest),
            "policies_count": len(self.policies),
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
        self._compiled_prompt = ""  # 清除缓存

    def add_policy(self, policy: str) -> None:
        """
        向上下文添加策略。

        参数：
            policy: 要添加的策略文本
        """
        self.policies.append(policy)
        self._compiled_prompt = ""  # 清除缓存

    def set_identity(self, identity: str) -> None:
        """
        设置 Agent 身份。

        参数：
            identity: 身份描述
        """
        self.identity = identity
        self._compiled_prompt = ""  # 清除缓存

    def clear(self) -> None:
        """清空所有上下文内容。"""
        self.identity = ""
        self.rules = []
        self.capabilities_manifest = ""
        self.policies = []
        self._compiled_prompt = ""

    def clear_rules(self) -> None:
        """清空所有规则。"""
        self.rules = []
        self._compiled_prompt = ""

    def clear_policies(self) -> None:
        """清空所有策略。"""
        self.policies = []
        self._compiled_prompt = ""

    def to_dict(self) -> dict[str, Any]:
        """
        转换为用于序列化的字典。

        返回：
            字典表示
        """
        return {
            "identity": self.identity,
            "rules": self.rules,
            "capabilities_manifest": self.capabilities_manifest,
            "policies": self.policies,
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
            capabilities_manifest=data.get("capabilities_manifest", ""),
            policies=data.get("policies", []),
            max_tokens=data.get("max_tokens", 16000),
        )

    def __str__(self) -> str:
        """字符串表示。"""
        return f"SystemContext(identity={len(self.identity)} chars, rules={len(self.rules)}, tokens~{self.estimate_tokens()})"

    def __repr__(self) -> str:
        """详细表示。"""
        return (
            f"SystemContext(identity='{self.identity[:50]}...', "
            f"rules={len(self.rules)}, capabilities={len(self.capabilities_manifest)} chars, "
            f"policies={len(self.policies)}, max_tokens={self.max_tokens})"
        )
