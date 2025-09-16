#!/usr/bin/env python3
"""
Banana Gen Web UI 启动脚本 - 旧版本
"""

import os
import sys
import subprocess
import threading

def check_dependencies():
    """检查依赖是否安装"""
    try:
        import flask
        print("✅ Flask 已安装")
    except ImportError:
        print("❌ Flask 未安装，正在安装依赖...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ 依赖安装完成")

def create_directories():
    """创建必要的目录"""
    directories = [
        "webui/keys",
        "webui/uploads", 
        "webui/outputs",
        "logs"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ 目录已创建: {directory}")

def open_browser():
    return None  # 移除自动打开浏览器逻辑

def main():
    """主函数"""
    print("🚀 Banana Gen Web UI 启动中...")
    
    # 检查依赖
    check_dependencies()
    
    # 创建目录
    create_directories()
    
    # 启动 Flask 应用
    print("\n📱 启动 Web UI...")
    print("🌐 访问地址: http://localhost:8888")
    print("🔑 Key 管理: http://localhost:8888/keys")
    print("📝 Prompt 管理: http://localhost:8888/prompts")
    print("🖼️ 图片来源管理: http://localhost:8888/sources")
    print("⚡ 任务执行: http://localhost:8888/execute")
    print("📊 日志查看: http://localhost:8888/logs")
    print("📁 创意相册: http://localhost:8888/outputs")
    print("\n按 Ctrl+C 停止服务")
    
    # 不再自动打开浏览器，避免重复打开
    
    try:
        # 导入并运行应用
        from app import app
        app.run(debug=True, host='0.0.0.0', port=8888)
    except ImportError as e:
        print(f"❌ 启动失败: {e}")
        print("💡 请确保在 banana-gen 项目根目录下运行此脚本")
        print("💡 或者使用: cd banana-gen && python webui/start_webui.py")
        sys.exit(1)

if __name__ == "__main__":
    main()
