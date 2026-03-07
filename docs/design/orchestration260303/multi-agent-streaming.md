# Multi-Agent Streaming Architecture Design

## Overview

This document describes the architecture for supporting streaming output in Multi-Agent mode, ensuring consistent behavior with single-Agent mode in the webapp.

## Current Architecture Analysis

### Data Flow (Current)

```
WebApp (SSE)
    ↓
Chat API Route
    ↓
MasterAgent.handle_request_stream()
    ↓
    ├── _handle_locally_stream() → Agent.chat_with_session_stream() ✓ Streaming
    │
    └── _distribute_task() → ZMQ DEALER → Worker
                                   ↓
                           WorkerAgent._execute_chat_task()
                                   ↓
                           Agent.chat_with_session() ✗ Non-streaming
```

### Core Issues

| Layer | Component | Current State | Problem |
|-------|-----------|---------------|---------|
| L1: Protocol | `messages.py` | Only `TASK_RESULT` | Missing streaming event types |
| L2: Worker | `worker.py:314` | `chat_with_session()` | Non-streaming call |
| L3: Master | `master.py:410` | `Future` wait | Cannot receive incremental events |
| L4: SubAgentWorker | `subagent_worker.py:488` | `chat_with_session()` | Non-streaming call |
| L5: Event Flow | Overall | Broken | Worker events cannot reach SSE |

## Proposed Architecture

### Design Principles

1. **Unified Event Flow**: All Agent output events converge to the same SSE channel
2. **Backward Compatibility**: Do not break existing non-streaming APIs
3. **Minimal Intrusion**: Reuse existing `Agent.chat_with_session_stream()` implementation
4. **Protocol Layer Decoupling**: Transport layer only handles event forwarding, not event semantics

### Event Protocol Extension

```python
class CommandType(Enum):
    # ... existing commands ...

    # New: Streaming event delivery
    STREAM_EVENT = "stream_event"      # Worker → Master streaming event
    STREAM_DONE = "stream_done"        # Worker → Master stream end marker


@dataclass
class StreamEventPayload:
    """Streaming event payload"""
    task_id: str
    session_id: str           # Route to correct SSE connection
    event: dict               # Actual event content
    sequence: int = 0         # Event sequence number (optional, for ordering)
```

### Data Flow (Proposed)

```
WebApp (SSE)
    ↓
Chat API Route
    ↓
MasterAgent.handle_request_stream()
    ↓
    ├── _handle_locally_stream() → Agent.chat_with_session_stream() ✓ Streaming
    │
    └── _distribute_task_stream()
            ↓
        ZMQ DEALER → Worker
            ↓
        WorkerAgent._execute_chat_task_stream()
            ↓
        Agent.chat_with_session_stream() ✓ Streaming
            ↓
        STREAM_EVENT messages → Master
            ↓
        Master._stream_queues[session_id] → SSE
```

## Implementation Details

### 1. Message Protocol Extension (messages.py)

```python
class CommandType(Enum):
    # ... existing ...
    STREAM_EVENT = "stream_event"
    STREAM_DONE = "stream_done"
```

### 2. Worker Streaming (worker.py)

```python
class WorkerAgent:
    async def _execute_chat_task_stream(self, task: TaskPayload) -> None:
        """Stream execute chat task, send incremental events to Master"""
        session_messages = task.context.get("session_messages", [])
        session_id = task.session_id or "worker"

        event_sequence = 0

        try:
            async for event in self._agent.chat_with_session_stream(
                message=task.content,
                session_messages=session_messages,
                session_id=session_id,
            ):
                await self._send_stream_event(
                    task_id=task.task_id,
                    session_id=session_id,
                    event=event,
                    sequence=event_sequence,
                )
                event_sequence += 1

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
        """Send streaming event"""
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

    async def _send_stream_done(self, task_id: str, session_id: str) -> None:
        """Send stream done marker"""
        message = AgentMessage.command(
            sender_id=self.agent_id,
            target_id="master",
            command_type=CommandType.STREAM_DONE,
            payload={"task_id": task_id, "session_id": session_id},
        )
        await self.bus._send_to_master(message)
```

