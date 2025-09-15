"""
图片列表类实现
"""

import os
import threading
from typing import List, Optional
from .base import ImageList, SingleImage, ImageStatus
from .single import ImageData, LocalImage, ImageGenerateTask


class ImageFolder(ImageList):
    """本地图片文件夹路径"""
    
    def __init__(self, folder_path: str, fallback_paths: List[str] = None):
        super().__init__()
        self._folder_path = folder_path
        self._fallback_paths = fallback_paths or []
        self._supported_extensions = ('.png', '.jpg', '.jpeg', '.webp')
        self._image_files = []
        self._lock = threading.Lock()
        self._load_image_files()
    
    def _load_image_files(self):
        """加载文件夹中的图片文件，支持自动回退"""
        # 尝试主路径
        if self._try_load_folder(self._folder_path):
            return
        
        # 尝试回退路径
        for fallback_path in self._fallback_paths:
            if self._try_load_folder(fallback_path):
                self._folder_path = fallback_path  # 更新为实际使用的路径
                return
        
        # 所有路径都失败
        self._status = ImageStatus.INVALID
        print(f"❌ ImageFolder 初始化失败: 无法找到有效的图片文件夹")
        print(f"   尝试的路径: {[self._folder_path] + self._fallback_paths}")
    
    def _try_load_folder(self, folder_path: str) -> bool:
        """尝试加载指定文件夹"""
        if not os.path.isdir(folder_path):
            return False
        
        try:
            files = []
            for filename in os.listdir(folder_path):
                if filename.startswith('.'):
                    continue
                if filename.lower().endswith(self._supported_extensions):
                    file_path = os.path.join(folder_path, filename)
                    if os.path.isfile(file_path):
                        files.append(file_path)
            
            # 按文件名排序
            self._image_files = sorted(files)
            if self._image_files:
                self._status = ImageStatus.VALID
                return True
            else:
                return False
        except Exception:
            return False
    
    def get_next_images(self, count: int = 1) -> List[SingleImage]:
        """获取下一批图片"""
        with self._lock:
            if not self.is_valid() or self._current_index >= len(self._image_files):
                return []
            
            # 计算结束索引
            end_index = min(self._current_index + count, len(self._image_files))
            
            # 获取图片文件路径
            file_paths = self._image_files[self._current_index:end_index]
            
            # 创建LocalImage对象
            images = []
            for file_path in file_paths:
                local_img = LocalImage(file_path)
                if local_img.is_valid():
                    images.append(local_img)
            
            # 滑动窗口：索引向前移动1（而不是移动到end_index）
            self._current_index += 1
            
            return images
    
    def has_more(self) -> bool:
        """检查是否还有更多图片"""
        return self._current_index < len(self._image_files)
    
    def reset(self):
        """重置索引"""
        with self._lock:
            self._current_index = 0
    
    def get_total_count(self) -> int:
        """获取总图片数量"""
        return len(self._image_files)
    
    def to_image_data(self):
        """转换为ImageData类型（返回当前图片）"""
        if not self.is_valid():
            return None
        
        # 检查是否有更多图片
        if self._current_index >= len(self._image_files):
            return None
        
        # 获取当前图片文件路径
        current_file = self._image_files[self._current_index]
        current_path = os.path.join(self._folder_path, current_file)
        
        # 创建 LocalImage 并转换为 ImageData
        local_img = LocalImage(current_path)
        if local_img.is_valid():
            return local_img.to_image_data()
        else:
            return None
    
    def get_info(self) -> str:
        """获取文件夹信息"""
        return f"ImageFolder(path={self._folder_path}, total={len(self._image_files)}, current={self._current_index})"


