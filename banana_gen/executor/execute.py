from typing import List, Dict
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from ..keys import AdvancedKeyManager, should_switch_key, get_error_description
from ..logging import install_log_tee, log_jsonl
from ..output.metadata import embed_info_to_png


def _mask_key(key: str) -> str:
    if not key:
        return ""
    return key[:6] + "..." + key[-4:] if len(key) > 12 else key


# 全局文件名生成锁和计数器
_filename_lock = threading.Lock()
_filename_counter = 0


def _generate_unique_filename(base_name: str, prompt_id: str) -> str:
    """线程安全的唯一文件名生成函数"""
    global _filename_counter
    with _filename_lock:
        _filename_counter += 1
        timestamp = datetime.now()
        time_str = timestamp.strftime("%m%d%H%M%S")
        microsecond = timestamp.microsecond
        thread_id = threading.get_ident() % 10000
        counter_str = f"{_filename_counter:04d}"
        
        # 截断过长的 base_name
        if len(base_name) > 20:
            base_name = base_name[:20]
        
        filename = f"{base_name}-{prompt_id}-{time_str}-{microsecond}-{thread_id}-{counter_str}.png"
        return filename


def _execute_single_task(task: Dict, key_manager: AdvancedKeyManager, embed_metadata: bool = True) -> str:
    """执行单个任务的内部函数"""
    output_dir = task["output_dir"]
    output_path = task["output_path"]
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 检查文件是否已存在，如果存在则生成新的唯一文件名
    if os.path.exists(output_path):
        base_name = os.path.splitext(os.path.basename(output_path))[0]
        prompt_id = task.get("prompt_id", "unknown")
        new_filename = _generate_unique_filename(base_name, prompt_id)
        output_path = os.path.join(output_dir, new_filename)
        task["output_path"] = output_path  # 更新任务中的路径

    # Key 轮换循环
    max_retries = 3
    for attempt in range(max_retries):
        current_key = key_manager.get_current_key()
        if not current_key:
            log_jsonl({"event": "error", "reason": "no_key", "task": task, "attempt": attempt + 1})
            if attempt == max_retries - 1:
                return f"❌ 失败 (无可用key): {task.get('prompt_id', 'unknown')}"
            time.sleep(1)
            continue

        try:
            # 这里应该调用实际模型生成图片并获得 PNG 字节
            # 为避免执行，使用空 PNG 头最小骨架作为占位（调用方替换为真实返回）
            png_stub = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xDE\x00\x00\x00\x0bIDAT\x08\xd7c```\x00\x00\x00\x05\x00\x01\x0d\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"

            meta = {
                "prompt_id": task.get("prompt_id"),
                "prompt": task.get("prompt_text"),
                "inputs": task.get("inputs"),
                "key": _mask_key(current_key),
                "timestamp": datetime.now().isoformat(),
            }
            
            if embed_metadata:
                out_bytes = embed_info_to_png(png_stub, meta)
            else:
                out_bytes = png_stub

            # 原子性写入文件
            temp_path = output_path + ".tmp"
            with open(temp_path, "wb") as fp:
                fp.write(out_bytes)
            os.rename(temp_path, output_path)

            log_jsonl({
                "event": "complete",
                "output": output_path,
                "key": _mask_key(current_key),
                "prompt_id": task.get("prompt_id"),
            })
            
            return f"✅ 成功: {output_path}"

        except Exception as e:
            error_desc = get_error_description(e)
            if should_switch_key(e):
                if key_manager.mark_key_failed(current_key, error_desc):
                    log_jsonl({
                        "event": "key_switch",
                        "reason": error_desc,
                        "key": _mask_key(current_key),
                        "attempt": attempt + 1
                    })
                    continue
                else:
                    return f"❌ 失败 (无可用key): {task.get('prompt_id', 'unknown')}"
            else:
                return f"❌ 失败 ({error_desc}): {task.get('prompt_id', 'unknown')}"

    return f"❌ 失败 (重试次数耗尽): {task.get('prompt_id', 'unknown')}"


def execute_plan(
    tasks: List[Dict],
    *,
    key_manager: AdvancedKeyManager,
    script_name: str = "banana-gen",
    embed_metadata: bool = True,
    max_workers: int = 3,
    max_retries: int = 3,
    log_path: str = None,
):
    """
    将 runner 生成的 plan 执行为本地输出文件（支持并发处理）。
    实际图像生成流程由调用方接入 Google API；此处只统一落盘与日志。
    
    Args:
        tasks: 任务列表
        key_manager: Key 管理器
        script_name: 脚本名称
        embed_metadata: 是否嵌入元数据
        max_workers: 最大并发数
        max_retries: 最大重试次数
        log_path: 日志文件路径（可选，如果不提供则不设置日志）
    """
    if log_path is None:
        log_path = install_log_tee(script_name)
    
    # 只有在有有效日志路径时才记录日志
    if log_path:
        log_jsonl({
            "event": "start", 
            "script": script_name, 
            "log": log_path,
            "total_tasks": len(tasks),
            "max_workers": max_workers
        })

    print(f"🚀 开始执行 {len(tasks)} 个任务，并行度: {max_workers}")
    
    completed_count = 0
    failed_count = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_task = {
            executor.submit(_execute_single_task, task, key_manager, embed_metadata): task 
            for task in tasks
        }
        
        # 处理完成的任务
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                result = future.result()
                print(result)
                if "✅" in result:
                    completed_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                print(f"❌ 任务异常: {task.get('prompt_id', 'unknown')} - {e}")
                failed_count += 1
    
    # 只有在有有效日志路径时才记录结束日志
    if log_path:
        log_jsonl({
            "event": "batch_complete",
            "completed": completed_count,
            "failed": failed_count,
            "total": len(tasks)
        })
    
    print(f"📊 批处理完成: 成功 {completed_count}, 失败 {failed_count}, 总计 {len(tasks)}")


