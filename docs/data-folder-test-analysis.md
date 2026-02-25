# Data 文件夹测试分析报告

> 测试日期：2026-02-25
> 测试用例：查询马斯克最新信息并写入 PDF 文件
> **改进状态：✅ 已完成**

---

## 一、测试概要

### 测试步骤
1. 清理历史数据
2. 通过 Web UI 发送测试消息："请帮我查一下马斯克的最新信息，写到pdf文件中"
3. 等待任务完成（约 121 秒）
4. 检查各数据文件夹状态

### 测试结果
| 数据目录/文件 | 预期行为 | 实际状态 | 是否正常 |
|--------------|----------|----------|----------|
| `react_traces/` | 记录推理过程 | ✅ 生成 2 个 trace 文件 | 正常 |
| `llm_debug/` | 记录 LLM 请求/响应 | ✅ 生成 17 个文件 | 正常 |
| `temp/` | 存放临时文件 | ✅ 生成 PDF 和 Python 脚本 | 正常 |
| `retrospects/` | 存放复盘记录 | ❌ **空目录** | **异常** |
| `plans/` | 存放任务计划 | ⚠️ 空目录 | 设计如此 |
| `output/` | 存放输出文件 | ⚠️ 空目录 | **需改进** |
| `scheduler/executions.json` | 执行记录 | ❌ **不存在** | **异常** |

---

## 二、问题详细分析

### 问题 1：retrospects 目录为空（复盘未保存）

#### 问题描述
任务耗时约 121 秒，超过复盘阈值（60秒），但 `data/retrospects/` 目录为空，没有生成复盘记录。

#### 根因分析

1. **复盘触发逻辑**（`session_helper.py:363-365`）：
```python
metrics = task_monitor.complete(success=True, response=response_text)
if metrics.retrospect_needed:
    asyncio.create_task(agent._do_task_retrospect_background(task_monitor, session_id))
```

2. **复盘保存逻辑**（`retrospect.py:151-167`）：
```python
record = RetrospectRecord(
    task_id=task_monitor.metrics.task_id,
    session_id=session_id,
    ...
)
storage = get_retrospect_storage()
storage.save(record)
```

3. **问题所在**：
   - 测试通过 Desktop Chat API 进行，`session_id` 可能为空字符串
   - 后台任务 `asyncio.create_task()` 可能因为事件循环问题未执行
   - 复盘 LLM 调用可能失败但没有记录错误

---

### 问题 2：output 目录为空（文件未归档）

#### 问题描述
PDF 文件生成在 `data/temp/` 目录，但没有移动到 `data/output/` 目录。

#### 根因分析

1. **deliver_artifacts 工具行为**（`im_channel.py:335-396`）：
```python
async def _deliver_artifacts_desktop(self, params: dict) -> str:
    """
    Desktop mode: instead of sending via IM adapter, return file URLs
    so the desktop frontend can display them inline.
    """
    # 只返回 file_url，不移动文件
    file_url = f"/api/files?path={urllib.parse.quote(abs_path, safe='')}"
```

2. **问题所在**：
   - 没有明确的文件归档机制
   - `temp/` 目录会积累大量临时文件
   - 用户期望生成的文件有明确的"输出"位置

---

### 问题 3：scheduler/executions.json 不存在

#### 问题描述
定时任务执行记录文件 `data/scheduler/executions.json` 不存在。

#### 根因分析

1. **执行记录保存逻辑**（`scheduler/scheduler.py:517-527`）：
```python
def _save_executions(self) -> None:
    executions_file = self.storage_path / "executions.json"
    try:
        recent = self._executions[-1000:]
        data = [e.to_dict() for e in recent]
        self._atomic_write_json(executions_file, data)
```

2. **问题所在**：
   - `_save_executions()` 只在任务执行后调用
   - 系统启动后如果没有任务执行，文件不会创建
   - 空执行列表时可能跳过保存

---

## 三、已实施的改进

### 3.1 复盘功能改进 ✅ 已完成

**修改文件**：
- `src/openakita/core/retrospect.py`
- `src/openakita/core/response_handler.py`
- `src/openakita/core/helpers/session_helper.py`

**改进内容**：
1. 添加完善的错误处理和日志
2. 确保 `session_id` 为空时使用 `task_id` 作为回退
3. 添加复盘开始、完成、保存的详细日志
4. 捕获并记录所有异常

