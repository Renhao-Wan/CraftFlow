# CraftFlow WebSocket 通信迁移方案

## 背景

当前前后端采用 REST API + 前端轮询（3s 间隔）的方式交互。存在以下问题：

1. **任务状态查询 bug**：`GET /tasks/{task_id}` 路由仅查 `CreationService._tasks`，润色任务永远返回 TASK_NOT_FOUND
2. **轮询效率低**：每 3 秒一次 HTTP 请求，大部分返回"状态未变"
3. **实时性差**：任务完成最多延迟 3 秒才能感知
4. **资源浪费**：20 个历史任务需 20 个并发 GET 请求来加载列表

迁移到 WebSocket 后：
- 服务端主动推送任务状态变更，实时性从 3s 降低到 <100ms
- 消除轮询产生的无效请求
- 统一任务查询入口，修复 TASK_NOT_FOUND bug
- 前端可移除 usePolling、Axios 拦截器等复杂逻辑

## 架构决策

| 决策 | 选择 | 理由 |
|------|------|------|
| REST 兼容 | **保留 REST + 新增 WS** | REST 用于健康检查、历史查询等无状态场景；WS 用于任务生命周期实时推送 |
| 流式策略 | **手动关键点推送** | 在 service 层用 `astream_events` 监听节点完成事件，手动调用 broadcaster。不侵入 graph nodes 代码 |
| 连接模型 | **单连接多任务复用** | 一个 WebSocket 连接管理所有任务，通过 taskId 订阅机制路由消息 |

---

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
| `error` | 协议错误 | `{ requestId?, code, message }` |
| `pong` | 心跳响应 | `{}` |

### 任务状态流转

```
create_creation/create_polishing
    → task_created (status=running)
    → task_update (status=running, progress=20, currentNode=planner)
    → task_update (status=interrupted, awaiting=outline_confirmation)  [仅创作]
    → [客户端发送 resume_task]                                         [仅创作]
    → task_update (status=running, progress=40)
    → ...
    → task_result (status=completed, result=...)  或  task_error (status=failed, error=...)
```

---

## 后端改动

### 新增文件

#### 1. `app/api/v1/ws.py` — WebSocket 端点 + 连接管理器

```python
# ConnectionManager: 管理所有 WebSocket 连接
# - connect(websocket, client_id): 注册连接
# - disconnect(client_id): 移除连接
# - broadcast(message): 向所有连接广播
# - send_to(client_id, message): 向指定客户端发送

# ws_endpoint(websocket): WebSocket 入口
# - 接受连接，生成 client_id
# - 消息循环：解析 JSON，按 type 路由到对应 handler
# - 异常时清理连接
```

消息路由：
- `create_creation` → 调用 `CreationService.start_task()` + 启动后台推送
- `create_polishing` → 调用 `PolishingService.start_task()` + 启动后台推送
- `resume_task` → 调用 `CreationService.resume_task()` + 启动后台推送
- `get_task_status` → 调用对应 service 的 `get_task_status()`，直接返回
- `subscribe_task` / `unsubscribe_task` → 管理客户端订阅列表
- `ping` → 回复 `pong`

#### 2. `app/api/v1/ws_handler.py` — WebSocket 消息处理逻辑

将消息解析、校验、路由逻辑从 `ws.py` 中拆分出来，保持端点文件简洁。

#### 3. `app/services/task_broadcaster.py` — 任务广播服务

```python
class TaskBroadcaster:
    """管理任务状态变更的 WebSocket 推送"""

    def __init__(self, connection_manager: ConnectionManager):
        self._subscribers: dict[str, set[str]] = {}  # taskId -> {client_ids}

    def subscribe(client_id, taskId)
    def unsubscribe(client_id, taskId)
    def remove_client(client_id)  # 清理断开连接的所有订阅

    async def broadcast_update(taskId, update: dict)
    async def broadcast_result(taskId, result: str, ...)
    async def broadcast_error(taskId, error: str)
```

#### 4. `app/schemas/ws_message.py` — WebSocket 消息 Pydantic 模型

定义所有客户端/服务端消息的类型，用于运行时校验。

### 修改文件

#### 5. `app/services/creation_svc.py` — 添加流式执行方法

