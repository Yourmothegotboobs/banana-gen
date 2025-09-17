import re
import hashlib
import threading
from datetime import datetime


def _slug(text: str, max_len: int = 40) -> str:
    """将文本转换为安全的文件名 slug"""
    s = re.sub(r"[^0-9A-Za-z-_]+", "-", str(text)).strip("-")
    if len(s) <= max_len:
        return s
    h = hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]
    return s[: max_len - 9] + "-" + h


def render_filename(template: str, context: dict) -> str:
    """渲染文件名模板，支持线程安全"""
    now = datetime.now()
    defaults = {
        "date": now.strftime("%Y%m%d"),
        "time": now.strftime("%H%M%S"),
        "microsecond": now.microsecond,
        "thread_id": threading.get_ident() % 10000,
    }
    values = {**defaults, **(context or {})}
    safe = {k: _slug(v) if isinstance(v, str) else v for k, v in values.items()}
    try:
        return template.format(**safe)
    except Exception:
        # 回退到基础模板
        return "{base}-{promptId}-{date}-{time}.png".format(**safe)


