# 长时自动化编程系统 v2.0

基于 [Anthropic 的长时运行代理研究](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) 构建的多项目自动化编程框架。

## 系统概述

本系统解决 AI Agent 在长时编程任务中的核心挑战：

| 问题 | 解决方案 |
|------|----------|
| **上下文记忆** - 每个新会话没有之前的记忆 | 通过 `progress.txt` 和 `feature_list.json` 持久化状态 |
| **过度乐观** - Agent 试图一次性完成所有工作 | Initializer Agent 将需求拆分为原子任务 |
| **过早完成** - Agent 过早宣布项目完成 | 功能列表所有项必须 `passes: true` |
| **测试不充分** - 功能未经验证就标记完成 | Coding Agent 必须执行验收步骤才能标记完成 |

## 核心架构

```
┌─────────────────────────────────────────────────────────────┐
│                    用户 / 需求文档                          │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Initializer Agent (首次运行)                    │
│  • 分析需求和现有代码                                        │
│  • 创建 feature_list.json (所有功能 passes: false)          │
│  • 创建 progress.txt                                        │
│  • 创建 init.sh                                             │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Coding Agent (循环执行)                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 1. 读取 progress.txt 和 git log                    │   │
│  │ 2. 读取 feature_list.json                          │   │
│  │ 3. 选择下一个未完成的任务                           │   │
│  │ 4. 运行 init.sh 验证环境                           │   │
│  │ 5. 实现功能                                        │   │
│  │ 6. 执行验收测试                                    │   │
│  │ 7. 更新 feature_list.json (passes: true)          │   │
│  │ 8. Git commit                                      │   │
│  │ 9. 更新 progress.txt                               │   │
│  └─────────────────────────────────────────────────────┘   │
│                    │                                        │
│                    ▼                                        │
│            还有未完成任务?                                   │
│         ┌─────────┴─────────┐                              │
│        Yes                  No                              │
│         │                    │                              │
│         ▼                    ▼                              │
│    继续循环              项目完成!                          │
└─────────────────────────────────────────────────────────────┘
```

## 目录结构

```
autonomous-coder-v2/
├── claude-coder.sh          # 统一入口脚本
├── core/                    # 通用框架核心
│   ├── lib.sh              # 公共函数库
│   ├── prompts/            # Prompt 模板
│   │   ├── initializer.md  # 初始化代理
│   │   └── coder.md        # 编码代理
│   └── templates/          # 文件模板
│       ├── feature_list.json
│       └── project.json
├── projects/               # 所有项目
│   ├── enterprise-refactor/
│   │   ├── project.json    # 项目元信息
│   │   ├── feature_list.json
│   │   ├── progress.txt
│   │   ├── init.sh
│   │   └── logs/
│   └── entropy-reduction/
└── history/               # 历史归档
```

## 快速开始

### 1. 创建新项目

```bash
# 交互式创建
./claude-coder.sh new my-project

# 从需求文档创建（会自动运行初始化代理）
./claude-coder.sh new my-project --from requirement.md
```

### 2. 查看项目

```bash
# 列出所有项目
./claude-coder.sh list

# 查看项目详情
./claude-coder.sh status my-project
```

### 3. 运行项目

```bash
# 持续运行直到完成
./claude-coder.sh run my-project

# 只运行一次
./claude-coder.sh run my-project --once

# 限制最大迭代次数
./claude-coder.sh run my-project --max 50
```

### 4. 暂停/恢复

```bash
# 暂停项目
./claude-coder.sh pause my-project

# 恢复项目
./claude-coder.sh resume my-project
```

### 5. 归档

```bash
# 归档完成的项目
./claude-coder.sh archive my-project
```

## 命令参考

| 命令 | 说明 |
|------|------|
| `new <项目名> [--from <文件>]` | 创建新项目 |
| `list` | 列出所有项目 |
| `status <项目名>` | 查看项目详情 |
| `run <项目名> [--once] [--max N]` | 运行项目 |
| `pause <项目名>` | 暂停项目 |
| `resume <项目名>` | 恢复项目 |
| `archive <项目名>` | 归档项目 |

## 文件说明

### project.json - 项目元信息

```json
{
  "id": "my-project",
  "name": "My Project",
  "status": "running|paused|completed|blocked|ready",
  "created_at": "2026-02-23",
  "updated_at": "2026-02-23",
  "description": "项目描述",
  "total_features": 10,
  "completed_features": 3
}
```

### feature_list.json - 功能列表

```json
{
  "features": [
    {
      "id": "FEAT-001",
      "category": "functional",
      "priority": "high",
      "description": "实现用户登录功能",
      "steps": [
        "验证用户名和密码输入框存在",
        "输入测试用户名和密码",
        "点击登录按钮",
        "验证登录成功提示"
      ],
      "files_affected": ["src/auth/login.py"],
      "dependencies": [],
      "passes": false,
      "completed_at": null
    }
  ],
  "implementation_order": ["FEAT-001", "FEAT-002"]
}
```

### progress.txt - 进度日志

```
# Agent Progress Log

## Session 0 - Initialization
- Date: 2026-02-23 10:00
- Agent: Initializer

### Completed:
- Created feature_list.json with 10 features
- Set up project structure

---

## Session 1 - Coding
- Date: 2026-02-23 10:30
- Agent: Coder
- Feature: FEAT-001 - 实现用户登录功能

### Completed:
- 实现了登录表单验证
- 添加了密码加密

### Test Results:
- Step 1: ✅ PASS
- Step 2: ✅ PASS
- Step 3: ✅ PASS
- Step 4: ✅ PASS

### Next Steps:
- 继续实现 FEAT-002

---
```

## 最佳实践

### 功能拆分原则

1. **原子性** - 每个功能应该在一个会话内完成
2. **可测试** - 每个功能有 3-5 个明确的验收步骤
3. **独立性** - 尽量减少功能间的依赖

### 需求文档建议

```markdown
# 项目名称

## 概述
项目简介和目标

## 功能需求
1. 用户可以...
2. 系统应该...

## 技术要求
- 使用框架: ...
- 数据库: ...

## 验收标准
- 所有测试通过
- 代码覆盖率 > 80%
```

### 失败处理

- 连续失败 3 次，项目自动变为 `blocked` 状态
- 查看日志文件 `logs/` 了解失败原因
- 修复问题后 `resume` 继续

## 与原系统的区别

| 特性 | v1 (autonomous-coder) | v2 (autonomous-coder-v2) |
|------|----------------------|--------------------------|
| 多项目支持 | ❌ 混在一起 | ✅ 独立目录 |
| 项目管理 | ❌ 无 | ✅ list/status/pause/resume |
| 通用框架 | ❌ 每个项目单独脚本 | ✅ 统一入口 |
| 历史归档 | ❌ 无 | ✅ history 目录 |
| 迁移能力 | ❌ 难以迁移 | ✅ 易于归档/恢复 |

## 参考

- [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk)
