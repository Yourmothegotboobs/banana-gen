@echo off
echo 🚀 Banana Gen Web UI 启动中...
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python 未安装或未添加到 PATH
    echo 请先安装 Python 3.7+
    pause
    exit /b 1
)

REM 启动 Web UI
python start.py

pause
