# Banana Gen

> 统一的图像生成管理框架 - 重构自 aistdio-banana

## 🚀 核心功能

### 🔑 智能 Key 管理
- **多级优先级** key 池自动管理
- **故障自动转移** 和冷却恢复
- **负载均衡** 轮换使用
- **线程安全** 并发支持

### 📝 统一 Prompt 管理
- **Prompt 类**：结构化管理（ID、文本、输入数量、标签）
- **按输入图数量分类**：0/1/2/3 输入图场景
- **JSON 格式** 注册表，易于管理
- **通过 ID 使用**：`registry.get_prompts_by_ids(["p2_change_people"])`
- **已导入** aistdio-banana 所有 prompt

### 🖼️ 灵活图片来源系统
- **多种图片类型**：支持本地图片、网络图片、文件夹、生成任务等
- **自动路径回退**：主路径失败时自动尝试备用路径
- **状态管理**：有效/失效/待定状态跟踪
- **滑动窗口**：支持批量处理和序列化处理

### 📁 智能输出管理
- **三种路径策略**：统一/分路径/子目录
- **自定义文件名**：支持占位符模板
- **冲突处理**：自动生成唯一文件名
- **元数据嵌入**：PNG 私有 chunk（不可被其他软件读取）

### 📊 完整日志系统
- **双重输出**：控制台 + 文件
- **结构化日志**：JSONL 格式
- **线程安全**：支持高并发
- **详细记录**：Key 使用、文件保存、错误信息

### 🎯 任务管理器
- **一键运行**：`task_manager.run_with_interactive_monitoring()`
- **动态任务生成**：避免内存溢出
- **实时进度监控**：显示完成状态、错误信息
- **自动负载均衡**：根据生成器空闲容量调度任务

## 🖼️ 图片类型详解

### SingleImage 类型（单个图片）

#### 1. ImageData - 图片数据
```python
# 直接使用图片字节数据
image_data = ImageData(data=bytes_data, format="PNG")
```

#### 2. LocalImage - 本地图片文件
```python
# 配置方式
input_configs = [
    {
        "type": "local_image",
        "main_path": "/path/to/main/image.jpg",
        "fallback_paths": ["/backup/image1.jpg", "/backup/image2.jpg"]
    }
]
```

#### 3. UrlImage - 网络图片
```python
# 配置方式
input_configs = [
    {
        "type": "url_image", 
        "main_path": "https://example.com/image.jpg",
        "fallback_paths": ["https://backup.com/image1.jpg", "https://backup.com/image2.jpg"]
    }
]
```

#### 4. ImageGenerateTask - 图片生成任务
```python
# 直接创建（用于复杂场景）
from banana_gen import ImageGenerateTask, LocalImage

# 创建输入图片列表
input_images = [LocalImage("/path/to/image1.jpg"), LocalImage("/path/to/image2.jpg")]
# 创建生成任务
task = ImageGenerateTask(input_images, "your prompt text")
# 执行任务
success = task.execute(generator)
```

### ImageList 类型（图片列表）

#### 1. ImageFolder - 本地文件夹
```python
# 配置方式
input_configs = [
    {
        "type": "folder",
        "main_path": "/path/to/main/folder",
        "fallback_paths": ["/backup/folder1", "/backup/folder2"]
    }
]
```

#### 2. ImageRecursionFolder - 递归文件夹
```python
# 配置方式
input_configs = [
    {
        "type": "recursive_folder",
        "main_path": "/path/to/main/folder",
        "fallback_paths": ["/backup/folder1", "/backup/folder2"]
    }
]
```

#### 3. ImageGenerateTasks - 生成任务列表
```python
# 直接创建（用于批量生成任务管理）
from banana_gen import ImageGenerateTasks, ImageGenerateTask

# 创建多个生成任务
tasks = [
    ImageGenerateTask([img1, img2], "prompt1"),
    ImageGenerateTask([img3, img4], "prompt2")
]
# 创建任务列表
task_list = ImageGenerateTasks(tasks)
```

## 🎯 使用场景

### 场景1：超级简化使用（推荐）
```python
from banana_gen import TaskManager, UnifiedImageGenerator, PromptRegistry

# 1. 初始化
generator = UnifiedImageGenerator(max_workers=2)
registry = PromptRegistry()

# 2. 配置输入图片
input_configs = [
    {
        "type": "folder",
        "main_path": "/path/to/pose/images",
        "fallback_paths": ["backup/poses"]
    },
    {
        "type": "local_image",
        "main_path": "/path/to/character.jpg", 
        "fallback_paths": ["backup/character.jpg"]
    }
]

# 3. 通过 ID 获取 prompts
prompts = registry.get_prompts_by_ids(["p2_change_people"])

# 4. 创建任务管理器
task_manager = TaskManager.create_with_auto_fallback(
    generator=generator,
    input_configs=input_configs,
    prompts=prompts,
    string_replace_list=[["photorealistic", "cartoon", "anime"]]
)

# 5. 一键运行
success = task_manager.run_with_interactive_monitoring()
```

### 场景2：混合图片类型
```python
input_configs = [
    {
        "type": "folder",  # 文件夹中的图片
        "main_path": "/path/to/poses",
        "fallback_paths": ["backup/poses"]
    },
    {
        "type": "url_image",  # 网络图片
        "main_path": "https://example.com/character.jpg",
        "fallback_paths": ["https://backup.com/character.jpg"]
    },
    {
        "type": "local_image",  # 本地固定图片
        "main_path": "/path/to/style.jpg",
        "fallback_paths": ["backup/style.jpg"]
    }
]
```

