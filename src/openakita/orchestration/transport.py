"""
Transport 通信抽象层

定义通信传输抽象接口，支持不同的通信实现：
- MemoryTransport: 进程内通信（默认）
- ZMQTransport: ZeroMQ 分布式通信（未来扩展）

MainAgent 通过 Transport 与 SubAgent 实例通信。
"""

import uuid
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


# ==================== 消息数据类 ====================


@dataclass
class Command:
    """
    命令消息

    用于发送给目标执行的命令。
    """

    command_id: str  # 命令唯一 ID
    command_type: str  # 命令类型
    payload: dict[str, Any]  # 命令负载
    sender_id: str  # 发送者 ID
    target_id: str  # 目标 ID

    # 可选字段
    correlation_id: str | None = None  # 关联 ID（用于请求-响应配对）
    timeout: float = 30.0  # 超时时间（秒）

    def to_dict(self) -> dict:
        """序列化为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Command":
        """从字典反序列化"""
        return cls(**data)

    @classmethod
    def create(
        cls,
        command_type: str,
        payload: dict[str, Any],
        sender_id: str,
        target_id: str,
        correlation_id: str | None = None,
        timeout: float = 30.0,
    ) -> "Command":
        """创建命令"""
        return cls(
            command_id=str(uuid.uuid4()),
            command_type=command_type,
            payload=payload,
            sender_id=sender_id,
            target_id=target_id,
            correlation_id=correlation_id,
            timeout=timeout,
        )


@dataclass
class Response:
    """
    响应消息

    用于响应命令执行结果。
    """

    command_id: str  # 关联的命令 ID
    success: bool  # 是否成功
    result: dict[str, Any] | None = None  # 成功时的结果
    error: str | None = None  # 失败时的错误信息

    # 元数据
    response_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_ms: float | None = None  # 执行耗时（毫秒）

    def to_dict(self) -> dict:
        """序列化为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Response":
        """从字典反序列化"""
        return cls(**data)

    @classmethod
    def success_response(
        cls,
        command_id: str,
        result: dict[str, Any],
        duration_ms: float | None = None,
    ) -> "Response":
        """创建成功响应"""
        return cls(
            command_id=command_id,
            success=True,
            result=result,
            duration_ms=duration_ms,
        )

    @classmethod
    def error_response(
        cls,
        command_id: str,
        error: str,
    ) -> "Response":
        """创建错误响应"""
        return cls(
            command_id=command_id,
            success=False,
            error=error,
        )


