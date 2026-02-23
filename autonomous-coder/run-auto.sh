#!/bin/bash
# 全自动企业级重构编码循环
# 无需任何人工干预，自动完成所有任务
#
# 用法: ./run-auto.sh [最大迭代次数] [任务超时秒数]
# 示例: ./run-auto.sh 100 600   # 最多100次，每次最多10分钟

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 参数
MAX_ITERATIONS=${1:-100}
TIMEOUT=${2:-600}  # 单次任务超时（秒）

# 日志
mkdir -p logs
LOG_FILE="logs/auto-$(date '+%Y%m%d-%H%M%S').log"

log() {
    echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 获取任务信息
get_next_task() {
    python3 << 'EOF'
import json
with open('enterprise_feature_list.json') as f:
    data = json.load(f)
order = data.get('implementation_order', [])
features = {f['id']: f for f in data.get('features', [])}

for fid in order:
    if fid in features and not features[fid].get('passes', False):
        deps = features[fid].get('dependencies', [])
        if all(features.get(d, {}).get('passes', False) for d in deps):
            print(f"{fid}|{features[fid].get('description', '')[:50]}")
            break
EOF
}

get_progress() {
    python3 << 'EOF'
import json
with open('enterprise_feature_list.json') as f:
    data = json.load(f)
total = len(data.get('features', []))
done = sum(1 for f in data.get('features', []) if f.get('passes', False))
print(f"{done}/{total}")
EOF
}

log "========================================"
log "  全自动企业级重构编码"
log "  最大迭代: $MAX_ITERATIONS"
log "  任务超时: ${TIMEOUT}s"
log "========================================"

iteration=0
while [ $iteration -lt $MAX_ITERATIONS ]; do
    iteration=$((iteration + 1))

    # 检查下一个任务
    TASK_INFO=$(get_next_task)

    if [ -z "$TASK_INFO" ]; then
        log ""
        log "✅ 所有任务已完成！"
        log "进度: $(get_progress)"
        exit 0
    fi

    TASK_ID=$(echo "$TASK_INFO" | cut -d'|' -f1)
    TASK_DESC=$(echo "$TASK_INFO" | cut -d'|' -f2)

    log ""
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "迭代 $iteration: $TASK_ID - $TASK_DESC"
    log "进度: $(get_progress)"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # 记录完成数量
    BEFORE=$(get_progress | cut -d'/' -f1)

    # 执行任务
    TASK_LOG="logs/${TASK_ID}-$(date '+%Y%m%d-%H%M%S').log"

    log "启动 Claude Code..."

    # 关键：使用 --print 模式（非交互）+ --dangerously-skip-permissions
    PROMPT=$(cat prompts/enterprise_coder.md)

    if timeout $TIMEOUT claude \
        --dangerously-skip-permissions \
        --print \
        "$PROMPT" 2>&1 | tee "$TASK_LOG"; then

        log "✅ Claude 执行完成"
    else
        exit_code=$?
        if [ $exit_code -eq 124 ]; then
            log "⏱️ 任务超时"
        else
            log "⚠️ 退出码: $exit_code"
        fi
    fi

    # 检查进度
    AFTER=$(get_progress | cut -d'/' -f1)

    if [ "$AFTER" -gt "$BEFORE" ]; then
        log "🎉 任务完成: $TASK_ID"
    else
        log "⚠️ 任务可能未完成"
    fi

    # 短暂等待
    sleep 3
done

log ""
log "达到最大迭代次数: $MAX_ITERATIONS"
log "当前进度: $(get_progress)"
