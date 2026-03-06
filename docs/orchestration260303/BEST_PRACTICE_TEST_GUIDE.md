# 数据处理流水线最佳实践 - 测试指南

> 创建日期: 2026-03-05
> 场景: data-pipeline

---

## 1. 环境准备

### 1.1 启动 OpenAkita 服务

```bash
cd /Users/zd/agents/openakita-main

# 激活虚拟环境
source venv/bin/activate

# 启动服务
python -m openakita.main
```

服务启动后访问：
- API 文档: http://127.0.0.1:18900/docs
- ReDoc: http://127.0.0.1:18900/redoc

### 1.2 验证场景已加载

```bash
# 查看所有场景
curl http://127.0.0.1:18900/api/scenarios | python -m json.tool

# 查看特定场景
curl http://127.0.0.1:18900/api/scenarios/data-pipeline | python -m json.tool
```

---

## 2. 方式一：通过 API 测试

### Step 1: 创建任务

```bash
# 方式 A: 通过场景 ID 创建
curl -X POST http://127.0.0.1:18900/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_id": "data-pipeline",
    "session_id": "test-session-001"
  }'

# 方式 B: 通过对话触发
curl -X POST http://127.0.0.1:18900/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "message": "帮我处理数据，生成一份用户配置",
    "session_id": "test-session-002"
  }'
```

返回示例：
```json
{
  "task_id": "task-xxx",
  "scenario_id": "data-pipeline",
  "status": "running",
  "current_step_id": "generate",
  "total_steps": 4,
  "completed_steps": 0,
  "progress_percent": 0.0
}
```

### Step 2: 查看任务详情

```bash
TASK_ID="task-xxx"  # 替换为实际的 task_id

curl http://127.0.0.1:18900/api/tasks/$TASK_ID | python -m json.tool
```

### Step 3: 查看任务上下文

```bash
curl http://127.0.0.1:18900/api/tasks/$TASK_ID/context | python -m json.tool
```

### Step 4: 确认步骤 (当步骤需要用户确认时)

```bash
curl -X POST http://127.0.0.1:18900/api/tasks/$TASK_ID/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "step_id": "generate",
    "edited_output": {
      "title": "用户配置",
      "bullets": ["name", "email", "role"]
    }
  }'
```

### Step 5: 切换步骤

```bash
curl -X POST http://127.0.0.1:18900/api/tasks/$TASK_ID/switch \
  -H "Content-Type: application/json" \
  -d '{
    "step_id": "validate"
  }'
```

### Step 6: 取消任务

```bash
curl -X POST http://127.0.0.1:18900/api/tasks/$TASK_ID/cancel
```

---

## 3. 方式二：通过对话测试 (Web UI)

### 3.1 启动 Web 界面

如果有前端项目，启动前端开发服务器。

### 3.2 触发对话

在对话框输入以下任一触发词：

```
数据处理流水线
```

或

```
data pipeline
```

或

```
帮我处理数据，生成一份配置并校验
```

### 3.3 完整对话示例

```
用户: 数据处理流水线

系统: [检测到场景匹配]
      场景: 数据处理流水线
      描述: 生成、校验、编辑、追踪数据的完整流程

      步骤列表:
      1. 生成数据 (需要确认)
      2. 数据校验
      3. 生成数据指纹
      4. 变更追踪 (需要确认)

      是否开始?

用户: 是的，开始吧

SubAgent [生成数据]:
      你好！我是数据生成专家。请告诉我你需要生成什么类型的数据？

      可选类型:
      - 用户档案
      - 项目配置
      - API 配置

用户: 用户档案，包含姓名、邮箱和角色

SubAgent [生成数据]:
      好的，正在生成用户档案数据...

      [调用 demo-echo-json]

      生成结果:
      ```json
      {
        "ok": true,
        "trace_id": "user-profile-001",
        "payload": {
          "name": "张三",
          "email": "zhangsan@example.com",
          "role": "developer"
        }
      }
      ```

      请确认或编辑此数据。

用户: 确认

系统: [Step 1 完成] 数据已生成

      [Step 2 自动执行] 数据校验中...
      [Step 3 自动执行] 生成数据指纹...

SubAgent [变更追踪]:
      原始数据已记录。现在请编辑数据（如需要），我将追踪变更。

      原始数据指纹: 2cf24dba...

      是否需要编辑数据？

用户: 把角色改成 admin

SubAgent [变更追踪]:
      [调用 demo-json-diff]

      变更报告:
      - 变更路径: payload.role
      - 修改前: "developer"
      - 修改后: "admin"
      - 统计: modified=1, added=0, removed=0

      是否确认此变更？

用户: 确认

系统: ✅ 任务完成！
      总步骤: 4
      完成步骤: 4
      最终输出: 变更报告已生成
```

---

## 4. 验证 Demo Skills

单独测试每个 demo skill：

### 4.1 demo-echo-json

```bash
# 命令行测试
python skills/demo-echo-json/scripts/echo.py --json '{"test":"hello"}'

# 预期输出
# {"ok": true, "received_at": "...", "payload": {"test": "hello"}, "trace_id": null}
```

### 4.2 demo-context-hash

```bash
python skills/demo-context-hash/scripts/hash.py --json '{"text":"hello","algorithm":"sha256"}'

# 预期输出
# {"ok": true, "algorithm": "sha256", "digest": "2cf24dba...", "length": 5}
```

### 4.3 demo-json-diff

```bash
python skills/demo-json-diff/scripts/diff.py --json '{"before":{"a":1},"after":{"a":2}}'

# 预期输出
# {"ok": true, "changed_paths": ["a"], "counts": {"added": 0, "removed": 0, "modified": 1}, "summary": "modified=1, added=0, removed=0"}
```

### 4.4 demo-schema-check

```bash
python skills/demo-schema-check/scripts/check.py --json '{"schema_id":"demo_draft_v1","data":{"title":"test","bullets":["a","b"]}}'

# 预期输出
# {"ok": true, "errors": []}
```

---

## 5. 故障排查

### 5.1 场景未加载

检查场景文件是否存在：
```bash
ls -la scenarios/data-pipeline.yaml
```

检查 YAML 格式：
```bash
python -c "import yaml; yaml.safe_load(open('scenarios/data-pipeline.yaml'))"
```

### 5.2 API 返回 503

检查 TaskOrchestrator 是否初始化：
- 查看 server.py 是否正确注册了 orchestrator
- 检查日志中的错误信息

### 5.3 Skill 调用失败

检查 skill 脚本：
```bash
ls -la skills/demo-*/scripts/*.py
```

---

## 6. 文件清单

### 已创建的文件

```
scenarios/
└── data-pipeline.yaml      # 最佳实践场景配置

skills/
├── demo-echo-json/         # 回显 JSON (已存在)
├── demo-context-hash/      # 上下文摘要 (已存在)
├── demo-json-diff/         # JSON 对比 (已存在)
└── demo-schema-check/      # Schema 校验 (已存在)
```

### 相关代码文件

```
src/openakita/orchestration/
├── models.py              # 数据结构
├── scenario_registry.py   # 场景注册表
├── task_session.py        # 任务会话
├── task_orchestrator.py   # 任务编排器
└── subagent_manager.py    # SubAgent 管理器

src/openakita/api/routes/
├── tasks.py               # 任务 API
└── scenarios.py           # 场景 API
```

---

## 7. 下一步

1. **添加更多场景**: 创建其他最佳实践场景（如代码审查、文档生成）
2. **前端集成**: 在 Web UI 中添加最佳实践入口
3. **扩展 Skills**: 创建更多实用技能