@dataclass
class Event:
    """
    事件消息

    用于广播事件给所有订阅者。
    """

    event_id: str  # 事件唯一 ID
    event_type: str  # 事件类型
    payload: dict[str, Any]  # 事件负载
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # 可选字段
    sender_id: str | None = None  # 发送者 ID
    topic: str | None = None  # 主题（用于过滤）

    def to_dict(self) -> dict:
        """序列化为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        """从字典反序列化"""
        return cls(**data)

    @classmethod
    def create(
        cls,
        event_type: str,
        payload: dict[str, Any],
        sender_id: str | None = None,
        topic: str | None = None,
    ) -> "Event":
        """创建事件"""
        return cls(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            payload=payload,
            sender_id=sender_id,
            topic=topic,
        )


# ==================== 命令类型常量 ====================


class CommandType:
    """命令类型常量"""

    # SubAgent 任务相关
    EXECUTE_STEP = "execute_step"  # 执行步骤
    CANCEL_STEP = "cancel_step"  # 取消步骤
    GET_STATUS = "get_status"  # 获取状态

    # 任务编排相关
    CREATE_TASK = "create_task"  # 创建任务
    RESUME_TASK = "resume_task"  # 恢复任务
    PAUSE_TASK = "pause_task"  # 暂停任务
    CANCEL_TASK = "cancel_task"  # 取消任务

    # 输入路由相关
    ROUTE_INPUT = "route_input"  # 路由用户输入


class EventType:
    """事件类型常量"""

    # 任务状态事件
    TASK_CREATED = "task_created"  # 任务创建
    TASK_STARTED = "task_started"  # 任务开始
    TASK_PAUSED = "task_paused"  # 任务暂停
    TASK_COMPLETED = "task_completed"  # 任务完成
    TASK_FAILED = "task_failed"  # 任务失败
    TASK_CANCELLED = "task_cancelled"  # 任务取消

    # 步骤状态事件
    STEP_STARTED = "step_started"  # 步骤开始
    STEP_COMPLETED = "step_completed"  # 步骤完成
    STEP_FAILED = "step_failed"  # 步骤失败

    # 用户交互事件
    USER_INPUT_REQUIRED = "user_input_required"  # 需要用户输入
    USER_FEEDBACK = "user_feedback"  # 用户反馈

    # 系统事件
    AGENT_REGISTERED = "agent_registered"  # Agent 注册
    AGENT_UNREGISTERED = "agent_unregistered"  # Agent 注销
    ERROR = "error"  # 错误事件


# ==================== Transport 抽象基类 ====================


class AgentTransport(ABC):
    """
    通信传输抽象基类

    定义 MainAgent 与 SubAgent 之间的通信接口。
    支持命令-响应模式和事件广播模式。
    """

    @abstractmethod
    async def start(self) -> None:
        """
        启动传输层

        初始化通信资源，准备接收和发送消息。
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """
        停止传输层

        释放通信资源，停止所有消息处理。
        """
        pass

    @abstractmethod
    async def send_command(
        self,
        target: str,
        command: Command,
        wait_response: bool = True,
        timeout: float | None = None,
    ) -> Response | None:
        """
        发送命令

        Args:
            target: 目标 ID
            command: 命令对象
            wait_response: 是否等待响应
            timeout: 超时时间（秒），None 使用命令默认超时

        Returns:
            响应对象（如果 wait_response=True）
        """
        pass

    @abstractmethod
    async def send_response(self, response: Response, target: str) -> None:
        """
        发送响应

        Args:
            response: 响应对象
            target: 目标 ID
        """
        pass

    @abstractmethod
    async def publish_event(self, event: Event) -> None:
        """
        发布事件

        将事件广播给所有订阅者。

        Args:
            event: 事件对象
        """
        pass

    @abstractmethod
    async def subscribe(
        self,
        topic: str,
        handler: Callable[[Event], Awaitable[None]],
    ) -> None:
        """
        订阅主题

        注册事件处理器，当收到匹配主题的事件时调用。

        Args:
            topic: 主题名称
            handler: 异步事件处理函数
        """
        pass

    @abstractmethod
    async def unsubscribe(self, topic: str) -> None:
        """
        取消订阅

        Args:
            topic: 主题名称
        """
        pass

    @abstractmethod
    def register_command_handler(
        self,
        command_type: str,
        handler: Callable[[Command], Awaitable[Response]],
    ) -> None:
        """
        注册命令处理器

        当收到指定类型的命令时调用对应的处理器。

        Args:
            command_type: 命令类型
            handler: 异步命令处理函数，返回响应
        """
        pass

    @abstractmethod
    def unregister_command_handler(self, command_type: str) -> None:
        """
        注销命令处理器

        Args:
            command_type: 命令类型
        """
        pass

    async def __aenter__(self) -> "AgentTransport":
        """异步上下文管理器入口"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口"""
        await self.stop()


# ==================== Transport 错误类 ====================


class TransportError(Exception):
    """传输层错误"""

    pass


class TransportTimeoutError(TransportError):
    """传输超时错误"""

    pass


class TransportNotStartedError(TransportError):
    """传输层未启动错误"""

    pass


class TargetNotFoundError(TransportError):
    """目标不存在错误"""

    pass


# ==================== MemoryTransport 实现 ====================


