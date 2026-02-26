# ask_user 处理逻辑梳理

## 概述

`ask_user` 是 OpenAkita Agent 中用于向用户提问并暂停执行的关键工具。本文档详细分析其完整处理流程，包括工具定义、拦截机制、IM/CLI 双模式处理、前端交互等。

---

## 一、整体架构

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            ask_user 处理流程                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   LLM 决策调用 ask_user                                                         │
│         │                                                                       │
│         ▼                                                                       │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                    ReasoningEngine (ACT 阶段)                          │   │
│   │  ┌─────────────────────────────────────────────────────────────────┐   │   │
│   │  │  1. 识别 ask_user 调用                                          │   │   │
│   │  │  2. 分离 ask_user_calls 和 other_calls                         │   │   │
│   │  │  3. 先执行 other_calls (如果有)                                 │   │   │
│   │  │  4. 拦截 ask_user，不执行实际 Handler                           │   │   │
│   │  └─────────────────────────────────────────────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│         │                                                                       │
│         ├─────────────────────────────────────────────────────────────┐       │
│         │                                                             │       │
│         ▼                                                             ▼       │
│   ┌───────────────────┐                                     ┌───────────────┐ │
│   │    CLI 模式        │                                     │    IM 模式     │ │
│   │  直接返回问题文本   │                                     │  等待用户回复   │ │
│   │  由用户下次输入回答 │                                     │  超时 + 追问    │ │
│   └───────────────────┘                                     └───────────────┘ │
│                                                                     │         │
│                                                                     ▼         │
│                                                           ┌─────────────────┐  │
│                                                           │ 用户回复/超时    │  │
│                                                           │ 注入 tool_result │  │
│                                                           │ 继续 ReAct 循环  │  │
│                                                           └─────────────────┘  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、工具定义

### 2.1 Schema 定义

位置：`src/openakita/tools/definitions/system.py`

```python
SYSTEM_TOOLS = [
    {
        "name": "ask_user",
        "category": "System",
        "description": "向用户提问并暂停执行，直到他们回复...",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "单个问题文本，或多问题时的总体说明/标题",
                },
                "options": {
                    "type": "array",
                    "description": "单个问题的选项列表（简单模式）",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "选项唯一标识"},
                            "label": {"type": "string", "description": "选项显示文本"},
                        },
                        "required": ["id", "label"],
                    },
                },
                "allow_multiple": {
                    "type": "boolean",
                    "description": "是否允许多选（默认 false）",
                    "default": False,
                },
                "questions": {
                    "type": "array",
                    "description": "多个问题列表（复杂模式）",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "问题唯一标识"},
                            "prompt": {"type": "string", "description": "问题文本"},
                            "options": {...},      # 同上
                            "allow_multiple": {...}, # 同上
                        },
                        "required": ["id", "prompt"],
                    },
                },
            },
            "required": ["question"],
        },
    },
]
```

### 2.2 使用场景

| 场景 | 参数配置 |
|------|----------|
| 简单单问 | `question="确认执行吗？"` |
| 单选 | `question="选择方案", options=[{id:"a",label:"方案A"},{id:"b",label:"方案B"}]` |
| 多选 | `question="选择功能", options=[...], allow_multiple=true` |
| 多问题 | `question="请填写", questions=[{id:"name",prompt:"姓名"},{id:"age",prompt:"年龄"}]` |

### 2.3 重要特性

```
┌─────────────────────────────────────────────────────────────────┐
│  ask_user 关键特性                                               │
├─────────────────────────────────────────────────────────────────┤
│  ✅ 调用后立即暂停当前任务执行循环                                 │
│  ✅ 用户回复后保留上下文继续执行                                   │
│  ✅ 支持 CLI 模式（返回等待）和 IM 模式（等待回复）                 │
│  ✅ 支持选项点击和自由输入                                         │
│  ✅ IM 模式支持超时提醒和自动决策                                  │
│  ❌ 不要在纯文本中提问——问号不会触发暂停                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、核心拦截机制

### 3.1 拦截位置

ask_user 的拦截发生在 `ReasoningEngine` 的 ReAct 循环 **ACT 阶段**：

```
ReAct 循环
    │
    ├── THINK: LLM 推理决策
    │
    └── ACT: 执行工具调用
              │
              ├── 检测 decision.tool_calls
              │
              ├── 🔍 拦截点：分离 ask_user_calls 和 other_calls
              │
              ├── 执行 other_calls（如果有）
              │
              └── 🔒 ask_user 特殊处理（不执行 Handler）