### 3. Master Event Routing (master.py)

```python
class MasterAgent:
    def __init__(self, ...):
        # ... existing init ...

        # Streaming event queues: session_id → asyncio.Queue
        self._stream_queues: dict[str, asyncio.Queue] = {}

    async def _distribute_task_stream(
        self,
        session_id: str,
        message: str,
        session_messages: list[dict] | None = None,
        session: Any = None,
        gateway: Any = None,
    ) -> AsyncIterator[dict]:
        """Stream distribute task to Worker"""

        # Create event queue
        event_queue = asyncio.Queue()
        self._stream_queues[session_id] = event_queue

        # Find idle worker
        worker = self.registry.find_idle_agent(exclude_ids=[self.agent_id])
        if not worker:
            # Fallback to local handling
            async for event in self._handle_locally_stream(...):
                yield event
            return

        # Create task
        task_id = str(uuid.uuid4())[:8]
        task = TaskPayload(
            task_id=task_id,
            task_type="chat",
            description=f"Handle user message: {message}",
            content=message,
            session_id=session_id,
            context={"session_messages": session_messages or []},
        )

        self._pending_tasks[task_id] = task

        try:
            # Send task to Worker
            await self.bus.send_command(
                target_id=worker.agent_id,
                command_type=CommandType.ASSIGN_TASK,
                payload=task.to_dict(),
                wait_response=False,
            )

            # Stream events
            while True:
                event = await asyncio.wait_for(
                    event_queue.get(),
                    timeout=task.timeout_seconds,
                )

                if event.get("type") == "__stream_done__":
                    break

                yield event

        except TimeoutError:
            yield {"type": "error", "message": "Task timeout"}
        finally:
            self._stream_queues.pop(session_id, None)
            self._pending_tasks.pop(task_id, None)
            self.registry.clear_agent_task(worker.agent_id, success=False)

    async def _handle_stream_event(self, message: AgentMessage) -> None:
        """Handle streaming event"""
        payload = message.payload
        session_id = payload.get("session_id")
        event = payload.get("event")

        queue = self._stream_queues.get(session_id)
        if queue:
            await queue.put(event)

    async def _handle_stream_done(self, message: AgentMessage) -> None:
        """Handle stream done marker"""
        payload = message.payload
        session_id = payload.get("session_id")

        queue = self._stream_queues.get(session_id)
        if queue:
            await queue.put({"type": "__stream_done__"})

    def _register_handlers(self) -> None:
        # ... existing handlers ...

        # New: Streaming event handlers
        self.bus.register_command_handler(
            CommandType.STREAM_EVENT,
            self._handle_stream_event,
        )
        self.bus.register_command_handler(
            CommandType.STREAM_DONE,
            self._handle_stream_done,
        )
```

### 4. SubAgentWorker Streaming (subagent_worker.py)

```python
class SubAgentWorker:
    async def execute_stream(
        self,
        payload: SubAgentPayload,
    ) -> AsyncIterator[dict]:
        """
        Stream execute step, yield events.

        Uses Agent.chat_with_session_stream() for streaming output.
        """
        if not self._running:
            await self.start()

        agent_config = payload.agent_config
        system_prompt = self._build_system_prompt(agent_config, payload)
        messages = self._build_chat_messages(payload, system_prompt)

        agent = Agent(name=agent_config.name)

        try:
            await agent.initialize(start_scheduler=False)

            # Stream execution
            async for event in agent.chat_with_session_stream(
                message=payload.user_input,
                session_messages=messages,
                session_id=f"task-{payload.task_id}-step-{payload.step_id}",
            ):
                yield event

        finally:
            await agent.shutdown()
```

### 5. TaskOrchestrator Streaming (task_orchestrator.py)

