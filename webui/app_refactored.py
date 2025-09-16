#!/usr/bin/env python3
"""
Banana Gen Web UI - 完全重构版本
基于新的 API，简洁干净的界面
"""

import os
import json
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from werkzeug.utils import secure_filename

# 导入 banana-gen 核心模块
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

try:
    from banana_gen import (
        UnifiedImageGenerator, TaskManager, PromptRegistry, Prompt,
        AdvancedKeyManager, TaskStatus,
        LocalImage, UrlImage, ImageFolder, ImageRecursionFolder,
        install_log_tee, log_jsonl,
        OutputPathManager, extract_info_from_png
    )
except ImportError as e:
    print(f"❌ 导入 banana_gen 模块失败: {e}")
    sys.exit(1)

app = Flask(__name__)
app.secret_key = 'banana-gen-webui-refactored'

# 全局状态
key_manager = None
generator = None
prompt_registry = None
current_task_manager = None
output_manager = None

# 配置
UPLOAD_FOLDER = 'webui/uploads'
OUTPUT_FOLDER = 'webui/outputs'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_key_manager():
    """初始化 Key 管理器"""
    global key_manager
    try:
        # 尝试多个目录位置
        key_dirs = ['banana_gen/keys', 'webui/keys', 'keys']
        for key_dir in key_dirs:
            print(f"🔍 检查目录: {key_dir}")
            if os.path.exists(key_dir):
                # 检查是否有 api_keys_*.txt 文件
                import glob
                key_files = glob.glob(os.path.join(key_dir, "api_keys_*.txt"))
                print(f"   找到 key 文件: {key_files}")

                if key_files:
                    print(f"🔑 尝试从目录 {key_dir} 加载 keys...")
                    key_manager = AdvancedKeyManager.from_directory(key_dir, min_active_keys=1)
                    print(f"✅ Key 管理器初始化成功，从目录: {key_dir}")

                    # 打印统计信息
                    stats = key_manager.get_stats()
                    print(f"   总 Keys: {stats.get('total_keys', 0)}")
                    print(f"   活跃 Keys: {stats.get('active_keys', 0)}")
                    return True
                else:
                    print(f"   目录 {key_dir} 存在但没有 api_keys_*.txt 文件")

        # 如果没有找到 keys 创建空的管理器
        print("⚠️ 未找到任何有效的 API Keys 文件，使用空配置")
        key_manager = AdvancedKeyManager({})
        return True
    except Exception as e:
        print(f"❌ Key 管理器初始化失败: {e}")
        import traceback
        traceback.print_exc()
        key_manager = None
        return False

def init_generator():
    """初始化统一图像生成器"""
    global generator, key_manager
    try:
        # 使用 CLI 的 Key 管理器初始化生成器
        if key_manager:
            generator = UnifiedImageGenerator(key_source=key_manager, max_workers=3)
        else:
            # 尝试自动扫描 keys
            generator = UnifiedImageGenerator(max_workers=3)
        print(f"✅ 统一图像生成器初始化成功")
        return True
    except Exception as e:
        print(f"❌ 统一图像生成器初始化失败: {e}")
        generator = None
        return False

def init_prompt_registry():
    """初始化 Prompt 注册表 - 使用 CLI 的自动加载机制"""
    global prompt_registry
    try:
        # 使用 CLI 的自动加载机制，它会自动查找并加载 prompts 文件
        prompt_registry = PromptRegistry()
        print(f"✅ Prompt 注册表初始化成功，共加载 {len(prompt_registry.list_all())} 个 prompts")
        return True
    except Exception as e:
        print(f"❌ Prompt 注册表初始化失败: {e}")
        prompt_registry = PromptRegistry()
        return False

def init_output_manager():
    """初始化输出管理器"""
    global output_manager
    try:
        output_manager = OutputPathManager(
            output_dir=OUTPUT_FOLDER,
            path_strategy='unified'  # 统一路径策略
        )
        print(f"✅ 输出管理器初始化成功")
        return True
    except Exception as e:
        print(f"❌ 输出管理器初始化失败: {e}")
        output_manager = None
        return False

@app.route('/')
def index():
    """主页"""
    return render_template('index_refactored.html')