class ImageRecursionFolder(ImageList):
    """递归遍历的图片文件夹路径"""
    
    def __init__(self, folder_path: str, fallback_paths: List[str] = None):
        super().__init__()
        self._folder_path = folder_path
        self._fallback_paths = fallback_paths or []
        self._supported_extensions = ('.png', '.jpg', '.jpeg', '.webp')
        self._image_files = []
        self._lock = threading.Lock()
        self._load_image_files()
    
    def _load_image_files(self):
        """递归加载文件夹中的图片文件，支持自动回退"""
        # 尝试主路径
        if self._try_load_folder_recursive(self._folder_path):
            return
        
        # 尝试回退路径
        for fallback_path in self._fallback_paths:
            if self._try_load_folder_recursive(fallback_path):
                self._folder_path = fallback_path  # 更新为实际使用的路径
                return
        
        # 所有路径都失败
        self._status = ImageStatus.INVALID
        print(f"❌ ImageRecursionFolder 初始化失败: 无法找到有效的图片文件夹")
        print(f"   尝试的路径: {[self._folder_path] + self._fallback_paths}")
    
    def _try_load_folder_recursive(self, folder_path: str) -> bool:
        """尝试递归加载指定文件夹"""
        if not os.path.isdir(folder_path):
            return False
        
        try:
            files = []
            for root, dirs, filenames in os.walk(folder_path):
                for filename in filenames:
                    if filename.startswith('.'):
                        continue
                    if filename.lower().endswith(self._supported_extensions):
                        file_path = os.path.join(root, filename)
                        if os.path.isfile(file_path):
                            files.append(file_path)
            
            # 按文件路径排序
            self._image_files = sorted(files)
            if self._image_files:
                self._status = ImageStatus.VALID
                return True
            else:
                return False
        except Exception:
            return False
    
    def get_next_images(self, count: int = 1) -> List[SingleImage]:
        """获取下一批图片"""
        with self._lock:
            if not self.is_valid() or self._current_index >= len(self._image_files):
                return []
            
            # 计算结束索引
            end_index = min(self._current_index + count, len(self._image_files))
            
            # 获取图片文件路径
            file_paths = self._image_files[self._current_index:end_index]
            
            # 创建LocalImage对象
            images = []
            for file_path in file_paths:
                local_img = LocalImage(file_path)
                if local_img.is_valid():
                    images.append(local_img)
            
            # 滑动窗口：索引向前移动1（而不是移动到end_index）
            self._current_index += 1
            
            return images
    
    def has_more(self) -> bool:
        """检查是否还有更多图片"""
        return self._current_index < len(self._image_files)
    
    def reset(self):
        """重置索引"""
        with self._lock:
            self._current_index = 0
    
    def get_total_count(self) -> int:
        """获取总图片数量"""
        return len(self._image_files)
    
    def to_image_data(self):
        """转换为ImageData类型（返回当前图片）"""
        if not self.is_valid():
            return None
        
        # 检查是否有更多图片
        if self._current_index >= len(self._image_files):
            return None
        
        # 获取当前图片文件路径
        current_file = self._image_files[self._current_index]
        current_path = os.path.join(self._folder_path, current_file)
        
        # 创建 LocalImage 并转换为 ImageData
        local_img = LocalImage(current_path)
        if local_img.is_valid():
            return local_img.to_image_data()
        else:
            return None
    
    def get_info(self) -> str:
        """获取文件夹信息"""
        return f"ImageRecursionFolder(path={self._folder_path}, total={len(self._image_files)}, current={self._current_index})"


class ImageGenerateTasks(ImageList):
    """包含了多个生图任务的列表"""
    
    def __init__(self, tasks: List[ImageGenerateTask]):
        super().__init__()
        self._tasks = tasks
        self._lock = threading.Lock()
        self._validate_tasks()
    
    def _validate_tasks(self):
        """验证任务列表"""
        if not self._tasks:
            self._status = ImageStatus.INVALID
            return
        
        # 检查所有任务是否有效
        for task in self._tasks:
            if not task.is_valid():
                self._status = ImageStatus.INVALID
                return
        
        self._status = ImageStatus.VALID
    
    def get_next_images(self, count: int = 1) -> List[SingleImage]:
        """获取下一批图片"""
        with self._lock:
            if not self.is_valid() or self._current_index >= len(self._tasks):
                return []
            
            # 计算结束索引
            end_index = min(self._current_index + count, len(self._tasks))
            
            # 获取任务
            tasks = self._tasks[self._current_index:end_index]
            
            # 滑动窗口：索引向前移动1（而不是移动到end_index）
            self._current_index += 1
            
            return tasks
    
    def has_more(self) -> bool:
        """检查是否还有更多任务"""
        return self._current_index < len(self._tasks)
    
    def reset(self):
        """重置索引"""
        with self._lock:
            self._current_index = 0
    
    def get_total_count(self) -> int:
        """获取总任务数量"""
        return len(self._tasks)
    
    def add_task(self, task: ImageGenerateTask):
        """添加任务"""
        with self._lock:
            self._tasks.append(task)
            self._validate_tasks()
    
    def remove_task(self, index: int):
        """移除任务"""
        with self._lock:
            if 0 <= index < len(self._tasks):
                del self._tasks[index]
                if self._current_index > index:
                    self._current_index -= 1
                self._validate_tasks()
    
    def get_task(self, index: int) -> Optional[ImageGenerateTask]:
        """获取指定索引的任务"""
        if 0 <= index < len(self._tasks):
            return self._tasks[index]
        return None
    
    def to_image_data(self, generator=None):
        """转换为ImageData类型（返回当前任务的生成图片）"""
        if not self.is_valid():
            return None
        
        # 获取当前任务
        if self._current_index >= len(self._tasks):
            return None
        
        current_task = self._tasks[self._current_index]
        
        # 如果任务没有执行，尝试自动执行
        if not current_task.is_executed:
            if generator is not None:
                current_task.execute(generator)
            else:
                return None
        
        # 检查执行结果
        if not current_task.is_success:
            return None
        
        return current_task.generated_image
    
    def get_info(self) -> str:
        """获取任务列表信息"""
        executed_count = sum(1 for task in self._tasks if task.is_executed)
        success_count = sum(1 for task in self._tasks if task.is_success)
        return f"ImageGenerateTasks(total={len(self._tasks)}, executed={executed_count}, success={success_count}, current={self._current_index})"
