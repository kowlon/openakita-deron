"""
PayloadAssembler - SubAgentPayload 组装器

负责从 OrchestrationTask 和 TaskStep 组装 SubAgentPayload。
实现上下文剪枝、制品引用生成、历史消息加载等优化逻辑。

设计说明:
- 引用传递：大数据生成 ArtifactReference 而非内联传输
- 上下文剪枝：根据窗口限制智能裁剪历史消息
- 延迟加载：Worker 按需加载制品内容
"""

import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import OrchestrationTask, StepStatus, SubAgentConfig, TaskStep
from .subagent_worker import ArtifactReference, SubAgentPayload

logger = logging.getLogger(__name__)


# ==================== 配置常量 ====================


@dataclass
class PayloadAssemblerConfig:
    """Payload 组装器配置"""

    # 历史消息窗口限制
    max_history_messages: int = 20  # 最大保留消息数
    max_history_tokens: int = 8000  # 最大保留 token 数

    # 摘要生成
    max_summary_length: int = 500  # 摘要最大长度

    # 制品处理
    max_inline_size: int = 1024  # 最大内联传输大小（字节）
    artifact_storage: str = "file"  # 制品存储方式: "file" | "db"


# ==================== PayloadAssembler ====================


class PayloadAssembler:
    """
    SubAgentPayload 组装器

    负责从 OrchestrationTask 和 TaskStep 组装 SubAgentPayload，
    实现上下文剪枝、制品引用生成、历史消息加载等优化逻辑。

    特性:
    - 前序步骤摘要生成
    - 任务上下文变量组装
    - 历史消息加载与剪枝
    - 制品引用生成
    """

    def __init__(self, config: PayloadAssemblerConfig | None = None):
        """
        初始化组装器

        Args:
            config: 组装器配置
        """
        self.config = config or PayloadAssemblerConfig()

    # ==================== 核心组装方法 ====================

    def assemble(
        self,
        task: OrchestrationTask,
        step: TaskStep,
        user_input: str = "",
        history_messages: list[dict] | None = None,
    ) -> SubAgentPayload:
        """
        组装 SubAgentPayload

        从任务和步骤信息组装完整的执行载荷。

        Args:
            task: 任务对象
            step: 步骤对象
            user_input: 用户输入
            history_messages: 历史消息（可选，从外部加载）

        Returns:
            SubAgentPayload 执行载荷
        """
        logger.debug(
            f"Assembling payload for step {step.id} of task {task.id}"
        )

        # 1. 提取前序步骤摘要
        previous_summary = self._extract_previous_steps_summary(task, step)

        # 2. 组装任务上下文变量
        task_context = self._assemble_task_context(task, step)

        # 3. 加载并剪枝历史消息
        pruned_history = self._prune_history_messages(
            history_messages or []
        )

        # 4. 生成制品引用
        artifacts = self._generate_artifact_references(task, step)

        # 5. 构建 Payload
        payload = SubAgentPayload(
            task_id=task.id,
            step_id=step.id,
            step_index=step.index,
            previous_steps_summary=previous_summary,
            task_context=task_context,
            history_messages=pruned_history,
            artifacts=artifacts,
            agent_config=step.sub_agent_config,
            user_input=user_input,
        )

        logger.debug(
            f"Payload assembled: {len(pruned_history)} history messages, "
            f"{len(artifacts)} artifacts"
        )

        return payload

    # ==================== 前序步骤摘要 ====================

    def _extract_previous_steps_summary(
        self,
        task: OrchestrationTask,
        current_step: TaskStep,
    ) -> str:
        """
        提取前序步骤摘要

        生成当前步骤之前所有已完成步骤的摘要。

        Args:
            task: 任务对象
            current_step: 当前步骤

        Returns:
            前序步骤摘要
        """
        summaries = []

        for step in task.steps:
            # 只处理当前步骤之前的步骤
            if step.index >= current_step.index:
                break

            # 跳过未完成的步骤
            if step.status != StepStatus.COMPLETED.value:
                continue

            # 生成步骤摘要
            summary = self._summarize_step(step)
            if summary:
                summaries.append(f"Step {step.index + 1} ({step.name}): {summary}")

        if not summaries:
            return ""

        result = "\n".join(summaries)

        # 限制摘要长度
        if len(result) > self.config.max_summary_length:
            result = result[:self.config.max_summary_length - 3] + "..."

        return result

    def _summarize_step(self, step: TaskStep) -> str:
        """
        生成单个步骤的摘要

        Args:
            step: 步骤对象

        Returns:
            步骤摘要
        """
        # 如果有输出结果，从中提取摘要
        if step.output_result:
            return self._extract_summary_from_result(step.output_result)

        # 否则使用步骤描述
        return step.description or ""

    def _extract_summary_from_result(self, result: dict[str, Any]) -> str:
        """
        从结果中提取摘要

        Args:
            result: 步骤输出结果

        Returns:
            摘要文本
        """
        # 尝试从常见字段提取
        if "summary" in result:
            return str(result["summary"])[:200]

        if "message" in result:
            return str(result["message"])[:200]

        if "response" in result:
            response = result["response"]
            if isinstance(response, str):
                return response[:200]
            elif isinstance(response, dict):
                if "content" in response:
                    return str(response["content"])[:200]

        # 从字典中提取关键信息
        key_info = []
        for key, value in result.items():
            if key in ("status", "error", "data", "files"):
                key_info.append(f"{key}: {str(value)[:50]}")

        if key_info:
            return ", ".join(key_info)

        return "Completed"

    # ==================== 任务上下文组装 ====================

    def _assemble_task_context(
        self,
        task: OrchestrationTask,
        step: TaskStep,
    ) -> dict[str, Any]:
        """
        组装任务上下文变量

        收集任务级别的变量供步骤执行使用。

        Args:
            task: 任务对象
            step: 步骤对象

        Returns:
            任务上下文字典
        """
        context = {}

        # 添加任务元数据
        context["task_name"] = task.name
        context["task_description"] = task.description
        context["task_id"] = task.id
        context["session_id"] = task.session_id
        context["template_id"] = task.template_id

        # 添加任务输入
        if task.input_payload:
            context["input"] = task.input_payload

        # 添加任务级共享变量
        if task.context_variables:
            context["variables"] = task.context_variables

        # 添加当前步骤信息
        context["current_step"] = {
            "index": step.index,
            "name": step.name,
            "description": step.description,
        }

        # 添加总步骤数
        context["total_steps"] = len(task.steps)

        return context

    # ==================== 历史消息剪枝 ====================

    def _prune_history_messages(
        self,
        messages: list[dict],
    ) -> list[dict]:
        """
        剪枝历史消息

        根据配置限制历史消息数量和大小。

        Args:
            messages: 原始历史消息

        Returns:
            剪枝后的历史消息
        """
        if not messages:
            return []

        # 策略 1: 保留关键消息
        key_messages = []
        other_messages = []

        for msg in messages:
            role = msg.get("role", "")
            # 系统消息和最近的用户消息是关键的
            if role == "system":
                key_messages.append(msg)
            else:
                other_messages.append(msg)

        # 策略 2: 按时间窗口保留
        max_other = self.config.max_history_messages - len(key_messages)
        if len(other_messages) > max_other:
            # 保留最近的消息
            other_messages = other_messages[-max_other:]

        # 组合并恢复顺序
        result = key_messages + other_messages

        # 按原始顺序排序（假设消息有 index 或 timestamp）
        # 简单实现：直接返回

        # 策略 3: Token 限制（估算）
        result = self._apply_token_limit(result)

        return result

    def _apply_token_limit(self, messages: list[dict]) -> list[dict]:
        """
        应用 token 限制

        估算消息的 token 数并裁剪。

        Args:
            messages: 消息列表

        Returns:
            裁剪后的消息列表
        """
        # 简单估算：每个字符约 0.25 token
        max_chars = self.config.max_history_tokens * 4

        result = []
        total_chars = 0

        # 从后向前添加消息
        for msg in reversed(messages):
            content = msg.get("content", "")
            msg_chars = len(str(content))

            if total_chars + msg_chars > max_chars:
                # 超出限制，生成摘要消息
                if result:
                    summary_msg = {
                        "role": "system",
                        "content": f"[Earlier {len(messages) - len(result)} messages truncated]",
                    }
                    result.insert(0, summary_msg)
                break

            result.insert(0, msg)
            total_chars += msg_chars

        return result

    # ==================== 制品引用生成 ====================

    def _generate_artifact_references(
        self,
        task: OrchestrationTask,
        step: TaskStep,
    ) -> list[ArtifactReference]:
        """
        生成制品引用

        从已完成步骤的输出中提取制品引用。

        Args:
            task: 任务对象
            step: 当前步骤

        Returns:
            制品引用列表
        """
        artifacts = []

        for prev_step in task.steps:
            # 只处理当前步骤之前的已完成步骤
            if prev_step.index >= step.index:
                break

            if prev_step.status != StepStatus.COMPLETED.value:
                continue

            # 从步骤输出提取制品
            step_artifacts = self._extract_artifacts_from_step(prev_step)
            artifacts.extend(step_artifacts)

        return artifacts

    def _extract_artifacts_from_step(
        self,
        step: TaskStep,
    ) -> list[ArtifactReference]:
        """
        从步骤输出提取制品引用

        Args:
            step: 步骤对象

        Returns:
            制品引用列表
        """
        artifacts = []

        # 1. 从步骤的 artifacts 字段提取
        for artifact_id in step.artifacts:
            artifact = ArtifactReference(
                id=artifact_id,
                type="data",
                uri=f"db://artifacts/{step.task_id}/{artifact_id}",
                summary=f"Artifact from step {step.name}",
            )
            artifacts.append(artifact)

        # 2. 从输出结果中提取文件引用
        if step.output_result:
            file_artifacts = self._extract_file_artifacts(step.output_result)
            artifacts.extend(file_artifacts)

        return artifacts

    def _extract_file_artifacts(
        self,
        result: dict[str, Any],
    ) -> list[ArtifactReference]:
        """
        从结果中提取文件制品

        Args:
            result: 步骤输出结果

        Returns:
            文件制品引用列表
        """
        artifacts = []

        # 查找文件路径
        file_paths = []

        # 检查常见字段
        if "files" in result:
            file_paths.extend(result["files"])

        if "output_files" in result:
            file_paths.extend(result["output_files"])

        if "file_path" in result:
            file_paths.append(result["file_path"])

        # 生成引用
        for path in file_paths:
            if isinstance(path, str):
                artifact = self._create_file_artifact(path)
                if artifact:
                    artifacts.append(artifact)

        return artifacts

    def _create_file_artifact(self, file_path: str) -> ArtifactReference | None:
        """
        创建文件制品引用

        Args:
            file_path: 文件路径

        Returns:
            文件制品引用，如果文件不存在则返回 None
        """
        try:
            path = Path(file_path)

            # 确定类型
            suffix = path.suffix.lower()
            type_map = {
                ".py": "code",
                ".js": "code",
                ".ts": "code",
                ".java": "code",
                ".go": "code",
                ".rs": "code",
                ".c": "code",
                ".cpp": "code",
                ".h": "code",
                ".png": "image",
                ".jpg": "image",
                ".jpeg": "image",
                ".gif": "image",
                ".svg": "image",
                ".pdf": "document",
                ".doc": "document",
                ".docx": "document",
                ".txt": "file",
                ".md": "file",
                ".json": "data",
                ".yaml": "data",
                ".yml": "data",
                ".xml": "data",
                ".csv": "data",
            }
            artifact_type = type_map.get(suffix, "file")

            # 获取文件信息
            size = None
            try:
                size = path.stat().st_size
            except Exception:
                pass

            return ArtifactReference(
                id=str(uuid.uuid4())[:8],
                type=artifact_type,
                uri=f"file://{file_path}",
                summary=f"{path.name}",
                size=size,
            )

        except Exception as e:
            logger.warning(f"Failed to create artifact for {file_path}: {e}")
            return None

    # ==================== 辅助方法 ====================

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "config": {
                "max_history_messages": self.config.max_history_messages,
                "max_history_tokens": self.config.max_history_tokens,
                "max_summary_length": self.config.max_summary_length,
                "max_inline_size": self.config.max_inline_size,
            },
        }


# ==================== 便捷函数 ====================


def assemble_payload(
    task: OrchestrationTask,
    step: TaskStep,
    user_input: str = "",
    history_messages: list[dict] | None = None,
    config: PayloadAssemblerConfig | None = None,
) -> SubAgentPayload:
    """
    组装 SubAgentPayload（便捷函数）

    Args:
        task: 任务对象
        step: 步骤对象
        user_input: 用户输入
        history_messages: 历史消息
        config: 组装器配置

    Returns:
        SubAgentPayload 执行载荷
    """
    assembler = PayloadAssembler(config)
    return assembler.assemble(task, step, user_input, history_messages)