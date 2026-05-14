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
| GET | `/api/v1/settings/llm-profiles` | 获取所有 LLM Profile | ✅ |
| POST | `/api/v1/settings/llm-profiles` | 创建新 LLM Profile | ✅ |
| PUT | `/api/v1/settings/llm-profiles/{id}` | 更新 LLM Profile | ✅ |
| DELETE | `/api/v1/settings/llm-profiles/{id}` | 删除 LLM Profile | ✅ |
| POST | `/api/v1/settings/llm-profiles/{id}/set-default` | 设为默认 Profile | ✅ |
| GET | `/api/v1/settings/writing-params` | 获取写作参数 | ✅ |
| PATCH | `/api/v1/settings/writing-params` | 更新写作参数 | ✅ |
| POST | `/api/v1/settings/llm-profiles/{id}/test` | 测试 LLM Profile 连接 | ✅ |
| POST | `/api/v1/chat` | SSE 流式对话 | ✅ |
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

### 2.8 获取所有 LLM Profile

```
GET /api/v1/settings/llm-profiles
X-API-Key: {api_key}  # server 模式
```

**响应** (200)：
```json
{
    "profiles": [
        {
            "id": "a1b2c3d4-...",
            "name": "GPT-4o",
            "api_key": "sk-***",  // 脱敏显示
            "api_base": "https://api.openai.com/v1",
            "model": "gpt-4o",
            "temperature": 0.7,
            "is_default": true,
            "created_at": "2026-05-12T10:00:00",
            "updated_at": "2026-05-12T10:00:00"
        },
        {
            "id": "e5f6g7h8-...",
            "name": "DeepSeek",
            "api_key": "sk-***",
            "api_base": "https://api.deepseek.com",
            "model": "deepseek-chat",
            "temperature": 0.7,
            "is_default": false,
            "created_at": "2026-05-12T09:00:00",
            "updated_at": "2026-05-12T09:00:00"
        }
    ]
}
```

---

### 2.9 创建 LLM Profile

```
POST /api/v1/settings/llm-profiles
Content-Type: application/json
X-API-Key: {api_key}  # server 模式
```

**请求体**：
```json
{
    "name": "GPT-4o",                              // 必填，唯一
    "api_key": "sk-xxx",                           // 必填
    "api_base": "https://api.openai.com/v1",       // 可选，默认 ""
    "model": "gpt-4o",                             // 必填
    "temperature": 0.7,                            // 可选，默认 0.7
    "is_default": true                             // 可选，默认 false
}
```

**响应** (201)：
```json
{
    "id": "a1b2c3d4-...",
    "name": "GPT-4o",
    "message": "LLM Profile 创建成功"
}
```

**错误响应**：
| 状态码 | 场景 |
|--------|------|
| 400 | name 已存在 |
| 422 | 请求参数验证失败 |

---

### 2.10 更新 LLM Profile

```
PUT /api/v1/settings/llm-profiles/{id}
Content-Type: application/json
X-API-Key: {api_key}  # server 模式
```

**请求体**（所有字段可选）：
```json
{
    "name": "GPT-4o Updated",
    "api_key": "sk-new-xxx",
    "api_base": "https://api.openai.com/v1",
    "model": "gpt-4o",
    "temperature": 0.5
}
```

**响应** (200)：
```json
{
    "id": "a1b2c3d4-...",
    "message": "LLM Profile 更新成功"
}
```

**错误响应**：
| 状态码 | 场景 |
|--------|------|
| 404 | Profile 不存在 |
| 400 | name 已存在（与其他 Profile 冲突） |
| 422 | 请求参数验证失败 |

---

### 2.11 删除 LLM Profile

```
DELETE /api/v1/settings/llm-profiles/{id}
X-API-Key: {api_key}  # server 模式
```

**响应** (200)：
```json
{
    "id": "a1b2c3d4-...",
    "message": "LLM Profile 删除成功"
}
```

**错误响应**：
| 状态码 | 场景 |
|--------|------|
| 404 | Profile 不存在 |
| 400 | 不能删除默认 Profile（需先设置其他 Profile 为默认） |

---

### 2.12 设为默认 Profile

```
POST /api/v1/settings/llm-profiles/{id}/set-default
X-API-Key: {api_key}  # server 模式
```

**响应** (200)：
```json
{
    "id": "a1b2c3d4-...",
    "message": "已设为默认 LLM Profile"
}
```

**说明**：
- 将指定 Profile 设为默认，其他 Profile 的 `is_default` 自动取消
- 创建任务时默认使用 `is_default=true` 的 Profile

**错误响应**：
| 状态码 | 场景 |
|--------|------|
| 404 | Profile 不存在 |

---

### 2.13 获取写作参数

```
GET /api/v1/settings/writing-params
X-API-Key: {api_key}  # server 模式
```

**响应** (200)：
```json
{
    "max_outline_sections": 5,
    "max_concurrent_writers": 3,
    "max_debate_iterations": 3,
    "editor_pass_score": 90,
    "task_timeout": 3600,
    "tool_call_timeout": 30
}
```

---

### 2.14 更新写作参数