```

### 3.2 拦截代码分析

位置：`src/openakita/core/reasoning_engine.py`

```python
# ACT 阶段 - 工具调用拦截
elif decision.type == DecisionType.TOOL_CALLS:
    tool_names = [tc.get("name", "?") for tc in decision.tool_calls]
    logger.info(f"[ReAct] Iter {iteration} — ACT: {tool_names}")

    # ========== ask_user 拦截 ==========
    ask_user_calls = [tc for tc in decision.tool_calls if tc.get("name") == "ask_user"]
    other_calls = [tc for tc in decision.tool_calls if tc.get("name") != "ask_user"]

    if ask_user_calls:
        logger.info(f"[ReAct] Iter {iteration} — ask_user intercepted")

        # 1. 添加 assistant 消息（保留 tool_use 内容用于上下文连贯）
        assistant_msg = {
            "role": "assistant",
            "content": decision.assistant_content,
        }
        if decision.thinking_content:
            assistant_msg["reasoning_content"] = decision.thinking_content
        working_messages.append(assistant_msg)

        # 2. 先执行非 ask_user 工具（如果有）
        other_tool_results = []
        if other_calls:
            other_results, other_executed, other_receipts = (
                await self._tool_executor.execute_batch(other_calls, ...)
            )
            other_tool_results = other_results if other_results else []

        # 3. 提取 ask_user 问题
        question = ask_user_calls[0].get("input", {}).get("question", "")
        ask_tool_id = ask_user_calls[0].get("id", "ask_user_0")

        # 4. 合并文本
        text_part = strip_thinking_tags(decision.text_content or "").strip()
        final_text = f"{text_part}\n\n{question}" if text_part and question else (question or text_part)

        # 5. 状态切换
        state.transition(TaskStatus.WAITING_USER)

        # 6. 等待用户回复（IM 模式）或返回问题（CLI 模式）
        user_reply = await self._wait_for_user_reply(final_text, state, ...)
        # ... 处理回复 ...
```

### 3.3 为什么不执行 Handler

位置：`src/openakita/tools/handlers/system.py`

```python
class SystemHandler:
    TOOLS = ["ask_user", "enable_thinking", ...]

    async def handle(self, tool_name: str, params: dict[str, Any]) -> str:
        if tool_name == "ask_user":
            # ask_user 正常由 ReasoningEngine 在 ACT 阶段拦截，不会到达此处
            # 此为防御性兜底：若意外到达，返回问题文本而不是报错
            question = params.get("question", "")
            logger.warning(f"[SystemHandler] ask_user reached handler (should be intercepted): {question[:80]}")
            return question or "（等待用户回复）"
```

**原因**：
1. ask_user 需要**暂停执行流**，而普通工具执行后会立即返回结果
2. 需要支持 **IM 模式的异步等待**，Handler 不适合处理
3. 需要构建特定的 **tool_result 消息**，保持上下文一致

---

## 四、双模式处理

### 4.1 模式判断

```python
# 判断是否为 IM 模式
gateway = session.get_metadata("_gateway") if hasattr(session, "get_metadata") else None
session_key = session.get_metadata("_session_key") if gateway else None

if not gateway or not session_key:
    # CLI 模式或无 gateway
    return None  # 不等待，直接返回问题
```

### 4.2 CLI 模式

**特点**：
- 直接返回问题文本给调用方
- 由调用方（如 CLI 界面）负责显示问题并获取用户输入
- 用户下次输入时作为新请求处理

**处理流程**：

```
CLI 模式
    │
    ├── ask_user 被拦截
    │
    ├── _wait_for_user_reply() 返回 None (无 gateway)
    │
    ├── 直接返回 final_text (问题文本)
    │
    ├── 状态: WAITING_USER
    │
    └── 用户下次输入 → 新 /api/chat 请求
```

**代码路径**：

```python
# CLI 模式分支
else:
    # CLI 模式或无 gateway → 直接返回问题文本
    tracer.end_trace(metadata={
        "result": "waiting_user",
        "iterations": iteration + 1,
        "tools_used": list(set(executed_tool_names)),
    })
    react_trace.append(_iter_trace)
    self._save_react_trace(react_trace, conversation_id, session_type, "waiting_user", _trace_started_at)
    logger.info(f"[ReAct] === WAITING_USER (CLI) after {iteration+1} iterations ===")
    return final_text
