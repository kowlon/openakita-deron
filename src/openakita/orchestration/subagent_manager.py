"""
SubAgent 管理器

管理 SubAgent 独立进程的生命周期、通信和状态。

关键设计:
- SubAgent 以独立进程运行
- 复用 WorkerAgent 架构和 ZMQ 通信
- 通过配置区分步骤执行模式
"""

import asyncio
import logging
import multiprocessing
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .bus import BusConfig, WorkerBus
from .config_loader import SubAgentConfigLoader
from .messages import (
    AgentInfo,
    AgentMessage,
    AgentStatus,
    AgentType,
    CommandType,
    EventType,
    MessageType,
    StepRequest,
    StepResponse,
    create_step_response,
)
from .models import ProcessMode, StepStatus, SubAgentConfig

logger = logging.getLogger(__name__)


class SubAgentManager:
    """
    SubAgent 管理器

    管理 SubAgent 独立进程的创建、销毁和通信。

    关键设计:
    - SubAgent 以独立进程运行，具备完整 Agent 能力
    - 使用 ZMQ 进行进程间通信
    - 通过 SubAgentConfig 配置行为和能力
    """

    def __init__(
        self,
        main_agent: Any = None,
        router_address: str = "tcp://127.0.0.1:5555",
        pub_address: str = "tcp://127.0.0.1:5556",
        data_dir: Path | None = None,
    ):
        """
        初始化 SubAgent 管理器

        Args:
            main_agent: 主 Agent 引用（用于共享配置）
            router_address: ZMQ ROUTER 地址
            pub_address: ZMQ PUB 地址
            data_dir: 数据目录
        """
        self._main_agent = main_agent
        self._router_address = router_address
        self._pub_address = pub_address
        self._data_dir = data_dir

        # SubAgent 映射: step_id -> sub_agent_id
        self._sub_agents: dict[str, str] = {}
        # 进程映射: sub_agent_id -> Process
        self._processes: dict[str, multiprocessing.Process] = {}
        # 信息映射: sub_agent_id -> AgentInfo
        self._agent_infos: dict[str, AgentInfo] = {}
        # 等待中的响应: request_id -> Future
        self._pending_responses: dict[str, asyncio.Future] = {}
        # 就绪事件: sub_agent_id -> Event
        self._ready_events: dict[str, asyncio.Event] = {}

        # 配置加载器
        self._config_loader = SubAgentConfigLoader()

        # 通信总线（用于接收 SubAgent 响应）
        self._bus: WorkerBus | None = None
        self._running = False

    # ==================== 生命周期 ====================

    async def start(self) -> None:
        """启动管理器"""
        if self._running:
            return

        # 初始化通信总线（连接到 Master）
        bus_config = BusConfig(
            router_address=self._router_address,
            pub_address=self._pub_address,
        )
        self._bus = WorkerBus(
            worker_id=f"subagent-manager-{uuid.uuid4().hex[:8]}",
            config=bus_config,
        )
        await self._bus.start()

        # 注册响应处理器 - 使用 STEP_RESPONSE 命令类型，但需要特殊处理响应消息
        self._bus.register_command_handler(
            CommandType.STEP_RESPONSE,
            self._handle_step_response,
        )

        # 设置默认处理器来捕获响应消息
        self._bus.set_default_handler(self._handle_default_message)

        self._running = True
        logger.info("SubAgentManager started")

    async def stop(self) -> None:
        """停止管理器并清理所有 SubAgent"""
        if not self._running:
            return

        self._running = False

        # 销毁所有 SubAgent
        await self.destroy_all()

        # 停止通信总线
        if self._bus:
            await self._bus.stop()

        logger.info("SubAgentManager stopped")

    # ==================== SubAgent 创建/销毁 ====================

    async def spawn_sub_agent(
        self,
        step_id: str,
        config: SubAgentConfig,
    ) -> str:
        """
        创建 SubAgent 进程

        Args:
            step_id: 步骤 ID
            config: SubAgent 配置

        Returns:
            SubAgent ID
        """
        if step_id in self._sub_agents:
            logger.warning(f"SubAgent already exists for step: {step_id}")
            return self._sub_agents[step_id]

        # 生成 SubAgent ID
        sub_agent_id = f"subagent-{uuid.uuid4().hex[:8]}"

        # 创建进程
        process = multiprocessing.Process(
            target=_subagent_process_entry,
            args=(
                sub_agent_id,
                self._router_address,
                self._pub_address,
                config.to_dict(),
                str(self._data_dir) if self._data_dir else None,
            ),
            daemon=True,
        )

        process.start()
        self._processes[sub_agent_id] = process

        # 记录映射
        self._sub_agents[step_id] = sub_agent_id

        # 初始化 AgentInfo
        self._agent_infos[sub_agent_id] = AgentInfo(
            agent_id=sub_agent_id,
            agent_type=AgentType.SPECIALIZED.value,
            process_id=process.pid or 0,
            status=AgentStatus.STARTING.value,
            capabilities=config.allowed_tools,
        )

        # 创建就绪事件
        self._ready_events[sub_agent_id] = asyncio.Event()

        logger.info(
            f"Spawned SubAgent {sub_agent_id} for step {step_id} (pid={process.pid})"
        )

        # 等待 SubAgent 启动（增加超时时间）
        ready = await self._wait_for_subagent_ready(sub_agent_id, timeout=60.0)

        if not ready:
            logger.warning(f"SubAgent {sub_agent_id} may not be fully ready, proceeding anyway")

        return sub_agent_id

    async def destroy_sub_agent(self, step_id: str) -> None:
        """
        销毁 SubAgent

        Args:
            step_id: 步骤 ID
        """
        sub_agent_id = self._sub_agents.get(step_id)
        if not sub_agent_id:
            return

        process = self._processes.get(sub_agent_id)
        if process:
            # 发送关闭命令
            try:
                if self._bus:
                    await self._bus._send_to_master(
                        AgentMessage.command(
                            sender_id="subagent-manager",
                            target_id=sub_agent_id,
                            command_type=CommandType.SHUTDOWN,
                            payload={},
                        )
                    )
            except Exception as e:
                logger.warning(f"Failed to send shutdown to SubAgent: {e}")

            # 等待进程退出
            process.join(timeout=5)
            if process.is_alive():
                logger.warning(f"SubAgent {sub_agent_id} didn't exit, terminating")
                process.terminate()
                process.join(timeout=2)

            # 清理
            del self._processes[sub_agent_id]

        # 清理映射
        self._sub_agents.pop(step_id, None)
        self._agent_infos.pop(sub_agent_id, None)

        logger.info(f"Destroyed SubAgent {sub_agent_id} for step {step_id}")

    async def destroy_all(self) -> None:
        """销毁所有 SubAgent"""
        step_ids = list(self._sub_agents.keys())
        for step_id in step_ids:
            await self.destroy_sub_agent(step_id)

    async def _wait_for_subagent_ready(
        self,
        sub_agent_id: str,
        timeout: float = 30.0,
    ) -> bool:
        """等待 SubAgent 就绪

        使用事件机制等待 SubAgent 进程启动完成并发送就绪通知。
        同时检查进程存活状态作为备用机制。
        """
        ready_event = self._ready_events.get(sub_agent_id)
        if not ready_event:
            logger.warning(f"No ready event for SubAgent {sub_agent_id}")
            return False

        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            # 检查进程是否存活
            process = self._processes.get(sub_agent_id)
            if not process:
                logger.error(f"SubAgent {sub_agent_id} process not found")
                return False

            if not process.is_alive():
                logger.error(f"SubAgent {sub_agent_id} process died")
                return False

            # 检查就绪事件是否已设置
            if ready_event.is_set():
                logger.info(f"SubAgent {sub_agent_id} is ready (event received)")
                return True

            # 短暂等待后继续检查
            await asyncio.sleep(0.1)

        # 超时但进程存活，返回成功（保守策略）
        process = self._processes.get(sub_agent_id)
        if process and process.is_alive():
            logger.warning(
                f"SubAgent {sub_agent_id} timeout after {timeout}s but process running (pid={process.pid}), proceeding anyway"
            )
            return True

        logger.warning(f"SubAgent {sub_agent_id} not ready within {timeout}s")
        return False

    # ==================== 步骤执行 ====================

    async def dispatch_request(
        self,
        step_id: str,
        request: StepRequest,
    ) -> StepResponse:
        """
        向 SubAgent 发送执行请求

        Args:
            step_id: 步骤 ID
            request: 步骤请求

        Returns:
            步骤响应
        """
        sub_agent_id = self._sub_agents.get(step_id)
        if not sub_agent_id:
            logger.error(f"Dispatch failed: No SubAgent for step {step_id}")
            raise ValueError(f"No SubAgent for step: {step_id}")

        # 检查进程是否存活
        process = self._processes.get(sub_agent_id)
        if not process or not process.is_alive():
            logger.error(f"Dispatch failed: SubAgent {sub_agent_id} process not running")
            return create_step_response(
                request_id=request.request_id,
                step_id=step_id,
                task_id=request.task_id,
                success=False,
                error=f"SubAgent process not running (sub_agent_id={sub_agent_id})",
            )

        # 更新 Agent 状态
        agent_info = self._agent_infos.get(sub_agent_id)
        if agent_info:
            agent_info.set_task(request.task_id, f"Step: {step_id}")

        # 创建 Future 等待响应
        future: asyncio.Future[StepResponse] = asyncio.get_event_loop().create_future()
        self._pending_responses[request.request_id] = future

        try:
            # 发送请求 - 使用 subagent-manager 作为 sender_id 以便响应能路由回来
            if self._bus:
                message = request.to_agent_message(
                    sender_id=self._bus.worker_id if hasattr(self._bus, 'worker_id') else "subagent-manager",
                    target_id=sub_agent_id,
                )
                logger.info(
                    f"Dispatching request {request.request_id} to SubAgent {sub_agent_id} "
                    f"(step={step_id}, task={request.task_id}, timeout={request.timeout_seconds}s)"
                )
                await self._bus._send_to_master(message)
            else:
                logger.error("Bus not initialized, cannot dispatch request")
                return create_step_response(
                    request_id=request.request_id,
                    step_id=step_id,
                    task_id=request.task_id,
                    success=False,
                    error="Communication bus not initialized",
                )

            # 等待响应
            response = await asyncio.wait_for(
                future,
                timeout=request.timeout_seconds,
            )
            logger.info(
                f"Request {request.request_id} completed: success={response.success}, "
                f"duration={response.duration_seconds:.2f}s"
            )
            return response

        except asyncio.TimeoutError:
            logger.error(
                f"Step request timeout: {request.request_id} (step={step_id}, "
                f"task={request.task_id}, timeout={request.timeout_seconds}s)"
            )
            return create_step_response(
                request_id=request.request_id,
                step_id=step_id,
                task_id=request.task_id,
                success=False,
                error=f"Request timeout after {request.timeout_seconds} seconds",
            )

        except Exception as e:
            logger.error(
                f"Unexpected error dispatching request {request.request_id}: {e}",
                exc_info=True
            )
            return create_step_response(
                request_id=request.request_id,
                step_id=step_id,
                task_id=request.task_id,
                success=False,
                error=f"Unexpected error: {str(e)}",
            )

        finally:
            self._pending_responses.pop(request.request_id, None)
            if agent_info:
                agent_info.clear_task(success=True)

    async def _handle_step_response(self, message: AgentMessage) -> AgentMessage | None:
        """处理步骤响应"""
        response = StepResponse.from_dict(message.payload)

        # 完成 Future
        future = self._pending_responses.pop(response.request_id, None)
        if future and not future.done():
            future.set_result(response)
        else:
            logger.warning(f"No pending response for request_id: {response.request_id}")

        return None

    async def _handle_default_message(self, message: AgentMessage) -> AgentMessage | None:
        """默认消息处理器 - 处理响应消息和就绪通知"""
        # 处理就绪通知
        if message.msg_type == MessageType.EVENT.value:
            if message.event_type == "agent_ready":
                sub_agent_id = message.payload.get("agent_id")
                if sub_agent_id:
                    self._mark_subagent_ready(sub_agent_id)
                return None

        # 响应消息通过 correlation_id 匹配
        if message.msg_type == MessageType.RESPONSE.value and message.correlation_id:
            # 尝试从 payload 构建 StepResponse
            try:
                if "request_id" in message.payload:
                    response = StepResponse.from_dict(message.payload)
                    future = self._pending_responses.pop(response.request_id, None)
                    if future and not future.done():
                        future.set_result(response)
                        logger.debug(f"Completed future for request_id: {response.request_id}")
                    else:
                        logger.warning(f"No pending response for request_id: {response.request_id}")
            except Exception as e:
                logger.error(f"Failed to handle response message: {e}")

        return None

    def _mark_subagent_ready(self, sub_agent_id: str) -> None:
        """标记 SubAgent 就绪"""
        # 更新 AgentInfo 状态
        agent_info = self._agent_infos.get(sub_agent_id)
        if agent_info:
            agent_info.status = AgentStatus.IDLE.value
            logger.info(f"SubAgent {sub_agent_id} status updated to IDLE")

        # 设置就绪事件
        ready_event = self._ready_events.get(sub_agent_id)
        if ready_event:
            ready_event.set()
            logger.info(f"SubAgent {sub_agent_id} ready event set")

    # ==================== 查询 ====================

    def get_sub_agent(self, step_id: str) -> str | None:
        """获取 SubAgent ID"""
        return self._sub_agents.get(step_id)

    def get_agent_info(self, sub_agent_id: str) -> AgentInfo | None:
        """获取 Agent 信息"""
        return self._agent_infos.get(sub_agent_id)

    def list_active(self) -> list[str]:
        """列出所有活跃的 SubAgent ID"""
        return [
            aid for aid, info in self._agent_infos.items()
            if info.status not in (AgentStatus.DEAD.value, AgentStatus.STOPPING.value)
        ]

    def is_running(self, step_id: str) -> bool:
        """检查 SubAgent 是否运行中"""
        sub_agent_id = self._sub_agents.get(step_id)
        if not sub_agent_id:
            return False
        agent_info = self._agent_infos.get(sub_agent_id)
        return agent_info is not None and agent_info.status == AgentStatus.BUSY.value


