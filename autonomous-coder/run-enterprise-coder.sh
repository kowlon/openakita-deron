#!/bin/bash
# 运行企业级重构编码会话
# 用法: ./run-enterprise-coder.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查必要文件是否存在
if [ ! -f "enterprise_feature_list.json" ]; then
    echo "错误: enterprise_feature_list.json 不存在"
    exit 1
fi

if [ ! -f "agent-progress.txt" ]; then
    echo "错误: agent-progress.txt 不存在"
    exit 1
fi

# 读取编码代理提示词
CODER_PROMPT=$(cat prompts/enterprise_coder.md)

# 获取当前会话编号
SESSION_NUM=$(grep -c "^## Session" agent-progress.txt 2>/dev/null || echo "0")
NEXT_SESSION=$((SESSION_NUM + 1))

# 检查是否有未完成的功能
PENDING=$(cat enterprise_feature_list.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
pending = [f for f in data.get('features', []) if not f.get('passes', False)]
print(len(pending))
" 2>/dev/null || echo "unknown")

# 获取下一个要实现的功能
NEXT_FEATURE=$(cat enterprise_feature_list.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
order = data.get('implementation_order', [])
features = {f['id']: f for f in data.get('features', [])}

# 按 implementation_order 顺序找第一个未完成的
for fid in order:
    if fid in features and not features[fid].get('passes', False):
        f = features[fid]
        deps = f.get('dependencies', [])
        # 检查依赖是否都完成
        deps_ok = all(features.get(d, {}).get('passes', False) for d in deps)
        if deps_ok:
            print(f\"{fid}: {f.get('description', '')}\")
            break
" 2>/dev/null || echo "unknown")

echo "========================================="
echo "  企业级重构编码代理启动"
echo "  会话编号: $NEXT_SESSION"
echo "  待完成功能: $PENDING"
echo "  下一个功能: $NEXT_FEATURE"
echo "========================================="
echo ""

# 添加时间戳到进度文件
echo "" >> agent-progress.txt
echo "## Session $NEXT_SESSION - Enterprise Coding" >> agent-progress.txt
echo "- 开始时间: $(date '+%Y-%m-%d %H:%M:%S')" >> agent-progress.txt

# 运行 Claude Code
claude --dangerously-skip-permissions "$CODER_PROMPT"

echo ""
echo "========================================="
echo "  编码会话 $NEXT_SESSION 完成"
echo "========================================="

# 显示当前进度
COMPLETED=$(cat enterprise_feature_list.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
completed = [f for f in data.get('features', []) if f.get('passes', False)]
print(len(completed))
" 2>/dev/null || echo "0")

TOTAL=$(cat enterprise_feature_list.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(len(data.get('features', [])))
" 2>/dev/null || echo "0")

echo "进度: $COMPLETED / $TOTAL 功能已完成"
