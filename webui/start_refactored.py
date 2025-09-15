#!/usr/bin/env python3
"""
Banana Gen Web UI 启动脚本 - 完全重构版本
简洁干净，无自动打开浏览器功能
"""

import os
import sys
import subprocess

def check_dependencies():
    """检查依赖是否安装"""
    try:
        import flask
        print("✅ Flask 已安装")
    except ImportError:
        print("❌ Flask 未安装，正在安装依赖...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "flask"])
        print("✅ 依赖安装完成")

def create_directories():
    """创建必要的目录"""
    directories = [
        "webui/uploads", 
        "webui/outputs",
        "logs"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ 目录已创建: {directory}")

def main():
    """主函数"""
    print("🚀 Banana Gen Web UI (重构版) 启动中...")
    
    # 检查依赖
    check_dependencies()
    
    # 创建目录
    create_directories()
    
    # 启动 Flask 应用
    print("\n📱 启动 Web UI...")
    print("🌐 访问地址: http://localhost:8888")
    print("📋 任务管理: http://localhost:8888/tasks")
    print("📁 输出文件: http://localhost:8888/outputs")
    print("📊 系统状态: http://localhost:8888/status")
    print("\n按 Ctrl+C 停止服务")
    
    try:
        # 导入并运行应用
        from app_refactored import app
        app.run(debug=True, host='0.0.0.0', port=8888)
    except ImportError as e:
        print(f"❌ 启动失败: {e}")
        print("💡 请确保在 banana-gen 项目根目录下运行此脚本")
        print("💡 或者使用: cd banana-gen && python webui/start_refactored.py")
        sys.exit(1)

if __name__ == "__main__":
    main()
