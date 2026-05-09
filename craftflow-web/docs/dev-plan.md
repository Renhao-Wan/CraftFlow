# CraftFlow 前端开发计划

## 技术栈

- Vue 3.5+ (Composition API, `<script setup>`)
- TypeScript 6.0+ (strict mode)
- Pinia 3.x 状态管理
- Vite 8.x 构建工具
- Vue Router 4.x 路由
- Axios HTTP 客户端
- `@` 路径别名指向 `src/`

## 后端接口契约

### 端点总览

| 方法 | 路径 | 说明 | 请求体 | 响应体 |
|------|------|------|--------|--------|
| POST | `/api/v1/creation` | 发起创作任务 | `CreationRequest` | `TaskResponse` |
| GET | `/api/v1/tasks/{task_id}` | 查询任务状态 | — | `TaskStatusResponse` |
| POST | `/api/v1/tasks/{task_id}/resume` | HITL 恢复执行 | `ResumeRequest` | `TaskResponse` |
| POST | `/api/v1/polishing` | 发起润色任务 | `PolishingRequest` | `TaskResponse` |
| GET | `/health` | 健康检查 | — | `{ status, version, environment }` |

### 数据模型

```typescript
// 请求模型
interface CreationRequest {
  topic: string           // 1-500 字符，必填
  description?: string    // 0-2000 字符，可选
}

interface PolishingRequest {
  content: string         // >=10 字符，Markdown 格式
  mode: 1 | 2 | 3        // 1=极速格式化, 2=专家对抗, 3=事实核查
}

interface ResumeRequest {
  action: 'confirm_outline' | 'update_outline' | 'approve_draft' | 'reject_draft'
  data?: Record<string, unknown>
}

// 响应模型
interface TaskResponse {
  task_id: string
  status: 'running' | 'interrupted' | 'completed' | 'failed'
  message?: string
  created_at?: string     // ISO 8601
}

interface TaskStatusResponse {
  task_id: string
  status: 'running' | 'interrupted' | 'completed' | 'failed'
  current_node?: string
  awaiting?: string       // 'outline_confirmation' 等
  data?: Record<string, unknown>
  result?: string         // 最终文章内容（Markdown）
  error?: string
  progress?: number       // 0-100
  state?: Record<string, unknown>
  history?: Array<{ checkpoint_id: string; ts: string }>
  created_at?: string
  updated_at?: string
}

interface ErrorResponse {
  error: string
  message: string
  detail?: Record<string, unknown>
  timestamp: string
  path?: string
}
```

### 业务流程

**Creation 流程（HITL）**：
1. 用户提交主题 → `POST /creation` → 获取 `task_id`，状态 `running` 或 `interrupted`
2. 轮询 `GET /tasks/{task_id}` 等待状态变为 `interrupted`（`awaiting: "outline_confirmation"`）
3. 用户确认/修改大纲 → `POST /tasks/{task_id}/resume`（action: `confirm_outline` 或 `update_outline`）
4. 继续轮询等待 `completed` 或 `failed`

**Polishing 流程（无人值守）**：
1. 用户提交内容+模式 → `POST /polishing` → 获取 `task_id`
2. 轮询 `GET /tasks/{task_id}` 等待 `completed` 或 `failed`
3. 从 `result` 字段获取润色后内容

---

## 开发阶段

### Phase 1: 基础设施

> 搭建项目骨架、路由、HTTP 客户端、TypeScript 类型定义

#### Task 1.1: 依赖安装与项目配置

安装核心依赖：`vue-router`, `axios`, `@vueuse/core`。

- [ ] 安装 `vue-router@4`, `axios`, `@vueuse/core`
- [ ] 创建 `src/router/index.ts`，配置路由表
- [ ] 在 `src/main.ts` 注册 Router
- [ ] 更新 `src/App.vue` 为 `<router-view />` 布局
- [ ] 在 `vite.config.ts` 中配置开发代理（`/api` → `http://127.0.0.1:8000`）

#### Task 1.2: TypeScript 类型定义

根据后端 Pydantic schema 创建前端类型文件，保持字段名、类型、约束完全一致。

- [ ] 创建 `src/api/types/task.ts` — 任务相关类型（`TaskResponse`, `TaskStatusResponse`, `ErrorResponse`）
- [ ] 创建 `src/api/types/creation.ts` — 创作请求类型（`CreationRequest`）
- [ ] 创建 `src/api/types/polishing.ts` — 润色请求类型（`PolishingRequest`, `PolishingMode`）
- [ ] 创建 `src/api/types/resume.ts` — 恢复请求类型（`ResumeRequest`, `ResumeAction`）
- [ ] 创建 `src/api/types/index.ts` — 统一导出