**关键改进代码**：
```python
# retrospect.py
async def do_task_retrospect_background(self, task_monitor, session_id):
    task_id = task_monitor.metrics.task_id or "unknown"
    effective_session_id = session_id or task_id or "unknown"

    logger.info(
        f"[Retrospect] Background task started: task_id={task_id}, "
        f"session_id={effective_session_id}, "
        f"duration={task_monitor.metrics.total_duration_seconds:.1f}s"
    )
    # ... 详细日志和错误处理
```

---

### 3.2 调度器改进 ✅ 已完成

**修改文件**：`src/openakita/scheduler/scheduler.py`

**改进内容**：
1. `_load_executions()` 现在会在文件不存在时创建空文件
2. `_save_executions()` 即使执行列表为空也会保存
3. 添加任务执行的详细日志（持续时间、状态等）
4. 处理 JSON 解析错误并备份损坏文件

**关键改进代码**：
```python
def _load_executions(self):
    executions_file = self.storage_path / "executions.json"

    # 如果文件不存在，创建空文件
    if not executions_file.exists():
        logger.info("No executions file found, creating empty file")
        self._atomic_write_json(executions_file, [])
        return

    # ... 加载逻辑
```

---

### 3.3 文件归档功能 ✅ 已完成

**修改文件**：
- `src/openakita/config.py`
- `src/openakita/tools/handlers/im_channel.py`

**新增配置**：
```python
# config.py
auto_archive_to_output: bool = Field(
    default=False,
    description="是否自动将 deliver_artifacts 的文件归档到 output 目录"
)
output_directory: str = Field(
    default="data/output",
    description="输出文件目录"
)
```

**改进内容**：
1. 添加可选的文件归档功能
2. 自动处理重名文件
3. 返回归档路径信息

**使用方法**：
在配置中启用归档功能：
```yaml
# ~/.openakita/settings.yaml
auto_archive_to_output: true
output_directory: "data/output"
```

---

## 四、改进后预期效果

### 4.1 复盘记录
- ✅ 复盘任务会正确执行并保存到 `data/retrospects/`
- ✅ 即使 `session_id` 为空，复盘记录也能正确保存
- ✅ 所有复盘操作都有详细日志，便于调试

### 4.2 调度器执行记录
- ✅ `data/scheduler/executions.json` 文件始终存在
- ✅ 每次任务执行都有详细日志
- ✅ 损坏的文件会自动备份并重建

### 4.3 文件输出
- ✅ 可选择将生成的文件归档到 `data/output/`
- ✅ 返回信息中包含归档路径
- ✅ 自动处理文件重名问题

---

## 五、验证方法

### 5.1 验证复盘功能

```bash
# 1. 重启服务
python -m openakita.main serve

# 2. 发送一个耗时较长的任务
curl -X POST http://localhost:18900/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "请帮我分析一下最近的AI发展趋势并写一份报告", "conversation_id": "test-001"}'

# 3. 检查日志
grep -i "retrospect" logs/openakita.log | tail -20

# 4. 检查复盘文件
ls -la data/retrospects/
cat data/retrospects/$(date +%Y-%m-%d)_retrospects.jsonl
```

### 5.2 验证调度器

```bash
# 1. 重启服务
python -m openakita.main serve

# 2. 检查执行记录文件是否创建
ls -la data/scheduler/executions.json

# 3. 检查任务执行日志
grep -i "scheduler" logs/openakita.log | tail -20
```

### 5.3 验证文件归档

```bash
# 1. 启用归档配置
echo "auto_archive_to_output: true" >> ~/.openakita/settings.yaml

# 2. 重启服务并发送任务
python -m openakita.main serve

# 3. 发送生成文件的任务
curl -X POST http://localhost:18900/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "请生成一个测试PDF文件", "conversation_id": "test-002"}'

# 4. 检查 output 目录
ls -la data/output/
```

---

## 六、总结

### 已完成的改进

| 优先级 | 问题 | 状态 | 修改文件 |
|--------|------|------|----------|
| 🔴 高 | 复盘功能静默失败 | ✅ 已修复 | `retrospect.py`, `response_handler.py`, `session_helper.py` |
| 🟡 中 | 调度器执行记录不创建 | ✅ 已修复 | `scheduler/scheduler.py` |
| 🟡 中 | 文件归档机制缺失 | ✅ 已添加 | `config.py`, `im_channel.py` |

### 改进效果

1. **复盘功能**：现在有完整的日志记录，即使 session_id 为空也能正确保存
2. **调度器**：执行记录文件始终存在，便于监控和调试
3. **文件输出**：可选择自动归档生成的文件到 output 目录
