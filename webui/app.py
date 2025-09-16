#!/usr/bin/env python3
"""
Banana Gen Web UI - Flask 后端
提供完整的 Web 界面来管理 Key、Prompt、图片来源和执行任务
"""

import os
import json
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from werkzeug.utils import secure_filename
import tempfile
import shutil

# 导入 banana-gen 核心模块
import sys
import os

# 添加 banana-gen 根目录到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

try:
    from banana_gen import (
        AdvancedKeyManager, PromptRegistry, build_plan, execute_plan,
        LocalImage, UrlImage, ImageFolder, ImageRecursionFolder,
        OutputPathManager, render_filename, log_jsonl, install_log_tee,
        UnifiedImageGenerator, TaskManager
    )
    # 导入旧的 ImageSource 类用于兼容性
    from banana_gen.images.sources import (
        LocalFileSource, UrlSource, FolderSequencerSource, RecursiveFolderSequencerSource
    )
except ImportError as e:
    print(f"❌ 导入 banana_gen 模块失败: {e}")
    print(f"📁 当前目录: {current_dir}")
    print(f"📁 父目录: {parent_dir}")
    print(f"📁 Python 路径: {sys.path[:3]}")
    print("💡 请确保在 banana-gen 项目根目录下运行")
    sys.exit(1)

app = Flask(__name__)
app.secret_key = 'banana-gen-webui-secret-key'

# 全局状态
key_manager = None
prompt_registry = None
generator = None
task_manager = None
current_tasks = []
execution_status = {"running": False, "progress": 0, "total": 0, "completed": 0, "failed": 0}
execution_logs = []

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
        # 使用 from_directory 方法直接创建 Key 管理器
        key_dirs = ['banana_gen/keys', 'webui/keys']
        
        for keys_dir in key_dirs:
            if os.path.exists(keys_dir):
                print(f"📁 尝试从目录加载 Key: {keys_dir}")
                try:
                    key_manager = AdvancedKeyManager.from_directory(keys_dir)
                    print(f"✅ 已从目录加载 Key: {keys_dir}")
                    print(f"✅ Key 管理器初始化完成，共 {key_manager.get_total_keys()} 个 Key")
                    return True
                except Exception as e:
                    print(f"⚠️ 从目录 {keys_dir} 加载 Key 失败: {e}")
                    continue
        
        # 如果所有目录都失败，创建空的 Key 管理器
        print("⚠️ 未找到有效的 Key 文件，创建空的 Key 管理器")
        key_manager = AdvancedKeyManager()
        return True
        
    except Exception as e:
        print(f"❌ Key 管理器初始化失败: {e}")
        key_manager = None
        return False

