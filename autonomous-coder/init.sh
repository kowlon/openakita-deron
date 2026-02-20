#!/bin/bash
# 项目初始化脚本
# 此脚本用于设置开发环境并验证项目可正常运行

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "========================================="
echo "  OpenAkita 项目初始化"
echo "========================================="
echo ""

cd "$PROJECT_ROOT"

# 1. 检查 Python 环境
echo "🔍 检查 Python 环境..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "   ✅ $PYTHON_VERSION"
else
    echo "   ❌ Python3 未安装"
    exit 1
fi

# 2. 检查/创建虚拟环境
echo ""
echo "🔍 检查虚拟环境..."
if [ -d "venv" ]; then
    echo "   ✅ 虚拟环境已存在"
else
    echo "   📦 创建虚拟环境..."
    python3 -m venv venv
    echo "   ✅ 虚拟环境创建完成"
fi

# 3. 激活虚拟环境
echo ""
echo "🔧 激活虚拟环境..."
source venv/bin/activate
echo "   ✅ 已激活"

# 4. 安装依赖
echo ""
echo "📦 安装依赖..."
if [ -f "requirements.txt" ]; then
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    echo "   ✅ 依赖安装完成"
else
    echo "   ⚠️  requirements.txt 不存在，跳过"
fi

# 5. 检查配置文件
echo ""
echo "🔍 检查配置文件..."
if [ -f ".env" ]; then
    echo "   ✅ .env 配置文件存在"
else
    echo "   ⚠️  .env 配置文件不存在"
    echo "   💡 请复制 .env.example 并配置 API 密钥"
fi

# 6. 运行基础测试
echo ""
echo "🧪 运行基础测试..."
if python3 -c "import openakita" 2>/dev/null; then
    echo "   ✅ openakita 模块可导入"
else
    echo "   ⚠️  openakita 模块导入失败"
    echo "   💡 可能需要先安装: pip install -e ."
fi

# 7. 检查数据库
echo ""
echo "🔍 检查数据目录..."
if [ -d "data" ]; then
    echo "   ✅ data 目录存在"
else
    echo "   📁 创建 data 目录..."
    mkdir -p data
    echo "   ✅ 创建完成"
fi

# 8. 显示状态
echo ""
echo "========================================="
echo "  初始化完成!"
echo "========================================="
echo ""
echo "项目根目录: $PROJECT_ROOT"
echo ""
echo "下一步:"
echo "  1. 配置 .env 文件中的 API 密钥"
echo "  2. 运行 'python -m openakita' 启动 CLI"
echo "  3. 或者运行 './autonomous-coder/run-coder.sh' 开始自动编码"
echo ""