# ==================== 任务管理 ====================

@app.route('/tasks')
def tasks_page():
    """任务管理页面"""
    if not prompt_registry:
        init_prompt_registry()
    
    prompts = []
    if prompt_registry:
        for prompt_id in prompt_registry.list_all():
            prompt = prompt_registry.get(prompt_id)
            if prompt:
                prompts.append({
                    'id': prompt.id, 
                    'text': prompt.text[:100] + '...', 
                    'input_count': prompt.input_count
                })
    
    return render_template('tasks_refactored.html', prompts=prompts, status=execution_status)

@app.route('/api/tasks/create', methods=['POST'])
def api_create_task():
    """创建任务 - 完全使用 CLI 接口"""
    data = request.json

    if not generator:
        return jsonify({'error': 'Generator not initialized'}), 500

    if not prompt_registry:
        return jsonify({'error': 'Prompt registry not initialized'}), 500

    try:
        # 记录任务创建事件
        log_jsonl({
            'event': 'task_creation_started',
            'timestamp': datetime.now().isoformat(),
            'input_sources_count': len(data.get('input_sources', [])),
            'prompt_ids': data.get('prompt_ids', [])
        })

        # 构建输入配置 - 使用 CLI 的标准配置格式
        input_configs = []
        for source_config in data.get('input_sources', []):
            source_type = source_config['type']
            if source_type == 'local_image':
                input_configs.append({
                    'type': 'local_image',
                    'main_path': source_config['path'],
                    'fallback_paths': source_config.get('fallback_paths', [])
                })
            elif source_type == 'url_image':
                input_configs.append({
                    'type': 'url_image',
                    'main_path': source_config['url'],
                    'fallback_urls': source_config.get('fallback_urls', [])
                })
            elif source_type == 'folder':
                input_configs.append({
                    'type': 'folder',
                    'main_path': source_config['path'],
                    'fallback_paths': source_config.get('fallback_paths', [])
                })
            elif source_type == 'recursive_folder':
                input_configs.append({
                    'type': 'recursive_folder',
                    'main_path': source_config['path'],
                    'fallback_paths': source_config.get('fallback_paths', [])
                })

        # 使用 CLI 的 prompt 获取方法
        prompt_ids = data.get('prompt_ids', [])
        prompts = prompt_registry.get_prompts_by_ids(prompt_ids)

        # 字符串替换规则
        string_replace_list = data.get('string_replace_list', [])

        # 使用 CLI 的输出管理器配置路径
        output_dir = data.get('output_dir', OUTPUT_FOLDER)
        if output_manager:
            output_dir = output_manager.get_output_dir()

        # 使用 CLI 的 TaskManager.create_with_auto_fallback 方法
        global current_task_manager
        current_task_manager = TaskManager.create_with_auto_fallback(
            generator=generator,
            input_configs=input_configs,
            prompts=prompts,
            string_replace_list=string_replace_list,
            output_dir=output_dir,
            filename_template=data.get('filename_template', '{base}-{prompt_idx}-{replace_idx}-{image_idx}.png'),
            base_name=data.get('base_name', 'webui_task')
        )

        # 使用 CLI 的任务统计计算
        total_tasks = current_task_manager._calculate_total_tasks()

        # 记录成功事件
        log_jsonl({
            'event': 'task_creation_completed',
            'timestamp': datetime.now().isoformat(),
            'total_tasks': total_tasks,
            'task_manager_id': id(current_task_manager)
        })

        return jsonify({
            'success': True,
            'task_count': total_tasks,
            'task_id': id(current_task_manager),
            'message': f'任务创建成功，共 {total_tasks} 个任务'
        })

    except Exception as e:
        error_msg = str(e)
        log_jsonl({
            'event': 'task_creation_failed',
            'timestamp': datetime.now().isoformat(),
            'error': error_msg
        })
        return jsonify({'error': error_msg}), 500

