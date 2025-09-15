"""
简化的任务管理器演示程序
展示使用 TaskManager.create_with_auto_fallback 的便捷方法
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from banana_gen import (
    UnifiedImageGenerator, TaskManager,
    Prompt, PromptRegistry
)


def main():
    print("🚀 简化的任务管理器演示程序")
    print("=" * 50)
    
    # 1. 初始化统一生图调度管理器
    print("🔑 初始化统一生图调度管理器...")
    try:
        generator = UnifiedImageGenerator(
            key_source=None,  # 使用默认的 banana_gen/keys 文件夹
            max_workers=2,    # 并行度设为2
            max_retries=3
        )
        print("✅ 统一生图调度管理器初始化成功")
    except Exception as e:
        print(f"❌ 统一生图调度管理器初始化失败: {e}")
        return
    
    # 2. 配置输入图片（使用便捷的配置方式）
    print("\n🖼️ 配置输入图片...")
    input_configs = [
        {
            "type": "folder",
            "main_path": "example/",
            "fallback_paths": ["example/test_images", "example/outputs"]
        },
        {
            "type": "local_image", 
            "main_path": "example.jpg",
            "fallback_paths": ["example/test_images/sample.jpg", "example/outputs/real_api_demo_01.png"]
        }
    ]
    
    # 3. 配置提示词和替换规则
    print("\n📝 配置提示词和替换规则...")
    
    # 通过 ID 从注册表获取 Prompt 对象
    registry = PromptRegistry()
    prompt_ids = ["p2_change_people", "p1_pose_skeleton"]  # 使用现有的 prompt ID
    
    prompts = registry.get_prompts_by_ids(prompt_ids)
    print(f"   提示词数量: {len(prompts)}")
    for i, prompt in enumerate(prompts):
        print(f"   Prompt {i+1}: {prompt.get_info()}")
    string_replace_list = [
        ["photorealistic", "cartoon", "anime", "realistic"],    # 第一组替换：风格
        ["seamless", "perfect", "flawless", "seamless"]         # 第二组替换：质量描述
    ]
    
    # 4. 使用便捷方法创建任务管理器
    print("\n📋 创建任务管理器...")
    try:
        task_manager = TaskManager.create_with_auto_fallback(
            generator=generator,
            input_configs=input_configs,
            prompts=prompts,
            string_replace_list=string_replace_list,
            output_dir="example/outputs/simple_task_manager",
            filename_template="{base}-{prompt_idx}-{replace_idx}-{image_idx}.png",
            base_name="simple_demo"
        )
        print("✅ 任务管理器创建成功")
    except Exception as e:
        print(f"❌ 任务管理器创建失败: {e}")
        return
    
    # 5. 一键运行（包含用户确认、进度监控、结果显示）
    success = task_manager.run_with_interactive_monitoring()
    
    if success:
        print("\n🎉 任务完成！")
    else:
        print("\n❌ 任务未完成")


if __name__ == "__main__":
    main()
