"""
单个图片类实现
"""

import os
import io
from typing import Optional, List, Any, Tuple, Union
from .base import SingleImage, ImageStatus, ImageList

# 可选依赖
try:
    import requests
except ImportError:
    requests = None

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None

try:
    from ..executor.google_api_manager import UnifiedImageGenerator
except ImportError:
    UnifiedImageGenerator = None


class ImageData(SingleImage):
    """数据类型的图片 - 已经读取了图片内容的数据"""
    
    def __init__(self, data: bytes, format: str = "PNG"):
        super().__init__()
        self._data = data
        self._format = format
        self._status = ImageStatus.VALID  # 数据类型的图片默认为有效
    
    @property
    def data(self) -> bytes:
        """获取图片数据"""
        return self._data
    
    @property
    def format(self) -> str:
        """获取图片格式"""
        return self._format
    
    def to_image_data(self) -> Optional['ImageData']:
        """转换为ImageData类型（返回自己）"""
        return self if self.is_valid() else None
    
    def get_info(self) -> str:
        """获取图片信息"""
        return f"ImageData(format={self._format}, size={len(self._data)} bytes)"
    
    def save_to_file(self, file_path: str) -> bool:
        """保存到文件"""
        try:
            with open(file_path, 'wb') as f:
                f.write(self._data)
            return True
        except Exception:
            return False
    
    def to_pil_image(self):
        """转换为PIL Image对象"""
        if PILImage is None:
            return None
        try:
            return PILImage.open(io.BytesIO(self._data))
        except Exception:
            return None


class LocalImage(SingleImage):
    """本地图片类型"""
    
    def __init__(self, file_path: str, fallback_paths: List[str] = None):
        super().__init__()
        self._file_path = file_path
        self._fallback_paths = fallback_paths or []
        self._validate()
    
    @property
    def file_path(self) -> str:
        """获取文件路径"""
        return self._file_path
    
    def _validate(self):
        """验证本地图片，支持自动回退"""
        # 尝试主路径
        if self._try_validate_file(self._file_path):
            return
        
        # 尝试回退路径
        for fallback_path in self._fallback_paths:
            if self._try_validate_file(fallback_path):
                self._file_path = fallback_path  # 更新为实际使用的路径
                return
        
        # 所有路径都失败
        self._status = ImageStatus.INVALID
        print(f"❌ LocalImage 初始化失败: 无法找到有效的图片文件")
        print(f"   尝试的路径: {[self._file_path] + self._fallback_paths}")
    
    def _try_validate_file(self, file_path: str) -> bool:
        """尝试验证指定文件"""
        if not os.path.exists(file_path):
            return False
        
        if not os.path.isfile(file_path):
            return False
        
        # 检查文件扩展名
        supported_extensions = ('.png', '.jpg', '.jpeg', '.webp')
        if not file_path.lower().endswith(supported_extensions):
            return False
        
        # 尝试打开图片验证格式
        if PILImage is not None:
            try:
                with PILImage.open(file_path) as img:
                    img.verify()
                self._status = ImageStatus.VALID
                return True
            except Exception:
                return False
        else:
            # 如果没有PIL，只检查文件存在性
            self._status = ImageStatus.VALID
            return True
    
    def to_image_data(self) -> Optional[ImageData]:
        """转换为ImageData类型"""
        if not self.is_valid():
            return None
        
        try:
            with open(self._file_path, 'rb') as f:
                data = f.read()
            
            # 根据文件扩展名确定格式
            ext = os.path.splitext(self._file_path)[1].lower()
            format_map = {
                '.png': 'PNG',
                '.jpg': 'JPEG',
                '.jpeg': 'JPEG',
                '.webp': 'WEBP'
            }
            format_name = format_map.get(ext, 'PNG')
            
            return ImageData(data, format_name)
        except Exception:
            return None
    
    def get_info(self) -> str:
        """获取图片信息"""
        if self.is_valid():
            try:
                size = os.path.getsize(self._file_path)
                return f"LocalImage(path={self._file_path}, size={size} bytes)"
            except Exception:
                return f"LocalImage(path={self._file_path}, status={self._status})"
        else:
            return f"LocalImage(path={self._file_path}, status={self._status})"


