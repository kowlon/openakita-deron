"""
场景注册表

管理最佳实践场景的定义和匹配。
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .models import (
    ScenarioDefinition,
    StepDefinition,
    TriggerPattern,
    TriggerType,
)

logger = logging.getLogger(__name__)


@dataclass
class ScenarioMatchResult:
    """场景匹配结果"""

    scenario: ScenarioDefinition
    confidence: float  # 匹配置信度 0-1
    matched_pattern: TriggerPattern | None = None
    extracted_params: dict[str, Any] = field(default_factory=dict)


class ScenarioRegistry:
    """
    场景注册表

    管理所有最佳实践场景的定义、加载和匹配。

    核心功能:
    - 场景注册和注销
    - 从对话消息匹配场景
    - 场景分类管理
    - 配置文件加载
    """

    def __init__(self):
        """初始化场景注册表"""
        self._scenarios: dict[str, ScenarioDefinition] = {}
        self._categories: dict[str, list[str]] = {}  # category -> scenario_ids
        self._compiled_patterns: dict[str, list[tuple[re.Pattern, TriggerPattern]]] = {}

    # ==================== 注册/注销 ====================

    def register(self, scenario: ScenarioDefinition) -> bool:
        """
        注册场景

        Args:
            scenario: 场景定义

        Returns:
            是否注册成功
        """
        if scenario.scenario_id in self._scenarios:
            logger.warning(f"Scenario already registered: {scenario.scenario_id}")
            return False

        self._scenarios[scenario.scenario_id] = scenario

        # 更新分类索引
        category = scenario.category
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(scenario.scenario_id)

        # 预编译正则模式
        self._compile_patterns(scenario)

        logger.info(f"Registered scenario: {scenario.scenario_id} ({scenario.name})")
        return True

    def unregister(self, scenario_id: str) -> bool:
        """
        注销场景

        Args:
            scenario_id: 场景 ID

        Returns:
            是否注销成功
        """
        if scenario_id not in self._scenarios:
            return False

        scenario = self._scenarios.pop(scenario_id)

        # 更新分类索引
        category = scenario.category
        if category in self._categories:
            self._categories[category] = [
                sid for sid in self._categories[category] if sid != scenario_id
            ]

        # 清理预编译模式
        self._compiled_patterns.pop(scenario_id, None)

        logger.info(f"Unregistered scenario: {scenario_id}")
        return True

    def _compile_patterns(self, scenario: ScenarioDefinition) -> None:
        """预编译场景的正则模式"""
        compiled = []
        for pattern in scenario.trigger_patterns:
            if pattern.type == TriggerType.REGEX and pattern.pattern:
                try:
                    compiled_pattern = re.compile(pattern.pattern, re.IGNORECASE)
                    compiled.append((compiled_pattern, pattern))
                except re.error as e:
                    logger.warning(
                        f"Invalid regex pattern in scenario {scenario.scenario_id}: {e}"
                    )
        self._compiled_patterns[scenario.scenario_id] = compiled

    # ==================== 查询 ====================

    def get(self, scenario_id: str) -> ScenarioDefinition | None:
        """
        获取场景定义

        Args:
            scenario_id: 场景 ID

        Returns:
            场景定义，不存在则返回 None
        """
        return self._scenarios.get(scenario_id)

    def list_all(self) -> list[ScenarioDefinition]:
        """
        列出所有场景

        Returns:
            场景列表
        """
        return list(self._scenarios.values())

    def list_by_category(self, category: str) -> list[ScenarioDefinition]:
        """
        按分类列出场景

        Args:
            category: 分类名称

        Returns:
            场景列表
        """
        scenario_ids = self._categories.get(category, [])
        return [self._scenarios[sid] for sid in scenario_ids if sid in self._scenarios]

    def list_categories(self) -> list[str]:
        """
        列出所有分类

        Returns:
            分类名称列表
        """
        return list(self._categories.keys())

    def count(self) -> int:
        """
        获取场景总数

        Returns:
            场景数量
        """
        return len(self._scenarios)

    # ==================== 匹配 ====================

    def match_from_dialog(self, message: str) -> ScenarioMatchResult | None:
        """
        从对话消息匹配场景

        匹配优先级:
        1. 正则模式匹配（按 priority 排序）
        2. 关键词匹配（按 priority 排序）

        Args:
            message: 用户消息

        Returns:
            匹配结果，无匹配则返回 None
        """
        if not message:
            return None

        message_lower = message.lower()
        best_match: ScenarioMatchResult | None = None

        # 收集所有匹配结果
        matches: list[ScenarioMatchResult] = []

        for scenario_id, scenario in self._scenarios.items():
            match_result = self._match_scenario(scenario, message, message_lower)
            if match_result:
                matches.append(match_result)

        if not matches:
            return None

        # 按置信度和优先级排序，返回最佳匹配
        matches.sort(key=lambda m: (-m.confidence, m.matched_pattern.priority if m.matched_pattern else 999))
        return matches[0]

    def _match_scenario(
        self,
        scenario: ScenarioDefinition,
        message: str,
        message_lower: str,
    ) -> ScenarioMatchResult | None:
        """
        匹配单个场景

        Args:
            scenario: 场景定义
            message: 原始消息
            message_lower: 小写消息

        Returns:
            匹配结果或 None
        """
        best_confidence = 0.0
        best_pattern: TriggerPattern | None = None
        extracted_params: dict[str, Any] = {}

        # 正则匹配
        compiled_patterns = self._compiled_patterns.get(scenario.scenario_id, [])
        for compiled_pattern, trigger_pattern in compiled_patterns:
            match = compiled_pattern.search(message)
            if match:
                confidence = 0.9  # 正则匹配置信度较高
                if trigger_pattern.priority < 10:
                    confidence = 1.0  # 高优先级正则

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_pattern = trigger_pattern
                    # 提取命名组参数
                    if match.groupdict():
                        extracted_params = {k: v for k, v in match.groupdict().items() if v}

        # 关键词匹配
        for trigger_pattern in scenario.trigger_patterns:
            if trigger_pattern.type == TriggerType.KEYWORD:
                keyword_match_count = 0
                for keyword in trigger_pattern.keywords:
                    if keyword.lower() in message_lower:
                        keyword_match_count += 1

                if keyword_match_count > 0:
                    # 根据匹配的关键词数量计算置信度
                    confidence = min(0.8, 0.4 + (keyword_match_count * 0.2))

                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_pattern = trigger_pattern

        if best_confidence > 0:
            return ScenarioMatchResult(
                scenario=scenario,
                confidence=best_confidence,
                matched_pattern=best_pattern,
                extracted_params=extracted_params,
            )

        return None

    # ==================== 加载 ====================

    def load_from_yaml(self, config_path: str | Path) -> ScenarioDefinition:
        """
        从 YAML 文件加载场景

        Args:
            config_path: 配置文件路径

        Returns:
            场景定义

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 配置格式错误
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Scenario config not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        if not isinstance(raw, dict):
            raise ValueError(f"Invalid config format: {path}")

        scenario = self._parse_scenario(raw)

        # 注册场景
        self.register(scenario)

        return scenario

    def load_from_directory(self, directory: str | Path) -> int:
        """
        从目录加载所有场景配置

        Args:
            directory: 配置目录路径

        Returns:
            加载的场景数量
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            logger.warning(f"Scenario directory not found: {dir_path}")
            return 0

        count = 0
        for config_file in dir_path.glob("*.yaml"):
            try:
                self.load_from_yaml(config_file)
                count += 1
            except Exception as e:
                logger.error(f"Failed to load scenario from {config_file}: {e}")

        logger.info(f"Loaded {count} scenarios from {dir_path}")
        return count

    def _parse_scenario(self, raw: dict) -> ScenarioDefinition:
        """解析场景定义"""
        # 解析触发模式
        trigger_patterns = []
        for p in raw.get("trigger_patterns", []):
            if isinstance(p, dict):
                trigger_patterns.append(self._parse_trigger_pattern(p))

        # 解析步骤
        steps = []
        for s in raw.get("steps", []):
            if isinstance(s, dict):
                steps.append(self._parse_step_definition(s))

        return ScenarioDefinition(
            scenario_id=raw["scenario_id"],
            name=raw["name"],
            description=raw.get("description", ""),
            category=raw.get("category", "general"),
            version=raw.get("version", "1.0"),
            trigger_patterns=trigger_patterns,
            steps=steps,
            metadata=raw.get("metadata", {}),
        )

    def _parse_trigger_pattern(self, raw: dict) -> TriggerPattern:
        """解析触发模式"""
        return TriggerPattern(
            type=TriggerType(raw.get("type", "keyword")),
            pattern=raw.get("pattern"),
            keywords=raw.get("keywords", []),
            priority=raw.get("priority", 0),
        )

    def _parse_step_definition(self, raw: dict) -> StepDefinition:
        """解析步骤定义"""
        # 解析工具配置
        tools_raw = raw.get("tools", {})
        from .models import ToolsConfig
        tools = ToolsConfig(
            system_tools=tools_raw.get("system_tools", []),
            mcp_tools=tools_raw.get("mcp_tools", []),
        )

        return StepDefinition(
            step_id=raw["step_id"],
            name=raw["name"],
            description=raw.get("description", ""),
            output_key=raw.get("output_key", ""),
            tools=tools,
            skills=raw.get("skills", []),
            system_prompt=raw.get("system_prompt", ""),
            requires_confirmation=raw.get("requires_confirmation", True),
            dependencies=raw.get("dependencies", []),
            timeout_seconds=raw.get("timeout_seconds", 300),
        )

    # ==================== 工具方法 ====================

    def clear(self) -> None:
        """清空所有场景"""
        self._scenarios.clear()
        self._categories.clear()
        self._compiled_patterns.clear()
        logger.info("Cleared all scenarios")

    def to_dict(self) -> dict[str, Any]:
        """导出为字典"""
        return {
            "scenarios": {sid: s.to_dict() for sid, s in self._scenarios.items()},
            "categories": self._categories,
        }


# ==================== 全局注册表 ====================

_global_registry: ScenarioRegistry | None = None


def get_scenario_registry() -> ScenarioRegistry:
    """获取全局场景注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ScenarioRegistry()
    return _global_registry


def reset_scenario_registry() -> None:
    """重置全局场景注册表"""
    global _global_registry
    _global_registry = None