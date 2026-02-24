"""
记忆整合器 - 批量整理对话历史

简化版（企业级）：
1. 保存对话上下文
2. 会话管理
3. 历史清理

注意：AI 自动提取功能已移除（消费者端功能）
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from .types import ConversationTurn, SessionSummary

logger = logging.getLogger(__name__)


class MemoryConsolidator:
    """记忆整合器 - 企业级简化版"""

    def __init__(
        self,
        data_dir: Path,
        brain=None,
        extractor=None,  # 已废弃，保留参数兼容性
    ):
        """
        Args:
            data_dir: 数据目录 (存放对话历史)
            brain: LLM 大脑实例
            extractor: 已废弃，忽略
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.brain = brain

        # 对话历史存储目录
        self.history_dir = self.data_dir / "conversation_history"
        self.history_dir.mkdir(exist_ok=True)

        # 已整理的会话
        self.summaries_file = self.data_dir / "session_summaries.json"

    def save_conversation_turn(
        self,
        session_id: str,
        turn: ConversationTurn,
    ) -> None:
        """
        保存对话轮次 (实时保存)

        每个会话一个文件，追加写入
        """
        session_file = self.history_dir / f"{session_id}.jsonl"

        with open(session_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(turn.to_dict(), ensure_ascii=False) + "\n")

    def load_session_history(self, session_id: str) -> list[ConversationTurn]:
        """加载会话历史"""
        session_file = self.history_dir / f"{session_id}.jsonl"

        if not session_file.exists():
            return []

        turns = []
        with open(session_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    turn = ConversationTurn(
                        role=data["role"],
                        content=data["content"],
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                        tool_calls=data.get("tool_calls", []),
                        tool_results=data.get("tool_results", []),
                    )
                    turns.append(turn)

        return turns

    def get_today_sessions(self) -> list[str]:
        """获取今天的所有会话 ID"""
        today = datetime.now().date()
        sessions = []

        for file in self.history_dir.glob("*.jsonl"):
            # 检查文件修改时间
            mtime = datetime.fromtimestamp(file.stat().st_mtime)
            if mtime.date() == today:
                sessions.append(file.stem)

        return sessions

    def get_unprocessed_sessions(self) -> list[str]:
        """获取未处理的会话"""
        # 加载已处理的会话
        processed = set()
        if self.summaries_file.exists():
            with open(self.summaries_file, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        summary = json.loads(line)
                        processed.add(summary["session_id"])

        # 找出未处理的
        unprocessed = []
        for file in self.history_dir.glob("*.jsonl"):
            if file.stem not in processed:
                unprocessed.append(file.stem)

        return unprocessed

    def _save_summary(self, summary: SessionSummary) -> None:
        """保存会话摘要"""
        with open(self.summaries_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(summary.to_dict(), ensure_ascii=False) + "\n")

    def get_recent_summaries(self, days: int = 7) -> list[SessionSummary]:
        """获取最近N天的会话摘要"""
        if not self.summaries_file.exists():
            return []

        cutoff = datetime.now() - timedelta(days=days)
        summaries = []

        with open(self.summaries_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    end_time = datetime.fromisoformat(data["end_time"])
                    if end_time > cutoff:
                        summaries.append(
                            SessionSummary(
                                session_id=data["session_id"],
                                start_time=datetime.fromisoformat(data["start_time"]),
                                end_time=end_time,
                                task_description=data.get("task_description", ""),
                                outcome=data.get("outcome", ""),
                                key_actions=data.get("key_actions", []),
                                learnings=data.get("learnings", []),
                                errors_encountered=data.get("errors_encountered", []),
                                memories_created=data.get("memories_created", []),
                            )
                        )

        return summaries

    def cleanup_old_history(self, days: int = 30) -> int:
        """
        清理旧的对话历史文件（按天数）

        保留摘要和记忆，删除原始对话
        """
        cutoff = datetime.now() - timedelta(days=days)
        deleted = 0

        for file in self.history_dir.glob("*.jsonl"):
            mtime = datetime.fromtimestamp(file.stat().st_mtime)
            if mtime < cutoff:
                file.unlink()
                deleted += 1
                logger.info(f"Deleted old history file: {file.name}")

        return deleted

    # ==================== 容量限制清理 ====================

    # 配置常量
    MAX_HISTORY_DAYS = 30  # 最多保留 30 天
    MAX_HISTORY_FILES = 1000  # 最多保留 1000 个文件
    MAX_HISTORY_SIZE_MB = 500  # 最多占用 500MB

    def cleanup_history(self) -> dict:
        """
        清理历史对话，防止磁盘爆炸

        策略（按优先级）:
        1. 删除超过 MAX_HISTORY_DAYS 天的文件
        2. 如果文件数超过 MAX_HISTORY_FILES，删除最旧的
        3. 如果总大小超过 MAX_HISTORY_SIZE_MB，删除最旧的

        Returns:
            清理统计 {"by_age": n, "by_count": n, "by_size": n}
        """
        deleted = {"by_age": 0, "by_count": 0, "by_size": 0}

        # 1. 按天数清理
        deleted["by_age"] = self.cleanup_old_history(days=self.MAX_HISTORY_DAYS)

        # 获取所有历史文件，按修改时间排序（最旧的在前）
        files = sorted(self.history_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime)

        # 2. 按文件数清理
        if len(files) > self.MAX_HISTORY_FILES:
            to_delete = files[: len(files) - self.MAX_HISTORY_FILES]
            for f in to_delete:
                try:
                    f.unlink()
                    deleted["by_count"] += 1
                    logger.debug(f"Deleted history file (by count): {f.name}")
                except Exception as e:
                    logger.error(f"Failed to delete {f.name}: {e}")

            # 更新文件列表
            files = files[len(to_delete) :]

        # 3. 按大小清理
        max_size = self.MAX_HISTORY_SIZE_MB * 1024 * 1024
        total_size = sum(f.stat().st_size for f in files)

        while total_size > max_size and files:
            f = files.pop(0)
            try:
                file_size = f.stat().st_size
                f.unlink()
                total_size -= file_size
                deleted["by_size"] += 1
                logger.debug(f"Deleted history file (by size): {f.name}")
            except Exception as e:
                logger.error(f"Failed to delete {f.name}: {e}")

        total_deleted = sum(deleted.values())
        if total_deleted > 0:
            logger.info(f"History cleanup completed: {deleted}")

        return deleted

    def get_history_stats(self) -> dict:
        """
        获取历史对话统计信息

        Returns:
            统计信息字典
        """
        files = list(self.history_dir.glob("*.jsonl"))
        total_size = sum(f.stat().st_size for f in files)

        return {
            "file_count": len(files),
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "max_files": self.MAX_HISTORY_FILES,
            "max_size_mb": self.MAX_HISTORY_SIZE_MB,
            "max_days": self.MAX_HISTORY_DAYS,
        }
