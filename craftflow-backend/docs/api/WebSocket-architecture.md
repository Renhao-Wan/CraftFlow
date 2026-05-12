# CraftFlow WebSocket 通信架构

## 背景

CraftFlow 采用 WebSocket + REST 双通道通信架构：

- **WebSocket** — 主要通道，用于任务创建、恢复、实时状态推送
- **REST (Axios)** — 辅助通道，用于健康检查、历史查询等无状态场景

相比纯 REST 轮询方案，WebSocket 实现了：
- 服务端主动推送，实时性从 3s 降低到 <100ms
- 消除轮询产生的无效请求
- 统一任务查询入口

## 架构决策

| 决策 | 选择 | 理由 |
|------|------|------|
| REST 兼容 | **保留 REST + 新增 WS** | REST 用于健康检查、历史查询等无状态场景；WS 用于任务生命周期实时推送 |
| 流式策略 | **手动关键点推送** | 在 service 层用 `astream_events` 监听节点完成事件，手动调用 broadcaster。不侵入 graph nodes 代码 |
| 连接模型 | **单连接多任务复用** | 一个 WebSocket 连接管理所有任务，通过 taskId 订阅机制路由消息 |

## 消息协议设计

所有消息均为 JSON 格式，通过 `type` 字段区分。每条消息包含 `requestId`（可选）用于请求-响应配对。

### 客户端 → 服务端

| type | 说明 | 负载 |
|------|------|------|
| `create_creation` | 创建创作任务 | `{ requestId, topic, description? }` |
| `create_polishing` | 创建润色任务 | `{ requestId, content, mode }` |
| `resume_task` | HITL 恢复 | `{ requestId, taskId, action, data? }` |
| `get_task_status` | 查询任务状态 | `{ requestId, taskId }` |
| `subscribe_task` | 订阅任务更新 | `{ taskId }` |
| `unsubscribe_task` | 取消订阅 | `{ taskId }` |
| `ping` | 心跳 | `{}` |

### 服务端 → 客户端

| type | 说明 | 负载 |
|------|------|------|
| `task_created` | 任务已创建 | `{ requestId?, taskId, status, createdAt }` |
| `task_update` | 任务状态变更（核心推送） | `{ taskId, status, currentNode?, progress?, awaiting?, data?, error? }` |
| `task_result` | 任务完成 | `{ taskId, result, createdAt?, updatedAt? }` |
| `task_error` | 任务失败 | `{ taskId, error }` |
| `task_status` | 单次查询响应 | `{ requestId, ...TaskStatusResponse }` |
| `creation_outline` | HITL 大纲确认 | `{ taskId, outline }` |
| `error` | 协议错误 | `{ requestId?, code, message }` |
| `pong` | 心跳响应 | `{}` |

### 任务状态流转

```
create_creation/create_polishing
    → task_created (status=running)
    → task_update (status=running, progress=20, currentNode=planner)
    → task_update (status=interrupted, awaiting=outline_confirmation)  [仅创作]
    → creation_outline (大纲数据)                                       [仅创作]
    → [客户端发送 resume_task]                                          [仅创作]
    → task_update (status=running, progress=40)
    → ...
    → task_result (status=completed, result=...)  或  task_error (status=failed, error=...)
```

## 后端模块

| 模块 | 职责 |
|------|------|
| `app/api/v1/ws.py` | WebSocket 端点，连接管理，API Key 鉴权 |
| `app/api/v1/ws_handler.py` | 消息解析、校验、路由逻辑 |
| `app/services/task_broadcaster.py` | `ConnectionManager` + `TaskBroadcaster`，管理订阅和广播 |

## 前端模块

| 模块 | 职责 |
|------|------|
| `src/api/wsClient.ts` | WebSocket 单例客户端（指数退避重连、心跳、requestId 配对、消息缓存） |
| `src/composables/useWebSocket.ts` | WebSocket Vue composable，提供响应式接口 |
| `src/stores/task.ts` | Pinia task store，处理 WebSocket 消息更新任务状态 |

### 前端 WebSocket 特性

- **指数退避重连**：1s → 2s → 4s → 8s → 16s → 30s，最大 6 次
- **心跳检测**：30s 发送 ping，10s pong 超时则重连
- **requestId 配对**：请求-响应匹配，支持并发请求
- **消息缓存**：断连期间缓存消息，重连后自动发送

---

**文档版本**: v1.0
**创建日期**: 2026-05-12
**维护者**: Renhao-Wan