class UrlImage(SingleImage):
    """URL图片类型"""
    
    def __init__(self, url: str, timeout: int = 10, fallback_urls: List[str] = None):
        super().__init__()
        self._url = url
        self._timeout = timeout
        self._fallback_urls = fallback_urls or []
        self._validate()
    
    @property
    def url(self) -> str:
        """获取URL"""
        return self._url
    
    def _validate(self):
        """验证URL图片，支持自动回退"""
        if requests is None:
            self._status = ImageStatus.INVALID
            print(f"❌ UrlImage 初始化失败: requests 库未安装")
            return
        
        # 尝试主URL
        if self._try_validate_url(self._url):
            return
        
        # 尝试回退URL
        for fallback_url in self._fallback_urls:
            if self._try_validate_url(fallback_url):
                self._url = fallback_url  # 更新为实际使用的URL
                return
        
        # 所有URL都失败
        self._status = ImageStatus.INVALID
        print(f"❌ UrlImage 初始化失败: 无法访问有效的图片URL")
        print(f"   尝试的URL: {[self._url] + self._fallback_urls}")
    
    def _try_validate_url(self, url: str) -> bool:
        """尝试验证指定URL"""
        try:
            response = requests.head(url, timeout=self._timeout)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                if content_type.startswith('image/'):
                    self._status = ImageStatus.VALID
                    return True
            return False
        except Exception:
            return False
    
    def to_image_data(self) -> Optional[ImageData]:
        """转换为ImageData类型"""
        if not self.is_valid() or requests is None:
            return None
        
        try:
            response = requests.get(self._url, timeout=self._timeout)
            response.raise_for_status()
            
            data = response.content
            
            # 根据Content-Type确定格式
            content_type = response.headers.get('content-type', '').lower()
            format_map = {
                'image/png': 'PNG',
                'image/jpeg': 'JPEG',
                'image/jpg': 'JPEG',
                'image/webp': 'WEBP'
            }
            format_name = format_map.get(content_type, 'PNG')
            
            return ImageData(data, format_name)
        except Exception:
            return None
    
    def get_info(self) -> str:
        """获取图片信息"""
        return f"UrlImage(url={self._url}, status={self._status})"


