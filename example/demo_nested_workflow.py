"""
嵌套 Workflow 演示程序
展示如何使用 ImageGenerateTask 进行嵌套的图片生成工作流
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from banana_gen import (
    UnifiedImageGenerator, ImageGenerateTask, LocalImage, ImageData,
    Prompt, PromptRegistry, TaskManager, ImageFolder
)


def demo_nested_workflow(file_path="example/pictures"):
    """演示嵌套 workflow"""
    print("🚀 嵌套 Workflow 演示")
    print("=" * 50)
    
    # 1. 初始化生成器
    print("🔑 初始化生成器...")
    generator = UnifiedImageGenerator(max_workers=1)
    
    # 2. 创建输入图片
    print("\n🖼️ 创建输入图片...")
    input_image = LocalImage(
        file_path=file_path,
        fallback_paths=[]
    )
    
    if not input_image.is_valid():
        print("❌ 输入图片无效，使用示例图片")
        # 创建一个示例图片数据
        input_image = ImageData(b"fake_image_data", "PNG")
    
    # 3. 创建嵌套的 ImageGenerateTask
    print("\n🔗 创建嵌套的 ImageGenerateTask...")
    
    # 第一层：图1 → prompt1 → 图2
    print("   创建 task1: 图1 → prompt1 → 图2")
    task1 = ImageGenerateTask(
        input_images=[input_image],
        prompt="""
        Generate a real-life photo of an Asian cosplayer portraying this character, with highly realistic skin texture. The cosplayer’s hairstyle, accessories, and clothing must match the character’s.

        The cosplayer is standing in the front of a green screen. The full body is visible. The cosplayer is holding nothing. 

        """
    )
    
    # 第二层：图2 → prompt2 → 图3
    print("   创建 task2: 图2 → prompt2 → 图3")
    task2 = ImageGenerateTask(
        input_images=[input_image],  # 使用 task1 作为输入
        prompt="""
        Convert the CG to a storyboard drawn by 2B black pencil. Generate the image.

        """
    )
    
    # 第三层：图3 → prompt3 → 图4
    print("   创建 task3: 图3 → prompt3 → 图4")
    task3 = ImageGenerateTask(
        input_images=[task1,task2],  # 使用 task2 作为输入
        prompt="""
        Make the cosplayer from image 1 cosplaying the scene from the storyboard of image 2. The cosplayer's posture and angle should be the same with image 2, meticulously recreating the iconic scene from image 2. The photo is captured in reality, emphasizing hyper-realism and avoiding any hint of 2D, anime, or 3D rendering.
        """
    )
    
    # 4. 执行嵌套 workflow
    print("\n⚡ 执行嵌套 workflow...")
    print("   执行 task3 会自动执行 task2，task2 会自动执行 task1")
    
    try:
        success = task3.execute(generator)
        
        if success:
            print("✅ 嵌套 workflow 执行成功！")
            
            # 5. 保存最终结果
            if task3.generated_image:
                output_path = "example/outputs/"+ os.path.basename(file_path).split(".")[0] + ".png"
                os.makedirs("example/outputs", exist_ok=True)
                
                if task3.generated_image.save_to_file(output_path):
                    print(f"📁 最终图片已保存到: {output_path}")
                else:
                    print("❌ 保存最终图片失败")
            
            # 6. 显示执行状态
            print("\n📊 执行状态:")
            print(f"   task1 执行状态: {task1.is_executed}, 成功: {task1.is_success}")
            print(f"   task2 执行状态: {task2.is_executed}, 成功: {task2.is_success}")
            print(f"   task3 执行状态: {task3.is_executed}, 成功: {task3.is_success}")
            
            # 7. 检查中间图片是否保存
            print("\n💾 中间图片保存情况:")
            print("   task1 生成的图片: 只在内存中，未保存到文件")
            print("   task2 生成的图片: 只在内存中，未保存到文件")
            print("   task3 生成的图片: 已保存到文件")
            
        else:
            print("❌ 嵌套 workflow 执行失败")
            print(f"   错误原因: {task3.error_reason}")
            
    except Exception as e:
        print(f"❌ 执行过程中发生异常: {e}")
        import traceback
        traceback.print_exc()


def demo_manual_nested_execution():
    """演示手动嵌套执行"""
    print("\n\n🔧 手动嵌套执行演示")
    print("=" * 50)
    
    # 1. 初始化生成器
    generator = UnifiedImageGenerator(max_workers=2)
    
    # 2. 创建输入图片
    input_image = LocalImage(
        file_path="/path/to/input.jpg",
        fallback_paths=["example/test_images/sample.jpg"]
    )
    
    if not input_image.is_valid():
        input_image = ImageData(b"fake_image_data", "PNG")
    
    # 3. 手动执行每一层
    print("📝 手动执行每一层...")
    
    # 第一层
    print("   执行 task1...")
    task1 = ImageGenerateTask([input_image], "Transform to cartoon style")
    success1 = task1.execute(generator)
    print(f"   task1 结果: {success1}")
    
    if success1:
        # 第二层
        print("   执行 task2...")
        task2 = ImageGenerateTask([task1], "Add beautiful background")
        success2 = task2.execute(generator)
        print(f"   task2 结果: {success2}")
        
        if success2:
            # 第三层
            print("   执行 task3...")
            task3 = ImageGenerateTask([task2], "Apply vintage filter")
            success3 = task3.execute(generator)
            print(f"   task3 结果: {success3}")
            
            if success3:
                # 保存最终结果
                output_path = "example/outputs/manual_nested_result.png"
                os.makedirs("example/outputs", exist_ok=True)
                
                if task3.generated_image.save_to_file(output_path):
                    print(f"📁 最终图片已保存到: {output_path}")
                else:
                    print("❌ 保存最终图片失败")



def main():
    print("🎯 嵌套 Workflow 演示程序")
    print("这个程序展示了如何使用 ImageGenerateTask 进行嵌套的图片生成工作流")
    print("=" * 70)
    
    try:
        # 演示自动嵌套执行
        pic_folder="example/pictures"
        for file_path in os.listdir(pic_folder):
            if (file_path.endswith(".jpg") or file_path.endswith(".png") or file_path.endswith(".jpeg") or file_path.endswith(".webp") )and not file_path.startswith("."):
                demo_nested_workflow(os.path.join(pic_folder, file_path))
        
        # 演示手动嵌套执行
        #demo_manual_nested_execution()
        
        
        print("\n🎉 演示完成！")
        print("\n📋 总结:")
        print("1. 嵌套 workflow 是可行的")
        print("2. 中间图片只在内存中传递，不会保存到文件")
        print("3. 只有最终图片会保存到文件")
        print("4. 支持自动嵌套执行和手动嵌套执行")
        print("5. 支持图片文件夹作为源头输入")
        
    except Exception as e:
        print(f"❌ 演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
