#!/bin/bash
# 持续运行编码代理直到所有功能完成
# 用法: ./run-loop.sh [最大迭代次数]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 最大迭代次数，默认 100
MAX_ITERATIONS=${1:-100}

# 检查必要文件是否存在
if [ ! -f "feature_list.json" ]; then
    echo "错误: feature_list.json 不存在"
    echo "请先运行 ./run-init.sh 初始化项目"
    exit 1
fi

# 获取项目名称
PROJECT_NAME=$(basename "$(dirname "$SCRIPT_DIR")")

echo "========================================="
echo "  自动编码循环启动"
echo "  项目: $PROJECT_NAME"
echo "  最大迭代: $MAX_ITERATIONS"
echo "========================================="
echo ""

# 函数：检查是否还有未完成的功能
has_pending_features() {
    python3 << 'EOF'
import json
try:
    with open('feature_list.json', 'r') as f:
        data = json.load(f)
    pending = [f for f in data.get('features', []) if not f.get('passes', False)]
    if len(pending) == 0:
        print("COMPLETE")
    else:
        print(f"PENDING:{len(pending)}")
except Exception as e:
    print(f"ERROR:{e}")
EOF
}

# 函数：显示进度
show_progress() {
    python3 << 'EOF'
import json
try:
    with open('feature_list.json', 'r') as f:
        data = json.load(f)
    features = data.get('features', [])
    completed = sum(1 for f in features if f.get('passes', False))
    total = len(features)
    print(f"进度: {completed}/{total} 功能完成")
    if completed < total:
        pending = [f for f in features if not f.get('passes', False)]
        print(f"下一个功能: {pending[0].get('id', 'unknown')} - {pending[0].get('description', '')[:50]}...")
except Exception as e:
    print(f"无法读取进度: {e}")
EOF
}

# 主循环
iteration=0
while [ $iteration -lt $MAX_ITERATIONS ]; do
    iteration=$((iteration + 1))

    echo ""
    echo "-----------------------------------------"
    echo "  迭代 $iteration / $MAX_ITERATIONS"
    echo "  $(date '+%Y-%m-%d %H:%M:%S')"
    echo "-----------------------------------------"

    # 显示当前进度
    show_progress

    # 检查是否完成
    status=$(has_pending_features)

    case $status in
        COMPLETE)
            echo ""
            echo "========================================="
            echo "  🎉 所有功能已完成！"
            echo "========================================="
            show_progress
            echo ""
            echo "项目已完成，可以进入下一阶段："
            echo "  - 代码审查"
            echo "  - 部署测试"
            echo "  - 用户验收"
            exit 0
            ;;
        ERROR:*)
            echo "错误: ${status#ERROR:}"
            echo "请检查 feature_list.json 文件"
            exit 1
            ;;
        PENDING:*)
            pending_count="${status#PENDING:}"
            echo "待完成功能数: $pending_count"
            ;;
    esac

    # 运行编码代理
    echo ""
    echo "启动编码代理..."
    ./run-coder.sh

    # 等待一小段时间，避免过于频繁调用
    echo ""
    echo "等待 5 秒后继续..."
    sleep 5
done

echo ""
echo "========================================="
echo "  达到最大迭代次数: $MAX_ITERATIONS"
echo "========================================="
show_progress
echo ""
echo "如需继续，请重新运行此脚本"