@app.route('/api/tasks/start', methods=['POST'])
def api_start_task():
    """开始执行任务 - 使用 CLI 的任务管理接口"""
    if not current_task_manager:
        return jsonify({'error': 'No task created'}), 400

    # 检查任务状态
    status = current_task_manager.get_status()
    if status['status'] == TaskStatus.RUNNING:
        return jsonify({'error': 'Task already running'}), 400

    try:
        # 使用 CLI 的 start() 方法，它内部处理线程管理
        current_task_manager.start()

        return jsonify({
            'success': True,
            'message': 'Task started successfully',
            'task_id': id(current_task_manager)  # 使用对象 ID 作为任务标识
        })

    except Exception as e:
        return jsonify({'error': f'Failed to start task: {str(e)}'}), 500

@app.route('/api/tasks/status')
def api_task_status():
    """获取任务状态 - 直接使用 CLI 的状态接口"""
    if current_task_manager:
        # 直接使用 CLI 的 get_status() 方法
        status = current_task_manager.get_status()

        # 格式化状态以便前端使用
        formatted_status = {
            'running': status['status'] == TaskStatus.RUNNING,
            'status': status['status'].name if hasattr(status['status'], 'name') else str(status['status']),
            'progress': {
                'completed': status['stats']['completed_tasks'],
                'failed': status['stats']['failed_tasks'],
                'total': status['stats']['total_tasks'],
                'progress_percent': (status['stats']['completed_tasks'] / max(status['stats']['total_tasks'], 1)) * 100
            },
            'stats': status['stats'],
            'generator_stats': status['generator_stats'],
            'start_time': status.get('start_time'),
            'end_time': status.get('end_time')
        }

        return jsonify(formatted_status)
    else:
        return jsonify({
            'running': False,
            'status': 'No task created',
            'progress': {'completed': 0, 'failed': 0, 'total': 0, 'progress_percent': 0},
            'stats': {},
            'generator_stats': {}
        })

