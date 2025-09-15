#!/bin/bash

echo "🚀 Banana Gen Web UI 启动中..."
echo

# 检查 Python 是否安装
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    echo "请先安装 Python 3.7+"
    exit 1
fi

# 检查 Python 版本
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
required_version="3.7"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 版本过低，需要 3.7+，当前版本: $python_version"
    exit 1
fi

# 启动 Web UI
python3 start.py
