# Autonomous Coder - 长时自动化编程系统

基于 [Anthropic 的长时运行代理研究](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) 构建的自动化编程系统。

## 系统概述

本系统解决 AI Agent 在长时编程任务中的核心挑战：

1. **上下文记忆问题** - 每个新会话开始时没有之前的记忆
2. **过度乐观问题** - Agent 倾向于一次性尝试完成太多工作
3. **过早完成问题** - Agent 可能过早宣布项目完成
4. **测试不充分** - Agent 可能在没有适当测试的情况下将功能标记为完成

## 核心组件

### 1. 初始化代理 (Initializer Agent)
- 设置初始开发环境
- 创建功能需求列表 (`feature_list.json`)
- 创建进度跟踪文件 (`agent-progress.txt`)
- 创建初始化脚本 (`init.sh`)

### 2. 编码代理 (Coding Agent)
- 每次会话只处理一个功能
- 读取进度文件了解历史
- 进行端到端测试验证
- 提交 git commit 并更新进度

## 快速开始

### 1. 初始化项目
```bash
# 启动初始化代理
./run-init.sh 你的需求文档.md

# 或者直接运行
claude --dangerously-skip-permissions "$(cat prompts/initializer.md)" -- "$(cat 你的需求文档.md)"
```

### 2. 运行编码代理（循环）
```bash
# 运行单次编码会话
./run-coder.sh

# 或持续运行直到完成
./run-loop.sh
```

### 3. 检查进度
```bash
# 查看进度
cat agent-progress.txt

# 查看功能完成情况
cat feature_list.json | jq '.[] | select(.passes == true) | .description'
```

## 文件结构

```
autonomous-coder/
├── README.md                 # 本文件
├── run-init.sh              # 运行初始化代理
├── run-coder.sh             # 运行单次编码会话
├── run-loop.sh              # 持续运行循环
├── check-progress.sh        # 检查进度脚本
├── prompts/
│   ├── initializer.md       # 初始化代理的提示词
│   └── coder.md             # 编码代理的提示词
├── templates/
│   ├── feature_list.json    # 功能列表模板
│   └── progress.md          # 进度文件模板
├── feature_list.json        # 当前项目的功能需求列表
├── agent-progress.txt       # 进度跟踪日志
└── init.sh                  # 项目启动脚本
```

## 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│                      需求文档                                │
└─────────────────────┬───────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              初始化代理 (Initializer Agent)                  │
│  • 分析需求文档                                              │
│  • 创建 feature_list.json (所有功能标记为 failing)           │
│  • 创建 agent-progress.txt                                  │
│  • 创建 init.sh (启动脚本)                                   │
│  • 创建初始 git commit                                       │
└─────────────────────┬───────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│               编码代理循环 (Coding Agent Loop)               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 1. 读取 agent-progress.txt 和 git log               │   │
│  │ 2. 读取 feature_list.json                           │   │
│  │ 3. 选择下一个未完成的功能                            │   │
│  │ 4. 运行 init.sh 确保环境正常                        │   │
│  │ 5. 实现功能                                         │   │
│  │ 6. 进行端到端测试验证                               │   │
│  │ 7. 更新 feature_list.json (标记 passes: true)       │   │
│  │ 8. 提交 git commit                                  │   │
│  │ 9. 更新 agent-progress.txt                          │   │
│  └──────────────────────────────────────────────────────┘   │
│                      │                                      │
│                      ▼                                      │
│              还有未完成功能?                                 │
│           ┌───────┴───────┐                                 │
│           │               │                                 │
│          Yes             No                                 │
│           │               │                                 │
│           ▼               ▼                                 │
│      继续循环         项目完成!                             │
└─────────────────────────────────────────────────────────────┘
```

## 最佳实践

### 需求文档格式
建议使用 Markdown 格式，包含：
- 项目概述
- 功能需求列表
- 技术要求
- 验收标准

### 功能列表管理
- 功能描述应该清晰、可测试
- 每个功能应该有明确的验收步骤
- 优先级应该合理排序

### Git 提交规范
- 每个功能一个 commit
- 提交信息清晰描述改动
- 保持代码在可工作状态

## 注意事项

1. **不要跳过测试** - 每个功能必须经过验证才能标记为完成
2. **保持原子性** - 每次只处理一个功能
3. **记录进度** - 详细记录每次会话的工作内容
4. **保持代码整洁** - 每次会话结束时代码应该是可工作的

## 参考

- [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk)
