"""
BestPracticeManager - 最佳实践模板管理器

提供最佳实践模板的注册、查询、删除和加载功能：
- 内存中管理模板实例
- 从 YAML 文件加载模板
- 模板格式验证
"""

import logging
from pathlib import Path

import yaml

from .models import BestPracticeConfig, StepTemplate, SubAgentConfig

logger = logging.getLogger(__name__)


class BestPracticeManagerError(Exception):
    """最佳实践管理器错误"""
    pass


class BestPracticeManager:
    """
    最佳实践模板管理器

    负责最佳实践模板的注册、查询、删除和加载。
    模板存储在内存中，支持从 YAML 文件批量加载。
    """

    def __init__(self) -> None:
        """初始化模板管理器"""
        self._templates: dict[str, BestPracticeConfig] = {}

    def register(self, template: BestPracticeConfig) -> bool:
        """
        注册模板

        Args:
            template: 要注册的模板配置

        Returns:
            是否注册成功
        """
        if not self._validate_template(template):
            logger.warning(f"Invalid template: {template.id}")
            return False

        self._templates[template.id] = template
        logger.info(f"Template registered: {template.id}")
        return True

    def unregister(self, template_id: str) -> bool:
        """
        注销模板

        Args:
            template_id: 模板 ID

        Returns:
            是否注销成功
        """
        if template_id in self._templates:
            del self._templates[template_id]
            logger.info(f"Template unregistered: {template_id}")
            return True
        return False

    def get(self, template_id: str) -> BestPracticeConfig | None:
        """
        获取模板

        Args:
            template_id: 模板 ID

        Returns:
            模板配置，不存在则返回 None
        """
        return self._templates.get(template_id)

    def list_all(self) -> list[BestPracticeConfig]:
        """
        列出所有模板

        Returns:
            所有模板配置列表
        """
        return list(self._templates.values())

    def load_from_directory(self, path: Path | str) -> int:
        """
        从目录加载 YAML 模板

        Args:
            path: 模板目录路径

        Returns:
            成功加载的模板数量
        """
        if isinstance(path, str):
            path = Path(path)

        if not path.exists():
            logger.warning(f"Template directory not found: {path}")
            return 0

        count = 0
        for yaml_file in path.glob("*.yaml"):
            template = self._load_yaml_template(yaml_file)
            if template:
                if self.register(template):
                    count += 1

        # Also load .yml files
        for yaml_file in path.glob("*.yml"):
            template = self._load_yaml_template(yaml_file)
            if template:
                if self.register(template):
                    count += 1

        logger.info(f"Loaded {count} templates from {path}")
        return count

    def _load_yaml_template(self, yaml_path: Path) -> BestPracticeConfig | None:
        """
        从 YAML 文件加载模板

        Args:
            yaml_path: YAML 文件路径

        Returns:
            模板配置，加载失败返回 None
        """
        try:
            with open(yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                logger.warning(f"Empty YAML file: {yaml_path}")
                return None

            # 解析步骤
            steps = []
            for step_data in data.get("steps", []):
                sub_agent_data = step_data.get("sub_agent_config", {})

                sub_agent_config = SubAgentConfig(
                    name=sub_agent_data.get("name", ""),
                    role=sub_agent_data.get("role", ""),
                    system_prompt=sub_agent_data.get("system_prompt", ""),
                    skills=sub_agent_data.get("skills", []),
                    mcps=sub_agent_data.get("mcps", []),
                    tools=sub_agent_data.get("tools", []),
                )

                step = StepTemplate(
                    name=step_data.get("name", ""),
                    description=step_data.get("description", ""),
                    sub_agent_config=sub_agent_config,
                )
                steps.append(step)

            template = BestPracticeConfig(
                id=data.get("id", ""),
                name=data.get("name", ""),
                description=data.get("description", ""),
                steps=steps,
            )

            return template

        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error in {yaml_path}: {e}")
            return None
        except KeyError as e:
            logger.error(f"Missing required field in {yaml_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load template from {yaml_path}: {e}")
            return None

    def _validate_template(self, template: BestPracticeConfig) -> bool:
        """
        验证模板格式

        Args:
            template: 要验证的模板

        Returns:
            是否验证通过
        """
        # 验证基本字段
        if not template.id:
            logger.warning("Template ID is required")
            return False

        if not template.name:
            logger.warning(f"Template name is required for: {template.id}")
            return False

        if not template.description:
            logger.warning(f"Template description is required for: {template.id}")
            return False

        # 验证步骤
        for i, step in enumerate(template.steps):
            if not step.name:
                logger.warning(f"Step {i} name is required in template: {template.id}")
                return False

            if not step.sub_agent_config:
                logger.warning(f"Step {i} sub_agent_config is required in template: {template.id}")
                return False

            if not step.sub_agent_config.name:
                logger.warning(f"Step {i} sub_agent name is required in template: {template.id}")
                return False

            if not step.sub_agent_config.role:
                logger.warning(f"Step {i} sub_agent role is required in template: {template.id}")
                return False

        return True

    def clear(self) -> None:
        """清除所有模板"""
        self._templates.clear()
        logger.info("All templates cleared")

    def count(self) -> int:
        """获取模板数量"""
        return len(self._templates)