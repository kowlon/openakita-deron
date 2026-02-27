"""
进化提案生成器

基于模式分析生成自我进化提案。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .models import (
    PatternObservation,
    EvolutionProposal,
)
from .pattern_extractor import PatternExtractor
from .experience_store import ExperienceStore

logger = logging.getLogger(__name__)


@dataclass
class ProposalConfig:
    """提案生成配置"""
    max_proposals: int = 20  # 最大提案数量
    min_pattern_confidence: float = 0.6  # 最小模式置信度
    enable_auto_approve: bool = False  # 是否自动批准低风险提案
    auto_approve_risk_threshold: str = "low"  # 自动批准的风险阈值


class ProposalGenerator:
    """
    进化提案生成器

    基于模式观察生成具体的改进提案：
    - 新技能建议
    - 技能改进建议
    - 流程优化建议
    """

    def __init__(
        self,
        store: ExperienceStore,
        extractor: PatternExtractor,
        config: ProposalConfig | None = None,
    ):
        """
        初始化提案生成器。

        Args:
            store: 经验存储
            extractor: 模式提取器
            config: 生成配置
        """
        self._store = store
        self._extractor = extractor
        self._config = config or ProposalConfig()
        self._proposals: list[EvolutionProposal] = []

    # ==================== 提案生成 ====================

    def generate_proposals(self) -> list[EvolutionProposal]:
        """
        生成进化提案。

        Returns:
            生成的提案列表
        """
        self._proposals = []

        # 确保模式已提取
        patterns = self._extractor.get_patterns()
        if not patterns:
            patterns = self._extractor.extract_patterns()

        if not patterns:
            logger.info("[ProposalGenerator] No patterns to generate proposals from")
            return []

        # 根据模式类型生成提案
        for pattern in patterns:
            if pattern.confidence < self._config.min_pattern_confidence:
                continue

            proposals = self._generate_from_pattern(pattern)
            self._proposals.extend(proposals)

        # 去重和排序
        self._deduplicate_proposals()
        self._proposals.sort(key=lambda p: self._calculate_priority(p), reverse=True)

        # 限制数量
        self._proposals = self._proposals[:self._config.max_proposals]

        # 自动批准低风险提案
        if self._config.enable_auto_approve:
            self._auto_approve()

        logger.info(f"[ProposalGenerator] Generated {len(self._proposals)} proposals")
        return self._proposals

    def _generate_from_pattern(self, pattern: PatternObservation) -> list[EvolutionProposal]:
        """
        从单个模式生成提案。

        Args:
            pattern: 模式观察

        Returns:
            生成的提案列表
        """
        proposals = []

        if pattern.pattern_type == "success_pattern":
            proposals = self._generate_from_success_pattern(pattern)
        elif pattern.pattern_type == "failure_pattern":
            proposals = self._generate_from_failure_pattern(pattern)
        elif pattern.pattern_type == "optimization_pattern":
            proposals = self._generate_from_optimization_pattern(pattern)

        return proposals

    def _generate_from_success_pattern(self, pattern: PatternObservation) -> list[EvolutionProposal]:
        """从成功模式生成提案"""
        proposals = []

        # 检查是否是能力组合模式
        if "combination" in pattern.description.lower() or "+" in pattern.description:
            # 提取能力名称
            capabilities = self._extract_capabilities_from_description(pattern.description)
            if len(capabilities) >= 2:
                proposal = EvolutionProposal(
                    title=f"Create combined skill for {', '.join(capabilities[:2])}",
                    description=f"Create a new skill that combines {', '.join(capabilities)} into a single workflow.",
                    rationale=f"This capability combination has a {pattern.confidence:.0%} success rate across {pattern.frequency} executions.",
                    proposal_type="new_skill",
                    affected_capabilities=capabilities,
                    expected_benefit="Reduce task complexity and improve execution efficiency",
                    risk_level="low",
                    implementation_steps=[
                        f"Analyze common usage patterns of {', '.join(capabilities)}",
                        "Design combined skill interface",
                        "Implement skill logic",
                        "Add tests and documentation",
                    ],
                )
                proposals.append(proposal)

        # 检查是否是步骤序列模式
        elif "sequence" in pattern.description.lower() or "step" in pattern.description.lower():
            steps = self._extract_steps_from_description(pattern.description)
            if steps:
                proposal = EvolutionProposal(
                    title=f"Document best practice: {' -> '.join(steps[:3])}",
                    description=f"Document and formalize the successful step sequence: {' -> '.join(steps)}",
                    rationale=f"This step sequence has proven effective in {pattern.frequency} successful executions.",
                    proposal_type="process_change",
                    affected_capabilities=steps,
                    expected_benefit="Improve task success rate through standardized workflow",
                    risk_level="low",
                    implementation_steps=[
                        "Document the step sequence as a best practice",
                        "Create a guide or template",
                        "Train the system to prefer this sequence",
                    ],
                )
                proposals.append(proposal)

        # 检查是否是可靠能力模式
        elif "reliable" in pattern.description.lower():
            cap = self._extract_single_capability(pattern.description)
            if cap:
                proposal = EvolutionProposal(
                    title=f"Promote {cap} as primary capability",
                    description=f"Mark {cap} as a recommended primary capability for relevant tasks.",
                    rationale=f"This capability has demonstrated high reliability with {pattern.confidence:.0%} success rate.",
                    proposal_type="skill_improvement",
                    affected_capabilities=[cap],
                    expected_benefit="Increase task success rate by preferentially using reliable capabilities",
                    risk_level="low",
                    implementation_steps=[
                        f"Update capability metadata for {cap}",
                        "Add priority scoring for capability selection",
                        "Update system prompts to recommend this capability",
                    ],
                )
                proposals.append(proposal)

        return proposals

    def _generate_from_failure_pattern(self, pattern: PatternObservation) -> list[EvolutionProposal]:
        """从失败模式生成提案"""
        proposals = []

        # 检查是否是常见错误模式
        if "common failure" in pattern.description.lower() or "error" in pattern.description.lower():
            proposal = EvolutionProposal(
                title=f"Add error handling for: {pattern.description[:50]}",
                description=f"Implement robust error handling and recovery for the common failure: {pattern.description}",
                rationale=f"This failure occurred {pattern.frequency} times with {pattern.confidence:.0%} frequency in failed tasks.",
                proposal_type="skill_improvement",
                affected_capabilities=[],
                expected_benefit=f"Reduce failure rate by handling this common error (affects ~{pattern.frequency} tasks)",
                risk_level="medium",
                implementation_steps=[
                    "Identify the root cause of the failure",
                    "Design error handling strategy",
                    "Implement fallback mechanism",
                    "Add tests for error scenarios",
                ],
            )
            proposals.append(proposal)

        # 检查是否是高失败率能力
        elif "high failure rate" in pattern.description.lower():
            cap = self._extract_single_capability(pattern.description)
            if cap:
                proposal = EvolutionProposal(
                    title=f"Improve reliability of {cap}",
                    description=f"Investigate and fix issues causing high failure rate in {cap}",
                    rationale=f"Capability {cap} has a high failure rate that impacts overall system reliability.",
                    proposal_type="skill_improvement",
                    affected_capabilities=[cap],
                    expected_benefit=f"Improve success rate for tasks using {cap}",
                    risk_level="medium",
                    implementation_steps=[
                        f"Analyze failure cases for {cap}",
                        "Identify common failure causes",
                        "Implement fixes and improvements",
                        "Add monitoring and alerts",
                    ],
                )
                proposals.append(proposal)

        # 检查是否是步骤失败
        elif "step" in pattern.description.lower() and "fail" in pattern.description.lower():
            step_name = self._extract_step_name(pattern.description)
            if step_name:
                proposal = EvolutionProposal(
                    title=f"Add fallback for step: {step_name}",
                    description=f"Implement fallback mechanism for step '{step_name}' to improve resilience",
                    rationale=f"Step '{step_name}' frequently fails, affecting {pattern.frequency} tasks.",
                    proposal_type="skill_improvement",
                    affected_capabilities=[step_name],
                    expected_benefit="Reduce task failures by providing fallback options",
                    risk_level="low",
                    implementation_steps=[
                        f"Identify alternative approaches for {step_name}",
                        "Implement fallback logic",
                        "Add retry mechanism with backoff",
                    ],
                )
                proposals.append(proposal)

        return proposals

    def _generate_from_optimization_pattern(self, pattern: PatternObservation) -> list[EvolutionProposal]:
        """从优化模式生成提案"""
        proposals = []

        # 检查是否是性能问题
        if "slow" in pattern.description.lower() or "performance" in pattern.description.lower():
            cap = self._extract_single_capability(pattern.description)
            if cap:
                proposal = EvolutionProposal(
                    title=f"Optimize performance of {cap}",
                    description=f"Investigate and optimize the performance of {cap}",
                    rationale=f"Capability {cap} is associated with slow executions, affecting overall task duration.",
                    proposal_type="skill_improvement",
                    affected_capabilities=[cap],
                    expected_benefit="Reduce average task execution time",
                    risk_level="medium",
                    implementation_steps=[
                        f"Profile {cap} to identify bottlenecks",
                        "Optimize critical paths",
                        "Add caching where appropriate",
                        "Monitor performance improvements",
                    ],
                )
                proposals.append(proposal)

        # 检查是否是能力协同
        elif "together" in pattern.description.lower() or "co-occurred" in pattern.description.lower():
            capabilities = self._extract_capabilities_from_description(pattern.description)
            if len(capabilities) >= 2:
                proposal = EvolutionProposal(
                    title=f"Create workflow for {capabilities[0]} + {capabilities[1]}",
                    description=f"Create an optimized workflow combining {capabilities[0]} and {capabilities[1]}",
                    rationale=f"These capabilities are frequently used together in {pattern.frequency} traces.",
                    proposal_type="new_skill",
                    affected_capabilities=capabilities[:2],
                    expected_benefit="Streamline common workflows, reduce decision overhead",
                    risk_level="low",
                    implementation_steps=[
                        f"Analyze common patterns with {capabilities[0]} and {capabilities[1]}",
                        "Design combined workflow interface",
                        "Implement with optimized handoffs",
                        "Add documentation",
                    ],
                )
                proposals.append(proposal)

        return proposals

    # ==================== 辅助方法 ====================

    def _extract_capabilities_from_description(self, description: str) -> list[str]:
        """从描述中提取能力名称"""
        import re
        # 查找引号中的内容或特定模式
        quoted = re.findall(r"'([^']+)'", description)
        if quoted:
            return quoted

        # 查找 "capability X" 模式
        cap_pattern = re.findall(r"capability[:\s]+(\w+)", description, re.IGNORECASE)
        if cap_pattern:
            return cap_pattern

        # 查找工具名称格式的词
        words = re.findall(r'\b([a-z_]+)\b', description.lower())
        return [w for w in words if len(w) > 3 and w not in ('this', 'that', 'with', 'from', 'have', 'been', 'often', 'using')]

    def _extract_single_capability(self, description: str) -> str | None:
        """从描述中提取单个能力名称"""
        capabilities = self._extract_capabilities_from_description(description)
        return capabilities[0] if capabilities else None

    def _extract_steps_from_description(self, description: str) -> list[str]:
        """从描述中提取步骤名称"""
        import re
        # 查找箭头分隔的序列
        if " -> " in description:
            parts = description.split(" -> ")
            return [p.strip() for p in parts if p.strip()]

        # 查找引号中的步骤
        quoted = re.findall(r"'([^']+)'", description)
        return quoted if quoted else []

    def _extract_step_name(self, description: str) -> str | None:
        """从描述中提取步骤名称"""
        import re
        match = re.search(r"step[:\s]+'?([^']+)?", description, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return self._extract_single_capability(description)

    def _calculate_priority(self, proposal: EvolutionProposal) -> float:
        """计算提案优先级分数"""
        score = 0.0

        # 风险级别影响
        risk_scores = {"low": 3.0, "medium": 2.0, "high": 1.0}
        score += risk_scores.get(proposal.risk_level, 1.0)

        # 提案类型影响
        type_scores = {"new_skill": 2.5, "skill_improvement": 2.0, "process_change": 1.5}
        score += type_scores.get(proposal.proposal_type, 1.0)

        # 影响范围
        score += min(len(proposal.affected_capabilities) * 0.5, 2.0)

        return score

    def _deduplicate_proposals(self) -> None:
        """去重提案"""
        seen = set()
        unique = []

        for proposal in self._proposals:
            key = (proposal.title, proposal.proposal_type)
            if key not in seen:
                seen.add(key)
                unique.append(proposal)

        self._proposals = unique

    def _auto_approve(self) -> None:
        """自动批准低风险提案"""
        for proposal in self._proposals:
            if proposal.risk_level == self._config.auto_approve_risk_threshold:
                if proposal.status == "proposed":
                    proposal.approve()

    # ==================== 查询方法 ====================

    def get_proposals(self) -> list[EvolutionProposal]:
        """获取所有提案"""
        return self._proposals

    def get_proposals_by_type(self, proposal_type: str) -> list[EvolutionProposal]:
        """按类型获取提案"""
        return [p for p in self._proposals if p.proposal_type == proposal_type]

    def get_proposals_by_status(self, status: str) -> list[EvolutionProposal]:
        """按状态获取提案"""
        return [p for p in self._proposals if p.status == status]

    def get_approved_proposals(self) -> list[EvolutionProposal]:
        """获取已批准的提案"""
        return [p for p in self._proposals if p.status in ("approved", "implemented")]

    def get_pending_proposals(self) -> list[EvolutionProposal]:
        """获取待处理的提案"""
        return self.get_proposals_by_status("proposed")

    def get_top_proposals(self, n: int = 5) -> list[EvolutionProposal]:
        """获取最重要的N个提案"""
        return self._proposals[:n]