```

### 4.3 IM 模式

**特点**：
- 通过 Gateway 向用户发送问题
- 轮询 `interrupt_queue` 等待回复
- 支持超时 + 追问提醒
- 超时后自动决策

**处理流程**：

```
IM 模式
    │
    ├── ask_user 被拦截
    │
    ├── 通过 Gateway 发送问题
    │
    ├── 轮询 interrupt_queue
    │   │
    │   ├── 用户回复 → 注入 tool_result → 继续 ReAct
    │   │
    │   └── 超时
    │       │
    │       ├── 发送追问提醒 (最多 max_reminders 次)
    │       │
    │       └── 追问次数用尽
    │           │
    │           └── 注入系统提示 → 让 LLM 自行决策
    │
    └── 状态切换: WAITING_USER → REASONING
```

### 4.4 IM 模式等待实现

位置：`src/openakita/core/reasoning_engine.py`

```python
async def _wait_for_user_reply(
    self,
    question: str,
    state: TaskState,
    *,
    timeout_seconds: int = 60,      # 每轮超时 60 秒
    max_reminders: int = 1,         # 最多追问 1 次
    poll_interval: float = 2.0,     # 轮询间隔 2 秒
) -> str | None:
    """
    等待用户回复 ask_user 的问题（仅 IM 模式生效）。

    Returns:
        - 用户回复文本
        - None（超时/无 gateway/被取消）
    """
    # 获取 gateway 和 session
    session = self._state.current_session
    gateway = session.get_metadata("_gateway") if hasattr(session, "get_metadata") else None
    session_key = session.get_metadata("_session_key") if gateway else None

    if not gateway or not session_key:
        return None  # CLI 模式

    # 发送问题到用户
    await gateway.send_to_session(session, question, role="assistant")

    reminders_sent = 0

    while reminders_sent <= max_reminders:
        elapsed = 0.0

        # 轮询等待
        while elapsed < timeout_seconds:
            # 检查任务取消
            if state.cancelled:
                return None

            # 检查中断队列（用户回复）
            reply_msg = await gateway.check_interrupt(session_key)
            if reply_msg:
                reply_text = reply_msg.plain_text.strip()
                if reply_text:
                    session.add_message(role="user", content=reply_text, source="ask_user_reply")
                    return reply_text

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        # 本轮超时
        if reminders_sent < max_reminders:
            reminders_sent += 1
            reminder = "⏰ 我在等你回复上面的问题哦，看到的话回复一下~"
            await gateway.send_to_session(session, reminder, role="assistant")
        else:
            # 追问次数用尽
            return None

    return None
```

### 4.5 用户回复处理

**用户在超时内回复**：

```python
if user_reply:
    # 用户在超时内回复了 → 注入回复，继续 ReAct 循环
    logger.info(f"[ReAct] Iter {iteration} — ask_user: user replied")
    state.react_trace.append(_iter_trace)

    working_messages.append({
        "role": "user",
        "content": _build_ask_user_tool_results(f"用户回复：{user_reply}"),
    })

    state.transition(TaskStatus.REASONING)
    return None  # 继续 ReAct 循环
```

**IM 模式用户超时**：

```python
elif user_reply is None and self._state.current_session and has_gateway:
    # IM 模式，用户超时未回复 → 注入系统提示让 LLM 自行决策
    logger.info(f"[ReAct] Iter {iteration} — ask_user: user timeout, injecting auto-decide prompt")

    working_messages.append({
        "role": "user",
        "content": _build_ask_user_tool_results(
            "[系统] 用户 2 分钟内未回复你的提问。"
            "请自行决策：如果能合理推断用户意图，继续执行任务；"
            "否则终止当前任务并告知用户你需要什么信息。"
        ),
    })

    state.transition(TaskStatus.REASONING)
    return None  # 继续 ReAct 循环，让 LLM 自行决策
