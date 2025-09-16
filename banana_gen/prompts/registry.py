"""
Prompt 注册表
"""

import json
import os
from typing import List, Dict, Any, Optional
from pathlib import Path

from .prompt import Prompt


class PromptRegistry:
    """Prompt 注册表，管理所有提示词"""
    
    def __init__(self):
        self.prompts: Dict[str, Prompt] = {}
        self._load_prompts()
    
    def _load_prompts(self):
        """加载提示词"""
        # 获取当前文件所在目录
        current_dir = Path(__file__).parent.parent.parent
        prompts_file = current_dir / "prompts" / "prompts_from_aistdio.json"
        
        if prompts_file.exists():
            try:
                with open(prompts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for prompt_data in data.get('prompts', []):
                        prompt = Prompt.from_dict(prompt_data)
                        self.prompts[prompt.id] = prompt
                print(f"✅ 加载了 {len(self.prompts)} 个提示词")
            except Exception as e:
                print(f"❌ 加载提示词失败: {e}")
        else:
            print(f"⚠️ 提示词文件不存在: {prompts_file}")
    
    def get(self, prompt_id: str) -> Optional[Prompt]:
        """获取提示词对象"""
        return self.prompts.get(prompt_id)
    
    def get_text(self, prompt_id: str) -> Optional[str]:
        """获取提示词文本"""
        prompt = self.get(prompt_id)
        return prompt.text if prompt else None
    
    def get_input_count(self, prompt_id: str) -> int:
        """获取推荐输入图片数量"""
        prompt = self.get(prompt_id)
        return prompt.input_count if prompt else 0
    
    def get_tags(self, prompt_id: str) -> List[str]:
        """获取标签"""
        prompt = self.get(prompt_id)
        return prompt.tags if prompt else []
    
    def list_by_input_count(self, input_count: int) -> List[str]:
        """根据输入图片数量列出提示词 ID"""
        return [
            prompt_id for prompt_id, prompt in self.prompts.items()
            if prompt.input_count == input_count
        ]
    
    def list_by_tag(self, tag: str) -> List[str]:
        """根据标签列出提示词 ID"""
        return [
            prompt_id for prompt_id, prompt in self.prompts.items()
            if prompt.has_tag(tag)
        ]
    
    def list_all(self) -> List[str]:
        """列出所有提示词 ID"""
        return list(self.prompts.keys())
    
    def search(self, keyword: str) -> List[str]:
        """搜索提示词"""
        keyword = keyword.lower()
        results = []
        for prompt_id, prompt in self.prompts.items():
            if (keyword in prompt_id.lower() or 
                keyword in prompt.text.lower() or
                any(keyword in tag.lower() for tag in prompt.tags)):
                results.append(prompt_id)
        return results
    
    def filter_by_tags(self, required_tags: List[str]) -> List[str]:
        """根据必需标签过滤提示词"""
        return [
            prompt_id for prompt_id, prompt in self.prompts.items()
            if prompt.matches_tags(required_tags)
        ]
    
    def add_prompt(self, prompt: Prompt):
        """添加新的提示词"""
        self.prompts[prompt.id] = prompt
    
    def remove_prompt(self, prompt_id: str) -> bool:
        """删除提示词"""
        if prompt_id in self.prompts:
            del self.prompts[prompt_id]
            return True
        return False
    
    def save_to_file(self, file_path: str):
        """保存到文件"""
        data = {
            "prompts": [prompt.to_dict() for prompt in self.prompts.values()]
        }
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def load_from_json(path: str) -> "PromptRegistry":
        """从 JSON 文件加载注册表"""
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        
        registry = PromptRegistry()
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        
        items: List[Dict[str, Any]] = data.get("prompts", []) if isinstance(data, dict) else data
        for item in items:
            prompt = Prompt.from_dict(item)
            registry.add_prompt(prompt)
        
        return registry
    
    def get_prompts_by_ids(self, prompt_ids: List[str]) -> List[Prompt]:
        """根据 ID 列表获取 Prompt 对象列表"""
        prompts = []
        for prompt_id in prompt_ids:
            prompt = self.get(prompt_id)
            if prompt:
                prompts.append(prompt)
            else:
                print(f"⚠️ 警告: 提示词 '{prompt_id}' 不存在")
        
        # 如果没有找到任何 prompt，创建默认的
        if not prompts:
            print("   ⚠️ 未找到指定的 prompt，创建默认 prompt...")
            default_prompt = Prompt(
                id="default_change_people",
                text="Change the person in Image 1 to match the pose and style of Image 2, while maintaining photorealistic quality and seamless integration.",
                input_count=2,
                tags=["change", "people", "pose", "style", "photorealistic", "seamless"]
            )
            prompts = [default_prompt]
            print(f"   使用默认 Prompt: {default_prompt.get_info()}")
        
        return prompts