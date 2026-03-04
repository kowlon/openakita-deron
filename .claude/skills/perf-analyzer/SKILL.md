# Performance Analyzer

分析 OpenAkita 聊天过程各阶段耗时，生成详细统计报告。

## 触发条件

当用户请求分析性能、统计耗时、查看聊天流程性能时触发。例如：
- "分析一下性能"
- "帮我统计这个请求的耗时"
- "性能分析报告"
- "查看各阶段耗时"

## 使用方法

### 1. 触发测试请求

```bash
curl -s -X POST http://127.0.0.1:18900/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "<你的测试消息>", "conversation_id": "perf_test_xxx"}'
```

### 2. 等待请求完成后分析日志

```bash
grep -E "\[PERF\]|\[ReAct\].*Iter|\[LLM\].*action=|\[Tool\]|perf_test_xxx" logs/openakita.log | tail -100
```

### 3. 生成性能报告

根据日志数据，生成包含以下内容的报告：
- 时间线分析
- 耗时分布统计
- Token 消耗统计
- 工具调用详情
- 性能瓶颈识别

## 性能日志说明

### 日志格式

| 日志类型 | 格式 | 说明 |
|----------|------|------|
| 工具执行 | `[PERF] ⏱️ Tool execution: Xms (N tools)` | 工具执行耗时 |
| 状态更新 | `[PERF] ⏱️ State update: Xms` | 工具后状态更新耗时 |
| 循环检测 | `[PERF] ⏱️ Loop detection: Xms` | 循环检测耗时 |
| 后处理总计 | `[PERF] ⏱️ Post-tool total: Xms` | 工具后处理总耗时 |
| LLM调用 | `[PERF] 🤖 LLM call: total=Xms, tokens=N→M` | LLM调用统计 |
| 任务总结 | `[PERF] 📊 Task Summary` | 任务完成总结 |

### 典型日志输出

```
[PERF] ⏱️ Tool execution: 1292ms (2 tools)
[PERF] ⏱️ State update: 0ms
[PERF] ⏱️ Loop detection: 0ms
[PERF] ⏱️ Post-tool total: 0ms
[PERF] 🤖 LLM call: total=12737ms, tokens=16934→302

============================================================
[PERF] 📊 Task Summary
============================================================
  Conversation ID: perf_test_xxx
  Total Iterations: 7
  LLM Calls: 7
  Tokens: 146098 in → 3397 out (149495 total)
  Tools Used: {'web_search': 1, 'write_file': 2, 'run_shell': 1}
============================================================
```

## 报告模板

### 任务概要

```
┌─────────────────────────────────────────────────────────────────────┐
│ 请求: <用户请求内容>                                                │
│ 会话ID: <conversation_id>                                           │
│ 总耗时: X.X 秒                                                      │
│ 迭代次数: N 次                                                      │
│ LLM调用: N 次                                                       │
│ Token消耗: XXX 输入 → XXX 输出 (XXX 总计)                           │
└─────────────────────────────────────────────────────────────────────┘
```

### 时间线分析

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 时间戳              │ 阶段           │ 操作                    │ 耗时        │
├─────────────────────────────────────────────────────────────────────────────────┤
│ HH:MM:SS.mmm        │ Iter N LLM     │ <描述>                  │ X,XXXms     │
│ HH:MM:SS.mmm        │ Iter N Tool    │ <工具名>                │ Xms         │
│ HH:MM:SS.mmm        │ Iter N Post    │ 状态更新+循环检测       │ Xms         │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 耗时分布统计

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 阶段                    │ 耗时        │ 占比     │ 说明                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│ LLM 调用 (N次)          │ XX.Xs       │ XX.X%    │ 主要耗时                   │
│ 工具执行 (N次)          │ X.Xs        │ X.X%     │                            │
│ 工具后处理 (N次)        │ Xms         │ <X%      │ 状态更新+循环检测          │
│ 其他开销                │ X.Xs        │ XX.X%    │ 网络延迟/处理间隙          │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 性能优化建议

### 常见瓶颈

1. **LLM 调用占比过高 (60%+)** - 正常现象，无法避免
2. **工具后处理耗时 > 10ms** - 需要检查循环检测逻辑
3. **Prompt 编译耗时 > 2s** - 考虑缓存优化
4. **Token 消耗递增过快** - 考虑上下文裁剪策略

### 优化方向

1. 缓存 Prompt 编译结果
2. 减少不必要的 LLM 轮次
3. 优化工具执行并行度
4. 增加中间状态 SSE 事件改善用户体验

## 代码位置

| 模块 | 文件路径 |
|------|----------|
| 性能追踪 | `src/openakita/infra/performance.py` |
| 推理引擎 | `src/openakita/core/reasoning_engine.py` |
| LLM客户端 | `src/openakita/llm/client.py` |
| 工具执行 | `src/openakita/tools/executor.py` |

## 示例用法

```bash
# 1. 发送测试请求
curl -s -X POST http://127.0.0.1:18900/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "帮我搜索马斯克最新新闻，写入到pdf文件中", "conversation_id": "perf_test_musk"}'

# 2. 等待完成后查看日志
grep -E "\[PERF\]|\[ReAct\].*Iter|perf_test_musk" logs/openakita.log | tail -50

# 3. 生成报告（由 Claude 根据日志数据生成）
```

## 分析流程

1. **发送测试请求** - 使用唯一的 conversation_id
2. **等待完成** - 监控日志直到看到 `[PERF] 📊 Task Summary`
3. **收集日志** - 提取所有 `[PERF]` 相关日志
4. **生成报告** - 按模板格式化输出
5. **给出建议** - 根据瓶颈给出优化建议