新增 `start_task_streaming(broadcaster, client_id)` 方法：
- 使用 `graph.astream_events(initial_state, config, version="v2")` 替代 `ainvoke`
- 监听 `on_chain_end` 事件，过滤节点名（planner、writer、reducer）
- 在关键节点完成时手动调用 `broadcaster.broadcast_update(taskId, {...})` 推送进度
- 捕获 `GraphInterrupt` 时推送 `task_update(status=interrupted, awaiting=outline_confirmation)`
- 最终推送 `task_result` 或 `task_error`
- 保留原有 `start_task()` 和 `get_task_status()` 不变（REST 兼容）

新增 `resume_task_streaming(broadcaster, client_id)` 方法，同理。

流式执行伪代码：
```python
async def start_task_streaming(self, topic, description, broadcaster, client_id):
    task_id = self._generate_task_id()
    self._save_task(task_id, ...)
    await broadcaster.send_to(client_id, {"type": "task_created", "taskId": task_id, ...})

    try:
        async for event in graph.astream_events(initial_state, config, version="v2"):
            if event["event"] == "on_chain_end" and event["name"] in KEY_NODES:
                await broadcaster.broadcast_update(task_id, {
                    "status": "running",
                    "currentNode": event["name"],
                    "progress": self._calculate_progress(...)
                })
    except GraphInterrupt:
        await broadcaster.broadcast_update(task_id, {"status": "interrupted", "awaiting": "outline_confirmation"})
    except Exception as e:
        await broadcaster.broadcast_error(task_id, str(e))
    else:
        await broadcaster.broadcast_result(task_id, result)
```

#### 6. `app/services/polishing_svc.py` — 添加流式执行方法

新增 `start_task_streaming(broadcaster, client_id)` 方法：
- 使用 `astream_events` 执行，监听 router、formatter、debate、fact_checker 节点完成事件
- 在每个关键节点完成时手动调用 `broadcaster.broadcast_update()` 推送进度
- 最终推送 `task_result` 或 `task_error`
- 保留原有 `start_task()` 和 `get_task_status()` 不变（REST 兼容）

#### 7. `app/main.py` — 注册 WebSocket 路由

```python
from app.api.v1.ws import ws_endpoint
app.add_api_websocket_route("/ws", ws_endpoint)
```

在 lifespan 中初始化 ConnectionManager 和 TaskBroadcaster。

#### 8. `app/api/dependencies.py` — 添加新依赖

添加 `get_connection_manager()` 和 `get_task_broadcaster()` 依赖函数。

---

## 前端改动

### 新增文件

#### 1. `src/api/wsClient.ts` — WebSocket 客户端

```typescript
// 单例 WebSocket 管理
// - connect(): 建立连接，指数退避自动重连
// - disconnect(): 关闭连接
// - send(message): 发送 JSON 消息
// - on(type, handler): 注册消息监听
// - off(type, handler): 移除监听
// - isConnected: Ref<boolean>
//
// 心跳机制：每 30s 发送 ping，超时 10s 未收到 pong 则重连
// 重连策略：1s → 2s → 4s → 8s → 16s → 30s，最大 6 次
// 消息队列：断连期间的消息缓存，重连后自动发送
```

#### 2. `src/composables/useWebSocket.ts` — WebSocket Vue composable

```typescript
// 包装 wsClient，提供 Vue 响应式接口
// - isConnected: Ref<boolean>
// - send<T>(type, payload): Promise<T> (带 requestId 匹配响应)
// - onMessage(type, handler): 注册监听，onUnmounted 自动清理
```

### 修改文件

#### 3. `src/stores/task.ts` — 改用 WebSocket 驱动

- 移除 `fetchTaskStatus` 中的 Axios 调用，改为通过 WebSocket 发送 `get_task_status`
- 新增 `handleTaskUpdate(update)` action，由 WebSocket 消息触发
- 新增 `handleTaskResult(result)` 和 `handleTaskError(error)` actions
- `setCurrentTask` 保留，但改为由 WebSocket 消息触发而非轮询回调

#### 4. `src/composables/useTaskLifecycle.ts` — 重构为 WebSocket 驱动

**移除**：
- `usePolling` 依赖
- `start()` 轮询逻辑
- `handleSubmit` 中的 `fetchTaskStatus` + `start()` 调用

**改为**：
- `submitCreation` → 通过 WebSocket 发送 `create_creation`，监听 `task_created` 确认
- `submitPolishing` → 通过 WebSocket 发送 `create_polishing`
- `resumeTask` → 通过 WebSocket 发送 `resume_task`
- `loadTask` → 通过 WebSocket 发送 `get_task_status` 或 `subscribe_task`
- 在 `setup()` 时注册全局 `task_update` / `task_result` / `task_error` 监听
- `onUnmounted` 时清理监听

