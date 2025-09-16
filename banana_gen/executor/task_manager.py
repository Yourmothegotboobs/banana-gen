"""
任务管理器
动态管理图片生成任务，支持内存优化和任务调度
"""

import os
import time
import threading
import itertools
from typing import List, Dict, Any, Optional, Tuple, Union
from enum import IntEnum
from concurrent.futures import ThreadPoolExecutor, Future

from .google_api_manager import UnifiedImageGenerator
from ..images import (
    Image, SingleImage, ImageList, ImageData, LocalImage, UrlImage,
    ImageGenerateTask, ImageFolder, ImageRecursionFolder, ImageGenerateTasks
)
from ..prompts import Prompt


class TaskStatus(IntEnum):
    """任务状态枚举"""
    STOPPED = 0    # 已停止
    RUNNING = 1    # 运行中
    PAUSED = 2     # 已暂停
    COMPLETED = 3  # 已完成


class TaskManager:
    """任务管理器 - 动态管理图片生成任务"""
    
    def __init__(self,
                 generator: UnifiedImageGenerator,
                 input_images: List[Image],
                 prompts: List[Union[str, Prompt]],
                 string_replace_list: List[List[str]],
                 output_dir: str = "outputs",
                 filename_template: str = "{base}-{prompt_idx}-{replace_idx}-{image_idx}.png",
                 base_name: str = "task"):
        """
        初始化任务管理器
        
        Args:
            generator: 统一生图调度管理器
            input_images: 输入图片列表
            prompts: 提示词列表
            string_replace_list: 字符串替换规则列表
            output_dir: 输出目录
            filename_template: 文件名模板
            base_name: 基础名称
        """
        self.generator = generator
        self.input_images = input_images
        self.prompts = prompts
        self.string_replace_list = string_replace_list
        
        # 处理 prompts，确保都是字符串
        self._processed_prompts = []
        for prompt in prompts:
            if isinstance(prompt, Prompt):
                self._processed_prompts.append(prompt.text)
            else:
                self._processed_prompts.append(prompt)
        self.output_dir = output_dir
        self.filename_template = filename_template
        self.base_name = base_name
        
        # 任务状态
        self.status = TaskStatus.STOPPED
        self.status_lock = threading.Lock()
        
        # 任务统计
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'pending_tasks': 0
        }
        self.stats_lock = threading.Lock()
        
        # 任务执行器
        self.executor = None
        self.futures = []
        self.futures_lock = threading.Lock()
        
        # 任务生成器
        self.task_generator = None
        self.generator_lock = threading.Lock()
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"✅ 任务管理器初始化成功")
        print(f"   📁 输出目录: {output_dir}")
        print(f"   🖼️ 输入图片: {len(input_images)} 个")
        print(f"   📝 提示词: {len(self._processed_prompts)} 个")
        print(f"   🔄 替换规则: {len(string_replace_list)} 组")
    
    @staticmethod
    def create_with_auto_fallback(
            generator: UnifiedImageGenerator,
            input_configs: List[Dict[str, Any]],
            prompts: List[Union[str, Prompt]],
            string_replace_list: List[List[str]],
            output_dir: str = "outputs",
            filename_template: str = "{base}-{prompt_idx}-{replace_idx}-{image_idx}.png",
            base_name: str = "task") -> 'TaskManager':
        """
        使用自动回退机制创建任务管理器
        
        Args:
            generator: 统一生图调度管理器
            input_configs: 输入图片配置列表，每个配置包含：
                - type: "folder" | "recursive_folder" | "local_image" | "url_image"
                - main_path: 主路径/URL
                - fallback_paths: 回退路径列表（可选）
            prompts: 提示词列表
            string_replace_list: 字符串替换规则列表
            output_dir: 输出目录
            filename_template: 文件名模板
            base_name: 基础名称
            
        Returns:
            TaskManager: 创建的任务管理器
        """
        input_images = []
        
        for i, config in enumerate(input_configs):
            img_type = config.get('type')
            main_path = config.get('main_path')
            fallback_paths = config.get('fallback_paths', [])
            
            if img_type == "folder":
                img = ImageFolder(main_path, fallback_paths=fallback_paths)
            elif img_type == "recursive_folder":
                img = ImageRecursionFolder(main_path, fallback_paths=fallback_paths)
            elif img_type == "local_image":
                img = LocalImage(main_path, fallback_paths=fallback_paths)
            elif img_type == "url_image":
                img = UrlImage(main_path, fallback_urls=fallback_paths)
            else:
                raise ValueError(f"不支持的图片类型: {img_type}")
            
            if img.is_valid():
                input_images.append(img)
                print(f"   ✅ 图片 {i+1}: {img.get_info()}")
            else:
                print(f"   ❌ 图片 {i+1}: 所有路径都无效")
        
        # 允许 0 输入图（纯文本生图）
        if not input_images:
            print("⚠️ 未提供有效输入图片，将按 0 输入图模式运行（仅使用文本 Prompt）")
        
        # 计算并显示任务统计
        total_combinations = 1
        for group in string_replace_list:
            total_combinations *= len(group)
        
        total_images = sum(img.get_total_count() if hasattr(img, 'get_total_count') else 1 for img in input_images)
        effective_images = total_images if total_images > 0 else 1
        estimated_tasks = effective_images * len(prompts) * total_combinations
        
        print(f"\n📊 任务统计:")
        print(f"   输入图片: {total_images} 张")
        print(f"   提示词: {len(prompts)} 个")
        print(f"   替换组合: {total_combinations} 种")
        print(f"   预计总任务数: {estimated_tasks}")
        
        return TaskManager(
            generator=generator,
            input_images=input_images,
            prompts=prompts,
            string_replace_list=string_replace_list,
            output_dir=output_dir,
            filename_template=filename_template,
            base_name=base_name
        )
    
    def _calculate_total_tasks(self) -> int:
        """计算总任务数量"""
        # 计算每个输入图片能生成的任务数
        total = 0
        for img in self.input_images:
            if isinstance(img, (ImageFolder, ImageRecursionFolder)):
                # 图片列表类型
                total += img.get_total_count()
            else:
                # 单个图片类型
                total += 1
        
        # 乘以提示词数量和替换组合数量
        prompt_count = len(self._processed_prompts)
        replace_combinations = 1
        for group in self.string_replace_list:
            replace_combinations *= len(group)
        
        effective_total = total if total > 0 else 1
        return effective_total * prompt_count * replace_combinations
    
    def _create_task_generator(self):
        """创建任务生成器"""
        def task_generator():
            """生成任务的生成器函数"""
            # 遍历所有输入图片
            for img_idx, img in enumerate(self.input_images):
                if isinstance(img, (ImageFolder, ImageRecursionFolder)):
                    # 图片列表类型 - 按顺序获取图片
                    img.reset()
                    while img.has_more():
                        # 获取下一张图片
                        single_images = img.get_next_images(1)
                        if not single_images:
                            break
                        
                        single_img = single_images[0]
                        yield from self._generate_tasks_for_image(single_img, img_idx)
                elif isinstance(img, ImageGenerateTasks):
                    # 任务列表类型 - 按顺序获取任务
                    img.reset()
                    while img.has_more():
                        # 获取下一个任务
                        tasks = img.get_next_images(1)
                        if not tasks:
                            break
                        
                        task = tasks[0]
                        yield from self._generate_tasks_for_image(task, img_idx)
                else:
                    # 单个图片类型
                    yield from self._generate_tasks_for_image(img, img_idx)
            # 若为 0 输入图模式（无任何输入图片），也需要基于文本生成任务
            if not self.input_images:
                # 基于文本生成：对每个 prompt 及其替换组合创建无输入的任务
                for prompt_idx, prompt in enumerate(self._processed_prompts):
                    for replace_combination in itertools.product(*self.string_replace_list):
                        current_prompt = self._apply_string_replacements(prompt, replace_combination)
                        task = ImageGenerateTask([], current_prompt)
                        replace_idx = self._get_replace_combination_index(replace_combination)
                        filename = self.filename_template.format(
                            base=self.base_name,
                            prompt_idx=prompt_idx,
                            replace_idx=replace_idx,
                            image_idx=0
                        )
                        yield {
                            'task': task,
                            'filename': filename,
                            'prompt_idx': prompt_idx,
                            'replace_idx': replace_idx,
                            'image_idx': 0
                        }
        
        return task_generator()
    
    def _generate_tasks_for_image(self, image: SingleImage, img_idx: int):
        """为单个图片生成所有任务"""
        # 遍历所有提示词
        for prompt_idx, prompt in enumerate(self._processed_prompts):
            # 生成所有替换组合
            for replace_combination in itertools.product(*self.string_replace_list):
                # 应用字符串替换
                current_prompt = self._apply_string_replacements(prompt, replace_combination)
                
                # 创建生图任务
                task = ImageGenerateTask([image], current_prompt)
                
                # 生成文件名
                replace_idx = self._get_replace_combination_index(replace_combination)
                filename = self.filename_template.format(
                    base=self.base_name,
                    prompt_idx=prompt_idx,
                    replace_idx=replace_idx,
                    image_idx=img_idx
                )
                
                yield {
                    'task': task,
                    'filename': filename,
                    'prompt_idx': prompt_idx,
                    'replace_idx': replace_idx,
                    'image_idx': img_idx
                }
    
    def _apply_string_replacements(self, prompt: str, replace_combination: Tuple[str, ...]) -> str:
        """应用字符串替换，按照原始代码的逻辑"""
        current_prompt = prompt
        
        for group_idx, replace_string in enumerate(replace_combination):
            group = self.string_replace_list[group_idx]
            base_string = group[0]  # 第一项是基础字符串
            
            # 如果选择的是第一项（基础字符串），则保持不变
            if replace_string == base_string:
                # 保持原始字符串，不需要替换
                continue
            
            # 处理空字符串替换的特殊情况
            if base_string == "":
                # 空字符串替换：在 prompt 末尾添加替换字符串
                if replace_string != "":
                    current_prompt = current_prompt + " " + replace_string
            else:
                # 正常字符串替换：检查是否存在
                if base_string in current_prompt:
                    current_prompt = current_prompt.replace(base_string, replace_string)
                else:
                    print(f"⚠️ 警告: 基础字符串 '{base_string}' 不在 prompt 中，跳过替换")
        
        return current_prompt
    
    def _get_replace_combination_index(self, combination: Tuple[str, ...]) -> int:
        """获取替换组合的索引"""
        # 计算组合在笛卡尔积中的索引
        indices = []
        for i, replace_string in enumerate(combination):
            group = self.string_replace_list[i]
            idx = group.index(replace_string)
            indices.append(idx)
        
        # 转换为单一索引（类似进制转换）
        result = 0
        multiplier = 1
        for i in reversed(range(len(indices))):
            result += indices[i] * multiplier
            if i > 0:
                multiplier *= len(self.string_replace_list[i-1])
        
        return result
    
    def _execute_single_task(self, task_info: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个任务"""
        task = task_info['task']
        filename = task_info['filename']
        
        try:
            # 执行任务
            success = task.execute(self.generator)
            
            if success and task.generated_image:
                # 保存图片
                output_path = os.path.join(self.output_dir, filename)
                if task.generated_image.save_to_file(output_path):
                    result = {
                        'success': True,
                        'output_path': output_path,
                        'task_info': task_info
                    }
                else:
                    result = {
                        'success': False,
                        'error': '图片保存失败',
                        'task_info': task_info
                    }
            else:
                result = {
                    'success': False,
                    'error': task.error_reason,
                    'task_info': task_info
                }
            
            # 更新统计
            with self.stats_lock:
                if result['success']:
                    self.stats['completed_tasks'] += 1
                else:
                    self.stats['failed_tasks'] += 1
            
            return result
            
        except Exception as e:
            with self.stats_lock:
                self.stats['failed_tasks'] += 1
            
            return {
                'success': False,
                'error': f'任务执行异常: {str(e)}',
                'task_info': task_info
            }
    
    def _monitor_and_schedule_tasks(self):
        """监控并调度任务"""
        print("🚀 开始任务调度...")
        
        # 计算总任务数
        total_tasks = self._calculate_total_tasks()
        with self.stats_lock:
            self.stats['total_tasks'] = total_tasks
        
        print(f"📊 预计总任务数: {total_tasks}")
        
        # 创建任务生成器
        task_gen = self._create_task_generator()
        
        # 主调度循环
        while self.status == TaskStatus.RUNNING:
            # 检查是否有空闲容量
            idle_capacity = self.generator.get_idle_capacity()
            
            if idle_capacity > 0:
                # 提交新任务
                for _ in range(idle_capacity):
                    try:
                        task_info = next(task_gen)
                        
                        # 提交任务
                        future = self.executor.submit(self._execute_single_task, task_info)
                        
                        with self.futures_lock:
                            self.futures.append(future)
                        
                        with self.stats_lock:
                            self.stats['pending_tasks'] += 1
                        
                        print(f"📋 提交任务: {task_info['filename']}")
                        
                    except StopIteration:
                        # 没有更多任务了
                        break
            
            # 检查完成的任务
            with self.futures_lock:
                completed_futures = []
                for future in self.futures:
                    if future.done():
                        completed_futures.append(future)
                        try:
                            result = future.result()
                            if result['success']:
                                print(f"✅ 任务完成: {result['output_path']}")
                            else:
                                print(f"❌ 任务失败: {result['error']}")
                        except Exception as e:
                            print(f"❌ 任务异常: {str(e)}")
                
                # 移除已完成的任务
                for future in completed_futures:
                    self.futures.remove(future)
                    with self.stats_lock:
                        self.stats['pending_tasks'] = max(0, self.stats['pending_tasks'] - 1)
            
            # 检查是否所有任务都完成了
            with self.futures_lock:
                if not self.futures and self.stats['completed_tasks'] + self.stats['failed_tasks'] >= total_tasks:
                    with self.status_lock:
                        self.status = TaskStatus.COMPLETED
                    break
            
            # 短暂休眠
            time.sleep(0.1)
        
        print("🏁 任务调度完成")
    
    def start(self):
        """开始执行任务"""
        with self.status_lock:
            if self.status == TaskStatus.RUNNING:
                print("⚠️ 任务已在运行中")
                return
            
            self.status = TaskStatus.RUNNING
        
        # 创建线程池
        self.executor = ThreadPoolExecutor(max_workers=self.generator.max_workers)
        
        # 启动监控线程
        monitor_thread = threading.Thread(target=self._monitor_and_schedule_tasks)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        print("🚀 任务管理器已启动")
    
    def pause(self):
        """暂停任务"""
        with self.status_lock:
            if self.status == TaskStatus.RUNNING:
                self.status = TaskStatus.PAUSED
                print("⏸️ 任务已暂停")
            else:
                print("⚠️ 任务未在运行中")
    
    def resume(self):
        """恢复任务"""
        with self.status_lock:
            if self.status == TaskStatus.PAUSED:
                self.status = TaskStatus.RUNNING
                print("▶️ 任务已恢复")
            else:
                print("⚠️ 任务未在暂停状态")
    
    def stop(self):
        """停止任务"""
        with self.status_lock:
            self.status = TaskStatus.STOPPED
        
        # 取消所有待执行的任务
        with self.futures_lock:
            for future in self.futures:
                future.cancel()
            self.futures.clear()
        
        # 关闭执行器
        if self.executor:
            self.executor.shutdown(wait=False)
        
        print("⏹️ 任务管理器已停止")
    
    def get_status(self) -> Dict[str, Any]:
        """获取任务状态"""
        with self.status_lock:
            status_name = {
                TaskStatus.STOPPED: "已停止",
                TaskStatus.RUNNING: "运行中",
                TaskStatus.PAUSED: "已暂停",
                TaskStatus.COMPLETED: "已完成"
            }[self.status]
        
        with self.stats_lock:
            stats = self.stats.copy()
        
        return {
            'status': status_name,
            'stats': stats,
            'generator_stats': self.generator.get_stats(),
            'active_tasks': self.generator.get_active_task_count(),
            'idle_capacity': self.generator.get_idle_capacity()
        }
    
    def wait_for_completion(self, timeout: Optional[float] = None, show_progress: bool = True, progress_interval: float = 5.0):
        """等待任务完成，并显示进度"""
        start_time = time.time()
        
        if show_progress:
            print("\n📈 监控任务进度...")
        
        while True:
            with self.status_lock:
                if self.status in [TaskStatus.STOPPED, TaskStatus.COMPLETED]:
                    break
            
            if timeout and (time.time() - start_time) > timeout:
                print("⏰ 等待超时")
                break
            
            if show_progress:
                self._show_progress(start_time)
            
            time.sleep(progress_interval)
        
        if show_progress:
            self._show_final_results()
        
        return self.get_status()
    
    def _show_progress(self, start_time: float):
        """显示任务进度"""
        status = self.get_status()
        stats = status['stats']
        current_time = time.time()
        elapsed_time = current_time - start_time
        
        print(f"\n⏰ 运行时间: {elapsed_time:.1f}s")
        print(f"   状态: {status['status']}")
        print(f"   已完成: {stats['completed_tasks']}")
        print(f"   失败: {stats['failed_tasks']}")
        print(f"   待处理: {stats['pending_tasks']}")
        print(f"   活跃任务: {status['active_tasks']}")
        print(f"   空闲容量: {status['idle_capacity']}")
        
        # 计算进度百分比
        if stats['total_tasks'] > 0:
            progress = (stats['completed_tasks'] + stats['failed_tasks']) / stats['total_tasks'] * 100
            print(f"   进度: {progress:.1f}%")
    
    def _show_final_results(self):
        """显示最终结果"""
        print("\n🏁 任务执行完成!")
        final_status = self.get_status()
        final_stats = final_status['stats']
        generator_stats = final_status['generator_stats']
        
        print(f"\n📊 最终统计:")
        print(f"   总任务数: {final_stats['total_tasks']}")
        print(f"   成功完成: {final_stats['completed_tasks']}")
        print(f"   失败: {final_stats['failed_tasks']}")
        
        if final_stats['total_tasks'] > 0:
            success_rate = final_stats['completed_tasks'] / final_stats['total_tasks'] * 100
            print(f"   成功率: {success_rate:.1f}%")
        
        print(f"\n🔑 生成器统计:")
        print(f"   总请求数: {generator_stats['total_requests']}")
        print(f"   成功请求: {generator_stats['successful_requests']}")
        print(f"   失败请求: {generator_stats['failed_requests']}")
        print(f"   Key 切换次数: {generator_stats['key_switches']}")
        
        # 显示输出目录信息
        if os.path.exists(self.output_dir):
            output_files = [f for f in os.listdir(self.output_dir) if f.endswith('.png')]
            print(f"\n📁 输出目录: {self.output_dir}")
            print(f"   生成图片数量: {len(output_files)}")
            if output_files:
                print(f"   示例文件: {output_files[:3]}")  # 显示前3个文件
        else:
            print(f"\n📁 输出目录不存在: {self.output_dir}")
    
    def run_with_interactive_monitoring(self, auto_start: bool = False):
        """运行任务并显示交互式监控"""
        print("\n❓ 是否开始执行任务？")
        print("   这将生成大量图片，请确保有足够的存储空间和 API 配额")
        
        if not auto_start:
            user_input = input("   输入 'yes' 开始执行，其他任意键退出: ").strip().lower()
            if user_input != 'yes':
                print("👋 用户取消执行，退出程序")
                return False
        
        # 开始执行任务
        print("\n🚀 开始执行任务...")
        self.start()
        
        try:
            # 等待完成并显示进度
            self.wait_for_completion(show_progress=True, progress_interval=5.0)
            return True
        except KeyboardInterrupt:
            print("\n⏹️ 用户中断，停止任务...")
            self.stop()
            return False
