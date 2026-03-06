"""
TaskStorage - 任务存储管理器

提供统一的任务存储接口，支持：
- 任务和步骤的 CRUD 操作
- 实时持久化
- 原子操作
- 快照恢复
"""

import asyncio
import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

from ..config import settings
from .models import (
    BestPracticeConfig,
    OrchestrationTask,
    SessionTasks,
    StepStatus,
    StepTemplate,
    SubAgentConfig,
    TaskStatus,
    TaskStep,
    TriggerType,
)

logger = logging.getLogger(__name__)


class OrchestrationStorageError(Exception):
    """任务编排存储错误"""
    pass


class TaskStorage:
    """
    任务存储管理器

    负责任务和步骤的 CRUD 操作，支持实时持久化、原子操作和快照恢复。
    是编排层和存储层之间的桥梁。
    """

    def __init__(self, db_path: Path | str | None = None):
        """
        初始化存储管理器

        Args:
            db_path: 数据库路径，默认使用 settings 中的配置
        """
        if db_path is None:
            self.db_path = settings.db_full_path
        elif isinstance(db_path, str):
            self.db_path = Path(db_path)
        else:
            self.db_path = db_path
        self._connection: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """连接数据库"""
        # Only create parent directories if not using in-memory database
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA foreign_keys = ON")
        await self._init_tables()
        logger.info(f"TaskStorage connected: {self.db_path}")

    async def _init_tables(self) -> None:
        """初始化任务编排表"""
        await self._connection.executescript("""
            -- 编排任务表
            CREATE TABLE IF NOT EXISTS orchestration_tasks (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                template_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                name TEXT,
                context_json TEXT DEFAULT '{}',
                meta_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            );

            -- 编排步骤表
            CREATE TABLE IF NOT EXISTS orchestration_steps (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                io_json TEXT DEFAULT '{}',
                config_json TEXT DEFAULT '{}',
                user_feedback TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                FOREIGN KEY (task_id) REFERENCES orchestration_tasks(id) ON DELETE CASCADE
            );

            -- 任务编排索引
            CREATE INDEX IF NOT EXISTS idx_orchestration_tasks_session ON orchestration_tasks(session_id);
            CREATE INDEX IF NOT EXISTS idx_orchestration_tasks_status ON orchestration_tasks(status);
            CREATE INDEX IF NOT EXISTS idx_orchestration_steps_task ON orchestration_steps(task_id);
            CREATE INDEX IF NOT EXISTS idx_orchestration_steps_status ON orchestration_steps(status);
        """)
        await self._connection.commit()

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("TaskStorage connection closed")

    async def _ensure_connection(self) -> aiosqlite.Connection:
        """确保数据库连接"""
        if not self._connection:
            await self.connect()
        return self._connection

    # ==================== 任务操作 ====================

    async def save_task(self, task: OrchestrationTask) -> None:
        """
        保存任务（含步骤）

        Args:
            task: 要保存的任务对象
        """
        conn = await self._ensure_connection()

        async with self._lock:
            try:
                now = datetime.now().isoformat()

                # 序列化 JSON 字段
                context_json = json.dumps({
                    "input_payload": task.input_payload,
                    "result_payload": task.result_payload,
                    "context_variables": task.context_variables,
                }, ensure_ascii=False)

                meta_json = json.dumps({
                    "trigger_type": task.trigger_type,
                    "trigger_message_id": task.trigger_message_id,
                    "description": task.description,
                    "suspend_reason": task.suspend_reason,
                    "irrelevant_turn_count": task.irrelevant_turn_count,
                    "current_step_index": task.current_step_index,
                    "template_id": task.template_id,
                }, ensure_ascii=False)

                # 使用 UPSERT
                await conn.execute(
                    """INSERT OR REPLACE INTO orchestration_tasks
                       (id, session_id, template_id, status, name, context_json, meta_json, created_at, updated_at, completed_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        task.id,
                        task.session_id,
                        task.template_id,
                        task.status,
                        task.name,
                        context_json,
                        meta_json,
                        task.created_at or now,
                        now,
                        task.completed_at,
                    )
                )

                # 保存步骤
                for step in task.steps:
                    await self._save_step_internal(conn, step)

                await conn.commit()
                logger.debug(f"Task saved: {task.id}")

            except Exception as e:
                logger.error(f"Failed to save task {task.id}: {e}")
                raise OrchestrationStorageError(f"Failed to save task: {e}") from e

    async def _save_step_internal(self, conn: aiosqlite.Connection, step: TaskStep) -> None:
        """内部方法：保存步骤（不带锁）"""
        now = datetime.now().isoformat()

        io_json = json.dumps({
            "input_args": step.input_args,
            "output_result": step.output_result,
        }, ensure_ascii=False)

        config_json = json.dumps(step.sub_agent_config.to_dict(), ensure_ascii=False)

        await conn.execute(
            """INSERT OR REPLACE INTO orchestration_steps
               (id, task_id, step_index, name, status, io_json, config_json, user_feedback, created_at, started_at, finished_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                step.id,
                step.task_id,
                step.index,
                step.name,
                step.status,
                io_json,
                config_json,
                step.user_feedback,
                step.created_at or now,
                step.started_at,
                step.finished_at,
            )
        )

    async def load_task(self, task_id: str) -> OrchestrationTask | None:
        """
        加载单个任务

        Args:
            task_id: 任务 ID

        Returns:
            任务对象，不存在则返回 None
        """
        conn = await self._ensure_connection()

        try:
            # 查询任务
            cursor = await conn.execute(
                "SELECT * FROM orchestration_tasks WHERE id = ?",
                (task_id,)
            )
            row = await cursor.fetchone()

            if not row:
                return None

            # 查询步骤
            cursor = await conn.execute(
                "SELECT * FROM orchestration_steps WHERE task_id = ? ORDER BY step_index",
                (task_id,)
            )
            step_rows = await cursor.fetchall()

            return self._row_to_task(row, step_rows)

        except Exception as e:
            logger.error(f"Failed to load task {task_id}: {e}")
            raise OrchestrationStorageError(f"Failed to load task: {e}") from e

    async def load_session_tasks(self, session_id: str) -> SessionTasks:
        """
        加载会话所有任务

        一次查询加载所有数据，避免 N+1 查询问题。

        Args:
            session_id: 会话 ID

        Returns:
            SessionTasks 对象
        """
        conn = await self._ensure_connection()

        try:
            # 查询所有任务
            cursor = await conn.execute(
                "SELECT * FROM orchestration_tasks WHERE session_id = ? ORDER BY created_at",
                (session_id,)
            )
            task_rows = await cursor.fetchall()

            if not task_rows:
                return SessionTasks(session_id=session_id)

            # 批量查询所有步骤
            task_ids = [row["id"] for row in task_rows]
            placeholders = ",".join("?" * len(task_ids))

            cursor = await conn.execute(
                f"SELECT * FROM orchestration_steps WHERE task_id IN ({placeholders}) ORDER BY task_id, step_index",
                task_ids
            )
            all_step_rows = await cursor.fetchall()

            # 按任务 ID 分组步骤
            steps_by_task: dict[str, list] = {}
            for step_row in all_step_rows:
                task_id = step_row["task_id"]
                if task_id not in steps_by_task:
                    steps_by_task[task_id] = []
                steps_by_task[task_id].append(step_row)

            # 构建任务对象
            tasks: dict[str, OrchestrationTask] = {}
            for task_row in task_rows:
                task_id = task_row["id"]
                step_rows = steps_by_task.get(task_id, [])
                tasks[task_id] = self._row_to_task(task_row, step_rows)

            return SessionTasks(
                session_id=session_id,
                tasks=tasks,
            )

        except Exception as e:
            logger.error(f"Failed to load session tasks {session_id}: {e}")
            raise OrchestrationStorageError(f"Failed to load session tasks: {e}") from e

    async def delete_task(self, task_id: str) -> bool:
        """
        删除任务

        Args:
            task_id: 任务 ID

        Returns:
            是否删除成功
        """
        conn = await self._ensure_connection()

        async with self._lock:
            try:
                cursor = await conn.execute(
                    "DELETE FROM orchestration_tasks WHERE id = ?",
                    (task_id,)
                )
                await conn.commit()
                deleted = cursor.rowcount > 0

                if deleted:
                    logger.debug(f"Task deleted: {task_id}")
                return deleted

            except Exception as e:
                logger.error(f"Failed to delete task {task_id}: {e}")
                raise OrchestrationStorageError(f"Failed to delete task: {e}") from e

    # ==================== 步骤操作 ====================

    async def update_step_status(
        self,
        step_id: str,
        status: StepStatus,
        result: dict[str, Any] | None = None,
    ) -> None:
        """
        更新步骤状态

        Args:
            step_id: 步骤 ID
            status: 新状态
            result: 可选的输出结果
        """
        conn = await self._ensure_connection()

        async with self._lock:
            try:
                now = datetime.now().isoformat()

                # 获取当前步骤信息
                cursor = await conn.execute(
                    "SELECT io_json FROM orchestration_steps WHERE id = ?",
                    (step_id,)
                )
                row = await cursor.fetchone()

                if not row:
                    raise OrchestrationStorageError(f"Step not found: {step_id}")

                io_data = json.loads(row["io_json"])

                # 更新输出结果
                if result is not None:
                    io_data["output_result"] = result

                # 更新时间戳
                started_at = None
                finished_at = None
                if status == StepStatus.RUNNING:
                    started_at = now
                elif status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED):
                    # 获取已存在的 started_at
                    cursor = await conn.execute(
                        "SELECT started_at FROM orchestration_steps WHERE id = ?",
                        (step_id,)
                    )
                    existing = await cursor.fetchone()
                    started_at = existing["started_at"] if existing else None
                    finished_at = now

                await conn.execute(
                    """UPDATE orchestration_steps
                       SET status = ?, io_json = ?, started_at = COALESCE(?, started_at), finished_at = ?
                       WHERE id = ?""",
                    (
                        status.value,
                        json.dumps(io_data, ensure_ascii=False),
                        started_at,
                        finished_at,
                        step_id,
                    )
                )
                await conn.commit()
                logger.debug(f"Step status updated: {step_id} -> {status.value}")

            except OrchestrationStorageError:
                raise
            except Exception as e:
                logger.error(f"Failed to update step status {step_id}: {e}")
                raise OrchestrationStorageError(f"Failed to update step status: {e}") from e

    async def save_step(self, step: TaskStep) -> None:
        """
        保存单个步骤

        Args:
            step: 要保存的步骤对象
        """
        conn = await self._ensure_connection()

        async with self._lock:
            try:
                await self._save_step_internal(conn, step)
                await conn.commit()
                logger.debug(f"Step saved: {step.id}")

            except Exception as e:
                logger.error(f"Failed to save step {step.id}: {e}")
                raise OrchestrationStorageError(f"Failed to save step: {e}") from e

    # ==================== 辅助方法 ====================

    def _row_to_task(
        self,
        task_row: aiosqlite.Row,
        step_rows: list[aiosqlite.Row],
    ) -> OrchestrationTask:
        """将数据库行转换为 OrchestrationTask 对象"""
        context_data = json.loads(task_row["context_json"])
        meta_data = json.loads(task_row["meta_json"])

        # 转换步骤
        steps = [self._row_to_step(row) for row in step_rows]

        return OrchestrationTask(
            id=task_row["id"],
            session_id=task_row["session_id"],
            template_id=meta_data.get("template_id"),
            trigger_type=meta_data.get("trigger_type", TriggerType.CONTEXT.value),
            trigger_message_id=meta_data.get("trigger_message_id"),
            status=task_row["status"],
            suspend_reason=meta_data.get("suspend_reason"),
            current_step_index=meta_data.get("current_step_index", 0),
            irrelevant_turn_count=meta_data.get("irrelevant_turn_count", 0),
            name=task_row["name"] or "",
            description=meta_data.get("description", ""),
            input_payload=context_data.get("input_payload", {}),
            result_payload=context_data.get("result_payload", {}),
            context_variables=context_data.get("context_variables", {}),
            steps=steps,
            created_at=task_row["created_at"],
            updated_at=task_row["updated_at"],
            completed_at=task_row["completed_at"],
        )

    def _row_to_step(self, row: aiosqlite.Row) -> TaskStep:
        """将数据库行转换为 TaskStep 对象"""
        io_data = json.loads(row["io_json"])
        config_data = json.loads(row["config_json"])

        sub_agent_config = SubAgentConfig.from_dict(config_data)

        return TaskStep(
            id=row["id"],
            task_id=row["task_id"],
            index=row["step_index"],
            name=row["name"],
            description="",  # 步骤描述不存储在数据库中
            sub_agent_config=sub_agent_config,
            status=row["status"],
            input_args=io_data.get("input_args", {}),
            output_result=io_data.get("output_result", {}),
            user_feedback=row["user_feedback"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )

    # ==================== 任务状态更新 ====================

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        result_payload: dict[str, Any] | None = None,
    ) -> None:
        """
        更新任务状态

        Args:
            task_id: 任务 ID
            status: 新状态
            result_payload: 可选的结果数据
        """
        conn = await self._ensure_connection()

        async with self._lock:
            try:
                now = datetime.now().isoformat()

                # 获取当前上下文
                cursor = await conn.execute(
                    "SELECT context_json, meta_json FROM orchestration_tasks WHERE id = ?",
                    (task_id,)
                )
                row = await cursor.fetchone()

                if not row:
                    raise OrchestrationStorageError(f"Task not found: {task_id}")

                context_data = json.loads(row["context_json"])
                meta_data = json.loads(row["meta_json"])

                # 更新结果
                if result_payload is not None:
                    context_data["result_payload"] = result_payload

                # 更新完成时间
                completed_at = None
                if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                    completed_at = now

                await conn.execute(
                    """UPDATE orchestration_tasks
                       SET status = ?, context_json = ?, updated_at = ?, completed_at = COALESCE(?, completed_at)
                       WHERE id = ?""",
                    (
                        status.value,
                        json.dumps(context_data, ensure_ascii=False),
                        now,
                        completed_at,
                        task_id,
                    )
                )
                await conn.commit()
                logger.debug(f"Task status updated: {task_id} -> {status.value}")

            except OrchestrationStorageError:
                raise
            except Exception as e:
                logger.error(f"Failed to update task status {task_id}: {e}")
                raise OrchestrationStorageError(f"Failed to update task status: {e}") from e

    async def update_task_meta(
        self,
        task_id: str,
        current_step_index: int | None = None,
        irrelevant_turn_count: int | None = None,
        suspend_reason: str | None = None,
    ) -> None:
        """
        更新任务元数据

        Args:
            task_id: 任务 ID
            current_step_index: 当前步骤索引
            irrelevant_turn_count: 无关对话计数
            suspend_reason: 暂停原因
        """
        conn = await self._ensure_connection()

        async with self._lock:
            try:
                now = datetime.now().isoformat()

                # 获取当前元数据
                cursor = await conn.execute(
                    "SELECT meta_json FROM orchestration_tasks WHERE id = ?",
                    (task_id,)
                )
                row = await cursor.fetchone()

                if not row:
                    raise OrchestrationStorageError(f"Task not found: {task_id}")

                meta_data = json.loads(row["meta_json"])

                # 更新字段
                if current_step_index is not None:
                    meta_data["current_step_index"] = current_step_index
                if irrelevant_turn_count is not None:
                    meta_data["irrelevant_turn_count"] = irrelevant_turn_count
                if suspend_reason is not None:
                    meta_data["suspend_reason"] = suspend_reason

                await conn.execute(
                    """UPDATE orchestration_tasks
                       SET meta_json = ?, updated_at = ?
                       WHERE id = ?""",
                    (
                        json.dumps(meta_data, ensure_ascii=False),
                        now,
                        task_id,
                    )
                )
                await conn.commit()

            except OrchestrationStorageError:
                raise
            except Exception as e:
                logger.error(f"Failed to update task meta {task_id}: {e}")
                raise OrchestrationStorageError(f"Failed to update task meta: {e}") from e


# ==================== 全局实例 ====================

_storage_instance: TaskStorage | None = None


async def get_task_storage() -> TaskStorage:
    """获取全局 TaskStorage 实例"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = TaskStorage()
        await _storage_instance.connect()
    return _storage_instance


async def close_task_storage() -> None:
    """关闭全局 TaskStorage 实例"""
    global _storage_instance
    if _storage_instance:
        await _storage_instance.close()
        _storage_instance = None