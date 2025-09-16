"""
Prompt 类定义
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class Prompt:
    """Prompt 类，表示一个提示词"""
    
    id: str
    text: str
    input_count: int
    tags: List[str]
    
    def __post_init__(self):
        """初始化后验证"""
        if not self.id:
            raise ValueError("Prompt ID 不能为空")
        if not self.text:
            raise ValueError("Prompt 文本不能为空")
        if self.input_count < 0:
            raise ValueError("输入图片数量不能为负数")
        if not isinstance(self.tags, list):
            raise ValueError("标签必须是列表")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "text": self.text,
            "input_count": self.input_count,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Prompt':
        """从字典创建 Prompt 对象"""
        return cls(
            id=data["id"],
            text=data["text"],
            input_count=data["input_count"],
            tags=data.get("tags", [])
        )
    
    def get_info(self) -> str:
        """获取 Prompt 信息"""
        return f"ID: {self.id}, 输入图片: {self.input_count}, 标签: {', '.join(self.tags)}"
    
    def has_tag(self, tag: str) -> bool:
        """检查是否包含指定标签"""
        return tag.lower() in [t.lower() for t in self.tags]
    
    def matches_tags(self, required_tags: List[str]) -> bool:
        """检查是否匹配所有必需标签"""
        if not required_tags:
            return True
        prompt_tags_lower = [t.lower() for t in self.tags]
        return all(tag.lower() in prompt_tags_lower for tag in required_tags)
