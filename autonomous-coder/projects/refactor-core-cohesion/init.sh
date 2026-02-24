#!/bin/bash
# Core 模块重构项目初始化脚本
# 验证开发环境，确保重构可以正常进行

set -e

# 项目根目录
PROJECT_ROOT="/Users/zd/agents/openakita-deron"
cd "$PROJECT_ROOT"

echo "========================================"
echo "Core Module Refactoring - Init"
echo "========================================"

echo ""
echo "[1/5] 检查 Python 版本..."
python --version

echo ""
echo "[2/5] 检查项目目录..."
if [ -d "$PROJECT_ROOT/src/openakita/core" ]; then
    echo "✓ src/openakita/core 存在"
    echo "  文件数量: $(ls $PROJECT_ROOT/src/openakita/core/*.py | wc -l)"
else
    echo "✗ src/openakita/core 不存在"
    exit 1
fi

echo ""
echo "[3/5] 检查核心模块导入..."
python -c "
from openakita.core import Agent, AgentState, TaskState, TaskStatus, Identity, RalphLoop
from openakita.llm import LLMClient
from openakita.tools import ShellTool, FileTool
from openakita.skills import SkillRegistry
from openakita.memory import MemoryManager
print('✓ 核心模块导入成功')
" || { echo "✗ 核心模块导入失败"; exit 1; }

echo ""
echo "[4/5] 检查 core 模块文件..."
echo "当前 core 文件列表:"
ls -la $PROJECT_ROOT/src/openakita/core/*.py | awk '{print "  " $NF}'

echo ""
echo "[5/5] 检查依赖关系..."
echo "core 模块对外的依赖:"
grep -h "^from \.\." $PROJECT_ROOT/src/openakita/core/*.py 2>/dev/null | sort -u | head -20

echo ""
echo "========================================"
echo "初始化完成!"
echo "========================================"
echo ""
echo "下一步: 运行 coding agent 开始重构"
echo "  ./claude-coder.sh run refactor-core-cohesion --once"
