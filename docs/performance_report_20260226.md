# OpenAkita 性能追踪报告

**生成时间**: 2026-02-26

---

## 📊 测试结果摘要

### Case 1: 简单问候语 "你好"

| 指标 | 值 |
|------|-----|
| **总耗时** | 19,590ms (~19.6秒) |
| **LLM调用次数** | 2次 |
| **总输入tokens** | 32,586 |
| **总输出tokens** | 327 |
| **输出速度** | 16.7 tok/s |

### Case 2: 搜索科技新闻

| 指标 | 值 |
|------|-----|
| **总耗时** | 55,405ms (~55.4秒) |
| **LLM调用次数** | 3次 |
| **总输入tokens** | 52,391 |
| **总输出tokens** | 529 |
| **输出速度** | 18.5 tok/s |

---

## 🔍 耗时分解 (Case 1: 问候语)

### 1. Prompt 构建阶段

| 阶段 | 耗时 | 占比 |
|------|------|------|
| compile_check | 0.2ms | 0.0% |
| identity | 0.1ms | 0.0% |
| runtime | 0.0ms | 0.0% |
| session_rules | 0.0ms | 0.0% |
| catalogs | 0.4ms | 0.0% |
| memory | 0.0ms | 0.0% |
| user | 0.0ms | 0.0% |
| **小计** | **~1ms** | **0.0%** |

**结论**: Prompt 构建非常快速（<1ms），几乎可以忽略不计。

### 2. LLM 调用阶段

| 调用序号 | 模型 | 耗时 | 输入tokens | 输出tokens | 速度 |
|----------|------|------|-----------|-----------|------|
| #1 | glm-5 | 9,890ms | 16,274 | 97 | 9.8 tok/s |
| #2 | glm-5 | 9,668ms | 16,312 | 230 | 23.8 tok/s |
| **总计** | - | **19,558ms** | **32,586** | **327** | **16.7 tok/s** |

**结论**: LLM 调用占总耗时的 **99.8%**，是主要的性能瓶颈。

### 3. 其他阶段

| 阶段 | 耗时 | 说明 |
|------|------|------|
| 会话准备 | ~30ms | TaskMonitor创建、状态初始化 |
| 响应处理 | ~1ms | 解析响应、记录日志 |

---

## 📈 Token 分析

### 输入 Token 构成

根据 system prompt 分析：

| 部分 | Token 数 | 说明 |
|------|----------|------|
| System Prompt | ~7,798 | 身份、原则、规则 |
| Messages | ~17 | 用户消息 |
| Tools | ~12,843 | 44个工具定义 |
| **总计** | **~20,658** | - |

### 输出 Token 分析

| 调用 | 输出tokens | 内容类型 |
|------|-----------|----------|
| #1 | 97 | 思考+简单回复 |
| #2 | 230 | 最终回答 |

---

## ⚡ 首Token时间 (TTFB)

当前测试显示 TTFB=0ms，这是因为：
1. 使用的是非流式 API 调用
2. 流式调用时才能准确测量 TTFB

**建议**: 对于需要测量 TTFB 的场景，应使用 `chat_stream` 方法。

---

## 🎯 性能优化建议

### 短期优化 (可立即实施)

1. **减少工具定义**
   - 当前 44 个工具消耗 ~12,843 tokens
   - 建议: 只注入必要工具，或使用渐进式披露

2. **精简 System Prompt**
   - 当前 ~7,798 tokens
   - 建议: 压缩重复内容，移除冗余规则

3. **启用 Prompt Caching**
   - Anthropic 支持 prompt caching
   - 可节省 ~90% 的输入 token 成本

### 中期优化 (需要代码改动)

1. **工具按需加载**
   - 根据任务类型动态选择工具
   - 预计可节省 50-70% 的工具 token

2. **System Prompt 分层**
   - 基础层: 始终加载
   - 扩展层: 按需加载
   - 预计可减少 40% 的 system prompt token

3. **流式响应优化**
   - 实现 TTFB 监控
   - 提前向用户展示进度

### 长期优化 (架构调整)

1. **多阶段处理**
   - 阶段1: 轻量模型分类意图
   - 阶段2: 根据意图加载必要上下文

2. **上下文压缩**
   - 使用 LLM 压缩历史对话
   - 保留关键信息，减少 token

---

## 📋 测试环境

- **操作系统**: macOS Darwin 25.2.0 (arm64)
- **Python**: 3.12.7
- **模型**: glm-5
- **代理**: socks5://127.0.0.1:59526

---

## 🔧 性能追踪使用方法

### 代码集成

```python
from openakita.infra.performance import get_performance_tracker

# 获取追踪器
perf = get_performance_tracker()

# 开始请求追踪
perf.start_request("用户查询内容")

# 追踪 Prompt 构建阶段
with perf.stage("identity"):
    # 构建身份层
    pass

with perf.stage("catalogs"):
    # 构建 Catalogs 层
    pass

# 追踪 LLM 调用
perf.start_llm_call("anthropic", "claude-3-opus")
# ... LLM 调用 ...
perf.record_first_token()  # 记录首 token
perf.end_llm_call(input_tokens, output_tokens)

# 结束请求并打印摘要
perf.end_request()
perf.log_summary()
```

### 日志输出示例

```
[PERF] 🔵 Request started: '你好'
[PERF] 🤖 LLM call: total=9890ms, tokens=16274→97
[PERF] 🟢 Request completed in 19590ms
============================================================
[PERF] 📊 Performance Summary
============================================================
  Query: '你好'
  Total Time: 19590ms

  Breakdown:
    Prompt Build: 1ms (0.0%)
    LLM Calls:    19558ms (99.8%)
    Other:        32ms (0.2%)

  Stage Details:
    compile_check: 0.2ms
    identity: 0.1ms
    runtime: 0.0ms
    session_rules: 0.0ms
    catalogs: 0.4ms
    memory: 0.0ms
    user: 0.0ms

  LLM Calls:
    #1 primary/glm-5: TTFB=0ms, total=9890ms, tokens=16274→97
    #2 primary/glm-5: TTFB=0ms, total=9668ms, tokens=16312→230

  Metrics: Avg TTFB=0ms, Total Tokens=32586+327
============================================================
```

---

## 📝 结论

1. **主要瓶颈**: LLM 调用（99.8%）
2. **Prompt 构建**: 非常快速（<1ms）
3. **优化方向**: 减少输入 token 数量，使用 prompt caching

---

*报告由 OpenAkita 性能追踪系统自动生成*
