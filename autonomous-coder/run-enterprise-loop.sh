#!/bin/bash
# 持续运行企业级重构编码代理，每个任务后重启清空上下文
# 用法: ./run-enterprise-loop.sh [最大迭代次数] [每次间隔秒数]
#
# 设计理念：
# - 每个任务完成后重启 Claude Code，清空上下文
# - 通过文件系统（feature_list.json, agent-progress.txt）维护状态
# - 避免上下文污染，保持任务独立性
# - 完全自动化，无需人工干预

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 配置参数
MAX_ITERATIONS=${1:-100}      # 最大迭代次数，默认 100
INTERVAL=${2:-5}              # 每次间隔秒数，默认 5 秒
TIMEOUT=${3:-600}             # 单次任务超时时间（秒），默认 10 分钟

# 检查必要文件
if [ ! -f "enterprise_feature_list.json" ]; then
    echo "错误: enterprise_feature_list.json 不存在"
    exit 1
fi

PROJECT_NAME=$(basename "$(dirname "$SCRIPT_DIR")")

# 创建日志目录
mkdir -p logs
LOG_FILE="logs/loop-$(date '+%Y%m%d-%H%M%S').log"

# 日志函数
log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg" | tee -a "$LOG_FILE"
}

log "╔══════════════════════════════════════════════════════════════╗"
log "║           企业级重构自动编码循环 (无人值守版)                  ║"
log "╠══════════════════════════════════════════════════════════════╣"
log "║  项目: $PROJECT_NAME"
log "║  最大迭代: $MAX_ITERATIONS"
log "║  任务间隔: ${INTERVAL}s"
log "║  任务超时: ${TIMEOUT}s"
log "║  日志文件: $LOG_FILE"
log "╚══════════════════════════════════════════════════════════════╝"

# 函数：获取任务状态（输出 shell 变量格式）
get_task_status() {
    python3 << 'EOF'
import json

try:
    with open('enterprise_feature_list.json', 'r') as f:
        data = json.load(f)

    features = data.get('features', [])
    order = data.get('implementation_order', [])
    feature_map = {f['id']: f for f in features}

    completed = [f for f in features if f.get('passes', False)]
    pending = [f for f in features if not f.get('passes', False)]

    # 按 implementation_order 找下一个可执行的任务
    next_task = None
    for fid in order:
        if fid in feature_map and not feature_map[fid].get('passes', False):
            deps = feature_map[fid].get('dependencies', [])
            deps_ok = all(feature_map.get(d, {}).get('passes', False) for d in deps)
            if deps_ok:
                next_task = feature_map[fid]
                break

    total = len(features)
    done = len(completed)

    if done == total:
        print('STATUS="COMPLETE"')
        print(f'COMPLETED="{done}/{total}"')
    else:
        print('STATUS="PENDING"')
        print(f'COMPLETED="{done}/{total}"')
        if next_task:
            print(f'NEXT_ID="{next_task["id"]}"')
            desc = next_task.get('description', '')[:60].replace('"', "'")
            print(f'NEXT_DESC="{desc}"')
            print(f'NEXT_PRIORITY="{next_task.get("priority", "unknown")}"')
        else:
            print('NEXT_ID=""')
            print('NEXT_DESC="No available task (check dependencies)"')
            print('NEXT_PRIORITY=""')

except Exception as e:
    print('STATUS="ERROR"')
    print(f'ERROR="{e}"')
EOF
}

# 函数：显示任务列表
show_task_list() {
    python3 << 'EOF'
import json

try:
    with open('enterprise_feature_list.json', 'r') as f:
        data = json.load(f)

    features = data.get('features', [])
    order = data.get('implementation_order', [])

    print("\n任务列表:")
    print("-" * 60)

    for i, fid in enumerate(order, 1):
        f = next((x for x in features if x['id'] == fid), None)
        if f:
            status = "✅" if f.get('passes', False) else "⬜"
            priority = f.get('priority', '?')[0].upper()
            desc = f.get('description', '')[:40]
            print(f"  {i:2}. {status} [{priority}] {fid}: {desc}")

    print("-" * 60)
except Exception as e:
    print(f"无法读取任务列表: {e}")
EOF
}

