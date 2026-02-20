#!/bin/bash
# 运行初始化代理
# 用法: ./run-init.sh <需求文档路径>

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查参数
if [ -z "$1" ]; then
    echo "用法: $0 <需求文档路径>"
    echo "示例: $0 ../docs/requirements.md"
    exit 1
fi

REQUIREMENTS_FILE="$1"

# 检查需求文档是否存在
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo "错误: 需求文档不存在: $REQUIREMENTS_FILE"
    exit 1
fi

# 读取需求文档内容
REQUIREMENTS=$(cat "$REQUIREMENTS_FILE")

# 读取初始化代理提示词
INIT_PROMPT=$(cat prompts/initializer.md)

# 组合完整提示词
FULL_PROMPT="${INIT_PROMPT}

---

## 用户需求文档

文件: ${REQUIREMENTS_FILE}

内容:
\`\`\`
${REQUIREMENTS}
\`\`\`
"

echo "========================================="
echo "  初始化代理启动"
echo "  需求文档: $REQUIREMENTS_FILE"
echo "========================================="
echo ""

# 运行 Claude Code
# 使用 --dangerously-skip-permissions 来避免频繁的权限请求
# 如果需要更安全，可以移除此选项
claude --dangerously-skip-permissions "$FULL_PROMPT"

echo ""
echo "========================================="
echo "  初始化完成"
echo "========================================="
echo ""
echo "下一步: 运行 ./run-coder.sh 开始编码"
