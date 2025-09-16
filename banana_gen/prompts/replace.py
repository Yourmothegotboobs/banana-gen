from typing import Dict, List


def apply_replacements(text: str, mapping: Dict[str, str]) -> str:
    if not mapping:
        return text
    result = text
    for key, val in mapping.items():
        if key and val is not None:
            result = result.replace(key, str(val))
    return result


class PromptPack:
    def __init__(self, base_ids: List[str]):
        self.base_ids = list(base_ids or [])

    def apply_pack(self, texts: Dict[str, str], mapping: Dict[str, str]) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for pid in self.base_ids:
            if pid in texts:
                out[pid] = apply_replacements(texts[pid], mapping)
        return out


