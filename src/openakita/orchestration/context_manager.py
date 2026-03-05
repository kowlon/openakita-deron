"""
上下文传递机制

管理多任务编排中步骤间的上下文传递。

关键功能:
- 自动提取步骤输出
- 注入到下一步骤的提示词
- 上下文格式化和摘要
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ContextEntry:
    """上下文条目"""

    key: str  # 键名（通常是 output_key）
    step_id: str  # 来源步骤
    value: Any  # 值
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    is_confirmed: bool = True  # 是否已确认

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "step_id": self.step_id,
            "value": self.value,
            "timestamp": self.timestamp,
            "is_confirmed": self.is_confirmed,
        }


class ContextManager:
    """
    上下文管理器

    管理任务执行过程中的上下文传递。

    核心功能:
    - 存储和检索上下文
    - 格式化上下文用于提示词注入
    - 上下文摘要和压缩
    """

    def __init__(self, max_context_size: int = 10000):
        """
        初始化上下文管理器

        Args:
            max_context_size: 最大上下文大小（字符数）
        """
        self._context: dict[str, ContextEntry] = {}
        self._max_context_size = max_context_size

    def store(self, key: str, step_id: str, value: Any, is_confirmed: bool = True) -> None:
        """
        存储上下文

        Args:
            key: 键名
            step_id: 来源步骤
            value: 值
            is_confirmed: 是否已确认
        """
        self._context[key] = ContextEntry(
            key=key,
            step_id=step_id,
            value=value,
            is_confirmed=is_confirmed,
        )
        logger.debug(f"Stored context: {key} from step {step_id}")

    def get(self, key: str) -> Any | None:
        """获取上下文值"""
        entry = self._context.get(key)
        return entry.value if entry else None

    def get_entry(self, key: str) -> ContextEntry | None:
        """获取上下文条目"""
        return self._context.get(key)

    def get_all_confirmed(self) -> dict[str, Any]:
        """获取所有已确认的上下文"""
        return {
            key: entry.value
            for key, entry in self._context.items()
            if entry.is_confirmed
        }

    def delete(self, key: str) -> bool:
        """删除上下文"""
        if key in self._context:
            del self._context[key]
            return True
        return False

    def clear(self) -> None:
        """清空上下文"""
        self._context.clear()

    # ==================== 格式化 ====================

    def format_for_prompt(
        self,
        keys: list[str] | None = None,
        max_length: int | None = None,
    ) -> str:
        """
        格式化上下文用于提示词注入

        Args:
            keys: 指定键列表（可选，默认全部）
            max_length: 最大长度（可选）

        Returns:
            格式化后的字符串
        """
        if not self._context:
            return ""

        max_len = max_length or self._max_context_size
        entries = []

        keys_to_format = keys if keys else list(self._context.keys())

        for key in keys_to_format:
            entry = self._context.get(key)
            if entry and entry.is_confirmed:
                entries.append(entry)

        if not entries:
            return ""

        lines = []
        total_length = 0

        for entry in entries:
            section = self._format_entry(entry)
            if total_length + len(section) > max_len:
                # 截断
                remaining = max_len - total_length
                if remaining > 100:
                    section = section[:remaining] + "\n... (truncated)"
                else:
                    break

            lines.append(section)
            total_length += len(section)

        return "\n".join(lines)

    def _format_entry(self, entry: ContextEntry) -> str:
        """格式化单个条目"""
        lines = [f"### {entry.key}"]
        lines.append(f"来源步骤: {entry.step_id}")
        lines.append("")

        value = entry.value

        if isinstance(value, str):
            lines.append(value)
        elif isinstance(value, dict):
            # 格式化字典
            try:
                formatted = json.dumps(value, ensure_ascii=False, indent=2)
                lines.append(f"```json\n{formatted}\n```")
            except Exception:
                lines.append(str(value))
        elif isinstance(value, list):
            # 格式化列表
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    lines.append(f"{i + 1}. {json.dumps(item, ensure_ascii=False)}")
                else:
                    lines.append(f"{i + 1}. {item}")
        else:
            lines.append(str(value))

        lines.append("")
        return "\n".join(lines)

    def format_summary(self) -> str:
        """格式化上下文摘要"""
        if not self._context:
            return "无上下文"

        lines = ["上下文摘要:"]
        for key, entry in self._context.items():
            value_preview = self._get_value_preview(entry.value)
            status = "✓" if entry.is_confirmed else "○"
            lines.append(f"  {status} {key}: {value_preview}")

        return "\n".join(lines)

    def _get_value_preview(self, value: Any, max_len: int = 50) -> str:
        """获取值的预览"""
        if isinstance(value, str):
            preview = value[:max_len]
            return preview + "..." if len(value) > max_len else preview
        elif isinstance(value, dict):
            return f"{{...}} ({len(value)} keys)"
        elif isinstance(value, list):
            return f"[...] ({len(value)} items)"
        else:
            return str(value)[:max_len]

    # ==================== 序列化 ====================

    def to_dict(self) -> dict[str, Any]:
        """导出为字典"""
        return {
            key: entry.to_dict()
            for key, entry in self._context.items()
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContextManager":
        """从字典导入"""
        manager = cls()
        for key, entry_data in data.items():
            manager._context[key] = ContextEntry(
                key=entry_data["key"],
                step_id=entry_data["step_id"],
                value=entry_data["value"],
                timestamp=entry_data.get("timestamp", datetime.now().isoformat()),
                is_confirmed=entry_data.get("is_confirmed", True),
            )
        return manager


# ==================== 输出提取器 ====================


class OutputExtractor:
    """
    步骤输出提取器

    从 SubAgent 响应中提取结构化输出。
    """

    @staticmethod
    def extract_from_response(response: str, output_key: str) -> dict[str, Any]:
        """
        从响应中提取输出

        Args:
            response: 响应文本
            output_key: 输出键名

        Returns:
            提取的结构化输出
        """
        output: dict[str, Any] = {}

        # 尝试提取 JSON 块
        json_blocks = OutputExtractor._extract_json_blocks(response)
        if json_blocks:
            # 使用第一个 JSON 块作为主要输出
            output["json"] = json_blocks[0]
            output["raw"] = response
        else:
            # 直接使用响应文本
            output["text"] = response
            output["raw"] = response

        output["output_key"] = output_key
        output["extracted_at"] = datetime.now().isoformat()

        return output

    @staticmethod
    def _extract_json_blocks(text: str) -> list[dict]:
        """提取文本中的 JSON 块"""
        import re

        blocks = []
        # 匹配 ```json ... ``` 块
        pattern = r"```json\s*([\s\S]*?)```"
        matches = re.findall(pattern, text)

        for match in matches:
            try:
                data = json.loads(match.strip())
                if isinstance(data, dict):
                    blocks.append(data)
            except json.JSONDecodeError:
                continue

        # 也尝试匹配裸 JSON 对象
        pattern = r"\{[\s\S]*\}"
        matches = re.findall(pattern, text)
        for match in matches:
            try:
                data = json.loads(match)
                if isinstance(data, dict) and data not in blocks:
                    blocks.append(data)
            except json.JSONDecodeError:
                continue

        return blocks


# ==================== 上下文注入器 ====================


class ContextInjector:
    """
    上下文注入器

    将上下文注入到系统提示词中。
    """

    @staticmethod
    def inject(
        system_prompt: str,
        context: dict[str, Any],
        context_manager: ContextManager | None = None,
    ) -> str:
        """
        注入上下文到系统提示词

        Args:
            system_prompt: 原始系统提示词
            context: 上下文字典
            context_manager: 上下文管理器（可选）

        Returns:
            注入后的系统提示词
        """
        if not context and not context_manager:
            return system_prompt

        # 构建上下文部分
        if context_manager:
            context_str = context_manager.format_for_prompt()
        else:
            context_str = ContextInjector._format_context_dict(context)

        if not context_str:
            return system_prompt

        # 查找插入点
        # 如果提示词中有 {{context}} 占位符，则替换
        if "{{context}}" in system_prompt:
            return system_prompt.replace("{{context}}", context_str)

        # 否则追加到末尾
        return f"{system_prompt}\n\n## 前置步骤输出\n{context_str}"

    @staticmethod
    def _format_context_dict(context: dict[str, Any]) -> str:
        """格式化上下文字典"""
        lines = []
        for key, value in context.items():
            if value:
                lines.append(f"### {key}")
                if isinstance(value, dict):
                    lines.append(json.dumps(value, ensure_ascii=False, indent=2))
                elif isinstance(value, str):
                    lines.append(value)
                else:
                    lines.append(str(value))
                lines.append("")
        return "\n".join(lines)