def init_prompt_registry():
    """初始化 Prompt 注册表"""
    global prompt_registry
    try:
        # 尝试从与 CLI 一致的位置加载 prompt 文件（优先）
        prompt_files = [
            'prompts/prompts_from_aistdio.json',
            'prompts/prompts.sample.json',
            # 兼容旧路径
            'samples/prompts_from_aistdio.json',
            'banana_gen/samples/prompts_from_aistdio.json'
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
    """主页 - 显示所有分栏页"""
    return render_template('index.html')

# ==================== Key 管理分栏页 ====================

@app.route('/keys')
def keys_page():
    """Key 管理页面"""
    key_files = []
    
    # 从多个目录读取 key 文件
    keys_dirs = ['webui/keys', 'banana_gen/keys']
    
    for keys_dir in keys_dirs:
        if os.path.exists(keys_dir):
            for f in os.listdir(keys_dir):
                if f.startswith('api_keys_') and f.endswith('.txt'):
                    file_path = os.path.join(keys_dir, f)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as fp:
                            # 过滤掉注释行和空行
                            keys = [line.strip() for line in fp if line.strip() and not line.strip().startswith('#')]
                        key_files.append({
                            'filename': f,
                            'priority': f.replace('api_keys_', '').replace('.txt', ''),
                            'count': len(keys),
                            'key_list': [k[:6] + '...' + k[-4:] if len(k) > 12 else k for k in keys],
                            'source': keys_dir  # 标记来源目录
                        })
                    except Exception as e:
                        print(f"⚠️ 读取 key 文件失败 {file_path}: {e}")
    
    # 获取 Key 管理器状态
    key_stats = {}
    print(f"🔍 Key 管理器状态检查: key_manager = {key_manager}")
    if key_manager:
        try:
            stats = key_manager.get_stats()
            print(f"📊 Key 统计信息: {stats}")
            key_stats = {
                'total_keys': stats.get('total_keys', 0),
                'active_keys': stats.get('total_available', 0),
                'failed_keys': stats.get('failed_count', 0),
                'permanent_failed': stats.get('permanent_failed_count', 0)
            }
            print(f"📈 处理后的统计信息: {key_stats}")
        except Exception as e:
            print(f"⚠️ 获取 Key 统计信息失败: {e}")
            key_stats = {
                'total_keys': 0,
                'active_keys': 0,
                'failed_keys': 0,
                'permanent_failed': 0
            }
    else:
        print("❌ Key 管理器未初始化")
        key_stats = {
            'total_keys': 0,
            'active_keys': 0,
            'failed_keys': 0,
            'permanent_failed': 0
        }
    
    return render_template('keys.html', key_files=key_files, key_stats=key_stats)

@app.route('/api/keys/upload', methods=['POST'])
def upload_keys():
    """上传 Key 文件"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    priority = request.form.get('priority', '1')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        filename = f'api_keys_{priority}.txt'
        file_path = os.path.join('webui/keys', filename)
        file.save(file_path)
        
        # 重新初始化 Key 管理器
        init_key_manager()
        
        return jsonify({'success': True, 'message': f'Keys uploaded to {filename}'})
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/api/keys/delete/<filename>')
def delete_key_file(filename):
    """删除 Key 文件"""
    file_path = os.path.join('webui/keys', secure_filename(filename))
    if os.path.exists(file_path):
        os.remove(file_path)
        init_key_manager()
        return jsonify({'success': True})
    return jsonify({'error': 'File not found'}), 404

# ==================== Prompt 管理分栏页 ====================

@app.route('/prompts')
def prompts_page():
    """Prompt 管理页面"""
    if not prompt_registry:
        init_prompt_registry()
    
    prompts_by_count = {}
    if prompt_registry:
        for prompt_id in prompt_registry.list_all():
            prompt = prompt_registry.get(prompt_id)
            if prompt:
                count = prompt.input_count
                if count not in prompts_by_count:
                    prompts_by_count[count] = []
                prompts_by_count[count].append(prompt)
    
    return render_template('prompts.html', prompts_by_count=prompts_by_count)

@app.route('/api/prompts/<prompt_id>')
def get_prompt(prompt_id):
    """获取特定 Prompt 详情"""
    if not prompt_registry:
        return jsonify({'error': 'Prompt registry not initialized'}), 500
    
    prompt = prompt_registry.get(prompt_id)
    if prompt:
        return jsonify({
            'id': prompt.id,
            'text': prompt.text,
            'input_count': prompt.input_count,
            'tags': prompt.tags or []
        })
    return jsonify({'error': 'Prompt not found'}), 404

# ==================== 图片来源管理分栏页 ====================

@app.route('/sources')
def sources_page():
    """图片来源管理页面"""
    return render_template('sources.html')

@app.route('/api/sources/upload', methods=['POST'])
def upload_image():
    """上传图片文件"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'path': file_path,
            'url': f'/uploads/{filename}'
        })
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """提供上传的图片文件"""
    return send_file(os.path.join(UPLOAD_FOLDER, filename))

@app.route('/api/sources/folder')
def list_folder():
    """列出文件夹中的图片"""
    folder_path = request.args.get('path', '')
    if not folder_path or not os.path.exists(folder_path):
        return jsonify({'error': 'Invalid folder path'}), 400
    
    images = []
    for f in os.listdir(folder_path):
        if allowed_file(f):
            images.append({
                'filename': f,
                'path': os.path.join(folder_path, f)
            })
    
    return jsonify({'images': images})

