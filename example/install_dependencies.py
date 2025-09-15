#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
安装 Banana Gen Demo 所需的依赖库
"""

import subprocess
import sys

def install_package(package):
    """安装 Python 包"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ 成功安装: {package}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 安装失败: {package} - {e}")
        return False

def main():
    print("🔧 安装 Banana Gen Demo 依赖库")
    print("=" * 40)
    
    # 需要安装的包
    packages = [
        "google-generativeai",  # Google AI API
        "pillow",              # 图片处理
        "requests",            # HTTP 请求
    ]
    
    success_count = 0
    total_count = len(packages)
    
    for package in packages:
        print(f"📦 安装 {package}...")
        if install_package(package):
            success_count += 1
        print()
    
    print("=" * 40)
    print(f"📊 安装结果: {success_count}/{total_count} 成功")
    
    if success_count == total_count:
        print("🎉 所有依赖库安装完成！")
        print("\n💡 现在可以运行带真实 API 的 demo:")
        print("   python example/demo_with_real_api.py")
    else:
        print("❌ 部分依赖库安装失败，请手动安装")
        print("\n💡 手动安装命令:")
        for package in packages:
            print(f"   pip install {package}")

if __name__ == "__main__":
    main()
