#!/bin/bash
# Enterprise Simplification - 项目初始化脚本
# 验证项目环境和依赖

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
PROJECT_DIR="$(dirname "$0")"

echo "=== Enterprise Simplification 项目初始化 ==="
echo ""

# 1. 检查项目根目录
echo "[1/6] 检查项目根目录..."
if [ ! -d "$PROJECT_ROOT/src/openakita" ]; then
    echo "❌ 错误: 找不到 src/openakita 目录"
    exit 1
fi
echo "✅ 项目根目录: $PROJECT_ROOT"

# 2. 检查 Python 环境
echo ""
echo "[2/6] 检查 Python 环境..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "✅ Python: $PYTHON_VERSION"
else
    echo "❌ 错误: 未找到 python3"
    exit 1
fi

# 3. 检查关键目录
echo ""
echo "[3/6] 检查关键目录..."
DIRS=(
    "src/openakita/context"
    "src/openakita/memory"
    "src/openakita/core"
    "src/openakita/channels"
    "identity"
    "data"
    "skills"
)
for dir in "${DIRS[@]}"; do
    if [ -d "$PROJECT_ROOT/$dir" ]; then
        echo "✅ $dir"
    else
        echo "⚠️  $dir 不存在"
    fi
done

# 4. 检查待删除文件
echo ""
echo "[4/6] 检查待删除文件..."
FILES_TO_CHECK=(
    "src/openakita/context/backends/legacy_adapter.py"
    "src/openakita/memory/backends/legacy_adapter.py"
    "identity/USER.md"
    "data/proactive_feedback.json"
)
for file in "${FILES_TO_CHECK[@]}"; do
    if [ -f "$PROJECT_ROOT/$file" ]; then
        echo "✅ $file (待删除)"
    else
        echo "⚠️  $file 不存在（可能已删除）"
    fi
done

# 5. 统计当前代码规模
echo ""
echo "[5/6] 统计当前代码规模..."
PYTHON_FILES=$(find "$PROJECT_ROOT/src/openakita" -name "*.py" 2>/dev/null | wc -l | tr -d ' ')
echo "📊 Python 文件数: $PYTHON_FILES"

if command -v tokei &> /dev/null; then
    echo ""
    tokei "$PROJECT_ROOT/src/openakita" --type=Python
elif command -v cloc &> /dev/null; then
    echo ""
    cloc "$PROJECT_ROOT/src/openakita" --include-lang=Python
fi

# 6. 验证核心模块导入
echo ""
echo "[6/6] 验证核心模块导入..."
cd "$PROJECT_ROOT"
python3 -c "
try:
    from openakita.context.enterprise.manager import EnterpriseContextManager
    print('✅ EnterpriseContextManager')
except Exception as e:
    print(f'⚠️  EnterpriseContextManager: {e}')

try:
    from openakita.memory.enterprise.router import EnterpriseMemoryRouter
    print('✅ EnterpriseMemoryRouter')
except Exception as e:
    print(f'⚠️  EnterpriseMemoryRouter: {e}')

try:
    from openakita.core.agent import Agent
    print('✅ Agent')
except Exception as e:
    print(f'⚠️  Agent: {e}')
"

echo ""
echo "=== 初始化完成 ==="
echo ""
echo "📋 项目目录: $PROJECT_DIR"
echo "📋 计划文档: $PROJECT_DIR/plan.md"
echo "📋 功能列表: $PROJECT_DIR/feature_list.json"
echo "📋 进度日志: $PROJECT_DIR/progress.txt"
echo ""
echo "🚀 开始执行: ./claude-coder.sh run enterprise-simplification"