# 主循环
iteration=0
consecutive_failures=0
MAX_CONSECUTIVE_FAILURES=3

while [ $iteration -lt $MAX_ITERATIONS ]; do
    iteration=$((iteration + 1))

    log ""
    log "══════════════════════════════════════════════════════════════"
    log "  迭代 $iteration / $MAX_ITERATIONS"
    log "══════════════════════════════════════════════════════════════"

    # 获取任务状态
    eval $(get_task_status)

    # 检查状态
    case $STATUS in
        COMPLETE)
            log ""
            log "╔══════════════════════════════════════════════════════════════╗"
            log "║                    🎉 所有任务已完成！                        ║"
            log "╚══════════════════════════════════════════════════════════════╝"
            log ""
            log "$COMPLETED"
            show_task_list | tee -a "$LOG_FILE"
            exit 0
            ;;

        ERROR)
            log "❌ 错误: $ERROR"
            exit 1
            ;;

        PENDING)
            if [ -z "$NEXT_ID" ]; then
                log "⚠️  没有可执行的任务（可能存在未完成的依赖）"
                show_task_list | tee -a "$LOG_FILE"
                exit 1
            fi
            log "📊 $COMPLETED"
            log "🎯 下一个任务: [$NEXT_PRIORITY] $NEXT_ID"
            log "   描述: $NEXT_DESC"
            ;;

        *)
            log "❌ 未知状态: $STATUS"
            exit 1
            ;;
    esac

    # 显示任务列表（每 5 次迭代显示一次）
    if [ $((iteration % 5)) -eq 1 ]; then
        show_task_list | tee -a "$LOG_FILE"
    fi

    # 记录开始时的完成数量
    BEFORE_COUNT=$(python3 -c "
import json
with open('enterprise_feature_list.json') as f:
    data = json.load(f)
print(sum(1 for f in data.get('features', []) if f.get('passes', False)))
")

    log ""
    log "🚀 启动编码代理..."
    log ""

    # 运行编码代理（带超时）
    TASK_LOG="logs/task-${iteration}-${NEXT_ID}-$(date '+%Y%m%d-%H%M%S').log"

    # 使用 timeout 和 --dangerously-skip-permissions
    # --print 选项让输出直接打印，不进入交互模式
    CODER_PROMPT=$(cat prompts/enterprise_coder.md)

    if timeout $TIMEOUT claude --dangerously-skip-permissions --print "$CODER_PROMPT" 2>&1 | tee "$TASK_LOG"; then
        log "✅ Claude 执行完成"
    else
        exit_code=$?
        if [ $exit_code -eq 124 ]; then
            log "⏱️  任务超时 (${TIMEOUT}s)"
        else
            log "⚠️  Claude 退出码: $exit_code"
        fi
    fi

    # 检查是否完成了任务
    AFTER_COUNT=$(python3 -c "
import json
with open('enterprise_feature_list.json') as f:
    data = json.load(f)
print(sum(1 for f in data.get('features', []) if f.get('passes', False)))
")

    if [ "$AFTER_COUNT" -gt "$BEFORE_COUNT" ]; then
        log "✅ 任务 $NEXT_ID 完成！($BEFORE_COUNT -> $AFTER_COUNT)"
        consecutive_failures=0
    else
        log "⚠️  任务可能未完成 ($BEFORE_COUNT -> $AFTER_COUNT)"
        consecutive_failures=$((consecutive_failures + 1))

        if [ $consecutive_failures -ge $MAX_CONSECUTIVE_FAILURES ]; then
            log ""
            log "❌ 连续失败 $consecutive_failures 次，停止循环"
            log "   请检查日志: $LOG_FILE"
            exit 1
        fi
    fi

    # 等待
    log ""
    log "💤 等待 ${INTERVAL}s..."
    sleep $INTERVAL

done

# 达到最大迭代次数
log ""
log "╔══════════════════════════════════════════════════════════════╗"
log "║              ⚠️  达到最大迭代次数: $MAX_ITERATIONS              ║"
log "╚══════════════════════════════════════════════════════════════╝"
show_task_list | tee -a "$LOG_FILE"