```

---

## 五、tool_result 消息构建

### 5.1 消息结构

ask_user 的 tool_result 必须与其他工具的 tool_result 一起在同一条 user 消息中：

```python
def _build_ask_user_tool_results(content_str: str) -> list[dict]:
    """构建包含所有 tool_result 的 user 消息 content"""
    results = list(other_tool_results)  # 其他工具的 tool_result
    results.append({
        "type": "tool_result",
        "tool_use_id": ask_tool_id,      # 对应 ask_user 的 tool_use id
        "content": content_str,          # "用户回复：xxx" 或 系统提示
    })
    return results
```

### 5.2 完整消息流

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  ask_user 调用后的消息流                                                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  消息序列：                                                                       │
│                                                                                 │
│  1. [assistant]                                                                 │
│     content: [{"type": "text", "text": "..."},                                  │
│              {"type": "tool_use", "id": "ask_user_0", "name": "ask_user", ...}] │
│                                                                                 │
│  2. [user] (用户回复后)                                                          │
│     content: [                                                                   │
│       {"type": "tool_result", "tool_use_id": "ask_user_0",                      │
│        "content": "用户回复：确认执行"},                                          │
│       ... (其他 tool_result)                                                     │
│     ]                                                                           │
│                                                                                 │
│  ─────────────────────────────────────────────────────────────────────────────  │
│                                                                                 │
│  如果用户超时（IM 模式）：                                                         │
│                                                                                 │
│  2. [user]                                                                      │
│     content: [                                                                   │
│       {"type": "tool_result", "tool_use_id": "ask_user_0",                      │
│        "content": "[系统] 用户 2 分钟内未回复你的提问..."}                          │
│     ]                                                                           │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 六、流式处理 (SSE)

### 6.1 流式事件

位置：`src/openakita/core/reasoning_engine.py` (execute_streaming)

```python
# ask_user 事件构建
ask_input = ask_user_calls[0].get("input", {})
ask_q = ask_input.get("question", "")
ask_options = ask_input.get("options")
ask_allow_multiple = ask_input.get("allow_multiple", False)
ask_questions = ask_input.get("questions")

text_part = decision.text_content or ""
question_text = f"{text_part}\n\n{ask_q}".strip() if text_part else ask_q

event: dict = {
    "type": "ask_user",
    "question": question_text,
    "conversation_id": conversation_id,
}

# 选项
if ask_options and isinstance(ask_options, list):
    event["options"] = [
        {"id": str(o.get("id", "")), "label": str(o.get("label", ""))}
        for o in ask_options
        if isinstance(o, dict) and o.get("id") and o.get("label")
    ]

# 多选
if ask_allow_multiple:
    event["allow_multiple"] = True

# 多问题
if ask_questions and isinstance(ask_questions, list):
    parsed_questions = []
    for q in ask_questions:
        if not isinstance(q, dict) or not q.get("id") or not q.get("prompt"):
            continue
        pq: dict = {"id": str(q["id"]), "prompt": str(q["prompt"])}
        # ... 处理 options 和 allow_multiple ...
        parsed_questions.append(pq)
    if parsed_questions:
        event["questions"] = parsed_questions

# 发送事件
yield event

# 记录退出原因
self._last_exit_reason = "ask_user"
yield {"type": "done"}
return
```

### 6.2 SSE 事件类型

| 事件类型 | 字段 | 说明 |
|----------|------|------|
| `ask_user` | question, options, allow_multiple, questions | 向用户提问 |
| `done` | - | 流结束 |

---

## 七、前端处理

### 7.1 Web UI (React)

位置：`webapps/seeagent-webui/src/hooks/useChat.ts`

```typescript
case 'ask_user': {
  // Handle ask_user event - store the question for UI to display
  const question = eventRecord.question as string || ''
  const options = eventRecord.options as Array<{ id: string; label: string }> | undefined
  const questions = eventRecord.questions as Array<{
    id: string;
    prompt: string;
    options?: Array<{ id: string; label: string }>;
    allow_multiple?: boolean;
  }> | undefined

  if (question || questions) {
    setAskUserQuestion({ question, options, questions })
  }
  break
}
```

### 7.2 Desktop App (Tauri)

位置：`apps/setup-center/src/views/ChatView.tsx`

```typescript
case "ask_user": {
  const askQuestions = event.questions;
  // 如果没有 questions 数组但有 allow_multiple，构造一个统一的 questions
  if (!askQuestions && event.allow_multiple && event.options?.length) {
    currentAsk = {
      question: event.question,
      options: event.options,
      questions: [{
        id: "__single__",
        prompt: event.question,
        options: event.options,
        allow_multiple: true,
      }],
    };
  } else {
    currentAsk = {
      question: event.question,
      options: event.options,
      questions: askQuestions,
    };
  }
  break;
}
```

### 7.3 用户回复流程

```
用户点击选项或输入文本
        │
        ▼
