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

# 获取下一个待完成任务
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
run_coder_once() {
    local project_name="$1"
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

    # 创建日志目录
    mkdir -p "$project_path/logs"
    local log_file="$project_path/logs/task-$(date '+%Y%m%d-%H%M%S').log"

    # 运行 Claude (从项目根目录)
    cd "$SCRIPT_DIR/.."

    # 使用 script 命令捕获完整交互输出，同时显示在终端
    if command -v script &> /dev/null; then
        script -q "$log_file" claude --dangerously-skip-permissions "$prompt"
    else
        # 如果没有 script 命令，直接运行并 tee 到日志
        claude --dangerously-skip-permissions "$prompt" 2>&1 | tee "$log_file"
    fi

    echo "$log_file"
}

# 运行编码代理（循环）
run_coder_loop() {
    local project_name="$1"
    local max_iterations="${2:-100}"
    local interval="${3:-5}"
    local project_path=$(get_project_path "$project_name")

    # 更新状态为 running
    update_project_meta "$project_name" "status" "running"

    log_header "自动编码循环启动"
    log_info "项目: $project_name"
    log_info "最大迭代: $max_iterations"
    log_info "间隔: ${interval}s"

    local iteration=0
    local consecutive_failures=0
    local MAX_CONSECUTIVE_FAILURES=3

    while [ $iteration -lt $max_iterations ]; do
        iteration=$((iteration + 1))

        # 检查是否被暂停
        local status=$(get_project_status "$project_name")
        if [ "$status" = "paused" ]; then
            log_warning "项目已被暂停"
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

        # 记录完成数量
        local before_count=$(get_project_progress "$project_name" | cut -d'/' -f1)

        # 运行编码代理
        log_info "启动编码代理..."
        run_coder_once "$project_name"

        # 检查是否完成
        local after_count=$(get_project_progress "$project_name" | cut -d'/' -f1)
        if [ "$after_count" -gt "$before_count" ]; then
            log_success "任务完成！($before_count -> $after_count)"
            consecutive_failures=0
        else
            log_warning "任务可能未完成"
            consecutive_failures=$((consecutive_failures + 1))

            if [ $consecutive_failures -ge $MAX_CONSECUTIVE_FAILURES ]; then
                log_error "连续失败 $consecutive_failures 次，停止循环"
                update_project_meta "$project_name" "status" "blocked"
                return 1
            fi
        fi

        sleep $interval
    done

    log_warning "达到最大迭代次数: $max_iterations"
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
