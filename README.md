# CraftFlow

<div align="center">

![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)
[![zread](https://img.shields.io/badge/Ask_Zread-_.svg?style=flat&color=00b0aa&labelColor=000000&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQuOTYxNTYgMS42MDAxSDIuMjQxNTZDMS44ODgxIDEuNjAwMSAxLjYwMTU2IDEuODg2NjQgMS42MDE1NiAyLjI0MDFWNC45NjAxQzEuNjAxNTYgNS4zMTM1NiAxLjg4ODEgNS42MDAxIDIuMjQxNTYgNS42MDAxSDQuOTYxNTZDNS4zMTUwMiA1LjYwMDEgNS42MDE1NiA1LjMxMzU2IDUuNjAxNTYgNC45NjAxVjIuMjQwMUM1LjYwMTU2IDEuODg2NjQgNS4zMTUwMiAxLjYwMDEgNC45NjE1NiAxLjYwMDFaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00Ljk2MTU2IDEwLjM5OTlIMi4yNDE1NkMxLjg4ODEgMTAuMzk5OSAxLjYwMTU2IDEwLjY4NjQgMS42MDE1NiAxMS4wMzk5VjEzLjc1OTlDMS42MDE1NiAxNC4xMTM0IDEuODg4MSAxNC4zOTk5IDIuMjQxNTYgMTQuMzk5OUg0Ljk2MTU2QzUuMzE1MDIgMTQuMzk5OSA1LjYwMTU2IDE0LjExMzQgNS42MDE1NiAxMy43NTk5VjExLjAzOTlDNS42MDE1NiAxMC42ODY0IDUuMzE1MDIgMTAuMzk5OSA0Ljk2MTU2IDEwLjM5OTlaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik0xMy43NTg0IDEuNjAwMUgxMS4wMzg0QzEwLjY4NSAxLjYwMDEgMTAuMzk4NCAxLjg4NjY0IDEwLjM5ODQgMi4yNDAxVjQuOTYwMUMxMC4zOTg0IDUuMzEzNTYgMTAuNjg1IDUuNjAwMSAxMS4wMzg0IDUuNjAwMUgxMy43NTg0QzE0LjExMTkgNS42MDAxIDE0LjM5ODQgNS4zMTM1NiAxNC4zOTg0IDQuOTYwMVYyLjI0MDFDMTQuMzk4NCAxLjg4NjY0IDE0LjExMTkgMS42MDAxIDEzLjc1ODQgMS42MDAxWiIgZmlsbD0iI2ZmZiIvPgo8cGF0aCBkPSJNNCAxMkwxMiA0TDQgMTJaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00IDEyTDEyIDQiIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPgo8L3N2Zz4K&logoColor=ffffff)](https://zread.ai/Renhao-Wan/CraftFlow)
[![Backend CI](https://img.shields.io/github/actions/workflow/status/Renhao-Wan/CraftFlow/backend.yml?label=Backend%20CI&logo=github&logoColor=white)](https://github.com/Renhao-Wan/CraftFlow/actions/workflows/backend.yml)
[![Frontend CI](https://img.shields.io/github/actions/workflow/status/Renhao-Wan/CraftFlow/frontend.yml?label=Frontend%20CI&logo=github&logoColor=white)](https://github.com/Renhao-Wan/CraftFlow/actions/workflows/frontend.yml)  <!-- 第1行 -->  
![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-1A1A1A.svg?logo=langchain&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3.41+-003B57.svg?logo=sqlite&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-4169E1.svg?logo=postgresql&logoColor=white)  <!-- 第2行 -->  
![Vue.js](https://img.shields.io/badge/Vue.js-3.5-4FC08D.svg?logo=vue.js&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6.svg?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-8-646CFF.svg?logo=vite&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-20.x_|_22.x-339933.svg?logo=node.js&logoColor=white)
![Electron](https://img.shields.io/badge/Electron-33-47848F.svg?logo=electron&logoColor=white)  <!-- 第3行 -->  

**基于 LangGraph 的智能长文创作与多阶审校平台**

</div>

## 项目简介

CraftFlow 是一个创新的 AI 内容创作平台，采用 LangGraph 驱动的双轨状态机架构，解决大语言模型在长文生成中的质量失控问题。项目以 monorepo 形式组织，包含后端服务、Web 前端和 Electron 桌面版三个子项目。

### 核心特性

- **渐进式织造 (Map-Reduce)** — 大纲先行 + 并发撰写，突破上下文长度限制
- **多阶审校流** — 极速格式化 / 专家对抗 / 事实核查三档弹性算力
- **强制人机协同 (HITL)** — 关键决策点自动挂起，支持断点续传
- **工具链增强** — 集成搜索、代码沙箱、链接验证等外部工具
- **长周期有状态任务** — 基于 Checkpointer 的持久化状态管理

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│  craftflow-desktop (Electron)                               │
│  ┌───────────────────────┐  ┌─────────────────────────────┐ │
│  │  craftflow-web (Vue)  │  │  craftflow-backend (Python) │ │
│  │  前端 SPA             │←→│  FastAPI + LangGraph        │ │
│  └───────────────────────┘  └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

**双图架构**：
- **Creation Graph** — PlannerNode → HITL 大纲确认 → WriterNode (Map-Reduce 并发) → ReducerNode
- **Polishing Graph** — RouterNode → 极速格式化 / Author-Editor 博弈 / 事实核查+博弈

## 项目结构

```
CraftFlow/
├── craftflow-backend/       # Python 后端（FastAPI + LangGraph）
├── craftflow-web/           # Vue 3 前端（TypeScript + Pinia + Vite）
├── craftflow-desktop/       # Electron 桌面版（打包后端+前端）
├── docs/                    # 项目文档
├── scripts/                 # 构建辅助脚本
├── LICENSE                  # Apache-2.0 许可证
└── README.md                # 本文件
```

## 前置要求

| 工具 | 版本要求 | 用途 |
|------|----------|------|
| Python | >= 3.11 | 后端运行 |
| Node.js | ^20.19.0 或 >= 22.12.0 | 前端/桌面版构建 |
| uv | 最新版 | Python 包管理 |
| Git |任意版本 | 版本控制 |

## 快速开始

### 后端 (craftflow-backend)

```bash
cd craftflow-backend

# 安装依赖
uv sync
uv sync --extra dev        # 含 pytest, black, ruff

# 配置环境变量
cp .env.example .env.dev
# 编辑 .env.dev，填写 LLM_API_KEY 等必要配置

# 启动开发服务器
uv run uvicorn app.main:app --reload --env-file .env.dev --host 127.0.0.1 --port 8000
```

服务启动后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 前端 (craftflow-web)

```bash
cd craftflow-web

# 安装依赖
npm install

# 启动开发服务器（自动代理 API 请求到后端）
npm run dev
```

### 桌面版 (craftflow-desktop)

```bash
cd craftflow-desktop

# 一键构建（同步源码 → 安装依赖 → 构建前端 → 构建后端 → 打包 Electron）
scripts\build-all.bat
```

构建产物输出到 `craftflow-desktop/release/` 目录。

开发模式：

```bash
npm run dev
```

## 技术栈

| 层级 | 技术 |
|------|------|
| **后端** | Python 3.11+, FastAPI, Pydantic V2, LangGraph, LangChain, Loguru |
| **前端** | Vue 3.5, TypeScript 5.x, Pinia 3, Vite 8, Vue Router 4.6, Axios |
| **桌面版** | Electron 33, electron-builder |
| **持久化** | SQLite, PostgreSQL + pgvector, Chroma |
| **外部工具** | Tavily (搜索), E2B (代码沙箱) |
| **包管理** | uv (后端), npm (前端/桌面版) |

## 相关文档

### 子项目文档

- [后端 README](craftflow-backend/README.md) — 后端项目详细文档
- [前端 README](craftflow-web/README.md) — 前端项目详细文档
- [桌面版 README](craftflow-desktop/README.md) — 桌面版详细文档

### 架构设计

- [系统架构设计](docs/architecture.md) — 整体架构设计
- [接口流程图解](docs/api-flow.md) — API 接口流程图
- [设计补充文档](docs/design-notes.md) — 设计补充说明
- [未来拓展路线图](docs/roadmap.md) — 项目功能规划

### 后端技术文档

- [Creation Graph 流程](craftflow-backend/docs/creation-graph.md) — 创作图详细流程
- [Polishing Graph 流程](craftflow-backend/docs/polishing-graph.md) — 润色图详细流程
- [核心开发蓝图](craftflow-backend/docs/core-dev-guide.md) — 核心开发规范
- [工具调用说明](craftflow-backend/docs/tool-calling.md) — 工具链调用说明

## 贡献指南

欢迎贡献代码、报告问题或提出改进建议。

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

### 提交规范

使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

- `feat:` 新功能
- `fix:` 修复问题
- `docs:` 文档更新
- `style:` 代码格式调整
- `refactor:` 重构
- `test:` 测试相关
- `chore:` 构建/工具链更新

## 许可证

本项目采用 Apache-2.0 许可证 - 详见 [LICENSE](LICENSE) 文件。

Copyright 2026 Renhao-Wan