```python
class TaskOrchestrator:
    async def execute_task_stream(
        self,
        task: OrchestrationTask,
    ) -> AsyncIterator[dict]:
        """
        Stream execute task, yield step events.

        For best-practice tasks with multiple steps.
        """
        task.status = TaskStatus.RUNNING.value
        await self._storage.save_task(task)

        # Publish task start event
        yield {
            "type": "task_started",
            "task_id": task.id,
            "task_name": task.name,
            "total_steps": len(task.steps),
        }

        try:
            for step in task.steps:
                # Publish step start event
                yield {
                    "type": "step_started",
                    "task_id": task.id,
                    "step_id": step.id,
                    "step_name": step.name,
                    "step_index": step.index,
                }

                # Stream execute step
                async for event in self._execute_step_stream(task, step):
                    yield event

                # Publish step complete event
                yield {
                    "type": "step_completed",
                    "task_id": task.id,
                    "step_id": step.id,
                }

                if step.status == StepStatus.FAILED.value:
                    break

            # Task complete
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
```

## Best Practice Task Flow

### Current Flow (Non-streaming)

```
User Message → TaskOrchestrator.route_input() → Match Best Practice
                      ↓
              create_task(template_id)
                      ↓
              OrchestrationTask (multi-step)
                      ↓
              for step in task.steps:
                  SubAgentWorker.execute(step)
                          ↓
                  Agent.chat_with_session()  ✗ Non-streaming
```

### Proposed Flow (Streaming)

```
User Message → TaskOrchestrator.route_input() → Match Best Practice
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
```

## SSE Event Format

### Unified Output Format

Frontend receives consistent SSE events regardless of execution path:

```typescript
interface SSEEvent {
  type:
    | "thinking_start" | "thinking_delta" | "thinking_end"
    | "text_delta"
    | "tool_call_start" | "tool_call_end"
    | "plan_created" | "plan_step_updated"
    | "step_started" | "step_progress" | "step_completed"  // Best practice tasks
    | "task_started" | "task_completed"                    // Best practice tasks
    | "ask_user"
    | "error" | "done"

  // Common fields
  content?: string
  message?: string

  // Tool call fields
  tool?: string
  args?: object
  result?: string

  // Step fields (best practice tasks)
  task_id?: string
  step_id?: string
  step_name?: string
  step_index?: number
}
```

## Implementation Priority

| Priority | Step | File | Change Scope |
|----------|------|------|--------------|
| **P0** | Extend message protocol | `messages.py` | Add `STREAM_EVENT`, `STREAM_DONE` |
| **P1** | Worker streaming execution | `worker.py` | Add `_execute_chat_task_stream()` |
| **P2** | Master event routing | `master.py` | Add `_stream_queues`, `_distribute_task_stream()` |
| **P3** | SubAgentWorker streaming | `subagent_worker.py` | Add `execute_stream()` |
| **P4** | TaskOrchestrator streaming | `task_orchestrator.py` | Add `execute_task_stream()` |
| **P5** | SSE unified output | `chat.py` | Verify event format consistency |

## Risks and Considerations

1. **ZMQ Message Ordering**: ZMQ DEALER/ROUTER guarantees message order on the same connection, but multiple Workers require `session_id` routing
2. **Resource Cleanup**: `_stream_queues` must be cleaned up when SSE connection drops to avoid memory leaks
3. **Timeout Handling**: Streaming task timeout mechanism needs redesign, cannot simply wait for Future
4. **Error Propagation**: Worker exceptions must be propagated to frontend via `error` events

## Testing Strategy

1. **Unit Tests**:
   - Test `_send_stream_event()` message format
   - Test `_handle_stream_event()` queue insertion
   - Test `_distribute_task_stream()` event yield

2. **Integration Tests**:
   - Test full streaming flow: Worker → Master → SSE
   - Test timeout handling
   - Test error propagation

3. **E2E Tests**:
   - Verify webapp displays step cards correctly
   - Verify streaming text output in real-time