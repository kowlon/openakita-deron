#!/bin/bash
# 运行单次编码会话
# 用法: ./run-coder.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查必要文件是否存在
if [ ! -f "feature_list.json" ]; then
    echo "错误: feature_list.json 不存在"
    echo "请先运行 ./run-init.sh 初始化项目"
    exit 1
fi

if [ ! -f "agent-progress.txt" ]; then
    echo "错误: agent-progress.txt 不存在"
    echo "请先运行 ./run-init.sh 初始化项目"
    exit 1
fi

# 读取编码代理提示词
CODER_PROMPT=$(cat prompts/coder.md)

# 获取当前会话编号
SESSION_NUM=$(grep -c "^## Session" agent-progress.txt 2>/dev/null || echo "0")
NEXT_SESSION=$((SESSION_NUM + 1))

# 检查是否有未完成的功能
PENDING=$(cat feature_list.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
pending = [f for f in data.get('features', []) if not f.get('passes', False)]
print(len(pending))
" 2>/dev/null || echo "unknown")

echo "========================================="
echo "  编码代理启动"
echo "  会话编号: $NEXT_SESSION"
echo "  待完成功能: $PENDING"
echo "========================================="
echo ""

# 添加时间戳到进度文件
echo "会话 $NEXT_SESSION 开始于: $(date '+%Y-%m-%d %H:%M:%S')" >> agent-progress.txt

# 运行 Claude Code
claude --dangerously-skip-permissions "$CODER_PROMPT"

echo ""
echo "========================================="
echo "  编码会话 $NEXT_SESSION 完成"
echo "========================================="
