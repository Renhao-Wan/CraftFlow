# CraftFlow

> 基于 LangGraph 的智能长文创作与多阶审校平台

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
│  CraftFlow-Desktop (Electron)                               │
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
├── CraftFlow-Desktop/       # Electron 桌面版（打包后端+前端）
├── scripts/                 # 构建辅助脚本
├── CLAUDE.md                # Claude Code 项目指引
└── README.md                # 本文件
```

## 快速开始

### 后端 (craftflow-backend)

```bash
cd craftflow-backend

# 安装依赖
uv sync
uv sync --extra dev        # 含 pytest, black, ruff

# 配置环境变量
cp .env.example .env.dev
# 编辑 .env.dev，填写 OPENAI_API_KEY 等必要配置

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

Node 要求：`^20.19.0 || >=22.12.0`

### 桌面版 (CraftFlow-Desktop)

```bash
cd CraftFlow-Desktop

# 安装依赖
npm install

# 开发模式（启动 Electron + 后端 + 前端）
npm run dev

# 构建桌面应用
npm run build

# 打包为可执行文件
npm run dist
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

- [后端 README](craftflow-backend/README.md) — 后端项目详细文档
- [前端 README](craftflow-web/README.md) — 前端项目详细文档
- [桌面版 README](CraftFlow-Desktop/README.md) — 桌面版详细文档
- [后端架构设计](craftflow-backend/docs/CraftFlow%20架构设计方案.md) — 整体架构设计
- [Creation Graph 流程](craftflow-backend/docs/Creation%20Graph%20创作流程详解.md) — 创作图详细流程
- [Polishing Graph 流程](craftflow-backend/docs/Polishing%20Graph%20润色流程详解.md) — 润色图详细流程

## 许可证

本项目采用 Apache-2.0 许可证 - 详见 [LICENSE](LICENSE) 文件。