### 场景3：高级用法 - 直接使用图片类
```python
from banana_gen import (
    ImageFolder, LocalImage, UrlImage, ImageGenerateTask,
    TaskManager, UnifiedImageGenerator
)

# 直接创建图片对象
input_images = [
    ImageFolder("/path/to/poses", fallback_paths=["backup/poses"]),
    LocalImage("/path/to/character.jpg", fallback_paths=["backup/character.jpg"]),
    UrlImage("https://example.com/style.jpg", fallback_urls=["https://backup.com/style.jpg"])
]

# 创建任务管理器
task_manager = TaskManager(
    generator=generator,
    input_images=input_images,  # 直接传入图片对象
    prompts=["p2_change_people"],
    string_replace_list=[["photorealistic", "cartoon", "anime"]]
)
```

## ⚡ 技术优势

- **完全线程安全**：支持高并发处理
- **无侵入式重构**：不修改原代码
- **生产就绪**：错误处理、重试机制、状态持久化
- **高度可配置**：路径策略、文件名模板、元数据等
- **智能冲突处理**：文件名冲突自动解决
- **内存优化**：动态任务生成，避免内存溢出
- **自动回退**：路径失败时自动尝试备用路径

## 📋 快速开始

### 1. 安装依赖
```bash
python example/install_dependencies.py
```

### 2. 配置 Keys
```bash
# 创建 key 文件
mkdir banana_gen/keys
echo "your_api_key_1" > banana_gen/keys/api_keys_1.txt
echo "your_api_key_2" > banana_gen/keys/api_keys_2.txt
```

### 3. 运行演示
```bash
# 超级简化演示（推荐）
python example/demo_ultra_simple.py

# 简化任务管理器演示
python example/demo_simple_task_manager.py

# 任务管理器测试
python example/demo_task_manager_test.py
```

## 🎮 Demo 程序

### 1. `demo_ultra_simple.py` - 超级简化演示（最推荐）
只需要几行代码就能完成复杂的图片生成任务：

**功能特点：**
- 一键创建任务管理器，自动处理路径回退
- 一键运行，包含用户确认、进度监控、结果显示
- 动态任务生成和调度
- 内存优化（避免一次性生成所有任务）
- 支持多种输入图片类型（文件夹、固定图片、URL图片）
- 字符串替换功能（类似原始代码的 STRING_REPLACE_LIST）
- 任务状态监控（开始/暂停/停止/完成）
- 实时进度显示
- 自动负载均衡和并发控制

**使用方法：**
```bash
# 1. 安装依赖
python example/install_dependencies.py

# 2. 运行 demo
python example/demo_ultra_simple.py
```

### 2. `demo_simple_task_manager.py` - 简化任务管理器演示
展示使用便捷方法创建任务管理器，通过 ID 使用 prompts：

**功能特点：**
- 通过 ID 从注册表获取 Prompt 对象
- 一键创建任务管理器，自动处理路径回退
- 一键运行，包含用户确认、进度监控、结果显示
- 支持多种输入图片类型
- 字符串替换功能

### 3. `demo_task_manager_test.py` - 任务管理器测试程序
仿照原始代码的结构，使用新的任务管理器进行测试：

**功能特点：**
- 通过 ID 从注册表获取 Prompt 对象
- 完整的任务管理器功能测试
- 支持复杂的输入配置
- 详细的测试日志

### 4. 测试程序
- `test_prompt_system.py` - Prompt 系统测试
- `test_prompt_by_id.py` - ID 方式测试

## 📚 文件结构

```
banana-gen/
├── banana_gen/                    # 核心包
│   ├── images/                   # 图片管理系统
│   │   ├── base.py              # 基础类定义
│   │   ├── single.py            # 单个图片类
│   │   └── lists.py             # 图片列表类
│   ├── prompts/                 # Prompt 管理系统
│   │   ├── prompt.py            # Prompt 类
│   │   ├── registry.py          # Prompt 注册表
│   │   └── replace.py           # 字符串替换
│   ├── executor/                # 执行器
│   │   ├── google_api_manager.py # 统一图片生成器
│   │   └── task_manager.py      # 任务管理器
│   ├── keys/                    # Key 管理
│   └── output/                  # 输出管理
├── prompts/                     # Prompt 文件
│   ├── prompts_from_aistdio.json # 原始 prompts
│   └── prompts.sample.json      # 示例 prompts
├── example/                     # 示例程序
│   ├── demo_ultra_simple.py     # 超级简化演示
│   ├── demo_simple_task_manager.py # 简化演示
│   ├── demo_task_manager_test.py # 测试程序
│   └── install_dependencies.py  # 依赖安装
└── README.md                    # 说明文档
```

## ⚠️ 重要说明

- **不修改原代码**：完全独立于 aistdio-banana
- **需要 API Key**：需要有效的 Google API Key
- **线程安全**：支持高并发处理
- **自动处理**：文件名冲突、Key 失效、状态持久化
- **路径回退**：自动尝试备用路径，提高容错性
- **内存优化**：动态任务生成，支持大规模处理

## 🔧 高级配置

### 自定义文件名模板
```python
filename_template = "{base}-{prompt_idx}-{replace_idx}-{image_idx}-{timestamp}.png"
```

### 自定义输出目录
```python
output_dir = "custom/output/directory"
```

### 自定义并发数
```python
generator = UnifiedImageGenerator(max_workers=5)  # 5个并发
```

### 自定义重试次数
```python
generator = UnifiedImageGenerator(max_retries=5)  # 5次重试
```