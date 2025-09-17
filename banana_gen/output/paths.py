import os
from typing import Optional


class OutputPathManager:
    """
    strategy:
      - "A": 全部统一路径 base_dir
      - "B": 按替换词（tokenKey 或摘要）分不同路径
      - "C": 同路径下按替换词建立子目录
    """

    def __init__(self, base_dir: str, strategy: str = "A", token_group_id: Optional[str] = None):
        self.base_dir = base_dir
        self.strategy = strategy.upper()
        self.token_group_id = token_group_id or "default"

    def ensure_dir(self, token_summary: Optional[str] = None) -> str:
        if self.strategy == "A":
            out = self.base_dir
        elif self.strategy == "B":
            out = os.path.join(self.base_dir, f"tokens-{self.token_group_id}")
        else:  # C
            sub = token_summary or self.token_group_id
            out = os.path.join(self.base_dir, sub)
        os.makedirs(out, exist_ok=True)
        return out