前端发送新 /api/chat 请求
{
  "conversation_id": "xxx",
  "message": "用户选择的选项 ID 或输入的文本",
  "answer_to": "ask_user"  // 标记这是对 ask_user 的回复
}
        │
        ▼
后端接收请求
        │
        ▼
继续 ReAct 循环（使用之前的 working_messages）
```

---

## 八、状态流转

### 8.1 TaskStatus 状态

```python
class TaskStatus(Enum):
    IDLE = "idle"                  # 空闲
    REASONING = "reasoning"        # 推理中
    ACTING = "acting"              # 执行工具
    WAITING_USER = "waiting_user"  # 等待用户回复（ask_user 触发）
    COMPLETED = "completed"        # 完成
    CANCELLED = "cancelled"        # 取消
```

### 8.2 状态流转图

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  ask_user 状态流转                                                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  REASONING ──────────────────────────────────────────────────────────────────▶  │
│      │                                                                          │
│      │ (LLM 决策调用 ask_user)                                                   │
│      ▼                                                                          │
│  ACTING ─────────────────────────────────────────────────────────────────────▶  │
│      │                                                                          │
│      │ (拦截 ask_user，设置状态)                                                  │
│      ▼                                                                          │
│  WAITING_USER ◀───────────────────────────────────────────────────────────────  │
│      │                                                                          │
│      │ (用户回复 或 IM 超时)                                                      │
│      ▼                                                                          │
│  REASONING ──────────────────────────────────────────────────────────────────▶  │
│      │                                                                          │
│      │ (继续 ReAct 循环)                                                         │
│      ▼                                                                          │
│  ...                                                                            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 8.3 退出原因记录

```python
# 记录退出原因
self._last_exit_reason = "ask_user"

# 保存 ReAct 轨迹
self._save_react_trace(react_trace, conversation_id, session_type, "ask_user", _trace_started_at)
```

---

## 九、关键代码路径汇总

| 文件 | 功能 |
|------|------|
| `src/openakita/tools/definitions/system.py` | ask_user 工具定义 Schema |
| `src/openakita/tools/handlers/system.py` | ask_user Handler（防御性兜底） |
| `src/openakita/core/reasoning_engine.py:640-725` | 非流式模式的 ask_user 拦截处理 |
| `src/openakita/core/reasoning_engine.py:1346-1478` | 流式模式的 ask_user 拦截处理 |
| `src/openakita/core/reasoning_engine.py:2181-2285` | execute_streaming 中的 ask_user 处理 |
| `src/openakita/core/reasoning_engine.py:133-240` | `_wait_for_user_reply` IM 模式等待实现 |
| `src/openakita/core/agent_state.py:31` | `WAITING_USER` 状态定义 |
| `src/openakita/api/routes/chat.py:165-200` | API 层 ask_user 问题文本捕获 |
| `webapps/seeagent-webui/src/hooks/useChat.ts:419-433` | Web UI ask_user 事件处理 |
| `apps/setup-center/src/views/ChatView.tsx:2029-2050` | Desktop App ask_user 事件处理 |

---

## 十、总结

### 10.1 核心设计要点

1. **拦截而非执行**：ask_user 在 ReasoningEngine 层被拦截，不会真正执行 Handler
2. **双模式支持**：CLI 模式返回等待，IM 模式异步等待回复
3. **上下文保持**：通过 working_messages 和 tool_result 保持对话连贯
4. **超时机制**：IM 模式支持超时提醒和自动决策
5. **消息完整性**：ask_user 的 tool_result 与其他工具的 tool_result 合并在同一条 user 消息中

### 10.2 潜在改进点

| 改进点 | 当前状态 | 建议 |
|--------|----------|------|
| 超时配置 | 硬编码 60 秒 | 可配置化 |
| 追问次数 | 硬编码 1 次 | 可配置化 |
| 超时决策 | 固定提示词 | 可自定义 |
| 多轮追问 | 不支持 | 可扩展 |
| 问卷验证 | 无 | 可添加 schema 验证 |