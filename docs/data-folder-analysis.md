# Data 文件夹结构分析文档

> 本文档详细分析了 OpenAkita 项目 `data/` 文件夹中各个子文件夹和文件的作用、生成方式及代码实现逻辑。

---

## 目录

1. [概述](#概述)
2. [文件夹结构总览](#文件夹结构总览)
3. [核心数据文件](#核心数据文件)
4. [子文件夹详细分析](#子文件夹详细分析)
   - [memory/ - 记忆系统](#memory---记忆系统)
   - [scheduler/ - 任务调度](#scheduler---任务调度)
   - [react_traces/ - 推理追踪](#react_traces---推理追踪)
   - [retrospects/ - 任务复盘](#retrospects---任务复盘)
   - [selfcheck/ - 系统自检](#selfcheck---系统自检)
   - [llm_debug/ - LLM调试](#llm_debug---llm调试)
   - [orchestration/ - 多Agent编排](#orchestration---多agent编排)
   - [temp/ - 临时文件](#temp---临时文件)
   - [plans/ - 任务计划](#plans---任务计划)
   - [output/ & out/ - 输出文件](#output--out---输出文件)
5. [数据流转关系](#数据流转关系)
6. [配置与数据文件的关系](#配置与数据文件的关系)

---

## 概述

`data/` 文件夹是 OpenAkita 系统的**核心数据存储目录**，负责持久化存储：

- **记忆数据**：用户偏好、会话历史、学习到的模式
- **调度数据**：定时任务配置和执行记录
- **追踪数据**：推理过程追踪、任务复盘结果
- **运行时状态**：Agent 注册信息、心跳数据
- **临时文件**：任务执行过程中生成的中间文件

---

## 文件夹结构总览

```
data/
├── agent.db                    # SQLite 主数据库
├── agent.db-shm                # SQLite 共享内存文件
├── agent.db-wal                # SQLite WAL 日志
├── backend.heartbeat           # 后端心跳文件
├── llm_endpoints.json          # LLM 端点配置
├── proactive_feedback.json     # 主动消息反馈记录
├── memory/                     # 记忆系统数据
│   ├── memories.json           # 记忆备份 (JSON)
│   ├── session_summaries.json  # 会话摘要
│   ├── conversation_history/   # 对话历史
│   ├── daily_summaries/        # 每日摘要
│   └── chromadb/               # 向量数据库
├── scheduler/                  # 调度器数据
│   ├── tasks.json              # 任务定义
│   └── executions.json         # 执行记录
├── react_traces/               # ReAct 推理追踪
│   └── {YYYYMMDD}/             # 按日期存储
├── retrospects/                # 任务复盘记录
├── selfcheck/                  # 自检报告
├── llm_debug/                  # LLM 请求/响应调试
├── orchestration/              # 多 Agent 编排
├── temp/                       # 临时文件
├── plans/                      # 任务计划
├── output/                     # 输出文件
└── out/                        # 备用输出目录
```

---

## 核心数据文件

### 1. agent.db / agent.db-shm / agent.db-wal

**作用**：SQLite 数据库文件，存储系统的核心结构化数据。

**产生方式**：
- 配置文件 `config.py` 定义数据库路径：
  ```python
  database_path: str = Field(default="data/agent.db", description="数据库路径")
  ```
- 系统启动时自动创建
- `-shm` 和 `-wal` 是 SQLite WAL 模式的辅助文件

**实现代码**：`src/openakita/storage/database.py`

### 2. backend.heartbeat

**作用**：记录后端服务的运行状态，用于健康检查。

**内容格式**：
```json
{
  "pid": 93947,
  "timestamp": 1772004017.375694,
  "phase": "running",
  "http_ready": true,
  "version": "1.22.9",
  "git_hash": "unknown"
}
```

**产生方式**：后端服务定期更新此文件，监控系统通过检查此文件判断服务是否存活。

### 3. llm_endpoints.json

**作用**：存储 LLM API 端点配置，支持多端点配置和故障转移。

**内容格式**：
```json
{
  "endpoints": [
    {
      "name": "primary",
      "provider": "openai-compatible",
      "api_type": "openai",
      "base_url": "https://open.bigmodel.cn/api/paas/v4",
      "model": "glm-5",
      "priority": 1,
      "capabilities": ["text", "tools", "thinking"]
    }
  ],
  "settings": {
    "retry_count": 2,
    "fallback_on_error": true
  }
}
```

**产生方式**：
- 首次运行时从 `llm_endpoints.json.example` 复制
- 用户可通过配置向导或手动编辑配置

**实现代码**：`src/openakita/llm/config.py`

### 4. proactive_feedback.json

**作用**：记录主动消息（如问候、晚安）的发送历史，用于避免重复发送和优化发送时机。

**内容格式**：
```json
{
  "records": [
    {
      "msg_type": "morning_greeting",
      "timestamp": "2026-02-20T07:23:31.292325",
      "reaction": null,
      "response_delay_minutes": null
    }
  ]
}
```

---

## 子文件夹详细分析

### memory/ - 记忆系统

**作用**：存储 Agent 的长期记忆、会话历史和向量索引。

#### 目录结构
```
memory/
├── memories.json              # 记忆数据备份
├── memories.json.bak          # 备份文件
├── session_summaries.json     # 会话摘要汇总
├── conversation_history/      # 对话历史记录
│   └── {session_id}.jsonl     # 每个会话一个文件
├── daily_summaries/           # 每日记忆整理结果
│   └── {YYYY-MM-DD}.json      # 按日期存储
└── chromadb/                  # ChromaDB 向量数据库
    └── {collection_id}/       # 集合数据
```

#### 文件详解

**1. memories.json**

存储所有长期记忆条目，每个记忆包含：
```json
[
  {
    "id": "97f81cc8",
    "type": "error",
    "priority": "long_term",
    "content": "任务执行复盘发现的问题...",
    "source": "retrospect",
    "created_at": "2026-02-20T11:11:44.044630",
    "importance_score": 0.7
  }
]
```

**产生方式**：
- 通过 `add_memory` 工具添加新记忆
- 每日凌晨 3 点的定时任务整理并更新
- 同时写入 SQLite 数据库和 JSON 备份

**实现代码**：
- `src/openakita/memory/storage.py` - `MemoryStorage` 类
- `src/openakita/memory/vector_store.py` - 向量存储

**2. session_summaries.json**

存储每个会话的摘要信息：
```json
[
  {
    "session_id": "1771605367178-qzt4xh3",
    "start_time": "2026-02-21T00:36:15.971939",
    "end_time": "2026-02-21T00:40:37.078312",
    "task_description": "用户请求...",
    "outcome": "success",
    "key_actions": ["..."],
    "learnings": ["..."],
    "errors_encountered": ["..."],
    "memories_created": []
  }
]
```

**3. conversation_history/**

存储完整的对话历史，每个会话一个 JSONL 文件：
```
conversation_history/
├── 1771773707655-eal7nld.jsonl
├── cli__cli__user.jsonl
└── ...
```

**4. daily_summaries/**

每日记忆整理的结果，包含当天处理的会话和提取的记忆：
```json
{
  "date": "2026-02-22",
  "result": {
    "sessions_processed": 9,
    "memories_extracted": 2,
    "memories_added": 2,
    "duplicates_removed": 0,
    "memory_md_refreshed": true
  },
  "sessions": [...]
}
```

**5. chromadb/**

ChromaDB 向量数据库文件，用于语义搜索：
- `chroma.sqlite3` - 元数据数据库
- `{uuid}/` - 向量索引数据

---

### scheduler/ - 任务调度

**作用**：存储定时任务的配置和执行记录。

#### 目录结构
```
scheduler/
├── tasks.json          # 任务定义
├── tasks.json.bak      # 备份
├── executions.json     # 执行记录
└── executions.json.bak # 备份
```

#### 文件详解

**1. tasks.json**

存储所有调度任务的定义：
```json
[
  {
    "id": "system_daily_selfcheck",
    "name": "每日系统自检",
    "description": "分析 ERROR 日志、尝试修复工具问题、生成报告",
    "trigger_type": "cron",
    "trigger_config": {"cron": "0 4 * * *"},
    "task_type": "task",
    "action": "system:daily_selfcheck",
    "enabled": true,
    "status": "scheduled",
    "last_run": "2026-02-25T04:00:41.976139",
    "next_run": "2026-02-26T04:00:00",
    "run_count": 7,
    "fail_count": 0
  }
]
```

**产生方式**：
- 系统启动时创建默认系统任务
- 用户通过 `schedule_task` 工具创建自定义任务
- 任务状态变更时自动保存

**实现代码**：`src/openakita/scheduler/scheduler.py`
- `TaskScheduler._save_tasks()` - 保存任务
- `TaskScheduler._load_tasks()` - 加载任务

**2. executions.json**

存储任务执行记录：
```json
[
  {
    "id": "exec_e3fe020fa88d",
    "task_id": "system_proactive_heartbeat",
    "started_at": "2026-02-19T23:58:18.969404",
    "finished_at": "2026-02-19T23:58:18.971377",
    "status": "success",
    "result": "Heartbeat check passed",
    "duration_seconds": 0.001973
  }
]
```

**系统内置任务**：
| 任务ID | 名称 | 触发方式 | 作用 |
|--------|------|----------|------|
| `system_daily_memory` | 每日记忆整理 | Cron (0 3 * * *) | 整理当天对话，提取记忆 |
| `system_daily_selfcheck` | 每日系统自检 | Cron (0 4 * * *) | 分析日志，修复问题，生成报告 |
| `system_proactive_heartbeat` | 活人感心跳 | Interval (30min) | 检查是否需要发送主动消息 |

---

### react_traces/ - 推理追踪

**作用**：记录 Agent 的 ReAct 推理过程，用于调试和分析。

#### 目录结构
```
react_traces/
├── 20260219/
├── 20260220/
│   ├── trace_1771986265232-ke_102819.json
│   └── ...
├── 20260221/
└── ...
```

#### 文件格式

每个追踪文件记录一次完整的推理过程：
```json
{
  "conversation_id": "1771986265232-kehbmib",
  "started_at": "2026-02-25T10:26:14",
  "result": "completed",
  "iterations": [
    {
      "iteration": 1,
      "model": "glm-5",
      "tokens": {"input": 3000, "output": 500},
      "tool_calls": [
        {"name": "web_search", "success": true, "duration_ms": 1200}
      ],
      "response_preview": "让我搜索一下..."
    }
  ],
  "summary": {
    "total_iterations": 7,
    "total_tokens_in": 21000,
    "total_tokens_out": 3500,
    "total_tools": 7
  }
}
```

**产生方式**：
- 每次 Agent 执行任务时自动记录
- 按日期分目录存储
- 自动清理超过 7 天的旧记录

**实现代码**：`src/openakita/core/reasoning_engine.py`
```python
def _save_react_trace(self, conversation_id, react_trace, result, started_at):
    date_str = datetime.now().strftime("%Y%m%d")
    trace_dir = Path("data/react_traces") / date_str
    trace_dir.mkdir(parents=True, exist_ok=True)
    # ... 保存追踪数据
    self._cleanup_old_traces(Path("data/react_traces"), max_age_days=7)
```

---

### retrospects/ - 任务复盘

**作用**：存储任务执行后的复盘分析结果，用于持续改进。

#### 目录结构
```
retrospects/
├── 2026-02-20_retrospects.jsonl
├── 2026-02-21_retrospects.jsonl
└── ...
```

#### 文件格式

JSONL 格式，每行一条复盘记录：
```json
{
  "task_id": "_100957",
  "session_id": "",
  "description": "搜索一下马斯克最新的新闻，然后将信息写入到pdf文件中",
  "duration_seconds": 132.37,
  "iterations": 8,
  "model_switched": false,
  "initial_model": "glm-5",
  "final_model": "glm-5",
  "retrospect_result": "**任务复杂度**：低。仅需\"搜索+写文件\"两步...",
  "timestamp": "2026-02-25T10:12:44.361256"
}
```

**产生方式**：
- 任务执行完成后，如果满足复盘条件（如耗时过长），自动触发复盘
- 使用 LLM 分析任务执行过程
- 将分析结果保存到当日文件

**实现代码**：`src/openakita/core/task_monitor.py`
```python
class RetrospectStorage:
    def save(self, record: RetrospectRecord) -> bool:
        today = datetime.now().strftime("%Y-%m-%d")
        file_path = self.storage_dir / f"{today}_retrospects.jsonl"
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
```

---

### selfcheck/ - 系统自检

**作用**：存储每日系统自检报告。

#### 目录结构
```
selfcheck/
├── 2026-02-20_report.json
├── 2026-02-20_report.md
├── 2026-02-21_report.json
├── 2026-02-21_report.md
└── ...
```

#### 文件格式

**JSON 格式**（机器可读）：
```json
{
  "date": "2026-02-25",
  "errors": {...},
  "test_results": [...],
  "fixed_issues": [...],
  "recommendations": [...]
}
```

**Markdown 格式**（人类可读）：
```markdown
# 每日系统报告 - 2026-02-25

## 摘要
- 总错误数: 0
- 核心组件错误: 0
- 工具错误: 0
- 尝试修复: 0

## 任务复盘统计
- 复盘任务数: 0
- 总耗时: 0秒

## 记忆系统优化建议
...
```

**产生方式**：
- 每日凌晨 4 点的定时任务 `system_daily_selfcheck` 触发
- 分析 ERROR 日志
- 尝试自动修复工具问题
- 生成报告并保存

**实现代码**：`src/openakita/evolution/self_check.py`

---

### llm_debug/ - LLM调试

**作用**：存储 LLM 请求和响应的完整记录，用于调试和问题排查。

#### 目录结构
```
llm_debug/
├── llm_request_20260225_150808_6de11c18.json
├── llm_response_20260225_150815_6de11c18.json
└── ...
```

#### 文件格式

**请求文件**：
```json
{
  "timestamp": "2026-02-25T15:08:08.567098",
  "caller": "messages_create_async",
  "llm_request": {
    "system": "## System\n\n# OpenAkita System\n...",
    "messages": [
      {"role": "user", "content": "1+1等于几？"}
    ],
    "tools": [...],
    "model": "glm-5"
  }
}
```

**响应文件**（通过 `request_id` 关联）：
```json
{
  "timestamp": "2026-02-25T15:08:15.123456",
  "request_id": "6de11c18",
  "response": {
    "content": [{"type": "text", "text": "1+1等于2"}],
    "usage": {"input_tokens": 3000, "output_tokens": 10}
  }
}
```

**产生方式**：
- 每次 LLM 调用时自动记录
- 请求和响应通过 `request_id` 关联

**实现代码**：`src/openakita/llm/brain.py`
```python
def _dump_llm_request(self, system, messages, tools, caller):
    debug_dir = Path("data/llm_debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    request_id = uuid.uuid4().hex[:8]
    debug_file = debug_dir / f"llm_request_{timestamp}_{request_id}.json"
    # ... 保存请求数据
    return request_id

def _dump_llm_response(self, response, caller, request_id):
    debug_dir = Path("data/llm_debug")
    debug_file = debug_dir / f"llm_response_{timestamp}_{request_id}.json"
    # ... 保存响应数据
```

---

### orchestration/ - 多Agent编排

**作用**：存储多 Agent 协同模式下的 Agent 注册信息。

#### 目录结构
```
orchestration/
└── registry.json
```

#### 文件格式

```json
{
  "agents": [
    {
      "agent_id": "worker-336cd364",
      "agent_type": "worker",
      "process_id": 98083,
      "status": "idle",
      "capabilities": ["chat", "execute"],
      "current_task": null,
      "tasks_completed": 0,
      "tasks_failed": 0,
      "last_heartbeat": "2026-02-25T13:37:36.314672"
    }
  ],
  "updated_at": "2026-02-25T13:37:36.314975"
}
```

**产生方式**：
- Worker Agent 启动时向 Master 注册
- 定期更新心跳
- 状态变更时自动保存

**实现代码**：`src/openakita/orchestration/registry.py`
```python
class AgentRegistry:
    def _save(self) -> None:
        data = {
            "agents": [a.to_dict() for a in self._agents.values()],
            "updated_at": datetime.now().isoformat(),
        }
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
```

---

### temp/ - 临时文件

**作用**：存储任务执行过程中生成的临时文件，如 PDF、脚本等。

#### 目录结构
```
temp/
├── 曹思奇搜索结果.pdf
├── create_musk_report.py
├── musk_news_report.pdf
├── test_memory/
│   └── MEMORY.md
└── ...
```

**产生方式**：
- Agent 执行任务时创建
- 如用户要求生成 PDF，脚本会先写入 temp 目录
- 可手动清理或由系统定期清理

---

### plans/ - 任务计划

**作用**：存储复杂任务的执行计划。

#### 目录结构
```
plans/
├── plan_20260220_110536_dc6c09.md
├── plan_20260220_121601_ea05f1.md
└── ...
```

#### 文件格式

Markdown 格式的任务计划：
```markdown
# 任务计划

## 任务描述
帮我查查曾德龙是谁，并帮我写入到pdf文件里

## 执行步骤
1. [ ] 使用 web_search 搜索"曾德龙"
2. [ ] 整理搜索结果
3. [ ] 使用 pdf 技能生成 PDF 文件

## 状态
- 创建时间: 2026-02-20 11:05:36
- 状态: in_progress
```

**产生方式**：
- 使用 `create_plan` 工具创建复杂任务计划
- 每完成一步更新状态

---

### output/ & out/ - 输出文件

**作用**：存储最终输出的文件，如生成的 PDF 报告。

#### 目录结构
```
output/
├── 曾德龙信息汇总.pdf
├── elon_musk_profile.pdf
└── musk_profile.pdf

out/
└── OpenAkita_System_Documentation.pdf
```

**产生方式**：
- 用户明确要求"交付文件"时，使用 `deliver_artifacts` 工具
- 文件会被复制/移动到 output 目录

---

## 数据流转关系

```
用户消息
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent 处理流程                             │
├─────────────────────────────────────────────────────────────┤
│  1. 会话管理 ──────────────────► data/memory/conversation_history/  │
│  2. 记忆检索 ──────────────────► data/memory/chromadb/             │
│  3. LLM 调用 ──────────────────► data/llm_debug/                   │
│  4. 推理执行 ──────────────────► data/react_traces/                │
│  5. 任务复盘 ──────────────────► data/retrospects/                 │
│  6. 文件生成 ──────────────────► data/temp/ 或 data/output/        │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
定时任务
    │
    ├─ 每日 03:00 ───────────────► data/memory/daily_summaries/
    │                               data/memory/memories.json
    │
    ├─ 每日 04:00 ───────────────► data/selfcheck/
    │
    └─ 每 30 分钟 ───────────────► data/proactive_feedback.json
```

---

## 配置与数据文件的关系

| 配置项 | 配置文件位置 | 对应数据文件 |
|--------|-------------|-------------|
| `database_path` | config.py | `data/agent.db` |
| `session_storage_path` | config.py | `data/sessions/` |
| `selfcheck_dir` | config.py | `data/selfcheck/` |
| `tracing_export_dir` | config.py | `data/traces/` |
| `evaluation_output_dir` | config.py | `data/evaluation/` |
| `log_dir` | config.py | `logs/` (非 data 目录) |

---

## 总结

`data/` 文件夹是 OpenAkita 系统的数据核心，主要分为以下几类：

1. **持久化存储**：SQLite 数据库、JSON 配置文件
2. **运行时数据**：心跳、注册信息、执行记录
3. **调试数据**：LLM 请求/响应、推理追踪
4. **分析数据**：任务复盘、自检报告
5. **用户数据**：记忆、对话历史
6. **临时数据**：生成的文件、脚本

所有数据文件都通过原子写入（先写临时文件再 rename）保证数据完整性，并支持从备份恢复。
