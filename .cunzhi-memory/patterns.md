# 常用模式和最佳实践

- WebUI 重构完成：基于完整 CLI 功能创建了简洁干净的 Web 界面，包含任务管理、图片来源管理、输出文件管理、系统状态监控等完整功能，使用 Flask + Bootstrap 5 实现现代化响应式设计
- 修复了旧版 WebUI 的模块导入问题：将 LocalFileSource/UrlSource/FolderSequencerSource/RecursiveFolderSequencerSource 改为正确的 LocalImage/UrlImage/ImageFolder/ImageRecursionFolder，并优化了 Key 扫描功能使用 AdvancedKeyManager.from_directory() 方法
