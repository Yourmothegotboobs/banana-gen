# 复制自 aistdio-banana/tools/advanced_key_manager.py，保持接口一致，便于独立演进
from typing import List, Optional, Dict, Set
import threading
import time
import os
import glob
from datetime import datetime, timedelta
from tqdm import tqdm


class AdvancedKeyManager:
    """
    高级API Key管理器（复制版），接口与原版一致：
    - 多级优先级key管理
    - 动态key池管理
    - 负载均衡轮换
    - 智能错误处理和key切换
    - 失效Key的冷却与自动恢复
    """

    def __init__(self, key_pools: Optional[Dict[int, List[str]]] = None, min_active_keys: int = 5):
        if key_pools is None:
            key_pools = {}
        
        self._key_pools = {}
        total_keys = 0
        for priority, keys in key_pools.items():
            clean_keys = [k.strip() for k in keys if k and k.strip()]
            if clean_keys:
                self._key_pools[priority] = clean_keys
                total_keys += len(clean_keys)

        self._min_active_keys = min_active_keys
        self._current_index = 0
        self._lock = threading.Lock()
        self._failed_keys: Set[str] = set()
        self._permanent_failed_keys: Set[str] = set()
        self._temporary_failures: Dict[str, Dict] = {}
        self._retry_cooldown: timedelta = timedelta(minutes=30)
        self._max_temp_failures_before_permanent: int = 3
        self._last_refresh_monotonic: float = 0.0
        self._active_keys = []
        with self._lock:
            self._rebuild_active_pool()
        
        if self._key_pools:
            print(f"🔑 多级Key管理器已初始化:")
            for priority in sorted(self._key_pools.keys()):
                print(f"   优先级 {priority}: {len(self._key_pools[priority])} 个key")
            print(f"   总key数: {total_keys}, 最小活跃数: {min_active_keys}")
        else:
            print("🔑 多级Key管理器已初始化（空状态）")
        with self._lock:
            print(f"   当前活跃池: {len(self._active_keys)} 个key")

    def configure_recovery(self, retry_cooldown_minutes: Optional[int] = None,
                           max_temp_failures_before_permanent: Optional[int] = None):
        with self._lock:
            if retry_cooldown_minutes is not None and retry_cooldown_minutes > 0:
                self._retry_cooldown = timedelta(minutes=retry_cooldown_minutes)
            if max_temp_failures_before_permanent is not None and max_temp_failures_before_permanent > 0:
                self._max_temp_failures_before_permanent = max_temp_failures_before_permanent

    @classmethod
    def from_directory(cls, directory: str, min_active_keys: int = 5):
        if not os.path.isdir(directory):
            raise ValueError(f"Directory '{directory}' does not exist.")
        pattern = os.path.join(directory, "api_keys_*.txt")
        key_files = glob.glob(pattern)
        if not key_files:
            raise ValueError(f"No api_keys_*.txt files found in '{directory}'")
        key_pools = {}
        for file_path in key_files:
            filename = os.path.basename(file_path)
            try:
                priority_str = filename.split('_')[2].split('.')[0]
                priority = int(priority_str)
                with open(file_path, 'r', encoding='utf-8') as f:
                    keys = []
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            keys.append(line)
                if keys:
                    key_pools[priority] = keys
                    print(f"📁 加载 {filename}: {len(keys)} 个key")
                else:
                    print(f"⚠️ {filename} 中没有找到有效key")
            except (ValueError, IndexError) as e:
                print(f"⚠️ 跳过文件 {filename}: 无法解析优先级 ({e})")
                continue
            except Exception as e:
                print(f"⚠️ 读取文件 {file_path} 失败: {e}")
                continue
        if not key_pools:
            raise ValueError(f"No valid keys loaded from '{directory}'")
        return cls(key_pools, min_active_keys)

    def _rebuild_active_pool(self):
        sorted_priorities = sorted(self._key_pools.keys())
        new_active_keys = []
        now = datetime.utcnow()
        for priority in sorted_priorities:
            for k in self._key_pools[priority]:
                if k in self._permanent_failed_keys:
                    continue
                if k in self._temporary_failures:
                    info = self._temporary_failures[k]
                    last_failed_at: datetime = info.get("last_failed_at", now)
                    if now - last_failed_at >= self._retry_cooldown:
                        self._failed_keys.discard(k)
                        self._temporary_failures.pop(k, None)
                        new_active_keys.append(k)
                    else:
                        continue
                else:
                    if k not in self._failed_keys:
                        new_active_keys.append(k)
            if len(new_active_keys) >= self._min_active_keys:
                break
        self._active_keys = new_active_keys
        self._current_index = 0
        if len(self._active_keys) < self._min_active_keys:
            tqdm.write(f"⚠️ 活跃key池仅有 {len(self._active_keys)} 个key，少于要求的 {self._min_active_keys} 个")

    def get_current_key(self) -> Optional[str]:
        with self._lock:
            self._maybe_refresh_locked()
            if not self._active_keys:
                return None
            active_count = len(self._active_keys)
            if active_count == 0:
                return None
            safe_index = self._current_index % active_count
            key = self._active_keys[safe_index]
            self._current_index = (self._current_index + 1) % active_count
            return key

    def mark_key_failed(self, key: str, error_type: str = "unknown") -> bool:
        if not key or not isinstance(key, str):
            return len(self._active_keys) > 0
        with self._lock:
            now = datetime.utcnow()
            is_perm = self._is_permanent_error_unlocked(error_type)
            self._failed_keys.add(key)
            if is_perm:
                self._permanent_failed_keys.add(key)
            else:
                info = self._temporary_failures.get(key, {"last_failed_at": now, "failure_count": 0, "error_type": error_type})
                info["failure_count"] = int(info.get("failure_count", 0)) + 1
                info["last_failed_at"] = now
                info["error_type"] = error_type
                self._temporary_failures[key] = info
                if info["failure_count"] >= self._max_temp_failures_before_permanent:
                    self._permanent_failed_keys.add(key)
                    self._temporary_failures.pop(key, None)

            failed_priority = None
            for priority, keys in self._key_pools.items():
                if key in keys:
                    failed_priority = priority
                    break

            def _mask(k: str) -> str:
                if len(k) <= 12:
                    return k[: max(1, len(k)//3)] + "..." + k[-max(1, len(k)//3):]
                return f"{k[:6]}...{k[-4:]}"

            masked = _mask(key)
            if key in self._permanent_failed_keys:
                scope = "永久失效"
                extra = ""
            else:
                scope = "临时失效"
                next_retry_at = now + self._retry_cooldown
                extra = f" | 冷却至: {next_retry_at.strftime('%Y-%m-%d %H:%M:%S')} UTC"
            if failed_priority is not None:
                tqdm.write(f"🔑 Key失效[{scope}] ({error_type}): 优先级 {failed_priority} | key: {masked}{extra}")
            else:
                tqdm.write(f"🔑 Key失效[{scope}] ({error_type}): 未知优先级 | key: {masked}{extra}")

            old_active_count = len(self._active_keys)
            self._rebuild_active_pool()
            new_active_count = len(self._active_keys)
            tqdm.write(f"🔑 活跃池更新: {old_active_count} -> {new_active_count} 个key")
            for priority in sorted(self._key_pools.keys()):
                available = 0
                total = len(self._key_pools[priority])
                for k in self._key_pools[priority]:
                    if k in self._permanent_failed_keys:
                        continue
                    if k in self._temporary_failures:
                        info = self._temporary_failures[k]
                        if datetime.utcnow() - info.get("last_failed_at", now) >= self._retry_cooldown:
                            available += 1
                    elif k not in self._failed_keys:
                        available += 1
                tqdm.write(f"🔑 优先级 {priority}: {available}/{total} 个可用key")
            return len(self._active_keys) > 0

    def has_available_keys(self) -> bool:
        with self._lock:
            self._maybe_refresh_locked()
            return len(self._active_keys) > 0

    def reset_failed_keys(self):
        with self._lock:
            self._failed_keys.clear()
            self._permanent_failed_keys.clear()
            self._temporary_failures.clear()
            self._rebuild_active_pool()
            print("🔄 已重置所有失效key，重新构建活跃池")

    def reactivate_key(self, key: str) -> bool:
        with self._lock:
            exists = any(key in keys for keys in self._key_pools.values())
            self._failed_keys.discard(key)
            self._permanent_failed_keys.discard(key)
            self._temporary_failures.pop(key, None)
            self._rebuild_active_pool()
            return exists

    def _maybe_refresh_locked(self):
        import time as _t
        now_mono = _t.monotonic()
        if now_mono - self._last_refresh_monotonic < 10:
            return
        self._last_refresh_monotonic = now_mono
        self._rebuild_active_pool()

    def _is_permanent_error_unlocked(self, error_type: str) -> bool:
        if not error_type:
            return False
        et = str(error_type).lower()
        permanent_keywords = [
            "unauthorized", "permissiondenied", "forbidden", "suspend", "suspended",
            "invalid", "revoked", "expired", "unauthenticated", "not found", "deleted",
        ]
        return any(k in et for k in permanent_keywords)

    def get_stats(self) -> dict:
        with self._lock:
            priority_stats = {}
            for priority in sorted(self._key_pools.keys()):
                available = 0
                for k in self._key_pools[priority]:
                    if k in self._permanent_failed_keys:
                        continue
                    if k in self._temporary_failures:
                        info = self._temporary_failures[k]
                        if datetime.utcnow() - info.get("last_failed_at", datetime.utcnow()) >= self._retry_cooldown:
                            available += 1
                    elif k not in self._failed_keys:
                        available += 1
                total = len(self._key_pools[priority])
                priority_stats[f"priority_{priority}"] = {
                    "total": total,
                    "available": available,
                    "failed": total - available
                }
            total_keys = sum(len(keys) for keys in self._key_pools.values())
            total_available = 0
            for keys in self._key_pools.values():
                for k in keys:
                    if k in self._permanent_failed_keys:
                        continue
                    if k in self._temporary_failures:
                        info = self._temporary_failures[k]
                        if datetime.utcnow() - info.get("last_failed_at", datetime.utcnow()) >= self._retry_cooldown:
                            total_available += 1
                    elif k not in self._failed_keys:
                        total_available += 1
            return {
                "total_keys": total_keys,
                "total_available": total_available,
                "failed_count": len(self._failed_keys),
                "permanent_failed_count": len(self._permanent_failed_keys),
                "temporary_failed_count": len(self._temporary_failures),
                "active_pool_size": len(self._active_keys),
                "min_active_keys": self._min_active_keys,
                "retry_cooldown_minutes": int(self._retry_cooldown.total_seconds() // 60),
                "max_temp_failures_before_permanent": self._max_temp_failures_before_permanent,
                "priority_levels": len(self._key_pools),
                "priorities": priority_stats
            }


def load_api_keys_advanced(keys_directory="keys", min_active_keys=5):
    return AdvancedKeyManager.from_directory(keys_directory, min_active_keys)


SWITCHABLE_HTTP_CODES = {
    400: "Bad Request - 请求参数错误",
    401: "Unauthorized - 认证失败",
    403: "Forbidden - API密钥被暂停或权限不足",
    404: "Not Found - 资源不存在",
    429: "Too Many Requests - 配额超出",
    500: "Internal Server Error - 服务器内部错误",
    502: "Bad Gateway - 网关错误",
    503: "Service Unavailable - 服务不可用",
    504: "Gateway Timeout - 网关超时",
}

SWITCHABLE_EXCEPTIONS = {
    "PermissionDenied": "权限拒绝",
    "ResourceExhausted": "配额超出",
    "InvalidArgument": "参数无效",
    "NotFound": "资源不存在",
    "Unauthenticated": "认证失败",
    "DeadlineExceeded": "请求超时",
    "ServiceUnavailable": "服务不可用",
    "ServerError": "服务器错误",
    "InternalServerError": "内部服务器错误",
}


def should_switch_key(exception_or_status) -> bool:
    if isinstance(exception_or_status, int):
        return exception_or_status != 200
    elif hasattr(exception_or_status, '__class__'):
        return True
    elif isinstance(exception_or_status, str):
        return True
    return True


def get_error_description(exception_or_status) -> str:
    if isinstance(exception_or_status, int):
        return SWITCHABLE_HTTP_CODES.get(exception_or_status, f"HTTP {exception_or_status}")
    elif hasattr(exception_or_status, '__class__'):
        class_name = exception_or_status.__class__.__name__
        if class_name in SWITCHABLE_EXCEPTIONS:
            return SWITCHABLE_EXCEPTIONS[class_name]
        else:
            return class_name
    elif isinstance(exception_or_status, str):
        return SWITCHABLE_EXCEPTIONS.get(exception_or_status, exception_or_status)
    return f"Unknown Error: {exception_or_status}"


# 为 AdvancedKeyManager 添加缺少的方法
def _add_missing_methods():
    """为 AdvancedKeyManager 类添加缺少的方法"""
    
    def get_total_keys(self) -> int:
        """获取总key数量"""
        with self._lock:
            return sum(len(keys) for keys in self._key_pools.values())
    
    def load_keys_from_file(self, file_path: str, priority: int = 1):
        """从文件加载 keys"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 过滤掉注释行和空行，只保留有效的 key
            keys = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    keys.append(line)
            
            if keys:
                with self._lock:
                    if priority not in self._key_pools:
                        self._key_pools[priority] = []
                    self._key_pools[priority].extend(keys)
                    self._rebuild_active_pool()
                print(f"✅ 从文件加载了 {len(keys)} 个 keys: {file_path}")
                print(f"   前3个 keys: {keys[:3]}")
            else:
                print(f"⚠️ 文件为空或无效: {file_path}")
        except Exception as e:
            print(f"❌ 加载 key 文件失败 {file_path}: {e}")
    
    def load_keys_from_directory(self, directory: str):
        """从目录加载所有 key 文件"""
        if not os.path.exists(directory):
            print(f"⚠️ 目录不存在: {directory}")
            return
        
        key_files = glob.glob(os.path.join(directory, "api_keys_*.txt"))
        if not key_files:
            print(f"⚠️ 目录中未找到 api_keys_*.txt 文件: {directory}")
            return
        
        for key_file in sorted(key_files):
            # 从文件名提取优先级
            filename = os.path.basename(key_file)
            if filename.startswith("api_keys_") and filename.endswith(".txt"):
                try:
                    priority = int(filename[9:-4])  # 提取数字部分
                except ValueError:
                    priority = 1
                self.load_keys_from_file(key_file, priority)
    
    # 将方法添加到类中
    AdvancedKeyManager.get_total_keys = get_total_keys
    AdvancedKeyManager.load_keys_from_file = load_keys_from_file
    AdvancedKeyManager.load_keys_from_directory = load_keys_from_directory

# 执行方法添加
_add_missing_methods()