import asyncio
import logging
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class _MessageWrapper:
    """消息包装器，用于区分消息类型"""

    def __init__(self, message: Command | Response):
        self.message = message
        self.is_response = isinstance(message, Response)
        self.is_command = isinstance(message, Command)


class MemoryTransport(AgentTransport):
    """
    进程内通信传输实现

    使用 asyncio.Queue 实现消息传递，具有零拷贝、无序列化开销的优势。
    适用于单机部署场景。

    特性:
    - 零拷贝：Python 对象引用传递
    - 无序列化：避免 JSON/Pickle 开销
    - 支持请求-响应配对
    - 支持事件广播
    """

    def __init__(self, transport_id: str = "main"):
        """
        初始化 MemoryTransport

        Args:
            transport_id: 传输层唯一标识
        """
        self.transport_id = transport_id

        # 运行状态
        self._running = False

        # 每个 target 的消息队列
        self._queues: dict[str, asyncio.Queue] = {}

        # 等待响应的 Future
        self._pending_responses: dict[str, asyncio.Future] = {}

        # 事件订阅
        self._subscriptions: dict[str, list[Callable[[Event], Awaitable[None]]]] = {}

        # 命令处理器
        self._command_handlers: dict[str, Callable[[Command], Awaitable[Response]]] = {}

        # 消息处理任务
        self._receive_tasks: dict[str, asyncio.Task] = {}

    async def start(self) -> None:
        """启动传输层"""
        if self._running:
            return

        self._running = True
        logger.info(f"MemoryTransport started: {self.transport_id}")

    async def stop(self) -> None:
        """停止传输层"""
        if not self._running:
            return

        self._running = False

        # 取消所有接收任务
        for task in self._receive_tasks.values():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # 清空队列
        self._queues.clear()
        self._receive_tasks.clear()

        # 取消所有等待中的响应
        for future in self._pending_responses.values():
            if not future.done():
                future.cancel()
        self._pending_responses.clear()

        # 清空订阅
        self._subscriptions.clear()

        logger.info(f"MemoryTransport stopped: {self.transport_id}")

    def register_target(self, target_id: str) -> asyncio.Queue:
        """
        注册目标

        为目标创建消息队列，目标可以通过队列接收消息。

        Args:
            target_id: 目标 ID

        Returns:
            目标的消息队列
        """
        if target_id not in self._queues:
            self._queues[target_id] = asyncio.Queue()
            # 启动接收任务
            if self._running:
                self._receive_tasks[target_id] = asyncio.create_task(
                    self._receive_loop(target_id)
                )
        return self._queues[target_id]

    def unregister_target(self, target_id: str) -> None:
        """
        注销目标

        Args:
            target_id: 目标 ID
        """
        if target_id in self._queues:
            del self._queues[target_id]

        if target_id in self._receive_tasks:
            self._receive_tasks[target_id].cancel()
            del self._receive_tasks[target_id]

    async def send_command(
        self,
        target: str,
        command: Command,
        wait_response: bool = True,
        timeout: float | None = None,
    ) -> Response | None:
        """
        发送命令

        Args:
            target: 目标 ID
            command: 命令对象
            wait_response: 是否等待响应
            timeout: 超时时间（秒）

        Returns:
            响应对象（如果 wait_response=True）

        Raises:
            TransportNotStartedError: 传输层未启动
            TargetNotFoundError: 目标不存在
            TransportTimeoutError: 超时
        """
        if not self._running:
            raise TransportNotStartedError("Transport not started")

        # 确保目标存在
        if target not in self._queues:
            raise TargetNotFoundError(f"Target not found: {target}")

        # 发送命令
        await self._queues[target].put(command)
        logger.debug(f"Command sent: {command.command_id} -> {target}")

        if not wait_response:
            return None

        # 创建 Future 等待响应
        future: asyncio.Future[Response] = asyncio.get_event_loop().create_future()
        self._pending_responses[command.command_id] = future

        try:
            timeout_val = timeout if timeout is not None else command.timeout
            response = await asyncio.wait_for(future, timeout=timeout_val)
            return response
        except asyncio.TimeoutError:
            logger.warning(f"Command timeout: {command.command_id}")
            raise TransportTimeoutError(f"Command timeout: {command.command_id}")
        finally:
            self._pending_responses.pop(command.command_id, None)

    async def send_response(self, response: Response, target: str) -> None:
        """
        发送响应

        Args:
            response: 响应对象
            target: 目标 ID
        """
        if not self._running:
            raise TransportNotStartedError("Transport not started")

        # 检查是否有等待这个响应的 Future
        future = self._pending_responses.get(response.command_id)
        if future and not future.done():
            future.set_result(response)
            logger.debug(f"Response delivered: {response.response_id}")
        else:
            # 如果没有等待的 Future，发送到目标队列
            if target in self._queues:
                await self._queues[target].put(response)

    async def publish_event(self, event: Event) -> None:
        """
        发布事件

        将事件广播给所有匹配主题的订阅者。

        Args:
            event: 事件对象
        """
        if not self._running:
            raise TransportNotStartedError("Transport not started")

        topic = event.topic or event.event_type
        handlers = self._subscriptions.get(topic, [])

        logger.debug(f"Publishing event: {event.event_id} to {len(handlers)} handlers")

        # 并发调用所有处理器
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    async def subscribe(
        self,
        topic: str,
        handler: Callable[[Event], Awaitable[None]],
    ) -> None:
        """
        订阅主题

        Args:
            topic: 主题名称
            handler: 异步事件处理函数
        """
        if topic not in self._subscriptions:
            self._subscriptions[topic] = []
        self._subscriptions[topic].append(handler)
        logger.debug(f"Subscribed to topic: {topic}")

    async def unsubscribe(self, topic: str) -> None:
        """
        取消订阅

        Args:
            topic: 主题名称
        """
        self._subscriptions.pop(topic, None)
        logger.debug(f"Unsubscribed from topic: {topic}")

    def register_command_handler(
        self,
        command_type: str,
        handler: Callable[[Command], Awaitable[Response]],
    ) -> None:
        """
        注册命令处理器

        Args:
            command_type: 命令类型
            handler: 异步命令处理函数
        """
        self._command_handlers[command_type] = handler
        logger.debug(f"Registered command handler: {command_type}")

    def unregister_command_handler(self, command_type: str) -> None:
        """
        注销命令处理器

        Args:
            command_type: 命令类型
        """
        self._command_handlers.pop(command_type, None)

    async def _receive_loop(self, target_id: str) -> None:
        """消息接收循环"""
        queue = self._queues.get(target_id)
        if not queue:
            return

        while self._running:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=0.1)

                if isinstance(message, Command):
                    await self._handle_command(message)
                elif isinstance(message, Response):
                    await self._handle_response(message)

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Receive loop error: {e}")

    async def _handle_command(self, command: Command) -> None:
        """处理收到的命令"""
        handler = self._command_handlers.get(command.command_type)
        if handler:
            try:
                response = await handler(command)
                # 发送响应
                future = self._pending_responses.get(command.command_id)
                if future and not future.done():
                    future.set_result(response)
            except Exception as e:
                logger.error(f"Command handler error: {e}")
                # 发送错误响应
                response = Response.error_response(command.command_id, str(e))
                future = self._pending_responses.get(command.command_id)
                if future and not future.done():
                    future.set_result(response)
        else:
            logger.warning(f"No handler for command type: {command.command_type}")

    async def _handle_response(self, response: Response) -> None:
        """处理收到的响应"""
        future = self._pending_responses.get(response.command_id)
        if future and not future.done():
            future.set_result(response)

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "transport_id": self.transport_id,
            "running": self._running,
            "targets": list(self._queues.keys()),
            "pending_responses": len(self._pending_responses),
            "subscriptions": list(self._subscriptions.keys()),
            "command_handlers": list(self._command_handlers.keys()),
        }