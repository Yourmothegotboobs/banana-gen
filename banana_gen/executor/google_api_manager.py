#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
统一生图调度管理器
完全自包含的 Google API 调度管理器，用户无需手动管理 Key
参考 aistdio-banana/2Picture/changepeople.py 的调用方式
"""

import os
import io
import time
import threading
from typing import List, Dict, Optional, Any, Union, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from PIL import Image

try:
    import google.generativeai as genai
    from google.api_core import exceptions
except ImportError:
    print("❌ 缺少 google-generativeai 库，请安装: pip install google-generativeai")
    raise

from ..keys.advanced_key_manager import AdvancedKeyManager
from ..logging.tee import log_jsonl


# Google API 安全设置 - 参考原始代码
SAFETY_SETTINGS = {
    'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE', 
    'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE',
    'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE', 
    'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE',
}

# 支持的图片格式 - 参考原始代码
SUPPORTED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp')

# 全局文件名生成锁 - 参考原始代码
_filename_generation_lock = threading.Lock()
_filename_counter = 0


def _mask_key(key: str) -> str:
    """掩码显示 API Key"""
    if not key:
        return ""
    return key[:6] + "..." + key[-4:] if len(key) > 12 else key


def _should_switch_key(error: Exception) -> bool:
    """判断是否需要切换 Key - 参考原始代码逻辑"""
    error_str = str(error).lower()
    switch_key_indicators = [
        'quota', 'limit', 'exceeded', 'rate', 'billing', 'payment',
        'invalid', 'unauthorized', 'forbidden', 'expired'
    ]
    return any(indicator in error_str for indicator in switch_key_indicators)


def _get_error_description(error: Exception) -> str:
    """获取错误描述"""
    return str(error)


def generate_unique_filename(base_name: str, prompt_id: str, generation_idx: int = 0) -> str:
    """线程安全的唯一文件名生成函数 - 参考原始代码"""
    global _filename_counter
    with _filename_generation_lock:
        timestamp = datetime.now()
        time_str = timestamp.strftime("%m%d%H%M%S")
        microsecond = timestamp.strftime("%f")
        thread_id = threading.get_ident() % 10000
        
        _filename_counter += 1
        counter_str = f"{_filename_counter:04d}"
        
        filename = f"{base_name}-{prompt_id}-G{generation_idx+1:02d}-{time_str}-{microsecond}-{thread_id:04d}-{counter_str}.png"
        return filename


class UnifiedImageGenerator:
    """统一生图调度管理器 - 完全自包含，用户无需手动管理 Key"""
    
    def __init__(self, 
                 key_source: Union[str, List[str], None] = None,
                 max_workers: int = 3, 
                 max_retries: int = 10):
        """
        初始化统一生图调度管理器
        
        Args:
            key_source: Key 来源，支持以下格式：
                - None: 默认扫描 banana_gen/keys 文件夹
                - str: 文件夹路径、txt文件路径或单个key字符串
                - List[str]: key字符串列表
            max_workers: 最大并行度，默认3
            max_retries: 最大重试次数，默认10
        """
        self.max_workers = max_workers
        self.max_retries = max_retries
        self._stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'key_switches': 0
        }
        self._stats_lock = threading.Lock()
        
        # 任务监控相关
        self._active_tasks = 0
        self._task_lock = threading.Lock()
        self._executor = None
        
        # 初始化 Key 管理器
        self.key_manager = self._init_key_manager(key_source)
        
        if not self.key_manager or not self.key_manager.has_available_keys():
            raise RuntimeError("❌ 无法初始化 Key 管理器，请检查 Key 来源")
        
        print(f"✅ 统一生图调度管理器初始化成功")
        print(f"   🔑 Key 数量: {self.key_manager.get_total_keys()}")
        print(f"   ⚡ 并行度: {max_workers}")
        print(f"   🔄 重试次数: {max_retries}")
    
    def _init_key_manager(self, key_source: Union[str, List[str], None]) -> Optional[AdvancedKeyManager]:
        """初始化 Key 管理器，自动判断输入类型"""
        if key_source is None:
            # 默认扫描 banana_gen/keys 文件夹
            default_keys_dir = "banana_gen/keys"
            if os.path.exists(default_keys_dir):
                print(f"🔍 自动扫描 Key 文件夹: {default_keys_dir}")
                return self._load_keys_from_directory(default_keys_dir)
            else:
                print(f"⚠️ 默认 Key 文件夹不存在: {default_keys_dir}")
                return None
        
        if isinstance(key_source, list):
            # 直接传入的 key 列表
            print(f"🔑 使用传入的 Key 列表: {len(key_source)} 个")
            return AdvancedKeyManager({1: key_source})
        
        if isinstance(key_source, str):
            key_source = key_source.strip()
            
            if os.path.isdir(key_source):
                # 文件夹路径
                print(f"📁 扫描 Key 文件夹: {key_source}")
                return self._load_keys_from_directory(key_source)
            
            elif os.path.isfile(key_source) and key_source.endswith('.txt'):
                # txt 文件路径
                print(f"📄 加载 Key 文件: {key_source}")
                return self._load_keys_from_file(key_source)
            
            elif key_source.startswith('AIzaSy'):
                # 单个 key 字符串
                print(f"🔑 使用单个 Key 字符串")
                return AdvancedKeyManager({1: [key_source]})
            
            else:
                raise ValueError(f"❌ 无法识别的 Key 来源: {key_source}")
        
        raise ValueError(f"❌ 不支持的 Key 来源类型: {type(key_source)}")
    
    def _load_keys_from_directory(self, directory: str) -> Optional[AdvancedKeyManager]:
        """从文件夹加载 keys"""
        try:
            key_manager = AdvancedKeyManager()
            key_manager.load_keys_from_directory(directory)
            return key_manager
        except Exception as e:
            print(f"❌ 从文件夹加载 Key 失败: {e}")
            return None
    
    def _load_keys_from_file(self, file_path: str) -> Optional[AdvancedKeyManager]:
        """从单个文件加载 keys"""
        try:
            key_manager = AdvancedKeyManager()
            key_manager.load_keys_from_file(file_path, priority=1)
            return key_manager
        except Exception as e:
            print(f"❌ 从文件加载 Key 失败: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._stats_lock:
            return self._stats.copy()
    
    def get_active_task_count(self) -> int:
        """获取当前活跃任务数量"""
        with self._task_lock:
            return self._active_tasks
    
    def has_idle_capacity(self) -> bool:
        """检查是否有空闲容量"""
        with self._task_lock:
            return self._active_tasks < self.max_workers
    
    def get_idle_capacity(self) -> int:
        """获取空闲容量数量"""
        with self._task_lock:
            return max(0, self.max_workers - self._active_tasks)
    
    def _increment_active_tasks(self):
        """增加活跃任务计数"""
        with self._task_lock:
            self._active_tasks += 1
    
    def _decrement_active_tasks(self):
        """减少活跃任务计数"""
        with self._task_lock:
            self._active_tasks = max(0, self._active_tasks - 1)
    
    def generate_image(self, 
                      image_paths: List[str], 
                      prompt: str) -> Tuple[bool, str, Optional[bytes]]:
        """
        生成单张图片
        
        Args:
            image_paths: 输入图片路径列表
            prompt: 文本提示词
            
        Returns:
            Tuple[bool, str, Optional[bytes]]: (是否成功, 错误原因, 图片字节数据)
        """
        self._increment_active_tasks()
        try:
            # Key 轮换循环
            while True:
                api_key = self.key_manager.get_current_key()
                if not api_key:
                    stats = self.key_manager.get_stats()
                    return False, f"所有API Key都已失效 [失效:{stats['failed_count']}]", None
                
                try:
                    # 配置 Google API
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-2.5-flash-image-preview')
                    
                    # 针对当前 Key 的重试循环
                    for attempt in range(self.max_retries):
                        try:
                            # 构建内容
                            contents = [prompt]
                            
                            # 加载图片
                            for image_path in image_paths:
                                if os.path.exists(image_path):
                                    img = Image.open(image_path)
                                    contents.append(img)
                            
                            # 调用 API
                            response = model.generate_content(
                                contents=contents,
                                safety_settings=SAFETY_SETTINGS
                            )
                            
                            # 从响应中提取图片数据
                            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                                for part in response.candidates[0].content.parts:
                                    if hasattr(part, 'inline_data') and part.inline_data:
                                        image_data = part.inline_data.data
                                        with self._stats_lock:
                                            self._stats['successful_requests'] += 1
                                        return True, "", image_data
                            
                            # 检查是否因安全策略被拦截
                            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                                reason = f"被安全策略阻止: {response.prompt_feedback}"
                                with self._stats_lock:
                                    self._stats['failed_requests'] += 1
                                return False, reason, None
                            
                            # 未找到有效数据，重试
                            if attempt < self.max_retries - 1:
                                time.sleep(2)
                        
                        # 捕获临时的服务器/网络错误
                        except (exceptions.ServerError, exceptions.ServiceUnavailable) as e:
                            if attempt < self.max_retries - 1:
                                time.sleep(5)
                    
                    # 重试次数耗尽
                    with self._stats_lock:
                        self._stats['failed_requests'] += 1
                    return False, "已达最大重试次数", None
                
                # 捕获需要切换key的异常
                except Exception as e:
                    error_desc = _get_error_description(e)
                    if _should_switch_key(e):
                        if self.key_manager.mark_key_failed(api_key, error_desc):
                            with self._stats_lock:
                                self._stats['key_switches'] += 1
                            continue
                        else:
                            # 所有key都失效了
                            stats = self.key_manager.get_stats()
                            with self._stats_lock:
                                self._stats['failed_requests'] += 1
                            return False, f"所有API Key都已失效 - {error_desc} [失效:{stats['failed_count']}]", None
                    else:
                        # 不需要切换key的严重错误
                        with self._stats_lock:
                            self._stats['failed_requests'] += 1
                        return False, f"严重错误: {error_desc}", None
        
        except Exception as e:
            with self._stats_lock:
                self._stats['failed_requests'] += 1
            return False, f"未知错误: {str(e)}", None
        finally:
            self._decrement_active_tasks()
    
    def generate_images_batch(self, 
                            requests: List[Dict[str, Any]]) -> List[Tuple[bool, str, Optional[bytes]]]:
        """
        批量生成图片
        
        Args:
            requests: 请求列表，每个请求包含 {'image_paths': List[str], 'prompt': str}
            
        Returns:
            List[Tuple[bool, str, Optional[bytes]]]: 结果列表
        """
        if not requests:
            return []
        
        print(f"🚀 开始批量生成 {len(requests)} 张图片，并行度: {self.max_workers}")
        
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_index = {
                executor.submit(self.generate_image, req['image_paths'], req['prompt']): i 
                for i, req in enumerate(requests)
            }
            
            # 收集结果
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    result = future.result()
                    results.append((index, result))
                except Exception as e:
                    results.append((index, (False, f"任务异常: {str(e)}", None)))
        
        # 按原始顺序排序结果
        results.sort(key=lambda x: x[0])
        return [result for _, result in results]
    
# 使用示例
if __name__ == "__main__":
    # 示例1: 使用默认 Key 文件夹
    generator = UnifiedImageGenerator()
    
    # 示例2: 使用自定义 Key 文件夹
    # generator = UnifiedImageGenerator(key_source="/path/to/keys")
    
    # 示例3: 使用单个 Key 文件
    # generator = UnifiedImageGenerator(key_source="/path/to/api_keys.txt")
    
    # 示例4: 使用 Key 字符串列表
    # generator = UnifiedImageGenerator(key_source=["AIzaSy...", "AIzaSy..."])
    
    # 示例5: 使用单个 Key 字符串
    # generator = UnifiedImageGenerator(key_source="AIzaSy...")
    
    # 生成单张图片
    image_paths = ["/path/to/image1.jpg", "/path/to/image2.jpg"]
    prompt = "Generate a new image based on these inputs"
    
    success, error_msg, image_data = generator.generate_image(image_paths, prompt)
    
    if success:
        print("✅ 图片生成成功！")
        # 保存图片
        with open("output.png", "wb") as f:
            f.write(image_data)
    else:
        print(f"❌ 图片生成失败: {error_msg}")
    
    # 批量生成图片
    requests = [
        {"image_paths": ["/path/to/image1.jpg"], "prompt": "Prompt 1"},
        {"image_paths": ["/path/to/image2.jpg"], "prompt": "Prompt 2"},
    ]
    
    results = generator.generate_images_batch(requests)
    for i, (success, error_msg, image_data) in enumerate(results):
        if success:
            print(f"✅ 图片 {i+1} 生成成功！")
        else:
            print(f"❌ 图片 {i+1} 生成失败: {error_msg}")
    
    # 查看统计信息
    stats = generator.get_stats()
    print(f"📊 统计信息: {stats}")