```
PATCH /api/v1/settings/writing-params
Content-Type: application/json
X-API-Key: {api_key}  # server 模式
```

**请求体**（所有字段可选）：
```json
{
    "max_outline_sections": 15,
    "max_concurrent_writers": 3,
    "max_debate_iterations": 5,
    "editor_pass_score": 85,
    "task_timeout": 7200,
    "tool_call_timeout": 60
}
```

**响应** (200)：
```json
{
    "message": "写作参数更新成功",
    "params": {
        "max_outline_sections": 15,
        "max_concurrent_writers": 3,
        "max_debate_iterations": 5,
        "editor_pass_score": 85,
        "task_timeout": 7200,
        "tool_call_timeout": 60
    }
}
```

**说明**：
- 修改后立即生效，无需重启服务
- 下次创建任务时使用新参数

---

### 2.15 测试 LLM Profile 连接

```
POST /api/v1/settings/llm-profiles/{id}/test
X-API-Key: {api_key}  # server 模式
```

**用途**：快速验证 LLM Profile 的 API Key、Base URL、Model 配置是否正确。

**响应** (200)：
```json
{
    "success": true,
    "reply": "OK. 连接正常。",
    "error": null
}
```

**错误响应** (200)：
```json
{
    "success": false,
    "reply": null,
    "error": "API Key 无效，请检查配置"
}
```

**说明**：
- 发送固定测试消息："请回复OK，确认连接正常。"
- 使用 REST 请求（非 SSE），等待完整响应
- 错误场景：API Key 无效、Base URL 不可达、模型不存在、请求超时（30s）

---

### 2.16 SSE 流式对话

```
POST /api/v1/chat
Content-Type: application/json
X-API-Key: {api_key}  # server 模式
```

**用途**：与 LLM 进行流式对话，用于快速验证配置或通用对话场景。

**请求体**：
```json
{
    "messages": [
        {"role": "user", "content": "你好，请介绍一下自己"}
    ],
    "profile_id": "optional-llm-profile-id"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `messages` | ChatMessage[] | ✅ | 完整对话历史（多轮上下文由前端维护，后端无状态） |
| `profile_id` | string | ❌ | 指定 LLM Profile，不传则使用默认 Profile |

**响应** (200, `text/event-stream`)：
```
data: {"content": "你", "done": false}

data: {"content": "好", "done": false}

data: {"content": "！", "done": false}

data: {"content": "", "done": true}

data: [DONE]
```

**SSE 格式说明**：
- `content`：本次 chunk 的文本内容
- `done`：是否生成完毕（`true` 时前端停止读取）
- 末尾以 `data: [DONE]\n\n` 结束（OpenAI SSE 惯例）

**错误响应**：

| 状态码 | 场景 | 响应体 |
|--------|------|--------|
| 400 | messages 为空或格式错误 | `{"error": "messages is required"}` |
| 404 | profile_id 不存在 | `{"error": "profile not found"}` |
| 500 | LLM 调用失败 | `{"error": "LLM provider error", "detail": "..."}` |
| 503 | LLM 未配置 | `{"error": "no LLM profile configured"}` |

**流中途错误**：
如果流已经开始（已返回 200），中途 LLM 报错：
- 发送 `data: {"error": "...", "done": true}` 通知前端
- 前端展示错误信息，标记该条消息为失败

**响应头**：
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no  # 禁用 Nginx 缓冲
```

**前端实现示例**：
```typescript
const response = await fetch('/api/v1/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ messages, profile_id })
})
const reader = response.body!.getReader()
const decoder = new TextDecoder()

while (true) {
  const { done, value } = await reader.read()
  if (done) break

  const text = decoder.decode(value)
  const lines = text.split('\n')

  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = line.slice(6)
      if (data === '[DONE]') return

      const chunk = JSON.parse(data)
      // 追加到消息列表
    }
  }
}
```

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
| `LLM_PROFILE_NOT_FOUND` | 404 | LLM Profile 不存在 |
| `LLM_PROFILE_NAME_EXISTS` | 400 | LLM Profile 名称已存在 |
| `LLM_PROFILE_IS_DEFAULT` | 400 | 不能删除默认 Profile |
| `NO_LLM_PROFILE` | 500 | 未配置 LLM Profile |
| `GRAPH_EXECUTION_ERROR` | 500 | Graph 执行错误 |
| `CHECKPOINTER_ERROR` | 500 | 状态持久化错误 |
| `TASK_TIMEOUT` | 408 | 任务执行超时 |
| `LLM_PROVIDER_ERROR` | 502 | LLM API 调用失败 |
| `TOOL_EXECUTION_ERROR` | 502 | 外部工具调用失败 |
| `VALIDATION_ERROR` | 422 | 业务验证失败 |
| `REQUEST_VALIDATION_ERROR` | 422 | 请求参数验证失败 |
| `INTERNAL_SERVER_ERROR` | 500 | 未捕获的内部错误 |

---

**文档版本**: v2.1
**创建日期**: 2026-05-12
**最后更新**: 2026-05-13
**维护者**: Renhao-Wan
