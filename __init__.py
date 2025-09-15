"""
Banana Gen - 统一的图像生成管理框架

重构自 aistdio-banana，提供统一的 Key 管理、Prompt 管理、图片来源管理、
日志系统和输出管理，支持 0/1/2/3 输入图场景的通用编排。
"""

__version__ = "0.1.0"
__author__ = "Banana Gen Team"

from .core import __version__
from .keys import AdvancedKeyManager, load_api_keys_advanced
from .prompts import PromptRegistry, apply_replacements, PromptPack
from .images import (
    ImageSpec, ImageSource, LocalFileSource, UrlSource,
    FolderSequencerSource, RecursiveFolderSequencerSource
)
from .logging import install_log_tee, log_jsonl
from .output import OutputPathManager, render_filename, embed_info_to_png, extract_info_from_png
from .runner import build_plan
from .executor import execute_plan

__all__ = [
    "__version__",
    "AdvancedKeyManager",
    "load_api_keys_advanced", 
    "PromptRegistry",
    "apply_replacements",
    "PromptPack",
    "ImageSpec",
    "ImageSource", 
    "LocalFileSource",
    "UrlSource",
    "FolderSequencerSource",
    "RecursiveFolderSequencerSource",
    "install_log_tee",
    "log_jsonl",
    "OutputPathManager",
    "render_filename",
    "embed_info_to_png",
    "extract_info_from_png",
    "build_plan",
    "execute_plan",
]