# ==================== 进程入口 ====================


def _subagent_process_entry(
    sub_agent_id: str,
    router_address: str,
    pub_address: str,
    config_dict: dict,
    data_dir: str | None,
) -> None:
    """
    SubAgent 进程入口函数

    在独立进程中运行，创建完整 Agent 实例并执行步骤任务。
    """
    import asyncio

    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s - {sub_agent_id} - %(levelname)s - %(message)s",
    )

    async def run_subagent():
        # 解析配置
        config = SubAgentConfig.from_dict(config_dict)

        # 创建 SubAgent 运行器
        runner = SubAgentRunner(
            sub_agent_id=sub_agent_id,
            config=config,
            router_address=router_address,
            pub_address=pub_address,
            data_dir=Path(data_dir) if data_dir else None,
        )

        await runner.start()

        try:
            while runner.is_running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            await runner.stop()

    asyncio.run(run_subagent())


class SubAgentRunner:
    """
    SubAgent 运行器

    在独立进程中运行，管理内置 Agent 实例并处理步骤请求。
    """

    def __init__(
        self,
        sub_agent_id: str,
        config: SubAgentConfig,
        router_address: str,
        pub_address: str,
        data_dir: Path | None = None,
    ):
        self.sub_agent_id = sub_agent_id
        self.config = config
        self._router_address = router_address
        self._pub_address = pub_address
        self._data_dir = data_dir

        # 内置 Agent
        self._agent = None
        # 通信总线
        self._bus: WorkerBus | None = None
        # 运行状态
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """启动 SubAgent"""
        logger.info(f"Starting SubAgent {self.sub_agent_id}")

        # 初始化内置 Agent
        await self._init_agent()

        # 初始化通信总线
        bus_config = BusConfig(
            router_address=self._router_address,
            pub_address=self._pub_address,
        )
        self._bus = WorkerBus(worker_id=self.sub_agent_id, config=bus_config)
        await self._bus.start()

        # 注册消息处理器
        self._bus.register_command_handler(
            CommandType.STEP_REQUEST,
            self._handle_step_request,
        )
        self._bus.register_command_handler(
            CommandType.SHUTDOWN,
            self._handle_shutdown,
        )

        # 注册到 Master
        await self._register()

        # 发送就绪通知
        await self._send_ready_notification()

        self._running = True
        logger.info(f"SubAgent {self.sub_agent_id} started")

    async def stop(self) -> None:
        """停止 SubAgent"""
        if not self._running:
            return

        logger.info(f"Stopping SubAgent {self.sub_agent_id}")
        self._running = False

        # 注销
        await self._unregister()

        # 停止通信总线
        if self._bus:
            await self._bus.stop()

        # 关闭内置 Agent
        if self._agent:
            await self._agent.shutdown()

        logger.info(f"SubAgent {self.sub_agent_id} stopped")

    async def _init_agent(self) -> None:
        """初始化内置 Agent"""
        from ..core.agent import Agent

        self._agent = Agent()
        await self._agent.initialize(start_scheduler=False)

        # 应用工具限制
        self._apply_tool_restrictions()

        logger.info(f"SubAgent {self.sub_agent_id}: internal agent initialized")

    def _apply_tool_restrictions(self) -> None:
        """
        应用工具限制

        根据 SubAgentConfig.allowed_tools 过滤 Agent 的可用工具。
        如果 allowed_tools 为空，则保留所有工具（无限制）。
        """
        if not self._agent:
            return

        allowed_tools = self.config.allowed_tools

        # 如果未配置允许的工具，则不做限制
        if not allowed_tools:
            logger.info(f"SubAgent {self.sub_agent_id}: no tool restrictions, all tools available")
            return

        # 获取当前所有工具
        all_tools = self._agent._tools
        tool_map = {t.get("name"): t for t in all_tools if t.get("name")}

        # 过滤工具：只保留允许的工具
        filtered_tools = []
        for tool_name in allowed_tools:
            if tool_name in tool_map:
                filtered_tools.append(tool_map[tool_name])
            else:
                logger.warning(
                    f"SubAgent {self.sub_agent_id}: allowed tool '{tool_name}' not found, skipping"
                )

        # 更新 Agent 的工具列表
        self._agent._tools = filtered_tools

        # 同时更新 handler_registry 的工具可见性
        # ToolExecutor 会通过 handler_registry 执行工具
        logger.info(
            f"SubAgent {self.sub_agent_id}: applied tool restrictions, "
            f"{len(all_tools)} -> {len(filtered_tools)} tools available: "
            f"{[t.get('name') for t in filtered_tools]}"
        )

    async def _register(self) -> None:
        """向 Master 注册"""
        agent_info = AgentInfo(
            agent_id=self.sub_agent_id,
            agent_type=AgentType.SPECIALIZED.value,
            process_id=multiprocessing.current_process().pid or 0,
            status=AgentStatus.IDLE.value,
            capabilities=self.config.allowed_tools,
        )

        message = AgentMessage.command(
            sender_id=self.sub_agent_id,
            target_id="master",
            command_type=CommandType.REGISTER,
            payload=agent_info.to_dict(),
        )

        if self._bus:
            await self._bus._send_to_master(message)

    async def _send_ready_notification(self) -> None:
        """发送就绪通知给 SubAgentManager"""
        # 广播就绪事件
        message = AgentMessage.event(
            sender_id=self.sub_agent_id,
            event_type=EventType.AGENT_REGISTERED,  # 复用已有的事件类型
            payload={
                "agent_id": self.sub_agent_id,
                "status": AgentStatus.IDLE.value,
                "ready": True,
            },
        )

        if self._bus:
            await self._bus._send_to_master(message)
            logger.info(f"SubAgent {self.sub_agent_id} sent ready notification")

    async def _unregister(self) -> None:
        """向 Master 注销"""
        message = AgentMessage.command(
            sender_id=self.sub_agent_id,
            target_id="master",
            command_type=CommandType.UNREGISTER,
            payload={"agent_id": self.sub_agent_id},
        )

        if self._bus:
            await self._bus._send_to_master(message)

    async def _handle_step_request(self, message: AgentMessage) -> AgentMessage | None:
        """处理步骤请求"""
        request = StepRequest.from_dict(message.payload)
        start_time = datetime.now()

        logger.info(f"SubAgent {self.sub_agent_id}: handling step request {request.step_id}")

        try:
            # 执行步骤
            output, output_data = await self._execute_step(request)
            duration = (datetime.now() - start_time).total_seconds()

            response = create_step_response(
                request_id=request.request_id,
                step_id=request.step_id,
                task_id=request.task_id,
                success=True,
                output=output,
                output_data=output_data,
                requires_confirmation=self.config.metadata.get("requires_confirmation", True),
            )
            response.duration_seconds = duration

        except Exception as e:
            logger.error(f"Step execution error: {e}", exc_info=True)
            response = create_step_response(
                request_id=request.request_id,
                step_id=request.step_id,
                task_id=request.task_id,
                success=False,
                error=str(e),
            )

        # 发送响应 - 发送给请求的发送者（通过 Master 路由）
        if self._bus:
            # 响应目标设置为请求的发送者
            response_message = response.to_agent_message(
                sender_id=self.sub_agent_id,
                target_id=message.sender_id,  # 发送给请求者
            )
            await self._bus._send_to_master(response_message)

        return None

    async def _execute_step(self, request: StepRequest) -> tuple[str, dict[str, Any]]:
        """
        执行步骤

        使用内置 Agent 处理请求，应用配置的工具限制和系统提示词。

        Returns:
            tuple[str, dict]: (原始输出字符串, 解析后的结构化数据)
        """
        if not self._agent:
            raise RuntimeError("Agent not initialized")

        # 构建系统提示词
        system_prompt = request.system_prompt_override or self.config.system_prompt

        # 注入上下文
        if request.context:
            context_str = self._format_context(request.context)
            if context_str:
                system_prompt = f"{system_prompt}\n\n## 前置步骤输出\n{context_str}"

        # 执行对话
        # 注意：工具限制已在 _init_agent 中通过 _apply_tool_restrictions() 应用
        response = await self._agent.chat(request.message)

        # 尝试从响应中提取结构化数据
        output_data = self._extract_output_data(response)

        return response, output_data

    def _extract_output_data(self, output: str) -> dict[str, Any]:
        """
        从 LLM 输出中提取结构化数据

        尝试解析 JSON 格式的输出，如果失败则返回包含原始输出的字典。
        """
        import json

        if not output:
            return {}

        # 尝试直接解析整个输出为 JSON
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass

        # 尝试从 markdown 代码块中提取 JSON
        import re
        json_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
        matches = re.findall(json_pattern, output, re.DOTALL)
        if matches:
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue

        # 尝试查找 JSON 对象
        json_obj_pattern = r'\{[^{}]*\}'
        matches = re.findall(json_obj_pattern, output, re.DOTALL)
        if matches:
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue

        # 无法解析，返回原始输出
        return {"raw_output": output}

    def _format_context(self, context: dict[str, Any]) -> str:
        """格式化上下文"""
        lines = []
        for key, value in context.items():
            if value:
                lines.append(f"### {key}")
                if isinstance(value, dict):
                    lines.append(str(value))
                elif isinstance(value, str):
                    lines.append(value)
                else:
                    lines.append(str(value))
                lines.append("")
        return "\n".join(lines)

    async def _handle_shutdown(self, message: AgentMessage) -> AgentMessage | None:
        """处理关闭命令"""
        logger.info(f"SubAgent {self.sub_agent_id}: received shutdown command")
        self._running = False

        return AgentMessage.response(
            sender_id=self.sub_agent_id,
            target_id=message.sender_id,
            correlation_id=message.msg_id,
            payload={"success": True},
        )