#!/usr/bin/env python3
"""
Banana Gen Web UI 启动脚本 - 重构版本
"""

import os
import sys
import subprocess

def main():
    print("🚀 Banana Gen Web UI (重构版) 启动中...")
    
    # 检查 Python 版本
    if sys.version_info < (3, 8):
        print("❌ 需要 Python 3.8 或更高版本")
        sys.exit(1)
    
    # 检查依赖
    try:
        import flask
        print(f"✅ Flask {flask.__version__} 已安装")
    except ImportError:
        print("❌ Flask 未安装，正在安装...")
        subprocess.run([sys.executable, "-m", "pip", "install", "flask"], check=True)
    
    # 设置环境变量
    os.environ['FLASK_APP'] = 'app_new.py'
    os.environ['FLASK_ENV'] = 'development'
    
    # 启动应用
    print("📱 访问地址: http://localhost:8888")
    print("📋 任务管理: http://localhost:8888/tasks")
    print("🖼️ 图片来源: http://localhost:8888/sources")
    print("📁 输出文件: http://localhost:8888/outputs")
    print("📊 系统状态: http://localhost:8888/status")
    print("=" * 50)
    
    try:
        # 运行 Flask 应用
        from app_new import app
        app.run(debug=True, host='0.0.0.0', port=8888)
    except KeyboardInterrupt:
        print("\n👋 Web UI 已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
