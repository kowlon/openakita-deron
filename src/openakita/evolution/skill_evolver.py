"""
技能进化器核心

负责根据进化提案执行实际的技能改进。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import EvolutionProposal
from .proposal_generator import ProposalGenerator
from .experience_store import ExperienceStore

logger = logging.getLogger(__name__)


@dataclass
class EvolverConfig:
    """进化器配置"""
    skills_directory: Path = field(default_factory=lambda: Path("skills"))
    backup_enabled: bool = True
    max_backup_age_days: int = 30
    dry_run: bool = False  # 干运行模式，不实际修改文件


class EvolutionResult:
    """进化结果"""

    def __init__(
        self,
        success: bool,
        proposal_id: str,
        message: str = "",
        changes: list[str] | None = None,
    ):
        self.success = success
        self.proposal_id = proposal_id
        self.message = message
        self.changes = changes or []
        self.timestamp = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "proposal_id": self.proposal_id,
            "message": self.message,
            "changes": self.changes,
            "timestamp": self.timestamp.isoformat(),
        }


class SkillEvolver:
    """
    技能进化器

    负责执行技能改进：
    - 创建新技能
    - 改进现有技能
    - 更新流程文档
    """

    def __init__(
        self,
        store: ExperienceStore,
        generator: ProposalGenerator,
        config: EvolverConfig | None = None,
    ):
        """
        初始化技能进化器。

        Args:
            store: 经验存储
            generator: 提案生成器
            config: 进化器配置
        """
        self._store = store
        self._generator = generator
        self._config = config or EvolverConfig()
        self._results: list[EvolutionResult] = []

    # ==================== 进化执行 ====================

    def evolve(self, proposal: EvolutionProposal) -> EvolutionResult:
        """
        执行进化提案。

        Args:
            proposal: 进化提案

        Returns:
            进化结果
        """
        logger.info(f"[SkillEvolver] Executing proposal: {proposal.title}")

        try:
            if proposal.proposal_type == "new_skill":
                result = self._create_new_skill(proposal)
            elif proposal.proposal_type == "skill_improvement":
                result = self._improve_skill(proposal)
            elif proposal.proposal_type == "process_change":
                result = self._update_process(proposal)
            else:
                result = EvolutionResult(
                    success=False,
                    proposal_id=proposal.proposal_id,
                    message=f"Unknown proposal type: {proposal.proposal_type}",
                )

            if result.success:
                proposal.implement()

            self._results.append(result)
            return result

        except Exception as e:
            logger.error(f"[SkillEvolver] Evolution failed: {e}")
            result = EvolutionResult(
                success=False,
                proposal_id=proposal.proposal_id,
                message=str(e),
            )
            self._results.append(result)
            return result

    def evolve_all_approved(self) -> list[EvolutionResult]:
        """
        执行所有已批准的提案。

        Returns:
            进化结果列表
        """
        approved = self._generator.get_approved_proposals()
        results = []

        for proposal in approved:
            if proposal.status == "approved":
                result = self.evolve(proposal)
                results.append(result)

        return results

    # ==================== 具体进化操作 ====================

    def _create_new_skill(self, proposal: EvolutionProposal) -> EvolutionResult:
        """
        创建新技能。

        Args:
            proposal: 提案

        Returns:
            进化结果
        """
        if self._config.dry_run:
            return EvolutionResult(
                success=True,
                proposal_id=proposal.proposal_id,
                message="[DRY RUN] Would create new skill",
                changes=[f"Would create skill based on: {proposal.title}"],
            )

        # 确定技能名称
        skill_name = self._generate_skill_name(proposal)
        skill_path = self._config.skills_directory / skill_name

        # 检查是否已存在
        if skill_path.exists():
            return EvolutionResult(
                success=False,
                proposal_id=proposal.proposal_id,
                message=f"Skill already exists: {skill_name}",
            )

        # 创建技能目录
        skill_path.mkdir(parents=True, exist_ok=True)

        changes = []

        # 创建 SKILL.md
        skill_md = self._generate_skill_md(proposal)
        skill_md_path = skill_path / "SKILL.md"
        skill_md_path.write_text(skill_md)
        changes.append(f"Created {skill_md_path}")

        # 创建 skill.py 模板
        skill_py = self._generate_skill_py(proposal)
        skill_py_path = skill_path / "skill.py"
        skill_py_path.write_text(skill_py)
        changes.append(f"Created {skill_py_path}")

        logger.info(f"[SkillEvolver] Created skill: {skill_name}")

        return EvolutionResult(
            success=True,
            proposal_id=proposal.proposal_id,
            message=f"Created new skill: {skill_name}",
            changes=changes,
        )

    def _improve_skill(self, proposal: EvolutionProposal) -> EvolutionResult:
        """
        改进现有技能。

        Args:
            proposal: 提案

        Returns:
            进化结果
        """
        if self._config.dry_run:
            return EvolutionResult(
                success=True,
                proposal_id=proposal.proposal_id,
                message="[DRY RUN] Would improve skill",
                changes=[f"Would apply: {proposal.title}"],
            )

        # 尝试找到要改进的技能
        affected = proposal.affected_capabilities
        if not affected:
            return EvolutionResult(
                success=False,
                proposal_id=proposal.proposal_id,
                message="No affected capabilities specified",
            )

        changes = []

        for capability in affected:
            skill_path = self._config.skills_directory / capability
            if skill_path.exists():
                # 备份
                if self._config.backup_enabled:
                    self._backup_skill(skill_path)

                # 更新 SKILL.md
                skill_md_path = skill_path / "SKILL.md"
                if skill_md_path.exists():
                    current_content = skill_md_path.read_text()
                    updated = self._update_skill_md(current_content, proposal)
                    skill_md_path.write_text(updated)
                    changes.append(f"Updated {skill_md_path}")

        return EvolutionResult(
            success=True,
            proposal_id=proposal.proposal_id,
            message=f"Improved skill(s): {', '.join(affected)}",
            changes=changes,
        )

    def _update_process(self, proposal: EvolutionProposal) -> EvolutionResult:
        """
        更新流程文档。

        Args:
            proposal: 提案

        Returns:
            进化结果
        """
        if self._config.dry_run:
            return EvolutionResult(
                success=True,
                proposal_id=proposal.proposal_id,
                message="[DRY RUN] Would update process",
                changes=[f"Would document: {proposal.title}"],
            )

        # 创建流程文档
        docs_path = self._config.skills_directory / "docs" / "processes"
        docs_path.mkdir(parents=True, exist_ok=True)

        process_name = self._generate_process_name(proposal)
        process_path = docs_path / f"{process_name}.md"

        content = self._generate_process_md(proposal)
        process_path.write_text(content)

        return EvolutionResult(
            success=True,
            proposal_id=proposal.proposal_id,
            message=f"Created process documentation: {process_name}",
            changes=[f"Created {process_path}"],
        )

    # ==================== 辅助方法 ====================

    def _generate_skill_name(self, proposal: EvolutionProposal) -> str:
        """生成技能名称"""
        # 从标题生成
        import re
        name = proposal.title.lower()
        name = re.sub(r'[^a-z0-9]+', '_', name)
        name = re.sub(r'_+', '_', name).strip('_')
        return name or f"new_skill_{proposal.proposal_id}"

    def _generate_skill_md(self, proposal: EvolutionProposal) -> str:
        """生成 SKILL.md 内容"""
        return f"""# {proposal.title}