#### 5. `src/api/creation.ts` — 改为 WebSocket 消息发送

```typescript
// createTask(data) → wsClient.send('create_creation', data)
// resumeTask(taskId, data) → wsClient.send('resume_task', { taskId, ...data })
```

#### 6. `src/api/tasks.ts` — 改为 WebSocket 消息发送

```typescript
// getTaskStatus(taskId) → wsClient.send('get_task_status', { taskId })
```

#### 7. `src/api/polishing.ts` — 改为 WebSocket 消息发送

```typescript
// createPolishingTask(data) → wsClient.send('create_polishing', data)
```

#### 8. `src/views/creation/TaskDetail.vue` — 移除轮询指示器

- 移除 `isPolling` 相关的 UI（蓝色脉冲点）
- 状态更新完全由 WebSocket `task_update` 消息驱动
- 其余逻辑不变（computed 属性自动响应 store 变化）

#### 9. `src/views/polishing/PolishingResult.vue` — 同上

#### 10. `src/views/TaskHistory.vue` — 批量订阅优化

- 加载历史时发送多个 `subscribe_task`，服务端在状态变更时推送
- 移除 `Promise.allSettled` 批量 GET 请求
- 改为：先发 `get_task_status` 获取初始状态，然后订阅后续更新

#### 11. `src/views/Home.vue` — 同上

#### 12. `src/composables/useNetworkStatus.ts` — 集成 WebSocket 连接状态

- WebSocket 的 `isConnected` 可替代 `navigator.onLine` 检测
- 断连时显示"连接已断开，正在重连..."

### 可删除的文件

- `src/composables/usePolling.ts` — 轮询机制被 WebSocket 推送完全替代

### 保留的文件（REST 兼容）

- `src/api/client.ts` — 保留 Axios 客户端，用于健康检查（`GET /health`）等非任务 API
- `src/api/types/` — 保留所有类型定义，WebSocket 消息复用同一套类型
- REST API 函数（`creation.ts`、`tasks.ts`、`polishing.ts`）— 改为 WebSocket 发送，但保留 REST fallback 注释

---

## 实施顺序

### 阶段 1：后端 WebSocket 基础设施

1. 创建 `app/schemas/ws_message.py` — 消息类型定义
2. 创建 `app/services/task_broadcaster.py` — 广播服务
3. 创建 `app/api/v1/ws_handler.py` — 消息处理逻辑
4. 创建 `app/api/v1/ws.py` — WebSocket 端点
5. 修改 `app/main.py` — 注册路由
6. 修改 `app/api/dependencies.py` — 添加依赖

### 阶段 2：后端 Service 流式执行

7. 修改 `app/services/creation_svc.py` — 添加 `start_task_streaming` 和 `resume_task_streaming`
8. 修改 `app/services/polishing_svc.py` — 添加 `start_task_streaming`

### 阶段 3：前端 WebSocket 客户端

9. 创建 `src/api/wsClient.ts` — WebSocket 客户端
10. 创建 `src/composables/useWebSocket.ts` — Vue composable 包装

### 阶段 4：前端迁移

11. 修改 `src/stores/task.ts` — WebSocket 驱动
12. 修改 `src/api/creation.ts`、`tasks.ts`、`polishing.ts` — 改用 WS 发送
13. 修改 `src/composables/useTaskLifecycle.ts` — 移除轮询，改用 WS
14. 修改各 View 组件 — 移除轮询 UI，适配 WS 更新
15. 删除 `src/composables/usePolling.ts`
16. 更新 `src/api/client.ts` — 仅保留健康检查等非任务 API（可选）

### 阶段 5：联调与验证

17. 端到端测试：创建 → 推送 → 中断 → 恢复 → 完成
18. 测试断连重连：断网 → 恢复 → 自动重连 + 状态同步
19. 测试多标签页：两个浏览器标签同时连接，验证广播

---

## 验证方案

1. **创建任务流**：提交创作任务 → 观察实时进度推送 → 大纲确认 → 恢复 → 完成
2. **润色任务流**：提交润色任务 → 观察实时进度 → 完成后展示结果
3. **断连恢复**：WebSocket 断开 → 自动重连 → 重新订阅 → 继续接收更新
4. **404 修复**：润色任务完成后查询状态，不再返回 TASK_NOT_FOUND
5. **类型检查**：`vue-tsc --noEmit` 和 `vite build` 通过
6. **后端测试**：`pytest` 通过（如有 WebSocket 相关测试）