# 添加任务控制端点
@app.route('/api/tasks/pause', methods=['POST'])
def api_pause_task():
    """暂停任务 - 使用 CLI 接口"""
    if not current_task_manager:
        return jsonify({'error': 'No task created'}), 400

    try:
        current_task_manager.pause()
        log_jsonl({
            'event': 'task_paused',
            'timestamp': datetime.now().isoformat(),
            'task_id': id(current_task_manager)
        })
        return jsonify({'success': True, 'message': 'Task paused'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/resume', methods=['POST'])
def api_resume_task():
    """恢复任务 - 使用 CLI 接口"""
    if not current_task_manager:
        return jsonify({'error': 'No task created'}), 400

    try:
        current_task_manager.resume()
        log_jsonl({
            'event': 'task_resumed',
            'timestamp': datetime.now().isoformat(),
            'task_id': id(current_task_manager)
        })
        return jsonify({'success': True, 'message': 'Task resumed'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/stop', methods=['POST'])
def api_stop_task():
    """停止任务 - 使用 CLI 接口"""
    if not current_task_manager:
        return jsonify({'error': 'No task created'}), 400

    try:
        current_task_manager.stop()
        log_jsonl({
            'event': 'task_stopped',
            'timestamp': datetime.now().isoformat(),
            'task_id': id(current_task_manager)
        })
        return jsonify({'success': True, 'message': 'Task stopped'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== Key 管理 ====================

@app.route('/keys')
def keys_page():
    """显示 Key 管理页面"""
    return render_template('keys_refactored.html')

@app.route('/api/keys/status')
def api_keys_status():
    """获取 Key 状态 - 使用 CLI 接口"""
    if not key_manager:
        return jsonify({'error': 'Key manager not initialized'}), 500

    try:
        stats = key_manager.get_stats()
        return jsonify({
            'success': True,
            'stats': stats,
            'has_available_keys': key_manager.has_available_keys()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/keys/reset', methods=['POST'])
def api_reset_keys():
    """重置失效 Keys - 使用 CLI 接口"""
    if not key_manager:
        return jsonify({'error': 'Key manager not initialized'}), 500

    try:
        key_manager.reset_failed_keys()
        log_jsonl({
            'event': 'keys_reset',
            'timestamp': datetime.now().isoformat()
        })
        return jsonify({'success': True, 'message': 'Failed keys reset successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== 输出文件管理 ====================

@app.route('/outputs')
def outputs_page():
    """输出文件页面 - 使用 CLI 的输出管理接口"""
    output_files = []

    try:
        if os.path.exists(OUTPUT_FOLDER):
            for root, dirs, files in os.walk(OUTPUT_FOLDER):
                for f in files:
                    if allowed_file(f):
                        file_path = os.path.join(root, f)
                        stat = os.stat(file_path)

                        # 尝试使用 CLI 的元数据提取功能
                        metadata = None
                        if f.lower().endswith('.png'):
                            try:
                                metadata = extract_info_from_png(file_path)
                            except:
                                pass

                        file_info = {
                            'filename': f,
                            'path': file_path,
                            'relative_path': os.path.relpath(file_path, OUTPUT_FOLDER),
                            'size': stat.st_size,
                            'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                            'metadata': metadata
                        }

                        output_files.append(file_info)

        # 按修改时间倒序排列
        output_files.sort(key=lambda x: x['modified'], reverse=True)

    except Exception as e:
        print(f"❌ 读取输出文件失败: {e}")

    return render_template('outputs_refactored.html', output_files=output_files)

@app.route('/outputs/<path:filename>')
def output_file(filename):
    """提供输出文件"""
    return send_file(os.path.join(OUTPUT_FOLDER, filename))

# ==================== 系统状态 ====================

@app.route('/status')
def status_page():
    """系统状态页面"""
    return render_template('status_refactored.html')

@app.route('/api/status')
def api_status():
    """获取系统状态 - 使用 CLI 的状态接口"""
    status = {
        'key_manager': key_manager is not None,
        'generator': generator is not None,
        'prompt_registry': prompt_registry is not None,
        'output_manager': output_manager is not None,
        'current_task': current_task_manager is not None
    }

    # Key 管理器状态
    if key_manager:
        try:
            key_stats = key_manager.get_stats()
            status['key_stats'] = key_stats
            status['keys_available'] = key_manager.has_available_keys()
        except Exception as e:
            status['key_stats'] = {'error': str(e)}
            status['keys_available'] = False

    # 生成器状态
    if generator:
        try:
            generator_stats = generator.get_stats()
            status['generator_stats'] = generator_stats
            status['generator_capacity'] = {
                'active_tasks': generator.get_active_task_count(),
                'idle_capacity': generator.get_idle_capacity()
            }
        except Exception as e:
            status['generator_stats'] = {'error': str(e)}

    # Prompt 注册表状态
    if prompt_registry:
        try:
            all_prompts = prompt_registry.list_all()
            status['prompt_count'] = len(all_prompts)
            status['prompts_by_input_count'] = {
                '0': len(prompt_registry.list_by_input_count(0)),
                '1': len(prompt_registry.list_by_input_count(1)),
                '2': len(prompt_registry.list_by_input_count(2)),
                '3': len(prompt_registry.list_by_input_count(3))
            }
        except Exception as e:
            status['prompt_count'] = 0
            status['prompt_error'] = str(e)

    # 任务状态
    if current_task_manager:
        try:
            task_status = current_task_manager.get_status()
            status['task_status'] = {
                'status': task_status['status'].name if hasattr(task_status['status'], 'name') else str(task_status['status']),
                'stats': task_status['stats']
            }
        except Exception as e:
            status['task_status'] = {'error': str(e)}

    return jsonify(status)

def initialize_app():
    """初始化应用 - 使用 CLI 的初始化流程"""
    print("🔧 初始化应用组件...")

    # 安装 CLI 的日志系统
    try:
        install_log_tee('webui')
        print("✅ 日志系统初始化成功")
    except Exception as e:
        print(f"⚠️ 日志系统初始化失败: {e}")

    # 按顺序初始化各个组件
    init_key_manager()
    init_generator()
    init_prompt_registry()
    init_output_manager()

    print("✅ 应用初始化完成")

# 自动初始化
initialize_app()

if __name__ == '__main__':
    print("🚀 Banana Gen Web UI (重构版) 启动中...")
    print("📱 访问地址: http://localhost:8888")
    print("📋 任务管理: http://localhost:8888/tasks")
    print("📁 输出文件: http://localhost:8888/outputs")
    print("📊 系统状态: http://localhost:8888/status")
    
    app.run(debug=True, host='0.0.0.0', port=8888)
