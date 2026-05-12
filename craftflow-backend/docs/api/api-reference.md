# CraftFlow API 接口参考

> 本文档列出 CraftFlow Python 后端的全部 REST 和 WebSocket 接口，包括请求格式、响应格式和鉴权要求。

## 一、接口总览

### REST API

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/api/v1/creation` | 创建创作任务 | ✅ |
| POST | `/api/v1/polishing` | 创建润色任务 | ✅ |
| GET | `/api/v1/tasks` | 查询任务列表 | ✅ |
| GET | `/api/v1/tasks/{task_id}` | 查询单任务状态 | ✅ |
| POST | `/api/v1/tasks/{task_id}/resume` | 恢复中断任务 | ✅ |
| DELETE | `/api/v1/tasks/{task_id}` | 删除任务记录 | ✅ |
| GET | `/health` | 健康检查 | ❌ |

### WebSocket

| 路径 | 说明 | 鉴权 |
|------|------|------|
| `/ws` | 实时通信端点 | ✅（查询参数 `api_key`） |

### 鉴权说明

- **standalone 模式**：所有接口无需鉴权，直接放行
- **server 模式 + ENABLE_AUTH=true**：REST 需要 `X-API-Key` 请求头，WebSocket 需要 `api_key` 查询参数

---

## 二、REST API 详细说明

### 2.1 健康检查

```
GET /health
```

**无需鉴权**

**响应** (200)：
```json
{
    "status": "ok",
    "version": "0.1.0",
    "mode": "standalone",
    "environment": "development"
}
```

---

### 2.2 创建创作任务

```
POST /api/v1/creation
Content-Type: application/json
X-API-Key: {api_key}  # server 模式
```

**请求体**：
```json
{
    "topic": "微服务架构演进",       // 必填，非空
    "description": "面向后端工程师"  // 可选，默认 ""
}
```

**响应** (201)：
```json
{
    "task_id": "c-550e8400-e29b-41d4-a716-446655440000",
    "status": "interrupted",
    "message": "大纲已生成，请确认后继续",
    "created_at": "2026-05-12T10:00:00"
}
```

**错误响应**：
| 状态码 | 场景 |
|--------|------|
| 401 | 未提供 API Key |
| 403 | 无效的 API Key |
| 422 | 请求参数验证失败（topic 为空） |
| 500 | Graph 执行错误 |

---

### 2.3 创建润色任务

```
POST /api/v1/polishing
Content-Type: application/json
X-API-Key: {api_key}  # server 模式
```

**请求体**：
```json
{
    "content": "需要润色的文章正文...",  // 必填，非空
    "mode": 3                          // 必填，1/2/3
}
```

**润色模式**：
| mode | 名称 | 说明 |
|------|------|------|
| 1 | 极速格式化 | 单次 LLM 调用，格式整理 |
| 2 | 专家对抗 | Author-Editor 多轮博弈 |
| 3 | 事实核查 | 准确性验证 + 对抗循环 |

**响应** (201)：
```json
{
    "task_id": "p-550e8400-e29b-41d4-a716-446655440000",
    "status": "completed",
    "message": "润色任务已完成",
    "created_at": "2026-05-12T10:00:00"
}
```

**错误响应**：
| 状态码 | 场景 |
|--------|------|
| 401 | 未提供 API Key |
| 403 | 无效的 API Key |
| 422 | 请求参数验证失败（content 为空、mode 不在 1-3） |
| 500 | Graph 执行错误 |

---

### 2.4 查询任务列表

```
GET /api/v1/tasks?limit=50&offset=0
X-API-Key: {api_key}  # server 模式
```

**查询参数**：
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| limit | int | 50 | 最大返回数量（1-200） |
| offset | int | 0 | 偏移量（分页） |

**响应** (200)：
```json
{
    "items": [
        {
            "task_id": "c-xxx",
            "graph_type": "creation",
            "status": "completed",
            "topic": "微服务架构",
            "created_at": "2026-05-12T10:00:00",
            "updated_at": "2026-05-12T10:05:00"
        },
        {
            "task_id": "p-xxx",
            "graph_type": "polishing",
            "status": "interrupted",
            "content": "文章内容...",
            "mode": 3,
            "created_at": "2026-05-12T09:00:00",
            "updated_at": "2026-05-12T09:01:00"
        }
    ],
    "total": 42
}
```

**说明**：
- 返回结果合并了内存中的运行态任务和 SQLite/PG 中的终态任务
- 按 `created_at` 降序排列
- 内存中的任务优先级高于持久化中的同 ID 任务（去重）

---

### 2.5 查询单任务状态

```
GET /api/v1/tasks/{task_id}?include_state=false&include_history=false
X-API-Key: {api_key}  # server 模式
```

**查询参数**：
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| include_state | bool | false | 是否包含完整图状态 |
| include_history | bool | false | 是否包含执行历史 |

**响应** (200)：
```json
{
    "task_id": "c-xxx",
    "status": "interrupted",
    "current_node": "outline_confirmation",
    "awaiting": "outline_confirmation",
    "progress": 30.0,
    "created_at": "2026-05-12T10:00:00",
    "updated_at": "2026-05-12T10:01:00",
    "state": null,
    "history": null
}
```

**状态值**：
| status | 说明 |
|--------|------|
| running | 任务执行中 |
| interrupted | 任务中断（等待用户输入） |
| completed | 任务完成 |
| failed | 任务失败 |

**awaiting 值**：
| awaiting | 说明 |
|----------|------|
| outline_confirmation | 等待大纲确认（创作任务） |

**错误响应**：
| 状态码 | 场景 |
|--------|------|
| 401 | 未提供 API Key |
| 403 | 无效的 API Key |
| 404 | 任务不存在 |

---

### 2.6 恢复中断任务

```
POST /api/v1/tasks/{task_id}/resume
Content-Type: application/json
X-API-Key: {api_key}  # server 模式
```

**请求体**：
```json
{
    "action": "confirm_outline",  // 必填
    "data": null                  // 可选
}
```

**支持的 action**：
| action | 说明 | data |
|--------|------|------|
| `confirm_outline` | 确认当前大纲 | 无需 |
| `update_outline` | 更新大纲后继续 | `{"outline": [...]}` |

**update_outline 的 data 格式**：
```json
{
    "action": "update_outline",
    "data": {
        "outline": [
            {"title": "第一章", "summary": "内容概述"},
            {"title": "第二章", "summary": "内容概述"}
        ]
    }
}
```

**响应** (200)：
```json
{
    "task_id": "c-xxx",
    "status": "completed",
    "message": "创作任务已完成",
    "created_at": "2026-05-12T10:00:00"
}
```

**错误响应**：
| 状态码 | 场景 |
|--------|------|
| 401 | 未提供 API Key |
| 403 | 无效的 API Key |
| 404 | 任务不存在 |
| 422 | 请求参数验证失败（无效 action） |
| 500 | Graph 执行错误 |

---

### 2.7 删除任务

```
DELETE /api/v1/tasks/{task_id}
X-API-Key: {api_key}  # server 模式
```

**响应** (200)：
```json
{
    "task_id": "c-xxx",
    "deleted": true
}
```

**删除逻辑**：
1. 先查内存（_tasks dict），有则从内存移除
2. 内存中没有则从 SQLite/PG 删除
3. 都没有则返回 404

**错误响应**：
| 状态码 | 场景 |
|--------|------|
| 401 | 未提供 API Key |
| 403 | 无效的 API Key |
| 404 | 任务不存在 |

---

## 三、WebSocket 接口

### 3.1 连接

```
ws://host:port/ws?api_key={api_key}
```

**鉴权**：server 模式下通过查询参数 `api_key` 验证。验证失败连接被关闭（code 4001）。

### 3.2 客户端消息类型

| type | 说明 | 参数 |
|------|------|------|
| `create_creation` | 创建创作任务 | `topic`, `description` |
| `create_polishing` | 创建润色任务 | `content`, `mode` |
| `resume_task` | 恢复中断任务 | `task_id`, `action`, `data` |
| `get_task_status` | 查询任务状态 | `task_id` |
| `subscribe` | 订阅任务更新 | `task_id` |
| `unsubscribe` | 取消订阅 | `task_id` |

**消息格式**：
```json
{
    "type": "create_creation",
    "request_id": "uuid-xxx",
    "payload": {
        "topic": "微服务架构",
        "description": "深度技术文章"
    }
}
```

### 3.3 服务端消息类型

| type | 说明 |
|------|------|
| `task_update` | 任务状态更新 |
| `task_result` | 任务完成结果 |
| `task_error` | 任务执行错误 |
| `task_status` | 任务状态查询响应 |
| `creation_outline` | HITL 大纲确认（创作任务） |

**消息格式**：
```json
{
    "type": "task_update",
    "request_id": "uuid-xxx",
    "payload": {
        "task_id": "c-xxx",
        "status": "interrupted",
        "awaiting": "outline_confirmation",
        "outline": [...]
    }
}
```

---

## 四、错误响应格式

### 4.1 业务异常（CraftFlowException）

```json
{
    "error": "TASK_NOT_FOUND",
    "message": "任务不存在: c-xxx",
    "detail": {"task_id": "c-xxx"},
    "timestamp": "2026-05-12T10:00:00",
    "path": "/api/v1/tasks/c-xxx"
}
```

**生产环境**（`ENVIRONMENT=production`）下 `detail` 为空对象 `{}`。

### 4.2 验证异常（422）

```json
{
    "error": "REQUEST_VALIDATION_ERROR",
    "message": "请求参数验证失败",
    "detail": {
        "errors": [
            {
                "type": "string_too_short",
                "loc": ["body", "topic"],
                "msg": "String should have at least 1 character",
                "input": ""
            }
        ]
    },
    "timestamp": "2026-05-12T10:00:00",
    "path": "/api/v1/creation"
}
```

### 4.3 通用异常（500）

```json
{
    "error": "INTERNAL_SERVER_ERROR",
    "message": "服务器内部错误，请稍后重试",
    "detail": {},
    "timestamp": "2026-05-12T10:00:00",
    "path": "/api/v1/creation"
}
```

**开发环境**下 `detail` 包含 `{"exception_type": "ValueError"}`。

### 4.4 错误码表

| error code | HTTP 状态码 | 说明 |
|------------|-------------|------|
| `TASK_NOT_FOUND` | 404 | 任务不存在 |
| `GRAPH_EXECUTION_ERROR` | 500 | Graph 执行错误 |
| `CHECKPOINTER_ERROR` | 500 | 状态持久化错误 |
| `TASK_TIMEOUT` | 408 | 任务执行超时 |
| `LLM_PROVIDER_ERROR` | 502 | LLM API 调用失败 |
| `TOOL_EXECUTION_ERROR` | 502 | 外部工具调用失败 |
| `VALIDATION_ERROR` | 422 | 业务验证失败 |
| `REQUEST_VALIDATION_ERROR` | 422 | 请求参数验证失败 |
| `INTERNAL_SERVER_ERROR` | 500 | 未捕获的内部错误 |

---

**文档版本**: v1.0  
**创建日期**: 2026-05-12  
**维护者**: Renhao-Wan
