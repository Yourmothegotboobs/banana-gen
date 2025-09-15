"""
基础图片类定义
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Any
from enum import IntEnum


class ImageStatus(IntEnum):
    """图片状态枚举"""
    INVALID = -1  # 图片失效
    PENDING = 0   # 待定
    VALID = 1     # 有效


class Image(ABC):
    """图片总父类"""
    
    def __init__(self):
        self._status = ImageStatus.PENDING
    
    @property
    def status(self) -> ImageStatus:
        """获取图片状态"""
        return self._status
    
    @status.setter
    def status(self, value: ImageStatus):
        """设置图片状态"""
        self._status = value
    
    def is_valid(self) -> bool:
        """检查图片是否有效"""
        return self._status == ImageStatus.VALID
    
    def is_invalid(self) -> bool:
        """检查图片是否失效"""
        return self._status == ImageStatus.INVALID
    
    def is_pending(self) -> bool:
        """检查图片是否待定"""
        return self._status == ImageStatus.PENDING
    
    @abstractmethod
    def get_info(self) -> str:
        """获取图片信息"""
        pass


class SingleImage(Image):
    """单个图片类"""
    
    def __init__(self):
        super().__init__()
    
    @abstractmethod
    def to_image_data(self):
        """转换为ImageData类型"""
        pass


class ImageList(Image):
    """图片列表类"""
    
    def __init__(self):
        super().__init__()
        self._current_index = 0
    
    @property
    def current_index(self) -> int:
        """获取当前索引"""
        return self._current_index
    
    @current_index.setter
    def current_index(self, value: int):
        """设置当前索引"""
        self._current_index = value
    
    @abstractmethod
    def get_next_images(self, count: int = 1) -> List[SingleImage]:
        """获取下一批图片"""
        pass
    
    @abstractmethod
    def has_more(self) -> bool:
        """检查是否还有更多图片"""
        pass
    
    @abstractmethod
    def reset(self):
        """重置索引"""
        pass
    
    @abstractmethod
    def get_total_count(self) -> int:
        """获取总图片数量"""
        pass
