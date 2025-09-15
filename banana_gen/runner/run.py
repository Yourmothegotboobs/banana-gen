from typing import List, Dict, Optional

from ..prompts.registry import PromptRegistry
from ..prompts.replace import apply_replacements
from ..images.sources import ImageSource, ImageSpec
from ..output.paths import OutputPathManager
from ..output.filenames import render_filename


def _token_summary(replacements: Dict[str, str], max_pairs: int = 3) -> str:
    if not replacements:
        return "default"
    pairs = []
    for i, k in enumerate(sorted(replacements.keys())):
        if i >= max_pairs:
            break
        v = str(replacements[k])
        pairs.append(f"{k}-{v[:12]}")
    return "_".join(pairs)


def build_plan(
    registry: PromptRegistry,
    prompt_id: str,
    input_sources: List[ImageSource],
    *,
    replacements: Optional[Dict[str, str]] = None,
    replacement_sets: Optional[List[Dict[str, str]]] = None,
    output_manager: Optional[OutputPathManager] = None,
    filename_template: str = "{base}-{promptId}-{date}-{time}.png",
    base_name: Optional[str] = None,
) -> List[dict]:
    """
    仅构建执行计划，不做任何 API 调用或磁盘写入。
    返回的每个任务包含：prompt 文本（已应用替换）、输入图片规格、输出目录与文件名。
    """
    entry = registry.get(prompt_id)

    # 收集输入图片规格（每个来源取一张）
    inputs: List[ImageSpec] = []
    for src in input_sources or []:
        spec = src.next_image()
        inputs.append(spec)

    def _one_task(rep: Dict[str, str]) -> dict:
        prompt_text = apply_replacements(entry.text, rep or {})
        token_sum = _token_summary(rep or {})
        out_dir = output_manager.ensure_dir(token_sum) if output_manager else "."
        context = {
            "base": base_name or prompt_id,
            "promptId": prompt_id,
        }
        out_name = render_filename(filename_template, context)
        return {
            "prompt_id": prompt_id,
            "prompt_text": prompt_text,
            "replacements": rep or {},
            "inputs": [spec.__dict__ for spec in inputs],
            "output_dir": out_dir,
            "output_filename": out_name,
            "output_path": f"{out_dir}/{out_name}",
        }

    tasks: List[dict] = []
    if replacement_sets:
        for rep in replacement_sets:
            tasks.append(_one_task(rep))
    else:
        tasks.append(_one_task(replacements or {}))
    return tasks


