"""
超级简化的任务管理器演示程序
只需要几行代码就能完成复杂的图片生成任务
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from banana_gen import (
    UnifiedImageGenerator, TaskManager
)


def main():
    print("🚀 超级简化的任务管理器演示")
    print("=" * 50)
    
    # 1. 初始化生成器
    generator = UnifiedImageGenerator(max_workers=2)
    
    # 2. 配置输入图片和替换规则
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
    
    prompts = ["p2_change_people"]
    string_replace_list = [
        ["photorealistic", "cartoon", "anime"],
        ["seamless", "perfect", "flawless"]
    ]
    
    # 3. 创建任务管理器
    task_manager = TaskManager.create_with_auto_fallback(
        generator=generator,
        input_configs=input_configs,
        prompts=prompts,
        string_replace_list=string_replace_list,
        output_dir="example/outputs/ultra_simple",
        base_name="ultra_simple"
    )
    
    # 4. 一键运行（包含用户确认、进度监控、结果显示）
    success = task_manager.run_with_interactive_monitoring()
    
    if success:
        print("\n🎉 任务完成！")
    else:
        print("\n❌ 任务未完成")


if __name__ == "__main__":
    main()
