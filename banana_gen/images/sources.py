from dataclasses import dataclass
from typing import Optional, List, Iterator
import os
import json
import hashlib
import threading


@dataclass
class ImageSpec:
    path: Optional[str] = None
    url: Optional[str] = None


class ImageSource:
    def next_image(self) -> ImageSpec:
        raise NotImplementedError

    def peek_info(self) -> str:
        return self.__class__.__name__


class LocalFileSource(ImageSource):
    def __init__(self, file_path: str):
        self.file_path = file_path

    def next_image(self) -> ImageSpec:
        return ImageSpec(path=self.file_path)

    def peek_info(self) -> str:
        return self.file_path


class UrlSource(ImageSource):
    def __init__(self, url: str):
        self.url = url

    def next_image(self) -> ImageSpec:
        return ImageSpec(url=self.url)

    def peek_info(self) -> str:
        return self.url


def _iter_sorted_files(folder: str, recursive: bool) -> Iterator[str]:
    """遍历文件夹中的图片文件，按文件名排序"""
    if not os.path.isdir(folder):
        return
    
    # 支持的图片格式 - 参考原始代码
    SUPPORTED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp')
    
    entries: List[str] = []
    if recursive:
        for root, _, files in os.walk(folder):
            for f in files:
                if f.startswith('.'):
                    continue
                # 只包含支持的图片格式
                if f.lower().endswith(SUPPORTED_EXTENSIONS):
                    entries.append(os.path.join(root, f))
    else:
        for f in os.listdir(folder):
            if f.startswith('.'):
                continue
            # 只包含支持的图片格式
            if f.lower().endswith(SUPPORTED_EXTENSIONS):
                entries.append(os.path.join(folder, f))
    
    for p in sorted(entries):
        yield p


class FolderSequencerSource(ImageSource):
    def __init__(self, folder: str, state_file: Optional[str] = None):
        self.folder = folder
        self.state_file = state_file
        self._current_index = 0
        self._files = list(_iter_sorted_files(folder, recursive=False))
        self._lock = threading.Lock()  # 添加线程锁
        self._load_state()

    def _load_state(self):
        if not self.state_file or not os.path.exists(self.state_file):
            return
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                folder_hash = hashlib.md5(self.folder.encode()).hexdigest()[:8]
                if data.get('folder_hash') == folder_hash:
                    self._current_index = data.get('index', 0)
        except Exception:
            pass

    def _save_state(self):
        if not self.state_file:
            return
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            folder_hash = hashlib.md5(self.folder.encode()).hexdigest()[:8]
            data = {
                'folder_hash': folder_hash,
                'index': self._current_index,
                'folder': self.folder
            }
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception:
            pass

    def next_image(self) -> ImageSpec:
        with self._lock:
            if self._current_index >= len(self._files):
                raise StopIteration("No more images in folder")
            path = self._files[self._current_index]
            self._current_index += 1
            self._save_state()
            return ImageSpec(path=path)

    def peek_info(self) -> str:
        return f"Folder[{self.folder}] ({self._current_index}/{len(self._files)})"


class RecursiveFolderSequencerSource(ImageSource):
    def __init__(self, folder: str, state_file: Optional[str] = None):
        self.folder = folder
        self.state_file = state_file
        self._current_index = 0
        self._files = list(_iter_sorted_files(folder, recursive=True))
        self._lock = threading.Lock()  # 添加线程锁
        self._load_state()

    def _load_state(self):
        if not self.state_file or not os.path.exists(self.state_file):
            return
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                folder_hash = hashlib.md5(self.folder.encode()).hexdigest()[:8]
                if data.get('folder_hash') == folder_hash:
                    self._current_index = data.get('index', 0)
        except Exception:
            pass

    def _save_state(self):
        if not self.state_file:
            return
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            folder_hash = hashlib.md5(self.folder.encode()).hexdigest()[:8]
            data = {
                'folder_hash': folder_hash,
                'index': self._current_index,
                'folder': self.folder
            }
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception:
            pass

    def next_image(self) -> ImageSpec:
        with self._lock:
            if self._current_index >= len(self._files):
                raise StopIteration("No more images in recursive folder")
            path = self._files[self._current_index]
            self._current_index += 1
            self._save_state()
            return ImageSpec(path=path)

    def peek_info(self) -> str:
        return f"RecursiveFolder[{self.folder}] ({self._current_index}/{len(self._files)})"


