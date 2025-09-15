import os
import sys
import json
import threading
from datetime import datetime

_tee_installed = False
_log_fp = None
_jsonl_lock = threading.Lock()


class _Tee:
    def __init__(self, *streams):
        self._streams = streams

    def write(self, s):
        for st in self._streams:
            try:
                st.write(s)
                st.flush()
            except Exception:
                pass

    def flush(self):
        for st in self._streams:
            try:
                st.flush()
            except Exception:
                pass


def install_log_tee(script_basename: str) -> str:
    global _tee_installed, _log_fp
    if _tee_installed and _log_fp:
        return _log_fp.name

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logs_dir = os.path.join(project_root, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(logs_dir, f"{script_basename}_{timestamp}.log")

    _log_fp = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = _Tee(sys.__stdout__, _log_fp)
    sys.stderr = _Tee(sys.__stderr__, _log_fp)
    _tee_installed = True
    return log_path


def _jsonl_path() -> str:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logs_dir = os.path.join(project_root, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    return os.path.join(logs_dir, "records.jsonl")


def log_jsonl(event: dict):
    """线程安全的 JSONL 日志记录"""
    with _jsonl_lock:
        try:
            event = dict(event or {})
            if "time" not in event:
                event["time"] = datetime.utcnow().isoformat() + "Z"
            with open(_jsonl_path(), "a", encoding="utf-8") as fp:
                fp.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            # 不抛出，避免影响主流程
            pass