# ==================== 任务执行分栏页 ====================

@app.route('/execute')
def execute_page():
    """任务执行页面"""
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
    
    return render_template('execute.html', prompts=prompts, status=execution_status)

# ==================== 新管线：TaskManager APIs ====================

@app.route('/api/tasks/create', methods=['POST'])
def api_tasks_create():
    """使用 TaskManager 创建任务（新管线）"""
    global task_manager, generator
    data = request.json or {}
    if generator is None:
        generator = UnifiedImageGenerator(max_workers=3, max_retries=10)
    if not prompt_registry:
        init_prompt_registry()

    input_configs = data.get('input_sources', [])
    prompt_ids = data.get('prompt_ids', [])
    prompts = prompt_registry.get_prompts_by_ids(prompt_ids)
    string_replace_list = data.get('string_replace_list', [])
    output_dir = data.get('output_dir', OUTPUT_FOLDER)
    filename_template = data.get('filename_template', '{base}-{prompt_idx}-{replace_idx}-{image_idx}.png')
    base_name = data.get('base_name', 'webui_task')

    # 允许 0 输入图：若所有选中 Prompt 的 input_count 均为 0，则可不传 input_sources
    try:
        max_required = max((p.input_count for p in prompts), default=0)
    except Exception:
        max_required = 0
    if max_required > 0 and not input_configs:
        return jsonify({'error': '所选 Prompt 需要输入图片，请配置图片来源'}), 400

    try:
        # 当所选 Prompt 最大 input_count == 0 时，强制允许空输入图
        try:
            max_required = max((p.input_count for p in prompts), default=0)
        except Exception:
            max_required = 0

        if max_required == 0 and not input_configs:
            input_configs = []

        task_manager = TaskManager.create_with_auto_fallback(
            generator=generator,
            input_configs=input_configs,
            prompts=prompts,
            string_replace_list=string_replace_list,
            output_dir=output_dir,
            filename_template=filename_template,
            base_name=base_name,
        )
        total = task_manager._calculate_total_tasks()
        return jsonify({'success': True, 'task_count': total})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/tasks/start', methods=['POST'])
def api_tasks_start():
    """启动任务执行（新管线）"""
    global task_manager
    if not task_manager:
        return jsonify({'error': 'No task created'}), 400
    if execution_status.get('running'):
        return jsonify({'error': 'Task already running'}), 400

    def _run():
        execution_status['running'] = True
        try:
            task_manager.run_with_interactive_monitoring(auto_start=True)
        finally:
            execution_status['running'] = False

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({'success': True})

@app.route('/api/tasks/status')
def api_tasks_status():
    """获取任务执行状态（新管线）"""
    if task_manager:
        s = task_manager.get_status()
        return jsonify({
            'running': execution_status.get('running', False),
            'status': getattr(s['status'], 'name', str(s['status'])),
            'stats': s['stats'],
            'generator_stats': s['generator_stats'],
        })
    return jsonify(execution_status)

