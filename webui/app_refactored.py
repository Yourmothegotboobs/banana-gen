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
        LocalImage, UrlImage, ImageFolder, ImageRecursionFolder
    )
except ImportError as e:
    print(f"❌ 导入 banana_gen 模块失败: {e}")
    sys.exit(1)

app = Flask(__name__)
app.secret_key = 'banana-gen-webui-refactored'

# 全局状态
generator = None
prompt_registry = None
current_task_manager = None
execution_status = {"running": False, "progress": 0, "total": 0, "completed": 0, "failed": 0}

# 配置
UPLOAD_FOLDER = 'webui/uploads'
OUTPUT_FOLDER = 'webui/outputs'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_generator():
    """初始化统一图像生成器"""
    global generator
    try:
        generator = UnifiedImageGenerator(max_workers=3)
        print(f"✅ 统一图像生成器初始化成功")
        return True
    except Exception as e:
        print(f"❌ 统一图像生成器初始化失败: {e}")
        generator = None
        return False

def init_prompt_registry():
    """初始化 Prompt 注册表"""
    global prompt_registry
    try:
        # 尝试从多个位置加载 prompt 文件
        prompt_files = [
            'prompts/prompts.sample.json',
            'prompts/prompts_from_aistdio.json'
        ]
        
        for prompt_file in prompt_files:
            if os.path.exists(prompt_file):
                prompt_registry = PromptRegistry.load_from_json(prompt_file)
                print(f"✅ 已加载 Prompt 文件: {prompt_file}")
                return True
        
        # 如果没有找到文件，创建空的注册表
        prompt_registry = PromptRegistry()
        print("⚠️ 未找到 Prompt 文件，创建空注册表")
        return True
    except Exception as e:
        print(f"❌ Prompt 注册表初始化失败: {e}")
        prompt_registry = PromptRegistry()
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
    """创建任务"""
    data = request.json
    
    if not generator:
        return jsonify({'error': 'Generator not initialized'}), 500
    
    if not prompt_registry:
        return jsonify({'error': 'Prompt registry not initialized'}), 500
    
    try:
        # 构建输入配置
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
        
        # 获取提示词
        prompt_ids = data.get('prompt_ids', [])
        prompts = prompt_registry.get_prompts_by_ids(prompt_ids)
        
        # 字符串替换规则
        string_replace_list = data.get('string_replace_list', [])
        
        # 创建任务管理器
        global current_task_manager
        current_task_manager = TaskManager.create_with_auto_fallback(
            generator=generator,
            input_configs=input_configs,
            prompts=prompts,
            string_replace_list=string_replace_list,
            output_dir=data.get('output_dir', OUTPUT_FOLDER),
            filename_template=data.get('filename_template', '{base}-{prompt_idx}-{replace_idx}-{image_idx}.png'),
            base_name=data.get('base_name', 'webui_task')
        )
        
        # 计算任务统计
        total_tasks = current_task_manager._calculate_total_tasks()
        
        return jsonify({
            'success': True,
            'task_count': total_tasks,
            'message': f'任务创建成功，共 {total_tasks} 个任务'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/start', methods=['POST'])
def api_start_task():
    """开始执行任务"""
    if not current_task_manager:
        return jsonify({'error': 'No task created'}), 400
    
    if execution_status['running']:
        return jsonify({'error': 'Task already running'}), 400
    
    # 在后台线程中执行
    def run_task():
        global execution_status
        execution_status['running'] = True
        execution_status['total'] = current_task_manager._calculate_total_tasks()
        execution_status['completed'] = 0
        execution_status['failed'] = 0
        
        try:
            # 运行任务
            success = current_task_manager.run_with_interactive_monitoring(auto_start=True)
            
        except Exception as e:
            import traceback
            error_msg = f"执行出错: {str(e)}"
            print(f"❌ {error_msg}")
            traceback.print_exc()
        finally:
            execution_status['running'] = False
    
    thread = threading.Thread(target=run_task)
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'message': 'Task started'})

@app.route('/api/tasks/status')
def api_task_status():
    """获取任务状态"""
    if current_task_manager:
        status = current_task_manager.get_status()
        return jsonify({
            'running': execution_status['running'],
            'status': status['status'].name if hasattr(status['status'], 'name') else str(status['status']),
            'stats': status['stats'],
            'generator_stats': status['generator_stats']
        })
    else:
        return jsonify(execution_status)

# ==================== 输出文件管理 ====================

@app.route('/outputs')
def outputs_page():
    """输出文件页面"""
    output_files = []
    if os.path.exists(OUTPUT_FOLDER):
        for root, dirs, files in os.walk(OUTPUT_FOLDER):
            for f in files:
                if allowed_file(f):
                    file_path = os.path.join(root, f)
                    stat = os.stat(file_path)
                    output_files.append({
                        'filename': f,
                        'path': file_path,
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    })
    
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
    """获取系统状态"""
    status = {
        'generator': generator is not None,
        'prompt_registry': prompt_registry is not None,
        'prompt_count': len(prompt_registry.list_all()) if prompt_registry else 0,
        'execution_status': execution_status,
        'current_task': current_task_manager is not None
    }
    
    if generator:
        try:
            stats = generator.get_stats()
            status['generator_stats'] = stats
        except:
            status['generator_stats'] = {}
    
    return jsonify(status)

def initialize_app():
    """初始化应用"""
    print("🔧 初始化应用组件...")
    init_generator()
    init_prompt_registry()
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
