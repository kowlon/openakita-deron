"""
SessionTasks - 会话任务管理器

管理单个会话内所有任务的状态：
- 维护任务集合与活跃任务
- 提供路由索引与上下文管理
- 确保同一时刻仅一个活跃任务（单活跃任务原则）
- 支持 LLM 智能路由判断（带关键词匹配回退）
"""

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

import yaml

from .models import OrchestrationTask, RouterPromptConfig, TaskStatus

if TYPE_CHECKING:
    from ..llm.brain import Brain

logger = logging.getLogger(__name__)


@dataclass
class RouteResult:
    """
    路由判断结果

    描述用户输入应该被路由到哪个任务/步骤。
    """

    routed: bool  # 是否路由到任务
    task_id: str | None = None  # 目标任务 ID
    step_id: str | None = None  # 目标步骤 ID
    reason: str | None = None  # 路由原因


class SessionTasks:
    """
    会话级任务管理

    管理单个会话内所有任务的状态，确保同一时刻仅一个活跃任务。

    特性:
    - 单活跃任务原则
    - 任务路由判断（支持 LLM 智能判断 + 关键词回退）
    - 自动暂停检测
    - 线程安全
    """

    # 自动暂停阈值（连续无关对话次数）
    AUTO_SUSPEND_THRESHOLD = 5

    def __init__(
        self,
        session_id: str,
        brain: "Brain | None" = None,
        router_config: RouterPromptConfig | None = None,
        router_config_path: str | None = None,
    ):
        """
        初始化会话任务管理器

        Args:
            session_id: 会话 ID
            brain: Brain 实例（用于 LLM 路由判断）
            router_config: 路由 prompt 配置（可选）
            router_config_path: 路由 prompt 配置文件路径（可选）
        """
        self._session_id = session_id
        self._active_task_id: str | None = None
        self._tasks: dict[str, OrchestrationTask] = {}
        self._lock = threading.Lock()

        # LLM 路由相关
        self._brain = brain
        self._router_config: RouterPromptConfig | None = None

        # 加载路由配置
        if router_config:
            self._router_config = router_config
        elif router_config_path:
            self._load_router_config(router_config_path)
        else:
            # 尝试加载默认配置
            self._load_default_router_config()

    # ==================== 属性 ====================

    @property
    def session_id(self) -> str:
        """会话 ID"""
        return self._session_id

    @property
    def active_task_id(self) -> str | None:
        """当前活跃任务 ID"""
        return self._active_task_id

    @property
    def tasks(self) -> dict[str, OrchestrationTask]:
        """所有任务（只读）"""
        return self._tasks.copy()

    @property
    def brain(self) -> "Brain | None":
        """LLM Brain 实例"""
        return self._brain

    @property
    def router_config(self) -> RouterPromptConfig | None:
        """路由 prompt 配置"""
        return self._router_config

    # ==================== 配置加载 ====================

    def _load_default_router_config(self) -> None:
        """加载默认路由配置"""
        default_paths = [
            Path("config/router_prompt.yaml"),
            Path("config/router_prompt.yml"),
        ]
        for path in default_paths:
            if path.exists():
                self._load_router_config(str(path))
                logger.info(f"Loaded default router config from {path}")
                return
        logger.debug("No default router config found, will use keyword matching")

    def _load_router_config(self, path: str) -> bool:
        """
        从 YAML 文件加载路由配置

        Args:
            path: 配置文件路径

        Returns:
            是否加载成功
        """
        try:
            config_path = Path(path)
            if not config_path.exists():
                logger.warning(f"Router config file not found: {path}")
                return False

            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                logger.warning(f"Empty router config file: {path}")
                return False

            self._router_config = RouterPromptConfig.from_dict(data)
            logger.info(f"Loaded router config from {path}, enabled={self._router_config.enabled}")
            return True

        except Exception as e:
            logger.error(f"Failed to load router config from {path}: {e}")
            return False

    def set_brain(self, brain: "Brain") -> None:
        """
        设置 Brain 实例

        Args:
            brain: Brain 实例
        """
        self._brain = brain
        logger.debug("Brain instance set for LLM routing")

    def set_router_config(self, config: RouterPromptConfig) -> None:
        """
        设置路由配置

        Args:
            config: 路由 prompt 配置
        """
        self._router_config = config
        logger.debug(f"Router config set, enabled={config.enabled}")

    def reload_router_config(self, path: str | None = None) -> bool:
        """
        重新加载路由配置

        Args:
            path: 配置文件路径（可选，默认使用当前配置路径）

        Returns:
            是否重载成功
        """
        if path:
            return self._load_router_config(path)
        return self._load_default_router_config()

    # ==================== 任务管理 ====================

    def get_active_task(self) -> OrchestrationTask | None:
        """
        获取当前活跃任务

        Returns:
            活跃任务对象，无活跃任务则返回 None
        """
        with self._lock:
            if self._active_task_id and self._active_task_id in self._tasks:
                return self._tasks[self._active_task_id]
            return None

    def activate_task(self, task_id: str) -> bool:
        """
        激活指定任务

        Args:
            task_id: 要激活的任务 ID

        Returns:
            是否激活成功
        """
        with self._lock:
            if task_id not in self._tasks:
                logger.warning(f"Cannot activate non-existent task: {task_id}")
                return False

            # 如果已有活跃任务，先取消
            if self._active_task_id and self._active_task_id != task_id:
                logger.info(f"Deactivating previous task: {self._active_task_id}")

            self._active_task_id = task_id
            logger.info(f"Activated task: {task_id}")
            return True

    def deactivate_task(self) -> str | None:
        """
        取消当前活跃任务

        Returns:
            被取消的任务 ID，无活跃任务则返回 None
        """
        with self._lock:
            if self._active_task_id:
                task_id = self._active_task_id
                self._active_task_id = None
                logger.info(f"Deactivated task: {task_id}")
                return task_id
            return None

    def add_task(self, task: OrchestrationTask) -> None:
        """
        添加新任务

        Args:
            task: 要添加的任务对象
        """
        with self._lock:
            self._tasks[task.id] = task
            logger.debug(f"Added task: {task.id}")

    def remove_task(self, task_id: str) -> bool:
        """
        移除任务

        Args:
            task_id: 要移除的任务 ID

        Returns:
            是否移除成功
        """
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]

                # 如果移除的是活跃任务，清除活跃状态
                if self._active_task_id == task_id:
                    self._active_task_id = None
                    logger.info(f"Removed active task: {task_id}")
                else:
                    logger.debug(f"Removed task: {task_id}")

                return True
            return False

    def get_task(self, task_id: str) -> OrchestrationTask | None:
        """
        获取指定任务

        Args:
            task_id: 任务 ID

        Returns:
            任务对象，不存在则返回 None
        """
        with self._lock:
            return self._tasks.get(task_id)

    def has_active_task(self) -> bool:
        """检查是否有活跃任务"""
        with self._lock:
            return self._active_task_id is not None and self._active_task_id in self._tasks

    def get_all_tasks(self) -> list[OrchestrationTask]:
        """获取所有任务列表"""
        with self._lock:
            return list(self._tasks.values())

    # ==================== 路由判断 ====================

    def route_input(self, user_input: str) -> RouteResult:
        """
        判断用户输入路由目标

        Args:
            user_input: 用户输入文本

        Returns:
            RouteResult 路由判断结果
        """
        with self._lock:
            # 没有活跃任务，不路由
            if not self._active_task_id:
                return RouteResult(
                    routed=False,
                    reason="No active task"
                )

            # 获取活跃任务
            task = self._tasks.get(self._active_task_id)
            if not task:
                return RouteResult(
                    routed=False,
                    reason="Active task not found"
                )

            # 任务不在运行状态，不路由
            if task.status != TaskStatus.RUNNING.value:
                return RouteResult(
                    routed=False,
                    reason=f"Task not running: {task.status}"
                )

            # 获取当前步骤
            current_step = task.get_current_step()
            if not current_step:
                return RouteResult(
                    routed=False,
                    reason="No current step"
                )

            # 检查输入是否与任务相关
            if self.is_irrelevant(user_input, task):
                # 递增无关计数
                should_suspend = self.increment_irrelevant_count(task)

                if should_suspend:
                    return RouteResult(
                        routed=False,
                        reason="Auto-suspend triggered"
                    )

                return RouteResult(
                    routed=False,
                    reason="Input irrelevant to task"
                )

            # 重置无关计数（输入相关）
            task.irrelevant_turn_count = 0

            return RouteResult(
                routed=True,
                task_id=task.id,
                step_id=current_step.id,
                reason="Routed to active task"
            )

    async def route_input_async(self, user_input: str) -> RouteResult:
        """
        异步路由判断（支持 LLM 智能判断）

        优先使用 LLM 进行智能路由判断，LLM 不可用时回退到关键词匹配。

        Args:
            user_input: 用户输入文本

        Returns:
            RouteResult 路由判断结果
        """
        with self._lock:
            # 没有活跃任务，不路由
            if not self._active_task_id:
                return RouteResult(
                    routed=False,
                    reason="No active task"
                )

            # 获取活跃任务
            task = self._tasks.get(self._active_task_id)
            if not task:
                return RouteResult(
                    routed=False,
                    reason="Active task not found"
                )

            # 任务不在运行状态，不路由
            if task.status != TaskStatus.RUNNING.value:
                return RouteResult(
                    routed=False,
                    reason=f"Task not running: {task.status}"
                )

            # 获取当前步骤
            current_step = task.get_current_step()
            if not current_step:
                return RouteResult(
                    routed=False,
                    reason="No current step"
                )

        # 释放锁后进行 LLM 调用（避免阻塞）
        is_irrelevant = await self._is_irrelevant_async(user_input, task)

        with self._lock:
            # 再次检查任务状态（可能在 LLM 调用期间发生变化）
            if self._active_task_id != task.id:
                return RouteResult(
                    routed=False,
                    reason="Task changed during routing"
                )

            if is_irrelevant:
                # 递增无关计数
                should_suspend = self.increment_irrelevant_count(task)

                if should_suspend:
                    return RouteResult(
                        routed=False,
                        reason="Auto-suspend triggered"
                    )

                return RouteResult(
                    routed=False,
                    reason="Input irrelevant to task"
                )

            # 重置无关计数（输入相关）
            task.irrelevant_turn_count = 0

            return RouteResult(
                routed=True,
                task_id=task.id,
                step_id=current_step.id,
                reason="Routed to active task"
            )

    async def _is_irrelevant_async(self, user_input: str, task: OrchestrationTask) -> bool:
        """
        异步判断输入是否与任务无关

        优先使用 LLM 判断，LLM 不可用时回退到关键词匹配。

        Args:
            user_input: 用户输入文本
            task: 任务对象

        Returns:
            是否与任务无关
        """
        # 检查是否可以使用 LLM 路由
        if self._can_use_llm_routing():
            try:
                result = await self._llm_is_irrelevant(user_input, task)
                logger.debug(f"LLM routing result: irrelevant={result}")
                return result
            except Exception as e:
                logger.warning(f"LLM routing failed, falling back to keyword matching: {e}")

        # 回退到关键词匹配
        return self._keyword_is_irrelevant(user_input, task)

    def _can_use_llm_routing(self) -> bool:
        """
        检查是否可以使用 LLM 路由

        Returns:
            是否可以使用 LLM 路由
        """
        if not self._brain:
            logger.debug("Brain not available for LLM routing")
            return False

        if not self._router_config:
            logger.debug("Router config not available for LLM routing")
            return False

        if not self._router_config.enabled:
            logger.debug("LLM routing disabled in config")
            return False

        if not self._router_config.system_prompt or not self._router_config.user_prompt_template:
            logger.debug("Router config missing required prompts")
            return False

        return True

    async def _llm_is_irrelevant(self, user_input: str, task: OrchestrationTask) -> bool:
        """
        使用 LLM 判断输入是否与任务无关

        Args:
            user_input: 用户输入文本
            task: 任务对象

        Returns:
            是否与任务无关
        """
        # 获取当前步骤信息
        current_step = task.get_current_step()
        step_name = current_step.name if current_step else ""
        step_description = current_step.description if current_step else ""

        # 格式化用户提示词
        user_prompt = self._router_config.format_user_prompt(
            user_input=user_input,
            task_name=task.name,
            task_description=task.description,
            step_name=step_name,
            step_description=step_description,
        )

        # 调用 LLM
        response = await self._brain.think_lightweight(
            prompt=user_prompt,
            system=self._router_config.system_prompt,
            max_tokens=512,
        )

        # 解析 LLM 响应
        result = self._parse_llm_routing_response(response.content)

        # 如果解析失败或置信度过低，回退到关键词匹配
        if result is None:
            logger.info("LLM routing returned None, falling back to keyword matching")
            return self._keyword_is_irrelevant(user_input, task)

        return result

    def _parse_llm_routing_response(self, response_content: str) -> bool:
        """
        解析 LLM 路由响应

        Args:
            response_content: LLM 响应内容

        Returns:
            是否与任务无关
        """
        try:
            # 尝试提取 JSON
            content = response_content.strip()

            # 尝试找到 JSON 块
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                json_str = content[json_start:json_end]
                result = json.loads(json_str)

                decision = result.get("decision", "").lower()
                confidence = result.get("confidence", 0.0)
                reason = result.get("reason", "")

                logger.debug(f"LLM routing decision: {decision}, confidence: {confidence}, reason: {reason}")

                # 如果置信度太低，回退到关键词匹配
                if confidence < 0.5:
                    logger.info(f"LLM routing confidence too low ({confidence}), using keyword fallback")
                    return None  # 返回 None 表示需要回退

                return decision == "irrelevant"

            logger.warning(f"Could not parse LLM routing response: {response_content[:100]}")
            return None  # 解析失败，需要回退

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM routing JSON: {e}")
            return None  # 解析失败，需要回退

    def is_irrelevant(self, user_input: str, task: OrchestrationTask) -> bool:
        """
        判断输入是否与任务无关（同步版本，使用关键词匹配）

        此方法保持向后兼容，始终使用关键词匹配。

        Args:
            user_input: 用户输入文本
            task: 任务对象

        Returns:
            是否与任务无关
        """
        return self._keyword_is_irrelevant(user_input, task)

    def _keyword_is_irrelevant(self, user_input: str, task: OrchestrationTask) -> bool:
        """
        使用关键词匹配判断输入是否与任务无关

        Args:
            user_input: 用户输入文本
            task: 任务对象

        Returns:
            是否与任务无关
        """

        input_lower = user_input.lower()

        # 空输入视为无关
        if not input_lower.strip():
            return True

        # 任务名称相关关键词
        task_keywords = [
            task.name.lower(),
            task.description.lower(),
        ]

        # 当前步骤相关关键词
        current_step = task.get_current_step()
        if current_step:
            task_keywords.extend([
                current_step.name.lower(),
                current_step.description.lower(),
            ])

        # 检查是否匹配任何关键词
        for keyword in task_keywords:
            if keyword and keyword in input_lower:
                return False

        # 检查常见的任务相关词汇
        task_related_words = [
            "继续", "continue", "next", "下一步", "下一个",
            "跳过", "skip", "暂停", "pause", "恢复", "resume",
            "取消", "cancel", "停止", "stop", "完成", "done",
            "是的", "yes", "不是", "no", "好的", "ok",
        ]

        for word in task_related_words:
            if word in input_lower:
                return False

        return True

    def increment_irrelevant_count(self, task: OrchestrationTask) -> bool:
        """
        递增无关对话计数

        Args:
            task: 任务对象

        Returns:
            是否触发自动暂停
        """
        task.irrelevant_turn_count += 1
        logger.debug(
            f"Task {task.id} irrelevant count: {task.irrelevant_turn_count}"
        )

        if task.irrelevant_turn_count >= self.AUTO_SUSPEND_THRESHOLD:
            logger.info(
                f"Task {task.id} auto-suspend triggered: "
                f"{task.irrelevant_turn_count} irrelevant turns"
            )
            return True

        return False

    # ==================== 序列化 ====================

    def to_dict(self) -> dict:
        """序列化为字典"""
        with self._lock:
            return {
                "session_id": self._session_id,
                "active_task_id": self._active_task_id,
                "tasks": {k: v.to_dict() for k, v in self._tasks.items()},
            }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionTasks":
        """从字典反序列化"""
        tasks = {
            k: OrchestrationTask.from_dict(v)
            for k, v in data.get("tasks", {}).items()
        }

        instance = cls(session_id=data["session_id"])
        instance._active_task_id = data.get("active_task_id")
        instance._tasks = tasks

        return instance

    # ==================== 统计信息 ====================

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            status_counts: dict[str, int] = {}
            for task in self._tasks.values():
                status = task.status
                status_counts[status] = status_counts.get(status, 0) + 1

            return {
                "session_id": self._session_id,
                "total_tasks": len(self._tasks),
                "active_task_id": self._active_task_id,
                "status_counts": status_counts,
            }