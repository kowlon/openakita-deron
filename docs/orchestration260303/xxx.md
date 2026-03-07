多Agent流式输出架构方案

  一、当前架构分析

  1.1 数据流现状

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                              WebApp (SSE)                                    │
  │                                  ↓                                           │
  │                           Chat API Route                                     │
  │                                  ↓                                           │
  │                    MasterAgent.handle_request_stream()                       │
  │                                  ↓                                           │
  │            ┌────────────────────┴────────────────────┐                      │
  │            ↓                                         ↓                      │
  │    _handle_locally_stream()              _distribute_task()                 │
  │            ↓                                         ↓                      │
  │    Agent.chat_with_session_stream()       ZMQ DEALER → Worker               │
  │            ✓ 流式                                  ↓                      │
  │                                          WorkerAgent._execute_chat_task()   │
  │                                                  ↓                          │
  │                                          Agent.chat_with_session()          │
  │                                                  ✗ 非流式                    │
  └─────────────────────────────────────────────────────────────────────────────┘

  1.2 核心问题

  ┌────────────────────┬────────────────────────┬─────────────────────┬───────────────────────┐
  │        层级        │          组件          │      当前状态       │         问题          │
  ├────────────────────┼────────────────────────┼─────────────────────┼───────────────────────┤
  │ L1: 消息协议       │ messages.py            │ 只有 TASK_RESULT    │ 缺少流式事件类型      │
  ├────────────────────┼────────────────────────┼─────────────────────┼───────────────────────┤
  │ L2: Worker执行     │ worker.py:314          │ chat_with_session() │ 非流式调用            │
  ├────────────────────┼────────────────────────┼─────────────────────┼───────────────────────┤
  │ L3: Master分发     │ master.py:410          │ Future 等待结果     │ 无法接收增量事件      │
  ├────────────────────┼────────────────────────┼─────────────────────┼───────────────────────┤
  │ L4: SubAgentWorker │ subagent_worker.py:488 │ chat_with_session() │ 非流式调用            │
  ├────────────────────┼────────────────────────┼─────────────────────┼───────────────────────┤
  │ L5: 事件传递       │ 整体链路               │ 断裂                │ Worker事件无法到达SSE │
  └────────────────────┴────────────────────────┴─────────────────────┴───────────────────────┘

  ---
  二、架构设计方案

  2.1 设计原则

  1. 统一事件流: 所有 Agent 产出的事件最终汇聚到同一 SSE 通道
  2. 向后兼容: 不破坏现有的非流式 API
  3. 最小侵入: 复用现有 Agent.chat_with_session_stream() 实现
  4. 协议层解耦: 传输层只管事件转发，不关心事件语义

  2.2 核心抽象：事件溯源通道

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                          Event Sourcing Channel                              │
  │                                                                              │
  │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────────────────┐  │
  │  │  Agent   │───▶│  Event   │───▶│  Event   │───▶│   SSE Response       │  │
  │  │ (任何位置)│    │  Queue   │    │  Router  │    │   (Chat API)         │  │
  │  └──────────┘    └──────────┘    └──────────┘    └──────────────────────┘  │
  │       │                               │                                      │
  │       │                               │                                      │
  │  ┌────┴────┐                    ┌─────┴─────┐                               │
  │  │ Worker  │                    │   Topic   │                               │
  │  │ Process │                    │  Routing  │                               │
  │  └─────────┘                    └───────────┘                               │
  └─────────────────────────────────────────────────────────────────────────────┘

  2.3 事件协议设计

  # ==================== 新增事件类型 ====================

  class StreamEventType(Enum):
      """流式事件类型 - 与 Agent.chat_with_session_stream() 输出对齐"""

      # 思考过程
      THINKING_START = "thinking_start"
      THINKING_DELTA = "thinking_delta"
      THINKING_END = "thinking_end"

      # 文本输出
      TEXT_DELTA = "text_delta"

      # 工具调用
      TOOL_CALL_START = "tool_call_start"
      TOOL_CALL_END = "tool_call_end"

      # Plan 相关
      PLAN_CREATED = "plan_created"
      PLAN_STEP_UPDATED = "plan_step_updated"

      # 交互
      ASK_USER = "ask_user"

      # 步骤级事件（用于最佳实践任务）
      STEP_STARTED = "step_started"
      STEP_PROGRESS = "step_progress"  # 步骤内的流式输出
      STEP_COMPLETED = "step_completed"

      # 终结
      DONE = "done"
      ERROR = "error"

  2.4 消息协议扩展

  # ==================== messages.py 扩展 ====================

  class CommandType(Enum):
      # ... 现有命令 ...

      # 新增：流式事件传递
      STREAM_EVENT = "stream_event"      # Worker → Master 流式事件
      STREAM_DONE = "stream_done"        # Worker → Master 流结束标记


  @dataclass
  class StreamEventPayload:
      """流式事件载荷"""
      task_id: str
      session_id: str           # 用于路由到正确的 SSE 连接
      event: dict               # 实际事件内容
      sequence: int = 0         # 事件序号（可选，用于顺序保证）

      def to_dict(self) -> dict:
          return {
              "task_id": self.task_id,
              "session_id": self.session_id,
              "event": self.event,
              "sequence": self.sequence,
          }

  ---
  三、实现方案

  3.1 方案一：ZMQ PUB/SUB 模式（推荐）

  架构图：

                      ┌─────────────────────────────────────┐
                      │           MasterAgent               │
                      │  ┌─────────────────────────────┐   │
                      │  │    Event Router             │   │
                      │  │  (session_id → SSE Queue)   │   │
                      │  └─────────────────────────────┘   │
                      │              ▲                      │
                      │              │ PUB                  │
                      │     ┌────────┴────────┐            │
                      │     │  ZMQ PUB Socket │            │
                      │     │  tcp://*:5557   │            │
                      │     └─────────────────┘            │
                      └─────────────────────────────────────┘
                                      │
                      ┌───────────────┼───────────────┐
                      │               │               │
                ┌─────┴─────┐  ┌─────┴─────┐  ┌─────┴─────┐
                │  Worker 1 │  │  Worker 2 │  │  Worker N │
                │ SUB Socket│  │ SUB Socket│  │ SUB Socket│
                └───────────┘  └───────────┘  └───────────┘

  优点：
  - ZMQ PUB/SUB 原生支持，性能优秀
  - Worker 可以订阅 Master 的控制消息（如取消任务）
  - 与现有 ROUTER/DEALER 架构互补

  实现要点：

  # ==================== Worker 端 ====================

  class WorkerAgent:
      async def _execute_chat_task_stream(self, task: TaskPayload) -> None:
          """流式执行对话任务，发送增量事件到 Master"""
          session_messages = task.context.get("session_messages", [])
          session_id = task.session_id or "worker"

          event_sequence = 0

          try:
              async for event in self._agent.chat_with_session_stream(
                  message=task.content,
                  session_messages=session_messages,
                  session_id=session_id,
              ):
                  # 发送流式事件到 Master
                  await self._send_stream_event(
                      task_id=task.task_id,
                      session_id=session_id,
                      event=event,
                      sequence=event_sequence,
                  )
                  event_sequence += 1

              # 发送完成标记
              await self._send_stream_done(task.task_id, session_id)

          except Exception as e:
              await self._send_stream_event(
                  task_id=task.task_id,
                  session_id=session_id,
                  event={"type": "error", "message": str(e)},
              )

      async def _send_stream_event(
          self,
          task_id: str,
          session_id: str,
          event: dict,
          sequence: int = 0,
      ) -> None:
          """发送流式事件"""
          message = AgentMessage.command(
              sender_id=self.agent_id,
              target_id="master",
              command_type=CommandType.STREAM_EVENT,
              payload={
                  "task_id": task_id,
                  "session_id": session_id,
                  "event": event,
                  "sequence": sequence,
              },
          )
          await self.bus._send_to_master(message)

  # ==================== Master 端 ====================

  class MasterAgent:
      def __init__(self, ...):
          # ... 现有初始化 ...

          # 流式事件队列：session_id → asyncio.Queue
          self._stream_queues: dict[str, asyncio.Queue] = {}

      async def _distribute_task_stream(
          self,
          session_id: str,
          message: str,
          session_messages: list[dict] | None = None,
          session: Any = None,
          gateway: Any = None,
      ) -> AsyncIterator[dict]:
          """流式分发任务给 Worker"""

          # 创建事件队列
          event_queue = asyncio.Queue()
          self._stream_queues[session_id] = event_queue

          # 创建任务
          task_id = str(uuid.uuid4())[:8]
          task = TaskPayload(
              task_id=task_id,
              task_type="chat",
              description=f"处理用户消息: {message}",
              content=message,
              session_id=session_id,
              context={"session_messages": session_messages or []},
          )

          # 发送任务到 Worker
          await self.bus.send_command(
              target_id=worker.agent_id,
              command_type=CommandType.ASSIGN_TASK,
              payload=task.to_dict(),
              wait_response=False,
          )

          try:
              # 流式返回事件
              while True:
                  event = await asyncio.wait_for(
                      event_queue.get(),
                      timeout=task.timeout_seconds,
                  )

                  if event.get("type") == "__stream_done__":
                      break

                  yield event

          finally:
              self._stream_queues.pop(session_id, None)

      async def _handle_stream_event(self, message: AgentMessage) -> None:
          """处理流式事件"""
          payload = message.payload
          session_id = payload.get("session_id")
          event = payload.get("event")

          queue = self._stream_queues.get(session_id)
          if queue:
              await queue.put(event)

      def _register_handlers(self) -> None:
          # ... 现有处理器 ...

          # 新增：流式事件处理
          self.bus.register_command_handler(
              CommandType.STREAM_EVENT,
              self._handle_stream_event,
          )

  3.2 方案二：共享事件总线（更优雅）

  核心思想： 将 TaskOrchestrator 的 Event 系统扩展为全局事件总线。

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                        Global Event Bus                                      │
  │                                                                              │
  │  ┌─────────────────────────────────────────────────────────────────────┐   │
  │  │                    EventRouter (单例)                                │   │
  │  │                                                                      │   │
  │  │   subscribe(session_id, queue) ────▶ 注册事件队列                    │   │
  │  │   publish(session_id, event) ──────▶ 分发到对应队列                  │   │
  │  │                                                                      │   │
  │  └─────────────────────────────────────────────────────────────────────┘   │
  │              ▲                           ▲                                  │
  │              │ publish                    │ publish                         │
  │     ┌────────┴────────┐        ┌─────────┴──────────┐                     │
  │     │  MasterAgent    │        │  WorkerAgent       │                     │
  │     │  (本地执行)      │        │  (进程间执行)       │                     │
  │     └─────────────────┘        └────────────────────┘                     │
  │                                              ▲                              │
  │                                              │ ZMQ 传递                    │
  │                                     ┌────────┴──────────┐                 │
  │                                     │ SubAgentWorker    │                 │
  │                                     │ (最佳实践步骤)     │                 │
  │                                     └───────────────────┘                 │
  └─────────────────────────────────────────────────────────────────────────────┘

  实现：

  # ==================== event_bus.py ====================

  import asyncio
  from typing import Any
  from dataclasses import dataclass
  from collections import defaultdict

  @dataclass
  class StreamEvent:
      """流式事件"""
      session_id: str
      event_type: str
      data: dict[str, Any]
      source: str = ""  # 来源标识 (master/worker/step)


  class GlobalEventBus:
      """
      全局事件总线

      单例模式，所有 Agent 共享同一个事件总线。
      支持按 session_id 订阅/发布事件。
      """

      _instance = None

      def __new__(cls):
          if cls._instance is None:
              cls._instance = super().__new__(cls)
              cls._instance._queues: dict[str, asyncio.Queue] = {}
              cls._instance._lock = asyncio.Lock()
          return cls._instance

      async def subscribe(self, session_id: str) -> asyncio.Queue:
          """订阅 session 的事件流"""
          async with self._lock:
              if session_id not in self._queues:
                  self._queues[session_id] = asyncio.Queue()
              return self._queues[session_id]

      async def unsubscribe(self, session_id: str) -> None:
          """取消订阅"""
          async with self._lock:
              self._queues.pop(session_id, None)

      async def publish(self, event: StreamEvent) -> None:
          """发布事件"""
          queue = self._queues.get(event.session_id)
          if queue:
              await queue.put(event)

      def publish_sync(self, event: StreamEvent) -> None:
          """同步发布（用于跨进程场景）"""
          queue = self._queues.get(event.session_id)
          if queue:
              # 非阻塞放入
              try:
                  queue.put_nowait(event)
              except asyncio.QueueFull:
                  pass


  # 全局单例
  event_bus = GlobalEventBus()

  ---
  四、最佳实践任务流式方案

  4.1 当前最佳实践流程

  用户消息 → TaskOrchestrator.route_input() → 命中最佳实践
                  ↓
           create_task(template_id)
                  ↓
           OrchestrationTask (多步骤)
                  ↓
           for step in task.steps:
               SubAgentWorker.execute(step)
                      ↓
               Agent.chat_with_session()  ✗ 非流式

  4.2 改造后的流程

  用户消息 → TaskOrchestrator.route_input() → 命中最佳实践
                  ↓
           create_task(template_id)
                  ↓
           publish(TASK_CREATED) ──────────────▶ SSE
                  ↓
           for step in task.steps:
               publish(STEP_STARTED) ──────────▶ SSE
                      ↓
               SubAgentWorker.execute_stream(step)
                      ↓
               Agent.chat_with_session_stream()
                      ↓
               for event in stream:
                   publish(STEP_PROGRESS) ─────▶ SSE
                      ↓
               publish(STEP_COMPLETED) ────────▶ SSE
                      ↓
           publish(TASK_COMPLETED) ────────────▶ SSE

  4.3 关键代码改造

  # ==================== TaskOrchestrator 扩展 ====================

  class TaskOrchestrator:
      async def execute_task_stream(
          self,
          task: OrchestrationTask,
      ) -> AsyncIterator[dict]:
          """
          流式执行任务，yield 步骤事件

          用于最佳实践任务的多步骤执行。
          """
          task.status = TaskStatus.RUNNING.value
          await self._storage.save_task(task)

          # 发布任务开始事件
          yield {
              "type": "task_started",
              "task_id": task.id,
              "task_name": task.name,
              "total_steps": len(task.steps),
          }

          try:
              for step in task.steps:
                  # 发布步骤开始事件
                  yield {
                      "type": "step_started",
                      "task_id": task.id,
                      "step_id": step.id,
                      "step_name": step.name,
                      "step_index": step.index,
                  }

                  # 流式执行步骤
                  async for event in self._execute_step_stream(task, step):
                      yield event

                  # 发布步骤完成事件
                  yield {
                      "type": "step_completed",
                      "task_id": task.id,
                      "step_id": step.id,
                  }

                  # 检查是否需要继续
                  if step.status == StepStatus.FAILED.value:
                      break

              # 任务完成
              task.status = TaskStatus.COMPLETED.value
              await self._storage.save_task(task)

              yield {
                  "type": "task_completed",
                  "task_id": task.id,
              }

          except Exception as e:
              yield {
                  "type": "task_failed",
                  "task_id": task.id,
                  "error": str(e),
              }

      async def _execute_step_stream(
          self,
          task: OrchestrationTask,
          step: TaskStep,
      ) -> AsyncIterator[dict]:
          """流式执行单个步骤"""

          step.set_status(StepStatus.RUNNING)
          await self._storage.save_step(step)

          # 构建 SubAgentPayload
          payload = SubAgentPayload(
              task_id=task.id,
              step_id=step.id,
              step_index=step.index,
              agent_config=step.sub_agent_config,
              task_context=task.context_variables,
              previous_steps_summary=self._build_previous_summary(task, step),
              user_input=task.input_payload.get("user_input", ""),
          )

          # 流式执行
          worker = self._get_available_worker()
          async for event in worker.execute_stream(payload):
              # 包装步骤上下文
              yield {
                  **event,
                  "task_id": task.id,
                  "step_id": step.id,
              }

  # ==================== SubAgentWorker 扩展 ====================

  class SubAgentWorker:
      async def execute_stream(
          self,
          payload: SubAgentPayload,
      ) -> AsyncIterator[dict]:
          """
          流式执行步骤，yield 事件

          使用 Agent.chat_with_session_stream() 实现流式输出。
          """
          if not self._running:
              await self.start()

          agent_config = payload.agent_config
          system_prompt = self._build_system_prompt(agent_config, payload)
          messages = self._build_chat_messages(payload, system_prompt)

          agent = Agent(name=agent_config.name)

          try:
              await agent.initialize(start_scheduler=False)

              # 流式执行
              async for event in agent.chat_with_session_stream(
                  message=payload.user_input,
                  session_messages=messages,
                  session_id=f"task-{payload.task_id}-step-{payload.step_id}",
              ):
                  yield event

          finally:
              await agent.shutdown()

  ---
  五、统一 SSE 输出格式

  5.1 前端兼容性保证

  无论任务是本地执行、Worker 执行还是最佳实践任务，前端收到的 SSE 事件格式完全一致：

  // 前端 SSE 事件类型定义
  interface SSEEvent {
    type:
      | "thinking_start" | "thinking_delta" | "thinking_end"
      | "text_delta"
      | "tool_call_start" | "tool_call_end"
      | "plan_created" | "plan_step_updated"
      | "step_started" | "step_progress" | "step_completed"  // 最佳实践任务
      | "task_started" | "task_completed"                    // 最佳实践任务
      | "ask_user"
      | "error" | "done"

    // 通用字段
    content?: string
    message?: string

    // 工具调用字段
    tool?: string
    args?: object
    result?: string

    // 步骤字段（最佳实践任务）
    task_id?: string
    step_id?: string
    step_name?: string
    step_index?: number
  }

  5.2 Chat API 统一入口

  # ==================== chat.py 统一处理 ====================

  async def _stream_chat(...) -> AsyncIterator[str]:
      """统一 SSE 流式输出"""

      if isinstance(agent, MasterAgent):
          # 多 Agent 模式
          async for event in agent.handle_request_stream(
              session_id=conversation_id,
              message=chat_request.message or "",
              session_messages=session_messages_history,
              session=session,
              gateway=None,
          ):
              # 统一 SSE 格式输出
              yield _sse(event.get("type", ""), {k: v for k, v in event.items() if k != "type"})

              # artifact 处理...
      else:
          # 单 Agent 模式（已有实现）
          async for event in actual_agent.chat_with_session_stream(...):
              yield _sse(event.get("type", ""), {k: v for k, v in event.items() if k != "type"})

  ---
  六、实现优先级与步骤

  ┌────────┬───────────────────────┬──────────────────────┬──────────────────────────────────────────────────┐
  │ 优先级 │         步骤          │         文件         │                     改动范围                     │
  ├────────┼───────────────────────┼──────────────────────┼──────────────────────────────────────────────────┤
  │ P0     │ 扩展消息协议          │ messages.py          │ 添加 STREAM_EVENT 命令类型                       │
  ├────────┼───────────────────────┼──────────────────────┼──────────────────────────────────────────────────┤
  │ P1     │ Worker 流式执行       │ worker.py            │ 添加 _execute_chat_task_stream()                 │
  ├────────┼───────────────────────┼──────────────────────┼──────────────────────────────────────────────────┤
  │ P2     │ Master 事件路由       │ master.py            │ 添加 _stream_queues 和 _distribute_task_stream() │
  ├────────┼───────────────────────┼──────────────────────┼──────────────────────────────────────────────────┤
  │ P3     │ SubAgentWorker 流式   │ subagent_worker.py   │ 添加 execute_stream()                            │
  ├────────┼───────────────────────┼──────────────────────┼──────────────────────────────────────────────────┤
  │ P4     │ TaskOrchestrator 流式 │ task_orchestrator.py │ 添加 execute_task_stream()                       │
  ├────────┼───────────────────────┼──────────────────────┼──────────────────────────────────────────────────┤
  │ P5     │ SSE 统一输出          │ chat.py              │ 验证事件格式一致性                               │
  └────────┴───────────────────────┴──────────────────────┴──────────────────────────────────────────────────┘

  ---
  七、风险与注意事项

  1. ZMQ 消息顺序：ZMQ DEALER/ROUTER 保证同一连接的消息顺序，但多 Worker 并发时需要通过 session_id 路由
  2. 资源清理：SSE 连接断开时需要清理 _stream_queues，避免内存泄漏
  3. 超时处理：流式任务的超时机制需要重新设计，不能简单等待 Future
  4. 错误传播：Worker 中的异常需要通过 error 事件传递到前端

  ---
  这个方案的核心优势是：

  1. 协议层统一：所有 Agent 都产出相同格式的事件
  2. 向后兼容：非流式 API 不受影响
  3. 渐进式实现：可以分阶段完成，每阶段都可独立验证
  4. 前端透明：前端代码无需修改，自动支持新的流式场景