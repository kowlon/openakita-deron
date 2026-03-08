"""
PromptConfigLoader - 统一配置加载器

提供统一的配置加载机制，支持：
- 从目录批量加载 YAML 配置
- 热重载（可选，依赖 watchdog）
- 配置验证
- 统一访问接口

支持的配置类型：
- RouterPromptConfig: 路由判断配置
- BestPracticeTriggerConfig: 最佳实践触发配置
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

logger = logging.getLogger(__name__)


# ==================== 配置模型 ====================


@dataclass
class RouterPromptConfig:
    """
    路由判断提示词配置

    用于 LLM 判断用户输入是否应该路由到现有任务或触发新任务。

    属性：
        name: 配置名称（用于检索）
        version: 配置版本
        language: 语言标识（如 "zh", "en"）
        description: 配置描述
        system_prompt: 系统提示词模板
        examples: 示例列表，用于 few-shot learning
        routing_rules: 路由规则描述
        metadata: 额外元数据
    """

    name: str
    version: str = "1.0.0"
    language: str = "zh"
    description: str = ""
    system_prompt: str = ""
    examples: list[dict[str, str]] = field(default_factory=list)
    routing_rules: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "name": self.name,
            "version": self.version,
            "language": self.language,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "examples": self.examples,
            "routing_rules": self.routing_rules,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RouterPromptConfig":
        """从字典反序列化"""
        return cls(
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            language=data.get("language", "zh"),
            description=data.get("description", ""),
            system_prompt=data.get("system_prompt", ""),
            examples=data.get("examples", []),
            routing_rules=data.get("routing_rules", []),
            metadata=data.get("metadata", {}),
        )

    def validate(self) -> list[str]:
        """
        验证配置

        Returns:
            错误消息列表，空列表表示验证通过
        """
        errors = []

        if not self.name:
            errors.append("name is required")

        if not self.system_prompt:
            errors.append("system_prompt is required")

        # 验证示例格式
        for i, example in enumerate(self.examples):
            if "user" not in example or "response" not in example:
                errors.append(f"example[{i}] must have 'user' and 'response' fields")

        return errors


@dataclass
class BestPracticeTriggerConfig:
    """
    最佳实践触发配置

    用于 LLM 判断用户输入是否触发某个最佳实践任务。

    属性：
        name: 配置名称（用于检索）
        version: 配置版本
        language: 语言标识（如 "zh", "en"）
        description: 配置描述
        trigger_instructions: 触发判断指令
        best_practices: 可用的最佳实践列表及其触发条件
        examples: 示例列表，用于 few-shot learning
        metadata: 额外元数据
    """

    name: str
    version: str = "1.0.0"
    language: str = "zh"
    description: str = ""
    trigger_instructions: str = ""
    best_practices: list[dict[str, Any]] = field(default_factory=list)
    examples: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "name": self.name,
            "version": self.version,
            "language": self.language,
            "description": self.description,
            "trigger_instructions": self.trigger_instructions,
            "best_practices": self.best_practices,
            "examples": self.examples,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BestPracticeTriggerConfig":
        """从字典反序列化"""
        return cls(
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            language=data.get("language", "zh"),
            description=data.get("description", ""),
            trigger_instructions=data.get("trigger_instructions", ""),
            best_practices=data.get("best_practices", []),
            examples=data.get("examples", []),
            metadata=data.get("metadata", {}),
        )

    def validate(self) -> list[str]:
        """
        验证配置

        Returns:
            错误消息列表，空列表表示验证通过
        """
        errors = []

        if not self.name:
            errors.append("name is required")

        if not self.trigger_instructions:
            errors.append("trigger_instructions is required")

        # 验证最佳实践格式
        for i, bp in enumerate(self.best_practices):
            if "id" not in bp:
                errors.append(f"best_practices[{i}] must have 'id' field")
            if "name" not in bp:
                errors.append(f"best_practices[{i}] must have 'name' field")

        # 验证示例格式
        for i, example in enumerate(self.examples):
            if "user" not in example or "response" not in example:
                errors.append(f"example[{i}] must have 'user' and 'response' fields")

        return errors


# ==================== 配置加载异常 ====================


class PromptConfigError(Exception):
    """配置加载错误"""
    pass


class ConfigValidationError(PromptConfigError):
    """配置验证错误"""
    pass


class ConfigNotFoundError(PromptConfigError):
    """配置不存在错误"""
    pass


# ==================== 配置加载器 ====================


class PromptConfigLoader:
    """
    统一配置加载器

    从目录批量加载 YAML 配置，支持热重载和配置验证。

    配置目录结构：
        data/prompts/
        ├── router/
        │   ├── route_decision.yaml
        │   └── route_decision_en.yaml
        └── best_practice_trigger/
            ├── bp_trigger.yaml
            └── bp_trigger_en.yaml

    使用示例：
        loader = PromptConfigLoader()

        # 从目录加载
        loader.load_from_directory("data/prompts/router", "router")
        loader.load_from_directory("data/prompts/best_practice_trigger", "bp_trigger")

        # 获取配置
        router_config = loader.get_router_prompt("route_decision")
        bp_config = loader.get_bp_trigger_prompt("bp_trigger")

        # 重载所有配置
        loader.reload_all()

        # 启用热重载（需要 watchdog）
        loader.enable_hot_reload()
    """

    def __init__(self):
        """初始化配置加载器"""
        # 配置存储
        self._router_prompts: dict[str, RouterPromptConfig] = {}
        self._bp_trigger_prompts: dict[str, BestPracticeTriggerConfig] = {}

        # 配置路径记录（用于重载）
        self._config_paths: dict[str, Path] = {}

        # 热重载相关
        self._watcher_thread: threading.Thread | None = None
        self._watcher_running: bool = False
        self._observer: Any = None

    # ==================== 加载方法 ====================

    def load_from_directory(
        self,
        directory: str | Path,
        config_type: str,
    ) -> int:
        """
        从目录批量加载配置

        Args:
            directory: 配置目录路径
            config_type: 配置类型 ("router" 或 "bp_trigger")

        Returns:
            成功加载的配置数量

        Raises:
            PromptConfigError: 加载失败
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            logger.warning(f"Config directory not found: {directory}")
            return 0

        if not dir_path.is_dir():
            raise PromptConfigError(f"Not a directory: {directory}")

        loaded_count = 0

        # 遍历目录中的 YAML 文件
        for yaml_file in dir_path.glob("*.yaml"):
            try:
                config = self._load_yaml_file(yaml_file, config_type)
                if config:
                    loaded_count += 1
                    # 记录路径用于重载
                    config_key = f"{config_type}:{config.name}"
                    self._config_paths[config_key] = yaml_file
            except Exception as e:
                logger.error(f"Failed to load config from {yaml_file}: {e}")

        # 也加载 .yml 文件
        for yaml_file in dir_path.glob("*.yml"):
            try:
                config = self._load_yaml_file(yaml_file, config_type)
                if config:
                    loaded_count += 1
                    config_key = f"{config_type}:{config.name}"
                    self._config_paths[config_key] = yaml_file
            except Exception as e:
                logger.error(f"Failed to load config from {yaml_file}: {e}")

        logger.info(f"Loaded {loaded_count} {config_type} configs from {directory}")
        return loaded_count

    def _load_yaml_file(
        self,
        file_path: Path,
        config_type: str,
    ) -> RouterPromptConfig | BestPracticeTriggerConfig | None:
        """
        加载单个 YAML 配置文件

        Args:
            file_path: YAML 文件路径
            config_type: 配置类型

        Returns:
            配置对象，加载失败返回 None
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                logger.warning(f"Empty config file: {file_path}")
                return None

            # 根据类型创建配置对象
            if config_type == "router":
                config = RouterPromptConfig.from_dict(data)
                self._router_prompts[config.name] = config
            elif config_type == "bp_trigger":
                config = BestPracticeTriggerConfig.from_dict(data)
                self._bp_trigger_prompts[config.name] = config
            else:
                raise PromptConfigError(f"Unknown config type: {config_type}")

            # 验证配置
            errors = config.validate()
            if errors:
                logger.warning(f"Config validation warnings for {file_path}: {errors}")

            logger.debug(f"Loaded config: {config.name} from {file_path}")
            return config

        except yaml.YAMLError as e:
            raise PromptConfigError(f"YAML parsing error in {file_path}: {e}")
        except Exception as e:
            raise PromptConfigError(f"Error loading {file_path}: {e}")

    def load_router_prompts(self, directory: str | Path) -> int:
        """
        加载路由提示词配置

        Args:
            directory: 配置目录路径

        Returns:
            成功加载的配置数量
        """
        return self.load_from_directory(directory, "router")

    def load_bp_trigger_prompts(self, directory: str | Path) -> int:
        """
        加载最佳实践触发配置

        Args:
            directory: 配置目录路径

        Returns:
            成功加载的配置数量
        """
        return self.load_from_directory(directory, "bp_trigger")

    # ==================== 访问方法 ====================

    def get_router_prompt(self, name: str) -> RouterPromptConfig:
        """
        获取路由提示词配置

        Args:
            name: 配置名称

        Returns:
            RouterPromptConfig 对象

        Raises:
            ConfigNotFoundError: 配置不存在
        """
        if name not in self._router_prompts:
            raise ConfigNotFoundError(f"Router prompt config not found: {name}")
        return self._router_prompts[name]

    def get_bp_trigger_prompt(self, name: str) -> BestPracticeTriggerConfig:
        """
        获取最佳实践触发配置

        Args:
            name: 配置名称

        Returns:
            BestPracticeTriggerConfig 对象

        Raises:
            ConfigNotFoundError: 配置不存在
        """
        if name not in self._bp_trigger_prompts:
            raise ConfigNotFoundError(f"BP trigger config not found: {name}")
        return self._bp_trigger_prompts[name]

    def list_router_prompts(self) -> list[str]:
        """列出所有路由提示词配置名称"""
        return list(self._router_prompts.keys())

    def list_bp_trigger_prompts(self) -> list[str]:
        """列出所有最佳实践触发配置名称"""
        return list(self._bp_trigger_prompts.keys())

    # ==================== 重载方法 ====================

    def reload_all(self) -> dict[str, int]:
        """
        重载所有配置

        Returns:
            各类型配置的重载数量
        """
        # 清空现有配置
        self._router_prompts.clear()
        self._bp_trigger_prompts.clear()

        # 按目录分组重载
        type_dirs: dict[str, set[Path]] = {}

        for config_key, path in self._config_paths.items():
            config_type = config_key.split(":")[0]
            if config_type not in type_dirs:
                type_dirs[config_type] = set()
            type_dirs[config_type].add(path.parent)

        # 重新加载
        result = {}
        for config_type, directories in type_dirs.items():
            count = 0
            for directory in directories:
                count += self.load_from_directory(directory, config_type)
            result[config_type] = count

        logger.info(f"Reloaded configs: {result}")
        return result

    def reload_config(self, name: str, config_type: str) -> bool:
        """
        重载单个配置

        Args:
            name: 配置名称
            config_type: 配置类型

        Returns:
            是否重载成功
        """
        config_key = f"{config_type}:{name}"
        if config_key not in self._config_paths:
            return False

        file_path = self._config_paths[config_key]
        try:
            config = self._load_yaml_file(file_path, config_type)
            return config is not None
        except Exception as e:
            logger.error(f"Failed to reload config {name}: {e}")
            return False

    # ==================== 热重载 ====================

    def enable_hot_reload(self) -> bool:
        """
        启用热重载

        使用 watchdog 监听文件变化，自动重载配置。

        Returns:
            是否成功启用
        """
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler, FileModifiedEvent
        except ImportError:
            logger.warning(
                "watchdog not installed. Hot reload is disabled. "
                "Install with: pip install watchdog"
            )
            return False

        if self._watcher_running:
            logger.warning("Hot reload already enabled")
            return True

        class ConfigFileHandler(FileSystemEventHandler):
            """配置文件变化处理器"""

            def __init__(self, loader: "PromptConfigLoader"):
                self.loader = loader

            def on_modified(self, event: FileModifiedEvent) -> None:
                if event.is_directory:
                    return

                # 查找对应的配置
                path = Path(event.src_path)
                for config_key, config_path in self.loader._config_paths.items():
                    if config_path.resolve() == path.resolve():
                        config_type, name = config_key.split(":")
                        logger.info(f"Config file modified, reloading: {config_key}")
                        self.loader.reload_config(name, config_type)
                        break

        # 创建观察者
        handler = ConfigFileHandler(self)
        self._observer = Observer()

        # 监听所有配置目录
        watched_dirs: set[Path] = set()
        for config_path in self._config_paths.values():
            parent_dir = config_path.parent
            if parent_dir not in watched_dirs:
                self._observer.schedule(handler, str(parent_dir), recursive=False)
                watched_dirs.add(parent_dir)

        # 启动观察者
        self._observer.start()
        self._watcher_running = True

        logger.info("Hot reload enabled")
        return True

    def disable_hot_reload(self) -> None:
        """禁用热重载"""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None

        self._watcher_running = False
        logger.info("Hot reload disabled")

    # ==================== 验证方法 ====================

    def validate_all(self) -> dict[str, list[str]]:
        """
        验证所有配置

        Returns:
            各配置的验证错误，键为配置名，值为错误列表
        """
        errors: dict[str, list[str]] = {}

        for name, config in self._router_prompts.items():
            config_errors = config.validate()
            if config_errors:
                errors[f"router:{name}"] = config_errors

        for name, config in self._bp_trigger_prompts.items():
            config_errors = config.validate()
            if config_errors:
                errors[f"bp_trigger:{name}"] = config_errors

        return errors

    # ==================== 统计信息 ====================

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "router_prompts_count": len(self._router_prompts),
            "bp_trigger_prompts_count": len(self._bp_trigger_prompts),
            "config_paths_count": len(self._config_paths),
            "hot_reload_enabled": self._watcher_running,
            "router_prompts": list(self._router_prompts.keys()),
            "bp_trigger_prompts": list(self._bp_trigger_prompts.keys()),
        }

    # ==================== 上下文管理 ====================

    def clear_all(self) -> None:
        """清空所有配置"""
        self._router_prompts.clear()
        self._bp_trigger_prompts.clear()
        self._config_paths.clear()
        logger.info("All configs cleared")

    def __enter__(self) -> "PromptConfigLoader":
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器退出"""
        self.disable_hot_reload()


# ==================== 全局实例 ====================

_loader_instance: PromptConfigLoader | None = None


def get_prompt_loader() -> PromptConfigLoader:
    """获取全局 PromptConfigLoader 实例"""
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = PromptConfigLoader()
    return _loader_instance


def clear_prompt_loader() -> None:
    """清空全局 PromptConfigLoader 实例"""
    global _loader_instance
    if _loader_instance:
        _loader_instance.disable_hot_reload()
        _loader_instance.clear_all()
    _loader_instance = None