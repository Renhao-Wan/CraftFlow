# CraftFlow Web

> CraftFlow 智能长文创作平台 — 前端应用

## 项目简介

CraftFlow Web 是基于 Vue 3 + TypeScript + Pinia + Vite 构建的 SPA 应用，提供完整的业务功能，包括任务创建、实时状态监控、中断恢复、结果展示等。采用 WebSocket 主通道 + REST 辅助通道的双通道通信架构。

## 技术栈

- **框架**: Vue 3.5 (Composition API, `<script setup>`)
- **语言**: TypeScript 5.x (strict mode)
- **状态管理**: Pinia 3
- **构建工具**: Vite 8
- **路由**: Vue Router 4.6 (Hash History)
- **HTTP 客户端**: Axios
- **Markdown 渲染**: Marked

## 快速开始

### 环境要求

- Node.js `^20.19.0 || >=22.12.0`

### 安装与运行

```bash
# 安装依赖
npm install

# 启动开发服务器（自动代理 API 请求到 http://127.0.0.1:8000）
npm run dev

# 类型检查 + 生产构建
npm run build

# 仅 Vite 构建（跳过类型检查）
npm run build-only

# vue-tsc 类型检查
npm run type-check

# 预览生产构建
npm run preview
```

### 环境变量

```bash
VITE_API_BASE_URL=/api                  # API 代理路径
VITE_WS_URL=ws://localhost:8000/ws      # WebSocket 地址
```

开发模式下 Vite 自动代理 `/api` 和 `/ws` 请求到后端服务。

## 项目结构

```
src/
├── api/                    # API 层
│   ├── client.ts           # Axios 客户端（拦截器、错误处理）
│   ├── wsClient.ts         # WebSocket 单例客户端（重连、心跳、requestId 配对）
│   ├── creation.ts         # 创作任务 API（WebSocket 驱动）
│   ├── polishing.ts        # 润色任务 API
│   ├── tasks.ts            # 任务列表/删除 API（REST）
│   └── types/              # TypeScript 类型定义
│
├── composables/            # 组合式函数
│   ├── useNetworkStatus.ts # 网络状态监听
│   ├── useTaskLifecycle.ts # 任务生命周期管理
│   ├── useToast.ts         # Toast 通知
│   └── useWebSocket.ts     # WebSocket 连接管理
│
├── stores/                 # Pinia 状态管理
│   └── task.ts             # 任务状态 store
│
├── components/             # 组件
│   ├── common/             # 通用组件（ErrorAlert, LoadingSpinner, MarkdownRenderer 等）
│   ├── creation/           # 创作组件（OutlineEditor 大纲编辑器）
│   └── layout/             # 布局组件（AppLayout, AppSidebar）
│
├── views/                  # 页面视图
│   ├── Home.vue            # 首页
│   ├── TaskHistory.vue     # 任务历史
│   ├── creation/           # 创作页面（TaskCreate, TaskDetail）
│   └── polishing/          # 润色页面（PolishingCreate, PolishingResult）
│
├── router/                 # 路由配置
├── styles/                 # 全局样式（CSS 变量）
└── utils/                  # 工具函数
```

## 路由

| 路径 | 组件 | 说明 |
|------|------|------|
| `/` | Home.vue | 首页 |
| `/creation` | TaskCreate.vue | 创作任务创建 |
| `/tasks/:taskId` | TaskDetail.vue | 创作任务详情 |
| `/polishing` | PolishingCreate.vue | 润色任务创建 |
| `/polishing/:taskId` | PolishingResult.vue | 润色结果 |
| `/history` | TaskHistory.vue | 任务历史 |
| `/:pathMatch(.*)*` | NotFound.vue | 404 |

## 核心模块

### 通信架构

- **WebSocket (主通道)** — 任务创建、恢复、实时状态推送。客户端实现指数退避重连（1s-30s, 最多 6 次）、30s 心跳、requestId 请求-响应配对、断连消息缓存
- **REST / Axios (辅助通道)** — 任务列表查询、任务删除

### 组合式函数

| 函数 | 职责 |
|------|------|
| `useTaskLifecycle` | 任务创建 → 跳转 → 轮询 → 中断 → 恢复 |
| `useWebSocket` | WebSocket 连接状态管理 |
| `useNetworkStatus` | 网络连接状态监听 |
| `useToast` | Toast 通知 |

### 通用组件

| 组件 | 说明 |
|------|------|
| `OutlineEditor.vue` | 大纲编辑器，用于 HITL 大纲确认和修改 |
| `MarkdownRenderer.vue` | Markdown 渲染组件 |
| `TaskStatusBadge.vue` | 任务状态徽章 |
| `ProgressBar.vue` | 进度条 |
| `ErrorAlert.vue` | 错误提示 |
| `LoadingSpinner.vue` | 加载动画 |

## 构建与部署

```bash
npm run build
```

构建产物输出到 `dist/` 目录，可部署到任何静态文件服务器。桌面版构建时 Vite 配置 `base: './'` 以兼容 Electron 的相对路径加载。