#### Task 1.3: Axios 客户端封装

封装统一的 HTTP 客户端，处理 baseURL、超时、错误拦截。

- [ ] 创建 `src/api/client.ts` — Axios 实例（baseURL 从环境变量读取，超时 30s）
- [ ] 响应拦截器：统一提取 `response.data`，错误时抛出结构化 `ApiError`
- [ ] 请求拦截器：预留 token 注入位置（当前无需认证）
- [ ] 创建 `src/api/types/errors.ts` — `ApiError` 类定义

#### Task 1.4: API 模块

按业务域拆分 API 调用函数，每个函数有完整的入参/出参类型。

- [ ] 创建 `src/api/creation.ts` — `createTask()`, `getTaskStatus()`, `resumeTask()`
- [ ] 创建 `src/api/polishing.ts` — `createPolishingTask()`
- [ ] 创建 `src/api/tasks.ts` — `getTaskStatus()`（通用查询，供两个流程共用）

### Phase 2: 状态管理与核心逻辑

> Pinia store、轮询机制、任务生命周期管理

#### Task 2.1: 任务 Store

全局任务状态管理，缓存任务列表，跟踪当前活跃任务。

- [ ] 创建 `src/stores/task.ts` — Pinia store
  - state: `currentTask: TaskStatusResponse | null`, `taskHistory: string[]`（最近 N 个 task_id）
  - actions: `fetchTaskStatus(taskId)`, `clearCurrentTask()`
  - getters: `isRunning`, `isInterrupted`, `isCompleted`, `isFailed`
- [ ] 任务历史持久化到 `localStorage`（最多 20 条）

#### Task 2.2: 轮询 Composable

通用轮询 Hook，支持启动/停止/错误重试/指数退避。

- [ ] 创建 `src/composables/usePolling.ts`
  - 参数：`pollFn: () => Promise<T>`, `interval: number`, `shouldStop: (result) => boolean`
  - 返回：`start()`, `stop()`, `isActive`, `lastResult`, `error`
  - 特性：组件卸载自动清理、指数退避（失败时 2s→4s→8s→最大 30s）、最大重试 5 次
  - `shouldStop` 回调：当 `status` 为 `completed` / `failed` 时自动停止

#### Task 2.3: 任务生命周期 Composable

封装完整的任务提交→轮询→中断→恢复流程。

- [ ] 创建 `src/composables/useTaskLifecycle.ts`
  - `submitCreation(topic, description)` — 提交创作任务，自动开始轮询
  - `submitPolishing(content, mode)` — 提交润色任务，自动开始轮询
  - `resumeTask(taskId, action, data)` — HITL 恢复，重启轮询
  - 内部调用 `usePolling`，组件只需关心 UI 展示

### Phase 3: 布局与通用组件

> 应用壳、导航、通用 UI 组件

#### Task 3.1: 应用布局

- [ ] 创建 `src/components/layout/AppHeader.vue` — 顶部导航栏（Logo、导航链接）
- [ ] 创建 `src/components/layout/AppLayout.vue` — 主布局（Header + 内容区）
- [ ] 更新 `src/App.vue` 使用 `AppLayout`

#### Task 3.2: 通用组件

- [ ] 创建 `src/components/common/TaskStatusBadge.vue` — 状态标签（running=蓝、interrupted=黄、completed=绿、failed=红）
- [ ] 创建 `src/components/common/ProgressBar.vue` — 进度条（接收 `percentage` prop）
- [ ] 创建 `src/components/common/LoadingSpinner.vue` — 加载指示器
- [ ] 创建 `src/components/common/ErrorAlert.vue` — 错误提示（显示 message + 重试按钮）
- [ ] 创建 `src/components/common/MarkdownRenderer.vue` — Markdown 渲染（使用 `v-html` + 简单样式）

### Phase 4: Creation 流程页面

> 创作任务的完整用户流程

#### Task 4.1: 任务创建页

- [ ] 创建 `src/views/creation/TaskCreate.vue`
  - 表单：主题输入（必填）、描述输入（可选 textarea）
  - 提交后跳转到任务详情页 `/tasks/:taskId`
  - 前端校验：topic 非空、长度限制

#### Task 4.2: 大纲确认组件

- [ ] 创建 `src/components/creation/OutlineEditor.vue`
  - 展示大纲列表（title + summary），支持内联编辑
  - 操作按钮：「确认大纲」/「更新大纲」
  - 支持拖拽排序（可选，后续迭代）

#### Task 4.3: 任务详情页（Creation）

