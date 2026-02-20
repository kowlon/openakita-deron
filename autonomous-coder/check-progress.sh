#!/bin/bash
# 检查项目进度
# 用法: ./check-progress.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================="
echo "  项目进度检查"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================="
echo ""

# 检查文件是否存在
if [ ! -f "feature_list.json" ]; then
    echo "⚠️  feature_list.json 不存在"
    echo "   请先运行 ./run-init.sh 初始化项目"
    exit 1
fi

if [ ! -f "agent-progress.txt" ]; then
    echo "⚠️  agent-progress.txt 不存在"
    echo "   请先运行 ./run-init.sh 初始化项目"
    exit 1
fi

# 显示功能统计
echo "📊 功能统计:"
echo "─────────────────────────────────────"
python3 << 'EOF'
import json
from datetime import datetime

try:
    with open('feature_list.json', 'r') as f:
        data = json.load(f)

    features = data.get('features', [])
    total = len(features)

    # 统计各状态
    completed = [f for f in features if f.get('passes', False)]
    pending = [f for f in features if not f.get('passes', False)]

    # 统计各优先级
    high_pending = [f for f in pending if f.get('priority') == 'high']
    medium_pending = [f for f in pending if f.get('priority') == 'medium']
    low_pending = [f for f in pending if f.get('priority') == 'low']

    # 统计各类型
    by_category = {}
    for f in features:
        cat = f.get('category', 'unknown')
        by_category[cat] = by_category.get(cat, 0) + 1

    print(f"  总功能数:     {total}")
    print(f"  ✅ 已完成:    {len(completed)}")
    print(f"  ⏳ 待完成:    {len(pending)}")
    print(f"  📈 完成率:    {len(completed)*100//total if total > 0 else 0}%")
    print()
    print(f"  待完成优先级分布:")
    print(f"    🔴 高优先级: {len(high_pending)}")
    print(f"    🟡 中优先级: {len(medium_pending)}")
    print(f"    🟢 低优先级: {len(low_pending)}")
    print()
    print(f"  类型分布:")
    for cat, count in sorted(by_category.items()):
        print(f"    {cat}: {count}")

except Exception as e:
    print(f"  错误: {e}")
EOF

echo ""
echo "📋 待完成功能列表:"
echo "─────────────────────────────────────"
python3 << 'EOF'
import json

try:
    with open('feature_list.json', 'r') as f:
        data = json.load(f)

    pending = [f for f in data.get('features', []) if not f.get('passes', False)]

    # 按优先级排序
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    pending.sort(key=lambda x: priority_order.get(x.get('priority', 'low'), 2))

    priority_icons = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}

    for i, f in enumerate(pending[:10], 1):  # 只显示前10个
        icon = priority_icons.get(f.get('priority', 'low'), '⚪')
        fid = f.get('id', 'unknown')
        desc = f.get('description', '')[:60]
        if len(f.get('description', '')) > 60:
            desc += '...'
        print(f"  {i}. {icon} [{fid}] {desc}")

    if len(pending) > 10:
        print(f"  ... 还有 {len(pending) - 10} 个功能")

except Exception as e:
    print(f"  错误: {e}")
EOF

echo ""
echo "📝 最近会话记录:"
echo "─────────────────────────────────────"
if [ -f "agent-progress.txt" ]; then
    tail -30 agent-progress.txt
else
    echo "  无记录"
fi

echo ""
echo "📦 最近 Git 提交:"
echo "─────────────────────────────────────"
cd ..
git log --oneline -5 2>/dev/null || echo "  无 git 历史"
cd "$SCRIPT_DIR"

echo ""
echo "========================================="
echo "  检查完成"
echo "========================================="