class ImageGenerateTask(SingleImage):
    """可以生成单个图片的生图任务"""
    
    def __init__(self, input_images: List[SingleImage], prompt: Union[str, 'Prompt']):
        super().__init__()
        self._input_images = input_images
        # 处理 prompt 参数，支持 str 和 Prompt 对象
        if isinstance(prompt, str):
            self._prompt = prompt
        else:
            # 假设是 Prompt 对象
            self._prompt = prompt.text
        self._is_executed = False
        self._is_success = False
        self._error_reason = ""
        self._generated_image: Optional[ImageData] = None
        self._validate_inputs()
    
    @classmethod
    def create_task(cls, input_images: List[SingleImage], prompt: Union[str, 'Prompt']):
        """创建任务，自动处理单个/多个图片的情况"""
        # 检查是否有 ImageList 类型的输入
        has_list_input = any(isinstance(img, ImageList) for img in input_images)
        
        if has_list_input:
            # 如果有列表输入，创建 ImageGenerateTasks
            from .lists import ImageGenerateTasks
            import itertools
            
            # 收集所有图片组合
            image_combinations = []
            
            for img in input_images:
                if isinstance(img, ImageList):
                    # 收集列表中的所有图片
                    img_list = []
                    # 重置索引
                    img.reset()
                    # 限制最大数量，避免无限循环
                    max_count = img.get_total_count()
                    count = 0
                    while img.has_more() and count < max_count:
                        single_images = img.get_next_images(1)
                        if single_images:
                            img_list.append(single_images[0])
                            count += 1
                        else:
                            break
                    image_combinations.append(img_list)
                else:
                    # 单个图片
                    image_combinations.append([img])
            
            # 生成所有组合
            tasks = []
            for combination in itertools.product(*image_combinations):
                task = cls(list(combination), prompt)
                tasks.append(task)
            
            return ImageGenerateTasks(tasks)
        else:
            # 都是单个图片，创建单个任务
            return cls(input_images, prompt)
    
    @property
    def input_images(self) -> List[SingleImage]:
        """获取输入图片列表"""
        return self._input_images
    
    @property
    def prompt(self) -> str:
        """获取提示词"""
        return self._prompt
    
    @property
    def is_executed(self) -> bool:
        """是否已经执行"""
        return self._is_executed
    
    @property
    def is_success(self) -> bool:
        """是否成功生成图片"""
        return self._is_success
    
    @property
    def error_reason(self) -> str:
        """获取错误原因"""
        return self._error_reason
    
    @property
    def generated_image(self) -> Optional[ImageData]:
        """获取生成的图片"""
        return self._generated_image
    
    def _validate_inputs(self):
        """验证输入图片"""
        if not self._input_images:
            self._status = ImageStatus.INVALID
            return
        
        # 检查所有输入图片是否有效
        for img in self._input_images:
            if not img.is_valid():
                self._status = ImageStatus.INVALID
                return
        
        self._status = ImageStatus.VALID
    
    def execute(self, generator) -> bool:
        """执行生图任务"""
        if generator is None:
            self._error_reason = "生成器未提供"
            self._is_executed = True
            self._is_success = False
            return False
        
        if not self.is_valid():
            self._error_reason = "输入图片无效"
            self._is_executed = True
            self._is_success = False
            return False
        
        try:
            # 转换输入图片为ImageData
            image_data_list = []
            for img in self._input_images:
                # 如果是ImageGenerateTask或ImageGenerateTasks，尝试自动执行
                from .lists import ImageGenerateTasks
                if isinstance(img, (ImageGenerateTask, ImageGenerateTasks)):
                    img_data = img.to_image_data(generator)
                    # 如果嵌套任务失败，传递错误信息
                    if img_data is None and img.is_executed and not img.is_success:
                        self._error_reason = f"嵌套任务失败: {img.error_reason}"
                        self._is_executed = True
                        self._is_success = False
                        return False
                else:
                    img_data = img.to_image_data()
                
                if img_data is None:
                    self._error_reason = f"无法转换输入图片: {img.get_info()}"
                    self._is_executed = True
                    self._is_success = False
                    return False
                image_data_list.append(img_data)
            
            # 准备图片路径（临时保存）
            temp_paths = []
            for i, img_data in enumerate(image_data_list):
                temp_path = f"/tmp/banana_gen_input_{i}.{img_data.format.lower()}"
                if img_data.save_to_file(temp_path):
                    temp_paths.append(temp_path)
                else:
                    self._error_reason = f"无法保存临时图片: {temp_path}"
                    self._is_executed = True
                    self._is_success = False
                    return False
            
            # 调用生成器
            success, error_msg, image_data = generator.generate_image(temp_paths, self._prompt)
            
            # 清理临时文件
            for temp_path in temp_paths:
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            
            # 更新状态
            self._is_executed = True
            if success and image_data and len(image_data) > 0:
                self._is_success = True
                self._generated_image = ImageData(image_data, "PNG")
                self._error_reason = ""
                return True
            else:
                self._is_success = False
                self._error_reason = error_msg or "未生成图片数据"
                return False
                
        except Exception as e:
            self._is_executed = True
            self._is_success = False
            self._error_reason = f"执行异常: {str(e)}"
            return False
    
    def to_image_data(self, generator=None) -> Optional[ImageData]:
        """转换为ImageData类型"""
        if not self._is_executed:
            # 如果没有执行，尝试自动执行
            if generator is not None:
                self.execute(generator)
            else:
                # 如果没有generator，返回None
                return None
        
        if self._is_success:
            return self._generated_image
        else:
            return None
    
    def get_info(self) -> str:
        """获取任务信息"""
        status_info = f"executed={self._is_executed}, success={self._is_success}"
        if self._error_reason:
            status_info += f", error={self._error_reason}"
        return f"ImageGenerateTask(inputs={len(self._input_images)}, {status_info})"
