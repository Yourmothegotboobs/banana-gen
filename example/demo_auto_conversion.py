"""
自动转换演示程序
展示 ImageGenerateTask.create_task() 如何自动处理单个/多个图片的情况
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from banana_gen import (
    UnifiedImageGenerator, ImageGenerateTask, LocalImage, ImageFolder,
    Prompt, PromptRegistry
)


def demo_auto_conversion():
    """演示自动转换功能"""
    print("🚀 自动转换演示")
    print("=" * 50)
    
    # 1. 初始化生成器
    generator = UnifiedImageGenerator(max_workers=2)
    
    # 2. 创建不同类型的输入
    print("🖼️ 创建不同类型的输入...")
    
    # 单个图片
    single_image = LocalImage(
        file_path="example.jpg",
        fallback_paths=[]
    )
    
    # 文件夹（多个图片）
    folder_images = ImageFolder(
        folder_path="example/",
        fallback_paths=[]
    )
    
    # 3. 演示自动转换
    print("\n🔄 演示自动转换...")
    
    # 情况1：单个图片输入
    print("   情况1：单个图片输入")
    task1 = ImageGenerateTask.create_task([single_image], "Transform to cartoon style")
    print(f"   结果类型: {type(task1).__name__}")
    print(f"   是否单个任务: {isinstance(task1, ImageGenerateTask)}")
    
    # 情况2：文件夹输入
    print("   情况2：文件夹输入")
    task2 = ImageGenerateTask.create_task([folder_images], "Transform to cartoon style")
    print(f"   结果类型: {type(task2).__name__}")
    print(f"   是否任务列表: {hasattr(task2, '_tasks')}")
    
    # 情况3：混合输入
    print("   情况3：混合输入（单个图片 + 文件夹）")
    task3 = ImageGenerateTask.create_task([single_image, folder_images], "Transform to cartoon style")
    print(f"   结果类型: {type(task3).__name__}")
    print(f"   是否任务列表: {hasattr(task3, '_tasks')}")
    
    # 4. 展示用户友好的使用方式
    print("\n👥 用户友好的使用方式:")
    print("   # 用户不需要关心内部转换")
    print("   task = ImageGenerateTask.create_task([folder_images], 'prompt')")
    print("   # 系统自动判断是创建单个任务还是任务列表")
    print("   # 用户只需要调用 execute() 或 to_image_data() 即可")


def demo_nested_with_auto_conversion():
    """演示嵌套 workflow 与自动转换的结合"""
    print("\n\n🔗 嵌套 Workflow + 自动转换演示")
    print("=" * 50)
    
    # 1. 初始化生成器
    generator = UnifiedImageGenerator(max_workers=1)
    
    # 2. 创建输入
    folder_source = ImageFolder(
        folder_path="example/pictures",
        fallback_paths=["example/test_images"]
    )
    
    # 3. 创建嵌套 workflow
    print("📝 创建嵌套 workflow...")
    
    # 第一层：文件夹 → prompt1 → 结果1
    print("   第一层：文件夹 → prompt1 → 结果1")
    task1 = ImageGenerateTask.create_task([folder_source], "Transform to cartoon style")
    print(f"   类型: {type(task1).__name__}")
    
    # 第二层：结果1 → prompt2 → 结果2
    print("   第二层：结果1 → prompt2 → 结果2")
    task2 = ImageGenerateTask.create_task([task1], "Add beautiful background")
    print(f"   类型: {type(task2).__name__}")
    
    # 第三层：结果2 → prompt3 → 最终结果
    print("   第三层：结果2 → prompt3 → 最终结果")
    task3 = ImageGenerateTask.create_task([task2], "Apply vintage filter")
    print(f"   类型: {type(task3).__name__}")
    
    print("\n💡 设计优势:")
    print("   1. 用户不需要关心内部类型转换")
    print("   2. 系统自动处理单个/多个图片的情况")
    print("   3. 嵌套 workflow 完全透明")
    print("   4. 类型系统保持清晰")


def main():
    print("🎯 自动转换演示程序")
    print("这个程序展示了 ImageGenerateTask.create_task() 的自动转换功能")
    print("=" * 70)
    
    try:
        # 演示自动转换
        demo_auto_conversion()
        
        # 演示嵌套 workflow
        demo_nested_with_auto_conversion()
        
        print("\n🎉 演示完成！")
        print("\n📋 总结:")
        print("1. ImageGenerateTask.create_task() 自动处理类型转换")
        print("2. 单个图片输入 → 创建 ImageGenerateTask")
        print("3. 多个图片输入 → 创建 ImageGenerateTasks")
        print("4. 用户使用完全透明，不需要关心内部实现")
        print("5. 支持嵌套 workflow 和自动转换的结合")
        
    except Exception as e:
        print(f"❌ 演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