@app.route('/api/execute/build_plan', methods=['POST'])
def api_build_plan():
    """兼容旧接口：改用新管线创建任务（TaskManager）"""
    data = request.json or {}
    # 映射旧的 input_sources -> 新的 input_configs
    mapped = []
    for src in data.get('input_sources', []):
        t = src.get('type')
        p = src.get('path') or src.get('url')
        if not t or not p:
            continue
        if t == 'local':
            mapped.append({'type': 'local_image', 'main_path': p, 'fallback_paths': []})
        elif t == 'url':
            mapped.append({'type': 'url_image', 'main_path': p, 'fallback_urls': []})
        elif t == 'folder':
            mapped.append({'type': 'folder', 'main_path': p, 'fallback_paths': []})
        elif t == 'recursive':
            mapped.append({'type': 'recursive_folder', 'main_path': p, 'fallback_paths': []})
    # prompt 映射
    prompt_ids = data.get('prompt_ids') or ([data.get('prompt_id')] if data.get('prompt_id') else [])
    payload = {
        'input_sources': mapped,
        'prompt_ids': prompt_ids,
        'string_replace_list': data.get('string_replace_list', []),
        'output_dir': data.get('output', {}).get('base_dir', OUTPUT_FOLDER),
        'filename_template': data.get('filename_template', '{base}-{prompt_idx}-{replace_idx}-{image_idx}.png'),
        'base_name': data.get('base_name', 'webui_task'),
    }
    # 复用新接口
    with app.test_request_context(json=payload):
        resp = api_tasks_create()
    # 返回兼容字段
    if isinstance(resp, tuple):
        body, code = resp
        return body, code
    body = resp.get_json() if hasattr(resp, 'get_json') else resp
    if body and body.get('success'):
        return jsonify({'success': True, 'task_count': body.get('task_count', 0)})
    return jsonify({'error': (body or {}).get('error', 'create failed')}), 400

@app.route('/api/execute/start', methods=['POST'])
def api_start_execution():
    """兼容旧接口：改用新管线启动执行"""
    # 复用新接口
    with app.test_request_context(json=request.get_json(silent=True) or {}):
        return api_tasks_start()

@app.route('/api/execute/status')
def api_execution_status():
    """兼容旧接口：返回新管线状态"""
    return api_tasks_status()

@app.route('/api/execute/logs')
def api_execution_logs():
    """获取执行日志"""
    return jsonify({'logs': execution_logs})

# ==================== 日志查看分栏页 ====================

@app.route('/logs')
def logs_page():
    """日志查看页面"""
    logs_dir = 'logs'
    log_files = []
    
    if os.path.exists(logs_dir):
        for f in os.listdir(logs_dir):
            if f.endswith('.log') or f.endswith('.jsonl'):
                file_path = os.path.join(logs_dir, f)
                stat = os.stat(file_path)
                log_files.append({
                    'filename': f,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
    
    return render_template('logs.html', log_files=log_files)

@app.route('/api/logs/<filename>')
def get_log_file(filename):
    """获取日志文件内容"""
    file_path = os.path.join('logs', secure_filename(filename))
    if not os.path.exists(file_path):
        return jsonify({'error': 'Log file not found'}), 404
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'content': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
    
    return render_template('outputs.html', output_files=output_files)

@app.route('/outputs/<path:filename>')
def output_file(filename):
    """提供输出文件"""
    return send_file(os.path.join(OUTPUT_FOLDER, filename))

@app.route('/api/outputs/<filename>/metadata')
def get_file_metadata(filename):
    """获取文件的元数据"""
    try:
        from banana_gen.output.metadata import extract_info_from_png
        
        file_path = os.path.join(OUTPUT_FOLDER, secure_filename(filename))
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        with open(file_path, 'rb') as f:
            png_bytes = f.read()
        
        metadata = extract_info_from_png(png_bytes)
        
        # 获取文件基本信息
        stat = os.stat(file_path)
        file_info = {
            'filename': filename,
            'size': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return jsonify({
            'file_info': file_info,
            'metadata': metadata
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def initialize_app():
    """初始化应用"""
    print("🔧 初始化应用组件...")
    init_key_manager()
    init_prompt_registry()
    print("✅ 应用初始化完成")

# 自动初始化
initialize_app()

if __name__ == '__main__':
    print("🚀 Banana Gen Web UI 启动中...")
    print("📱 访问地址: http://localhost:8888")
    print("🔑 Key 管理: http://localhost:8888/keys")
    print("📝 Prompt 管理: http://localhost:8888/prompts")
    print("🖼️ 图片来源管理: http://localhost:8888/sources")
    print("⚡ 任务执行: http://localhost:8888/execute")
    print("📊 日志查看: http://localhost:8888/logs")
    print("📁 输出文件: http://localhost:8888/outputs")
    
    app.run(debug=True, host='0.0.0.0', port=8888)