- [ ] 创建 `src/views/creation/TaskDetail.vue`
  - 状态 `running`：显示进度条 + 当前节点名称 + 加载动画
  - 状态 `interrupted`：展示 `OutlineEditor` 组件，用户确认后调用 `resumeTask()`
  - 状态 `completed`：展示最终文章（Markdown 渲染）+ 复制按钮
  - 状态 `failed`：展示错误信息 + 重试按钮
  - 使用 `useTaskLifecycle` composable

### Phase 5: Polishing 流程页面

> 润色任务的完整用户流程

#### Task 5.1: 润色任务创建页

- [ ] 创建 `src/views/polishing/PolishingCreate.vue`
  - 文本输入区（Markdown 内容，textarea 或简易编辑器）
  - 模式选择：三个卡片（极速格式化 / 专家对抗 / 事实核查），附说明
  - 提交后跳转到润色结果页 `/polishing/:taskId`

#### Task 5.2: 润色结果页

- [ ] 创建 `src/views/polishing/PolishingResult.vue`
  - 状态 `running`：显示进度条 + 模式名称 + 加载动画
  - 状态 `completed`：展示润色后内容（Markdown 渲染）+ 对比视图（原文 vs 润色后）
  - 状态 `failed`：展示错误信息 + 重试按钮
  - 使用 `useTaskLifecycle` composable

### Phase 6: 任务历史与路由收尾

> 任务历史列表、路由完善

#### Task 6.1: 任务历史页

- [ ] 创建 `src/views/TaskHistory.vue`
  - 从 `localStorage` 读取历史 task_id 列表
  - 逐个查询状态，展示列表（task_id、类型、状态、创建时间）
  - 点击跳转到对应详情页

#### Task 6.2: 路由表完善

- [ ] 更新 `src/router/index.ts`，配置完整路由：

```
/                        → 重定向到 /creation
/creation                → TaskCreate.vue
/tasks/:taskId           → TaskDetail.vue (Creation)
/polishing               → PolishingCreate.vue
/polishing/:taskId       → PolishingResult.vue
/history                 → TaskHistory.vue
```

#### Task 6.3: 首页/落地页

- [ ] 创建 `src/views/Home.vue`
  - 两个入口卡片：「开始创作」/「润色文章」
  - 展示最近任务列表（从 history 中取前 5 条）

### Phase 7: 体验优化

> 错误处理、空状态、响应式适配

#### Task 7.1: 全局错误处理

- [ ] 在 Axios 拦截器中处理 401/403/500 等状态码
- [ ] 网络断开时显示全局提示

#### Task 7.2: 空状态与边界处理

- [ ] 各页面添加空状态/加载态/错误态 UI
- [ ] 任务不存在时（404）跳转到历史页

#### Task 7.3: 响应式布局

- [ ] 确保移动端可用（基础适配）

---

## 目录结构（目标）

```
src/
├── api/
│   ├── client.ts               # Axios 实例
│   ├── creation.ts             # 创作 API
│   ├── polishing.ts            # 润色 API
│   ├── tasks.ts                # 通用任务 API
│   └── types/
│       ├── index.ts            # 统一导出
│       ├── task.ts             # 任务响应类型
│       ├── creation.ts         # 创作请求类型
│       ├── polishing.ts        # 润色请求类型
│       ├── resume.ts           # 恢复请求类型
│       └── errors.ts           # API 错误类型
├── composables/
│   ├── usePolling.ts           # 轮询 Hook
│   └── useTaskLifecycle.ts     # 任务生命周期 Hook
├── stores/
│   ├── counter.ts              # (已有，待移除)
│   └── task.ts                 # 任务状态 Store
├── components/
│   ├── layout/
│   │   ├── AppHeader.vue
│   │   └── AppLayout.vue
│   ├── common/
│   │   ├── TaskStatusBadge.vue
│   │   ├── ProgressBar.vue
│   │   ├── LoadingSpinner.vue
│   │   ├── ErrorAlert.vue
│   │   └── MarkdownRenderer.vue
│   └── creation/
│       └── OutlineEditor.vue
├── views/
│   ├── Home.vue
│   ├── TaskHistory.vue
│   ├── creation/
│   │   ├── TaskCreate.vue
│   │   └── TaskDetail.vue
│   └── polishing/
│       ├── PolishingCreate.vue
│       └── PolishingResult.vue
├── router/
│   └── index.ts
├── App.vue
└── main.ts
```

## 约定

- **命名**：组件 PascalCase，composables `use` 前缀，API 函数 camelCase
- **文件组织**：按功能域分目录（`creation/`, `polishing/`），通用组件放 `common/`
- **TypeScript**：strict mode，禁止 `any`，API 响应必须类型化
- **样式**：单文件组件 `<style scoped>`，不引入外部 UI 库（后续可选）
- **后端地址**：开发环境通过 Vite proxy 转发 `/api` 到 `http://127.0.0.1:8000`
