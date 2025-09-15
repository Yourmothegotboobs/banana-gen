# Banana Gen Web UI

> 基于 Flask 的 Web 界面，提供完整的图像生成管理功能

## 🚀 快速开始

### 1. 安装依赖
```bash
cd webui
pip install -r requirements.txt
```

### 2. 启动服务

#### 方式一：从项目根目录启动（推荐，自动打开浏览器）
```bash
# 在 banana-gen 项目根目录下
python start_webui.py
```

#### 方式二：从 webui 目录启动（不自动打开浏览器）
```bash
cd webui
python start.py
```

### 3. 访问界面
启动后会自动打开浏览器，或手动访问：http://localhost:8888

## 📱 功能模块

### 🔑 Key 管理
- 上传多级优先级 Key 文件
- 查看 Key 使用状态和统计
- 支持 Key 文件的增删改查

### 📝 Prompt 管理
- 按输入图数量分类展示 Prompt
- 支持 Prompt 搜索和筛选
- 可查看 Prompt 详情和使用示例

### 🖼️ 图片来源管理
- 支持四种图片来源类型：
  - 本地文件
  - 网络链接
  - 文件夹序列
  - 递归文件夹
- 拖拽上传图片文件
- 图片来源配置预览

### ⚡ 任务执行
- 可视化任务配置界面
- 支持替换词和批量替换
- 实时执行状态监控
- 并发执行控制

### 📊 日志查看
- 实时日志流显示
- 日志文件管理
- 支持 JSONL 和普通日志格式

### 📁 创意相册
- 画廊式作品展示（网格/列表视图）
- 图片预览和元数据查看
- 一键复制提示词
- 批量下载和文件管理

## 🛠️ 技术特性

- **响应式设计**：支持桌面和移动端
- **实时更新**：WebSocket 实时状态同步
- **线程安全**：支持高并发处理
- **模块化架构**：易于扩展和维护

## 📂 目录结构

```
webui/
├── app.py              # Flask 主应用
├── start.py            # 启动脚本
├── requirements.txt    # Python 依赖
├── templates/          # HTML 模板
│   ├── base.html      # 基础模板
│   ├── index.html     # 首页
│   ├── keys.html      # Key 管理
│   ├── prompts.html   # Prompt 管理
│   ├── sources.html   # 图片来源管理
│   ├── execute.html   # 任务执行
│   ├── logs.html      # 日志查看
│   └── outputs.html   # 输出文件
├── keys/              # Key 文件存储
├── uploads/           # 上传文件存储
├── outputs/           # 输出文件存储
└── logs/              # 日志文件存储
```

## 🔧 配置说明

### 环境变量
- `FLASK_ENV`: 运行环境 (development/production)
- `FLASK_DEBUG`: 调试模式 (True/False)

### 文件路径
- Key 文件：`webui/keys/`
- 上传文件：`webui/uploads/`
- 输出文件：`webui/outputs/`
- 日志文件：`logs/`

## 🚨 注意事项

1. **首次使用**：需要先配置 API Keys
2. **文件权限**：确保应用有读写权限
3. **端口占用**：默认使用 8888 端口（冷门端口，避免冲突）
4. **浏览器兼容**：推荐使用现代浏览器
5. **自动打开**：启动后会自动打开默认浏览器

## 🔄 更新日志

### v1.0.0
- 初始版本发布
- 完整的 Web UI 功能
- 支持所有核心模块
