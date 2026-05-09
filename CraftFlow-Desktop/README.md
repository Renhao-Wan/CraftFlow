# CraftFlow Desktop

> CraftFlow 智能长文创作平台 — Electron 桌面版

## 项目简介

CraftFlow Desktop 使用 Electron 将后端（Python + LangGraph）和前端（Vue 3）打包为独立的桌面应用，支持 Windows、macOS 和 Linux。用户无需手动部署后端服务，开箱即用。

## 技术栈

- **桌面框架**: Electron 33
- **打包工具**: electron-builder 25
- **后端**: PyInstaller 打包的 Python 可执行文件
- **前端**: Vite 构建的 Vue 3 SPA

## 快速开始

### 环境要求

- Node.js `^20.19.0 || >=22.12.0`
- Python 3.11+（用于后端打包）
- PyInstaller（`pip install pyinstaller`）

### 开发模式

```bash
# 安装依赖
npm install

# 启动 Electron 开发模式
# 需要先确保后端已通过 PyInstaller 打包到 backend/dist/craftflow/
npm run dev
```

### 构建打包

```bash
# 全量构建（前端 + 后端 + Electron）
npm run build

# 打包为可执行文件（Windows NSIS 安装程序）
npm run dist
```

也可以分步构建：

```bash
# 1. 构建前端
npm run build:frontend

# 2. 构建后端（PyInstaller）
npm run build:backend

# 3. 打包 Electron 应用
npm run build:electron
```

构建产物输出到 `release/` 目录。

## 架构说明

### 主进程流程

```
应用启动
  → 显示启动画面 (splash.html)
  → 启动 PyInstaller 打包的后端子进程 (craftflow.exe)
  → 轮询 /health 等待后端就绪（最多 30 次，每次 1s）
  → 创建 BrowserWindow 加载前端 dist/index.html
  → 应用退出时关闭后端子进程
```

### 数据路径

| 平台 | 数据目录 |
|------|----------|
| Windows | `%APPDATA%/CraftFlow/` |
| macOS | `~/.craftflow/` |
| Linux | `~/.craftflow/` |

该目录包含：
- SQLite 数据库（任务持久化）
- Checkpoints（LangGraph 图状态）
- 日志文件
- 环境变量配置（`.env`）

### 目录结构

```
CraftFlow-Desktop/
├── electron/
│   ├── main.js          # Electron 主进程
│   ├── preload.js       # 安全 IPC 桥接
│   └── splash.html      # 启动画面
├── backend/             # 后端源码（从 craftflow-backend 复制）
├── frontend/            # 前端源码（从 craftflow-web 复制）
├── image/               # 应用图标资源
├── scripts/             # 构建辅助脚本
├── release/             # 打包输出目录
├── package.json
└── electron-builder.yml # 打包配置
```

## 平台支持

| 平台 | 安装格式 | 状态 |
|------|----------|------|
| Windows x64 | NSIS 安装程序 | 已配置 |
| macOS | DMG | 预留配置 |
| Linux | AppImage | 预留配置 |
