#!/bin/bash
# 长时自动化编程系统 v2.0 - 统一入口
# 参考: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
#
# 用法: ./claude-coder.sh <command> [args]
#
# 命令:
#   new <项目名> [--from requirement.md]  创建新项目
#   list                                  列出所有项目
#   status <项目名>                       查看项目详情
#   run <项目名> [--once] [--max N]       运行项目
#   pause <项目名>                        暂停项目
#   resume <项目名>                       恢复项目
#   archive <项目名>                      归档项目
#   help                                  显示帮助

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/core/lib.sh"

# 显示帮助
show_help() {
    cat << EOF
长时自动化编程系统 v2.0
参考: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

用法: ./claude-coder.sh <command> [args]

命令:
  项目管理:
    new <项目名> [--from <file>]    创建新项目
    list                            列出所有项目
    status <项目名>                 查看项目详情

  运行控制:
    run <项目名> [--once] [--max N] 运行项目
                                    --once: 只运行一次
                                    --max N: 最多 N 次迭代
    pause <项目名>                  暂停项目
    resume <项目名>                 恢复项目

  归档:
    archive <项目名>                归档完成的项目

  帮助:
    help                            显示此帮助信息

示例:
  # 创建新项目
  ./claude-coder.sh new my-project --from requirement.md

  # 列出所有项目
  ./claude-coder.sh list

  # 运行项目（持续直到完成）
  ./claude-coder.sh run my-project

  # 只运行一次
  ./claude-coder.sh run my-project --once

  # 暂停项目
  ./claude-coder.sh pause my-project

  # 恢复项目
  ./claude-coder.sh resume my-project

EOF
}

# 解析命令
command="$1"
shift || true

case "$command" in
    new)
        project_name=""
        requirement_file=""

        while [[ $# -gt 0 ]]; do
            case "$1" in
                --from)
                    requirement_file="$2"
                    shift 2
                    ;;
                *)
                    if [ -z "$project_name" ]; then
                        project_name="$1"
                    fi
                    shift
                    ;;
            esac
        done

        if [ -z "$project_name" ]; then
            log_error "请指定项目名称"
            echo "用法: ./claude-coder.sh new <项目名> [--from <需求文件>]"
            exit 1
        fi

        create_project "$project_name" "$requirement_file"
        ;;

    list)
        list_projects
        ;;

    status)
        if [ -z "$1" ]; then
            log_error "请指定项目名称"
            exit 1
        fi
        show_project_status "$1"
        ;;

    run)
        project_name=""
        run_once=false
        max_iterations=100

        while [[ $# -gt 0 ]]; do
            case "$1" in
                --once)
                    run_once=true
                    shift
                    ;;
                --max)
                    max_iterations="$2"
                    shift 2
                    ;;
                *)
                    if [ -z "$project_name" ]; then
                        project_name="$1"
                    fi
                    shift
                    ;;
            esac
        done

        if [ -z "$project_name" ]; then
            log_error "请指定项目名称"
            exit 1
        fi

        if ! project_exists "$project_name"; then
            log_error "项目 '$project_name' 不存在"
            exit 1
        fi

        if [ "$run_once" = true ]; then
            run_coder_once "$project_name"
        else
            run_coder_loop "$project_name" "$max_iterations"
        fi
        ;;

    pause)
        if [ -z "$1" ]; then
            log_error "请指定项目名称"
            exit 1
        fi
        pause_project "$1"
        ;;

    resume)
        if [ -z "$1" ]; then
            log_error "请指定项目名称"
            exit 1
        fi
        resume_project "$1"
        ;;

    switch)
        if [ -z "$1" ]; then
            log_error "请指定项目名称"
            exit 1
        fi
        # TODO: 实现切换功能 - 暂停当前运行的项目，恢复指定项目
        log_warning "switch 命令尚未完全实现"
        resume_project "$1"
        ;;

    archive)
        if [ -z "$1" ]; then
            log_error "请指定项目名称"
            exit 1
        fi
        archive_project "$1"
        ;;

    help|--help|-h)
        show_help
        ;;

    *)
        if [ -n "$command" ]; then
            log_error "未知命令: $command"
        fi
        show_help
        exit 1
        ;;
esac