{proposal.description}

## Rationale

{proposal.rationale}

## Expected Benefit

{proposal.expected_benefit}

## Implementation

{chr(10).join(f'- {step}' for step in proposal.implementation_steps)}

## Metadata

- Created: {datetime.now().isoformat()}
- Proposal ID: {proposal.proposal_id}
- Risk Level: {proposal.risk_level}
"""

    def _generate_skill_py(self, proposal: EvolutionProposal) -> str:
        """生成 skill.py 模板"""
        return f'''"""
{proposal.title}

Auto-generated skill based on evolution proposal {proposal.proposal_id}.
"""
from __future__ import annotations

from agentskills import skill, SkillContext


@skill(
    name="{self._generate_skill_name(proposal)}",
    description="{proposal.description[:100]}",
)
async def execute(ctx: SkillContext, **kwargs) -> dict:
    """
    Execute the skill.

    Args:
        ctx: Skill context
        **kwargs: Skill parameters

    Returns:
        Execution result
    """
    # TODO: Implement skill logic
    # This is an auto-generated template based on proposal {proposal.proposal_id}

    return {{
        "status": "success",
        "message": "Skill executed successfully",
        "data": {{}}
    }}
'''

    def _generate_process_name(self, proposal: EvolutionProposal) -> str:
        """生成流程名称"""
        import re
        name = proposal.title.lower()
        name = re.sub(r'[^a-z0-9]+', '_', name)
        name = re.sub(r'_+', '_', name).strip('_')
        return name or f"process_{proposal.proposal_id}"

    def _generate_process_md(self, proposal: EvolutionProposal) -> str:
        """生成流程文档内容"""
        return f"""# {proposal.title}

{proposal.description}

## Background

{proposal.rationale}

## Steps

{chr(10).join(f'{i+1}. {step}' for i, step in enumerate(proposal.implementation_steps))}

## Expected Outcome

{proposal.expected_benefit}

## Risk Level

{proposal.risk_level}

---

*Generated on {datetime.now().isoformat()} from proposal {proposal.proposal_id}*
"""

    def _update_skill_md(self, current: str, proposal: EvolutionProposal) -> str:
        """更新 SKILL.md 内容"""
        # 添加改进记录
        improvement_section = f"""

## Evolution History

### {datetime.now().strftime("%Y-%m-%d")}

{proposal.description}

- Proposal ID: {proposal.proposal_id}
- Rationale: {proposal.rationale}
- Expected Benefit: {proposal.expected_benefit}
"""
        return current + improvement_section

    def _backup_skill(self, skill_path: Path) -> Path:
        """备份技能"""
        import shutil

        backup_dir = skill_path.parent / "backups"
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"{skill_path.name}_{timestamp}"

        shutil.copytree(skill_path, backup_path)
        logger.debug(f"[SkillEvolver] Backed up to {backup_path}")

        return backup_path

    # ==================== 查询方法 ====================

    def get_results(self) -> list[EvolutionResult]:
        """获取所有进化结果"""
        return self._results

    def get_successful_results(self) -> list[EvolutionResult]:
        """获取成功的进化结果"""
        return [r for r in self._results if r.success]

    def get_failed_results(self) -> list[EvolutionResult]:
        """获取失败的进化结果"""
        return [r for r in self._results if not r.success]

    def get_evolution_stats(self) -> dict[str, Any]:
        """获取进化统计"""
        total = len(self._results)
        successful = len(self.get_successful_results())
        failed = len(self.get_failed_results())

        return {
            "total_evolutions": total,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total if total > 0 else 0,
        }