#!/bin/bash
# 公共函数库 - 长时自动化编程系统 v2.0
# 参考: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 路径定义
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORE_DIR="$SCRIPT_DIR/core"
PROJECTS_DIR="$SCRIPT_DIR/projects"
HISTORY_DIR="$SCRIPT_DIR/history"
TEMPLATES_DIR="$CORE_DIR/templates"
PROMPTS_DIR="$CORE_DIR/prompts"

# 日志函数
log_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_header() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC} $1"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# 检查项目是否存在
project_exists() {
    local project_name="$1"
    [ -d "$PROJECTS_DIR/$project_name" ]
}

# 获取项目路径
get_project_path() {
    local project_name="$1"
    echo "$PROJECTS_DIR/$project_name"
}

# 读取项目元信息
get_project_meta() {
    local project_name="$1"
    local field="$2"
    local project_path=$(get_project_path "$project_name")
    local meta_file="$project_path/project.json"

    if [ ! -f "$meta_file" ]; then
        echo ""
        return
    fi

    python3 -c "
import json
with open('$meta_file') as f:
    data = json.load(f)
print(data.get('$field', ''))
"
}

# 更新项目元信息
update_project_meta() {
    local project_name="$1"
    local field="$2"
    local value="$3"
    local project_path=$(get_project_path "$project_name")
    local meta_file="$project_path/project.json"

    python3 -c "
import json
with open('$meta_file', 'r') as f:
    data = json.load(f)
data['$field'] = '''$value'''
data['updated_at'] = '$(date "+%Y-%m-%d %H:%M:%S")'
with open('$meta_file', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
"
}

# 获取项目状态
get_project_status() {
    local project_name="$1"
    get_project_meta "$project_name" "status"
}

# 获取项目进度
get_project_progress() {
    local project_name="$1"
    local project_path=$(get_project_path "$project_name")
    local feature_file="$project_path/feature_list.json"

    if [ ! -f "$feature_file" ]; then
        echo "0/0"
        return
    fi

    python3 -c "
import json
with open('$feature_file') as f:
    data = json.load(f)
features = data.get('features', [])
total = len(features)
done = sum(1 for f in features if f.get('passes', False))
print(f'{done}/{total}')
"
}

# 获取下一个待完成任务（简短格式）
get_next_task() {
    local project_name="$1"
    local project_path=$(get_project_path "$project_name")
    local feature_file="$project_path/feature_list.json"

    python3 -c "
import json

feature_file = '$feature_file'

try:
    with open(feature_file) as f:
        data = json.load(f)

    features = data.get('features', [])
    order = data.get('implementation_order', [])
    feature_map = {f['id']: f for f in features}

    # 按 implementation_order 找下一个可执行的任务
    for fid in order:
        if fid in feature_map and not feature_map[fid].get('passes', False):
            deps = feature_map[fid].get('dependencies', [])
            deps_ok = all(feature_map.get(d, {}).get('passes', False) for d in deps)
            if deps_ok:
                task = feature_map[fid]
                print(f'{task[\"id\"]}|{task.get(\"priority\", \"medium\")}|{task.get(\"description\", \"\")[:60]}')
                exit(0)

    # 如果没有 implementation_order，按顺序找
    for f in features:
        if not f.get('passes', False):
            deps = f.get('dependencies', [])
            deps_ok = all(
                any(x['id'] == d and x.get('passes', False) for x in features)
                for d in deps
            )
            if deps_ok:
                print(f'{f[\"id\"]}|{f.get(\"priority\", \"medium\")}|{f.get(\"description\", \"\")[:60]}')
                exit(0)

    print('NONE')
except Exception as e:
    print(f'ERROR:{e}')
"
}

# 获取任务的完整详情（JSON 格式）
get_task_details() {
    local project_name="$1"
    local task_id="$2"
    local project_path=$(get_project_path "$project_name")
    local feature_file="$project_path/feature_list.json"

    python3 -c "
import json

feature_file = '$feature_file'
task_id = '$task_id'

try:
    with open(feature_file) as f:
        data = json.load(f)

    features = data.get('features', [])
    feature_map = {f['id']: f for f in features}

    if task_id in feature_map:
        task = feature_map[task_id]
        # 输出 JSON 格式的完整任务信息
        print(json.dumps(task, ensure_ascii=False))
    else:
        print('NOT_FOUND')
except Exception as e:
    print(f'ERROR:{e}')
"
}

# 检查是否所有功能已完成
is_project_complete() {
    local project_name="$1"
    local project_path=$(get_project_path "$project_name")
    local feature_file="$project_path/feature_list.json"

    python3 -c "
import json

feature_file = '$feature_file'

try:
    with open(feature_file) as f:
        data = json.load(f)
    features = data.get('features', [])
    pending = [f for f in features if not f.get('passes', False)]
    if len(pending) == 0:
        print('COMPLETE')
    else:
        print(f'PENDING:{len(pending)}')
except Exception as e:
    print(f'ERROR:{e}')
"
}

# 列出所有项目
list_projects() {
    echo ""
    echo -e "${CYAN}项目列表:${NC}"
    echo "─────────────────────────────────────────────────────────────────"

    if [ ! -d "$PROJECTS_DIR" ] || [ -z "$(ls -A $PROJECTS_DIR 2>/dev/null)" ]; then
        echo "  (暂无项目，使用 'claude-coder.sh new <项目名>' 创建)"
        return
    fi

    for project_dir in "$PROJECTS_DIR"/*/; do
        [ ! -d "$project_dir" ] && continue
        local name=$(basename "$project_dir")
        local status=$(get_project_status "$name")
        local progress=$(get_project_progress "$name")

        # 状态图标
        local icon
        case $status in
            running) icon="🔄" ;;
            paused) icon="⏸️" ;;
            completed) icon="✅" ;;
            blocked) icon="🚫" ;;
            *) icon="❓" ;;
        esac

        printf "  %s %-25s [%-8s] 进度: %s\n" "$icon" "$name" "$status" "$progress"
    done

    echo "─────────────────────────────────────────────────────────────────"
}

# 创建新项目
create_project() {
    local project_name="$1"
    local requirement_file="$2"

    if project_exists "$project_name"; then
        log_error "项目 '$project_name' 已存在"
        return 1
    fi

    local project_path=$(get_project_path "$project_name")
    mkdir -p "$project_path/logs"

    # 创建项目元信息
    cat > "$project_path/project.json" << EOF
{
  "id": "$project_name",
  "name": "$project_name",
  "status": "initialized",
  "created_at": "$(date "+%Y-%m-%d %H:%M:%S")",
  "updated_at": "$(date "+%Y-%m-%d %H:%M:%S")",
  "paused_at": null,
  "description": "",
  "target_path": "../../",
  "total_features": 0,
  "completed_features": 0
}
EOF

    # 创建空的 feature_list.json
    if [ -f "$TEMPLATES_DIR/feature_list.json" ]; then
        cp "$TEMPLATES_DIR/feature_list.json" "$project_path/feature_list.json"
    else
        echo '{"features": [], "implementation_order": []}' > "$project_path/feature_list.json"
    fi

    # 创建空的 progress.txt
    touch "$project_path/progress.txt"

    # 创建 init.sh
    cat > "$project_path/init.sh" << 'EOF'
#!/bin/bash
# 项目初始化脚本
# 请根据项目需要修改此脚本

set -e

echo "初始化项目环境..."

# TODO: 添加项目特定的初始化命令
# 例如：
# - 安装依赖
# - 启动开发服务器
# - 运行测试

echo "初始化完成"
EOF
    chmod +x "$project_path/init.sh"

    log_success "项目 '$project_name' 创建成功"
    echo "  路径: $project_path"

    # 如果提供了需求文件，运行初始化代理
    if [ -n "$requirement_file" ] && [ -f "$requirement_file" ]; then
        log_info "正在运行初始化代理分析需求..."
        run_initializer "$project_name" "$requirement_file"
    fi
}

# 运行初始化代理
run_initializer() {
    local project_name="$1"
    local requirement_file="$2"
    local project_path=$(get_project_path "$project_name")

    if [ ! -f "$PROMPTS_DIR/initializer.md" ]; then
        log_error "找不到初始化代理 prompt: $PROMPTS_DIR/initializer.md"
        return 1
    fi

    local prompt=$(cat "$PROMPTS_DIR/initializer.md")
    local requirement=$(cat "$requirement_file")

    # 替换变量
    prompt="${prompt//\{\{PROJECT_NAME\}\}/$project_name}"
    prompt="${prompt//\{\{PROJECT_PATH\}\}/$project_path}"

    # 运行 Claude
    cd "$project_path"
    claude --dangerously-skip-permissions --print "$prompt

## 需求文档

$requirement" 2>&1 | tee "logs/init-$(date '+%Y%m%d-%H%M%S').log"

    # 更新项目状态
    update_project_meta "$project_name" "status" "ready"
}

# 运行编码代理（单次）
# 参数: project_name [task_id] [task_description] [auto_mode]
run_coder_once() {
    local project_name="$1"
    local task_id="$2"
    local task_desc="$3"
    local auto_mode="${4:-false}"
    local project_path=$(get_project_path "$project_name")

    # 优先使用项目自定义的 custom-coder.md，否则使用通用模板
    local prompt_file="$project_path/custom-coder.md"
    if [ ! -f "$prompt_file" ]; then
        prompt_file="$PROMPTS_DIR/coder.md"
    fi

    if [ ! -f "$prompt_file" ]; then
        log_error "找不到编码代理 prompt"
        return 1
    fi

    log_info "使用 prompt: $prompt_file"
    local prompt=$(cat "$prompt_file")

    # 替换变量
    prompt="${prompt//\{\{PROJECT_NAME\}\}/$project_name}"
    prompt="${prompt//\{\{PROJECT_PATH\}\}/$project_path}"

    # 如果指定了任务，追加任务信息到 prompt
    if [ -n "$task_id" ]; then
        # 获取完整的任务详情
        local task_json=$(get_task_details "$project_name" "$task_id")
        local task_files=""
        local task_deps=""

        if [[ "$task_json" != "NOT_FOUND" ]] && [[ "$task_json" != ERROR* ]]; then
            # 解析任务详情
            task_files=$(echo "$task_json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
files = data.get('files', [])
if files:
    print('\n'.join(['  - ' + f for f in files]))
else:
    print('  (未指定)')
")
            task_deps=$(echo "$task_json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
deps = data.get('dependencies', [])
if deps:
    print(', '.join(deps))
else:
    print('无')
")
        fi

        local task_info="

## ⚠️ 当前任务（由系统指定 - 必须完成此任务）

**你必须且只能实现以下任务，禁止选择其他任务：**

| 字段 | 值 |
|------|-----|
| **任务 ID** | \`$task_id\` |
| **任务描述** | $task_desc |
| **依赖任务** | $task_deps |
| **涉及文件** |
$task_files

### 执行要求

1. **只实现此任务** - 不要同时处理其他任务
2. 完成后必须更新 \`feature_list.json\` 中此任务的 \`passes\` 字段为 \`true\`
3. 添加 \`completed_at\` 字段为当前时间
4. 提交 git commit，消息格式：\`feat: $task_desc\`
5. 更新 \`progress.txt\` 记录完成情况
"
        prompt="${prompt}${task_info}"
    fi

    # 创建日志目录
    mkdir -p "$project_path/logs"
    local log_file="$project_path/logs/task-$(date '+%Y%m%d-%H%M%S').log"

    # 运行 Claude (从项目根目录)
    cd "$SCRIPT_DIR/.."

    # auto_mode 使用 --print 实现真正的自动化（Agent 完成后自动退出）
    # 否则使用交互模式（Agent 完成后等待用户输入）
    if [ "$auto_mode" = "true" ]; then
        log_info "自动模式运行，日志: $log_file"
        # 使用 --print 模式，输出重定向到日志和终端
        {
            echo "=== 任务开始: $(date '+%Y-%m-%d %H:%M:%S') ==="
            echo "任务 ID: $task_id"
            echo "任务描述: $task_desc"
            echo ""
            claude --dangerously-skip-permissions --print "$prompt" 2>&1
            echo ""
            echo "=== 任务结束: $(date '+%Y-%m-%d %H:%M:%S') ==="
        } 2>&1 | tee "$log_file"
    else
        log_info "交互模式运行，完成后需手动退出"
        if command -v script &> /dev/null; then
            script -q "$log_file" claude --dangerously-skip-permissions "$prompt"
        else
            claude --dangerously-skip-permissions "$prompt" 2>&1 | tee "$log_file"
        fi
    fi

    echo "$log_file"
}

# 运行编码代理（循环）
# 参数: project_name [max_iterations] [interval] [auto_mode]
run_coder_loop() {
    local project_name="$1"
    local max_iterations="${2:-100}"
    local interval="${3:-5}"
    local auto_mode="${4:-false}"
    local project_path=$(get_project_path "$project_name")

    # 记录运行开始时间
    local start_time=$(date +%s)
    local start_time_str=$(date "+%Y-%m-%d %H:%M:%S")

    # 初始化运行统计
    init_run_stats "$project_name" "$start_time_str" "$max_iterations"

    # 更新状态为 running
    update_project_meta "$project_name" "status" "running"

    log_header "自动编码循环启动"
    log_info "项目: $project_name"
    log_info "最大迭代: $max_iterations"
    log_info "间隔: ${interval}s"
    log_info "开始时间: $start_time_str"
    echo ""
    log_info "💡 在另一个终端运行以下命令查看实时状态："
    log_info "   ./claude-coder.sh monitor $project_name"
    echo ""

    local iteration=0
    local consecutive_failures=0
    local MAX_CONSECUTIVE_FAILURES=3

    while [ $iteration -lt $max_iterations ]; do
        iteration=$((iteration + 1))

        # 检查是否被暂停
        local status=$(get_project_status "$project_name")
        if [ "$status" = "paused" ]; then
            log_warning "项目已被暂停"
            update_run_stats "$project_name" "paused" "" "" "$iteration"
            return 0
        fi

        echo ""
        log_info "迭代 $iteration / $max_iterations"
        log_info "进度: $(get_project_progress "$project_name")"

        # 检查是否完成
        local complete_status=$(is_project_complete "$project_name")
        if [ "$complete_status" = "COMPLETE" ]; then
            log_header "🎉 所有功能已完成！"
            update_project_meta "$project_name" "status" "completed"
            update_run_stats "$project_name" "completed" "" "" "$iteration"
            # 显示最终统计
            show_final_stats "$project_name" "$start_time"
            return 0
        fi

        # 获取下一个任务
        local next_task=$(get_next_task "$project_name")
        if [[ "$next_task" == "NONE" ]] || [[ "$next_task" == ERROR* ]]; then
            log_warning "没有可执行的任务"
            break
        fi

        IFS='|' read -r task_id task_priority task_desc <<< "$next_task"
        log_info "下一个任务: [$task_priority] $task_id - $task_desc"

        # 更新运行状态
        update_run_stats "$project_name" "running" "$task_id" "$task_desc" "$iteration"

        # 记录任务开始时间
        local task_start_time=$(date +%s)

        # 记录完成数量
        local before_count=$(get_project_progress "$project_name" | cut -d'/' -f1)

        # 运行编码代理（传递任务信息和自动模式）
        log_info "启动编码代理..."
        run_coder_once "$project_name" "$task_id" "$task_desc" "$auto_mode"

        # 计算任务耗时
        local task_end_time=$(date +%s)
        local task_elapsed=$((task_end_time - task_start_time))
        local task_minutes=$((task_elapsed / 60))
        local task_seconds=$((task_elapsed % 60))

        # 检查是否完成
        local after_count=$(get_project_progress "$project_name" | cut -d'/' -f1)
        if [ "$after_count" -gt "$before_count" ]; then
            log_success "任务完成！($before_count -> $after_count) - 耗时: ${task_minutes}m ${task_seconds}s"
            consecutive_failures=0
            # 更新成功计数
            increment_success_count "$project_name"
        else
            log_warning "任务可能未完成 - 耗时: ${task_minutes}m ${task_seconds}s"
            consecutive_failures=$((consecutive_failures + 1))
            # 更新失败计数
            increment_failure_count "$project_name"

            if [ $consecutive_failures -ge $MAX_CONSECUTIVE_FAILURES ]; then
                log_error "连续失败 $consecutive_failures 次，停止循环"
                update_project_meta "$project_name" "status" "blocked"
                update_run_stats "$project_name" "blocked" "$task_id" "$task_desc" "$iteration"
                return 1
            fi
        fi

        # 打印总运行时间
        local current_time=$(date +%s)
        local total_elapsed=$((current_time - start_time))
        local total_hours=$((total_elapsed / 3600))
        local total_minutes=$(((total_elapsed % 3600) / 60))
        local total_seconds=$((total_elapsed % 60))
        log_info "总运行时间: ${total_hours}h ${total_minutes}m ${total_seconds}s"

        # 更新运行时间
        update_elapsed_time "$project_name" "$start_time"

        sleep $interval
    done

    log_warning "达到最大迭代次数: $max_iterations"
    update_run_stats "$project_name" "stopped" "" "" "$iteration"
}

# 初始化运行统计
init_run_stats() {
    local project_name="$1"
    local start_time="$2"
    local max_iterations="$3"
    local project_path=$(get_project_path "$project_name")
    local stats_file="$project_path/run_stats.json"

    cat > "$stats_file" << EOF
{
  "status": "running",
  "start_time": "$start_time",
  "elapsed_seconds": 0,
  "current_task_id": "",
  "current_task_desc": "",
  "current_iteration": 0,
  "max_iterations": $max_iterations,
  "success_count": 0,
  "failure_count": 0,
  "last_task_duration": 0,
  "total_task_durations": 0,
  "last_update": "$start_time"
}
EOF
}

# 更新运行统计
update_run_stats() {
    local project_name="$1"
    local status="$2"
    local task_id="$3"
    local task_desc="$4"
    local iteration="$5"
    local project_path=$(get_project_path "$project_name")
    local stats_file="$project_path/run_stats.json"

    if [ ! -f "$stats_file" ]; then
        return
    fi

    python3 -c "
import json
with open('$stats_file', 'r') as f:
    data = json.load(f)
data['status'] = '$status'
data['current_task_id'] = '''$task_id'''
data['current_task_desc'] = '''$task_desc'''
data['current_iteration'] = $iteration
data['last_update'] = '$(date "+%Y-%m-%d %H:%M:%S")'
with open('$stats_file', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
"
}

# 更新运行时间
update_elapsed_time() {
    local project_name="$1"
    local start_time="$2"
    local project_path=$(get_project_path "$project_name")
    local stats_file="$project_path/run_stats.json"

    if [ ! -f "$stats_file" ]; then
        return
    fi

    local current_time=$(date +%s)
    local elapsed=$((current_time - start_time))

    python3 -c "
import json
with open('$stats_file', 'r') as f:
    data = json.load(f)
data['elapsed_seconds'] = $elapsed
with open('$stats_file', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
"
}

# 增加成功计数
increment_success_count() {
    local project_name="$1"
    local project_path=$(get_project_path "$project_name")
    local stats_file="$project_path/run_stats.json"

    if [ ! -f "$stats_file" ]; then
        return
    fi

    python3 -c "
import json
with open('$stats_file', 'r') as f:
    data = json.load(f)
data['success_count'] = data.get('success_count', 0) + 1
with open('$stats_file', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
"
}

# 增加失败计数
increment_failure_count() {
    local project_name="$1"
    local project_path=$(get_project_path "$project_name")
    local stats_file="$project_path/run_stats.json"

    if [ ! -f "$stats_file" ]; then
        return
    fi

    python3 -c "
import json
with open('$stats_file', 'r') as f:
    data = json.load(f)
data['failure_count'] = data.get('failure_count', 0) + 1
with open('$stats_file', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
"
}

# 显示最终统计
show_final_stats() {
    local project_name="$1"
    local start_time="$2"
    local project_path=$(get_project_path "$project_name")
    local stats_file="$project_path/run_stats.json"

    local current_time=$(date +%s)
    local total_elapsed=$((current_time - start_time))
    local hours=$((total_elapsed / 3600))
    local minutes=$(((total_elapsed % 3600) / 60))
    local seconds=$((total_elapsed % 60))

    local success_count=0
    local failure_count=0

    if [ -f "$stats_file" ]; then
        success_count=$(python3 -c "import json; print(json.load(open('$stats_file')).get('success_count', 0))")
        failure_count=$(python3 -c "import json; print(json.load(open('$stats_file')).get('failure_count', 0))")
    fi

    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "                     📊 运行统计报告"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    echo "  项目名称:     $project_name"
    echo "  总运行时间:   ${hours}h ${minutes}m ${seconds}s"
    echo "  成功任务数:   $success_count"
    echo "  失败任务数:   $failure_count"
    echo "  成功率:       $(python3 -c "total=$success_count+$failure_count; print(f'{($success_count/total*100):.1f}%' if total>0 else 'N/A')")"
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
}

# 显示实时监控状态
show_monitor_status() {
    local project_name="$1"
    local project_path=$(get_project_path "$project_name")
    local stats_file="$project_path/run_stats.json"
    local progress=$(get_project_progress "$project_name")

    # 检查项目是否存在
    if ! project_exists "$project_name"; then
        log_error "项目 '$project_name' 不存在"
        return 1
    fi

    # 检查是否有运行统计
    if [ ! -f "$stats_file" ]; then
        echo ""
        echo "─────────────────────────────────────────────────────────────────"
        echo -e "${CYAN}项目: $project_name${NC}"
        echo "─────────────────────────────────────────────────────────────────"
        echo "  状态:     $(get_project_status "$project_name")"
        echo "  进度:     $progress"
        echo ""
        echo "  💡 尚未开始运行，或运行统计不可用"
        echo "─────────────────────────────────────────────────────────────────"
        return 0
    fi

    # 读取统计信息
    local status=$(python3 -c "import json; print(json.load(open('$stats_file')).get('status', 'unknown'))")
    local start_time=$(python3 -c "import json; print(json.load(open('$stats_file')).get('start_time', ''))")
    local elapsed=$(python3 -c "import json; print(json.load(open('$stats_file')).get('elapsed_seconds', 0))")
    local current_task_id=$(python3 -c "import json; print(json.load(open('$stats_file')).get('current_task_id', ''))")
    local current_task_desc=$(python3 -c "import json; print(json.load(open('$stats_file')).get('current_task_desc', ''))")
    local current_iteration=$(python3 -c "import json; print(json.load(open('$stats_file')).get('current_iteration', 0))")
    local max_iterations=$(python3 -c "import json; print(json.load(open('$stats_file')).get('max_iterations', 100))")
    local success_count=$(python3 -c "import json; print(json.load(open('$stats_file')).get('success_count', 0))")
    local failure_count=$(python3 -c "import json; print(json.load(open('$stats_file')).get('failure_count', 0))")
    local last_update=$(python3 -c "import json; print(json.load(open('$stats_file')).get('last_update', ''))")

    # 计算运行时间
    local hours=$((elapsed / 3600))
    local minutes=$(((elapsed % 3600) / 60))
    local seconds=$((elapsed % 60))

    # 计算成功率
    local total=$((success_count + failure_count))
    local success_rate="N/A"
    if [ $total -gt 0 ]; then
        success_rate=$(python3 -c "print(f'{($success_count/$total*100):.1f}%')")
    fi

    # 计算预估剩余时间
    local remaining_tasks=$(echo "$progress" | cut -d'/' -f2)
    local done_tasks=$(echo "$progress" | cut -d'/' -f1)
    local pending_tasks=$((remaining_tasks - done_tasks))

    local avg_time_per_task="N/A"
    local estimated_remaining="N/A"
    if [ $done_tasks -gt 0 ] && [ $elapsed -gt 0 ]; then
        avg_time_per_task=$((elapsed / done_tasks))
        local est_seconds=$((pending_tasks * avg_time_per_task))
        local est_hours=$((est_seconds / 3600))
        local est_minutes=$(((est_seconds % 3600) / 60))
        estimated_remaining="${est_hours}h ${est_minutes}m"
        avg_time_per_task="$((avg_time_per_task / 60))m"
    fi

    # 状态图标
    local status_icon
    case $status in
        running) status_icon="🔄 运行中" ;;
        paused) status_icon="⏸️  已暂停" ;;
        completed) status_icon="✅ 已完成" ;;
        blocked) status_icon="🚫 已阻塞" ;;
        stopped) status_icon="⏹️  已停止" ;;
        *) status_icon="❓ $status" ;;
    esac

    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo -e "${CYAN}                   📊 实时监控 - $project_name${NC}"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    echo "  状态:           $status_icon"
    echo "  开始时间:       $start_time"
    echo "  运行时间:       ${hours}h ${minutes}m ${seconds}s"
    echo "  最后更新:       $last_update"
    echo ""
    echo "───────────────────────────────────────────────────────────────"
    echo "                      📈 任务进度"
    echo "───────────────────────────────────────────────────────────────"
    echo ""
    echo "  当前迭代:       $current_iteration / $max_iterations"
    echo "  任务完成:       $progress"
    echo "  待完成任务:     $pending_tasks"
    echo ""

    if [ -n "$current_task_id" ]; then
        echo "  当前任务:       ${GREEN}$current_task_id${NC}"
        echo "  任务描述:       $current_task_desc"
        echo ""
    fi

    echo "───────────────────────────────────────────────────────────────"
    echo "                      📊 执行统计"
    echo "───────────────────────────────────────────────────────────────"
    echo ""
    echo "  成功任务数:     ${GREEN}$success_count${NC}"
    echo "  失败任务数:     ${RED}$failure_count${NC}"
    echo "  成功率:         $success_rate"
    echo "  平均任务时间:   $avg_time_per_task"
    echo ""
    echo "───────────────────────────────────────────────────────────────"
    echo "                      ⏱️  预估"
    echo "───────────────────────────────────────────────────────────────"
    echo ""
    echo "  预估剩余时间:   $estimated_remaining"
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
}

# 持续监控模式
monitor_loop() {
    local project_name="$1"
    local refresh_interval="${2:-5}"
    local project_path=$(get_project_path "$project_name")

    if ! project_exists "$project_name"; then
        log_error "项目 '$project_name' 不存在"
        return 1
    fi

    log_info "开始监控项目: $project_name (每 ${refresh_interval}s 刷新一次, Ctrl+C 退出)"
    log_info "提示: 使用 'watch -n ${refresh_interval} ./claude-coder.sh monitor $project_name' 获得更好的显示效果"
    echo ""

    # 记录监控开始时间
    local monitor_start=$(date +%s)

    while true; do
        # 先清屏再显示，避免输出混乱
        clear

        # 调用显示状态函数
        show_monitor_status_v2 "$project_name" "$monitor_start"

        # 检查是否已结束
        local stats_file="$project_path/run_stats.json"
        if [ -f "$stats_file" ]; then
            local status=$(python3 -c "import json; print(json.load(open('$stats_file')).get('status','unknown'))" 2>/dev/null || echo "unknown")
            if [[ "$status" == "completed" ]] || [[ "$status" == "blocked" ]] || [[ "$status" == "stopped" ]]; then
                echo ""
                log_info "项目已结束，退出监控"
                break
            fi
        fi

        # 显示下次刷新倒计时
        echo ""
        echo -e "${CYAN}[按 Ctrl+C 退出监控]${NC}"

        sleep $refresh_interval
    done
}

# 显示实时监控状态（v2 - 独立计算时间）
show_monitor_status_v2() {
    local project_name="$1"
    local monitor_start="$2"
    local project_path=$(get_project_path "$project_name")
    local stats_file="$project_path/run_stats.json"
    local progress=$(get_project_progress "$project_name")

    # 检查是否有运行统计
    if [ ! -f "$stats_file" ]; then
        echo ""
        echo "═══════════════════════════════════════════════════════════════"
        echo -e "${CYAN}                   📊 实时监控 - $project_name${NC}"
        echo "═══════════════════════════════════════════════════════════════"
        echo ""
        echo "  状态:           $(get_project_status "$project_name")"
        echo "  进度:           $progress"
        echo ""
        echo "  💡 尚未开始运行，或运行统计不可用"
        echo "═══════════════════════════════════════════════════════════════"
        return 0
    fi

    # 读取统计信息
    local status=$(python3 -c "import json; print(json.load(open('$stats_file')).get('status', 'unknown'))" 2>/dev/null || echo "unknown")
    local start_time=$(python3 -c "import json; print(json.load(open('$stats_file')).get('start_time', ''))" 2>/dev/null || echo "")
    local current_task_id=$(python3 -c "import json; print(json.load(open('$stats_file')).get('current_task_id', ''))" 2>/dev/null || echo "")
    local current_task_desc=$(python3 -c "import json; print(json.load(open('$stats_file')).get('current_task_desc', ''))" 2>/dev/null || echo "")
    local current_iteration=$(python3 -c "import json; print(json.load(open('$stats_file')).get('current_iteration', 0))" 2>/dev/null || echo "0")
    local max_iterations=$(python3 -c "import json; print(json.load(open('$stats_file')).get('max_iterations', 100))" 2>/dev/null || echo "100")
    local success_count=$(python3 -c "import json; print(json.load(open('$stats_file')).get('success_count', 0))" 2>/dev/null || echo "0")
    local failure_count=$(python3 -c "import json; print(json.load(open('$stats_file')).get('failure_count', 0))" 2>/dev/null || echo "0")
    local last_task_duration=$(python3 -c "import json; print(json.load(open('$stats_file')).get('last_task_duration', 0))" 2>/dev/null || echo "0")

    # 独立计算运行时间（从监控开始算起）
    local current_time=$(date +%s)
    local elapsed=$((current_time - monitor_start))
    local hours=$((elapsed / 3600))
    local minutes=$(((elapsed % 3600) / 60))
    local seconds=$((elapsed % 60))

    # 计算成功率
    local total=$((success_count + failure_count))
    local success_rate="N/A"
    if [ $total -gt 0 ]; then
        success_rate=$(python3 -c "print(f'{($success_count/$total*100):.1f}%')")
    fi

    # 计算预估剩余时间
    local remaining_tasks=$(echo "$progress" | cut -d'/' -f2)
    local done_tasks=$(echo "$progress" | cut -d'/' -f1)
    local pending_tasks=$((remaining_tasks - done_tasks))

    local avg_time_per_task="N/A"
    local estimated_remaining="N/A"
    if [ $done_tasks -gt 0 ] && [ $elapsed -gt 0 ]; then
        avg_time_per_task=$((elapsed / done_tasks))
        local est_seconds=$((pending_tasks * avg_time_per_task))
        local est_hours=$((est_seconds / 3600))
        local est_minutes=$(((est_seconds % 3600) / 60))
        estimated_remaining="${est_hours}h ${est_minutes}m"
        avg_time_per_task="$((avg_time_per_task / 60))m"
    fi

    # 上一个任务耗时
    local last_task_min=$((last_task_duration / 60))
    local last_task_sec=$((last_task_duration % 60))

    # 状态图标
    local status_icon
    case $status in
        running) status_icon="🔄 运行中" ;;
        paused) status_icon="⏸️  已暂停" ;;
        completed) status_icon="✅ 已完成" ;;
        blocked) status_icon="🚫 已阻塞" ;;
        stopped) status_icon="⏹️  已停止" ;;
        *) status_icon="❓ $status" ;;
    esac

    # 当前时间
    local now=$(date "+%Y-%m-%d %H:%M:%S")

    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo -e "${CYAN}                   📊 实时监控 - $project_name${NC}"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    echo "  状态:           $status_icon"
    echo "  开始时间:       $start_time"
    echo "  运行时间:       ${hours}h ${minutes}m ${seconds}s"
    echo "  当前时间:       $now"
    echo ""
    echo "───────────────────────────────────────────────────────────────"
    echo "                      📈 任务进度"
    echo "───────────────────────────────────────────────────────────────"
    echo ""
    echo "  当前迭代:       $current_iteration / $max_iterations"
    echo "  任务完成:       $progress"
    echo "  待完成任务:     $pending_tasks"
    echo ""

    if [ -n "$current_task_id" ]; then
        echo -e "  当前任务:       ${GREEN}$current_task_id${NC}"
        echo "  任务描述:       $current_task_desc"
        if [ $last_task_duration -gt 0 ]; then
            echo "  上次耗时:       ${last_task_min}m ${last_task_sec}s"
        fi
        echo ""
    fi

    echo "───────────────────────────────────────────────────────────────"
    echo "                      📊 执行统计"
    echo "───────────────────────────────────────────────────────────────"
    echo ""
    echo -e "  成功任务数:     ${GREEN}$success_count${NC}"
    echo -e "  失败任务数:     ${RED}$failure_count${NC}"
    echo "  成功率:         $success_rate"
    echo "  平均任务时间:   $avg_time_per_task"
    echo ""
    echo "───────────────────────────────────────────────────────────────"
    echo "                      ⏱️  预估"
    echo "───────────────────────────────────────────────────────────────"
    echo ""
    echo "  预估剩余时间:   $estimated_remaining"
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
}

# 暂停项目
pause_project() {
    local project_name="$1"

    if ! project_exists "$project_name"; then
        log_error "项目 '$project_name' 不存在"
        return 1
    fi

    update_project_meta "$project_name" "status" "paused"
    update_project_meta "$project_name" "paused_at" "$(date "+%Y-%m-%d %H:%M:%S")"
    log_success "项目 '$project_name' 已暂停"
}

# 恢复项目
resume_project() {
    local project_name="$1"

    if ! project_exists "$project_name"; then
        log_error "项目 '$project_name' 不存在"
        return 1
    fi

    local status=$(get_project_status "$project_name")
    if [ "$status" != "paused" ]; then
        log_warning "项目状态为 '$status'，不是暂停状态"
    fi

    update_project_meta "$project_name" "status" "ready"
    update_project_meta "$project_name" "paused_at" "null"
    log_success "项目 '$project_name' 已恢复"
}

# 归档项目
archive_project() {
    local project_name="$1"

    if ! project_exists "$project_name"; then
        log_error "项目 '$project_name' 不存在"
        return 1
    fi

    local project_path=$(get_project_path "$project_name")
    local archive_path="$HISTORY_DIR/$project_name-$(date '+%Y%m%d')"

    mv "$project_path" "$archive_path"
    log_success "项目 '$project_name' 已归档到: $archive_path"
}

# 显示项目详情
show_project_status() {
    local project_name="$1"

    if ! project_exists "$project_name"; then
        log_error "项目 '$project_name' 不存在"
        return 1
    fi

    local project_path=$(get_project_path "$project_name")
    local status=$(get_project_status "$project_name")
    local progress=$(get_project_progress "$project_name")
    local created=$(get_project_meta "$project_name" "created_at")
    local updated=$(get_project_meta "$project_name" "updated_at")
    local desc=$(get_project_meta "$project_name" "description")

    echo ""
    echo "─────────────────────────────────────────────────────────────────"
    echo -e "${CYAN}项目: $project_name${NC}"
    echo "─────────────────────────────────────────────────────────────────"
    echo "  状态:     $status"
    echo "  进度:     $progress"
    echo "  创建时间: $created"
    echo "  更新时间: $updated"
    echo "  描述:     $desc"
    echo "  路径:     $project_path"
    echo "─────────────────────────────────────────────────────────────────"

    # 显示任务列表
    if [ -f "$project_path/feature_list.json" ]; then
        echo ""
        echo -e "${CYAN}任务列表:${NC}"
        python3 << PYEOF
import json
with open('$project_path/feature_list.json') as f:
    data = json.load(f)
features = data.get('features', [])
order = data.get('implementation_order', [f['id'] for f in features])

for i, fid in enumerate(order, 1):
    f = next((x for x in features if x['id'] == fid), None)
    if f:
        icon = "✅" if f.get('passes', False) else "⬜"
        priority = f.get('priority', '?')[0].upper()
        desc = f.get('description', '')[:40]
        print(f"  {i:2}. {icon} [{priority}] {fid}: {desc}")
PYEOF
    fi
}
