# CraftFlow 流式输出架构设计

> 本文档描述 CraftFlow 中流式输出场景的协议选型、架构设计和实现方案，涵盖 LLM 对话功能的流式传输，以及 standalone / server 双端部署下的数据流路径。

## 一、设计背景

### 1.1 需求场景

需要新增 LLM 对话功能，用途包括：
- **快速验证配置**：确认当前 LLM Profile 的 API Key、Base URL、Model 是否正常工作
- **通用对话**：用户直接与大模型交互，用于测试、提问等轻量场景

对话功能的核心特征是**流式输出** — LLM 逐 token 生成内容，用户应能实时看到输出过程，而非等待完整响应。

### 1.2 现有通信架构

项目当前有两种通信协议：

| 协议 | 用途 | 特征 |
|------|------|------|
| **WebSocket** | 任务生命周期（创建、订阅、中断恢复） | 长连接、双向、发布/订阅模式 |
| **REST (Axios)** | CRUD 操作（设置、任务列表、删除） | 短连接、请求/响应模式 |

WebSocket 由 `wsClient.ts` 单例管理，支持指数退避重连、心跳、`requestId` 请求-响应配对。REST 由 `client.ts`（Axios 实例）管理，带拦截器和错误处理。

### 1.3 核心问题

对话流式输出应使用哪种协议？是否应在现有 WebSocket 上扩展，还是引入新协议？

## 二、协议选型分析

### 2.1 候选方案

| 方案 | 描述 |
|------|------|
| A. WebSocket 流式 | 在现有 WebSocket 协议上新增 `create_chat` / `chat_chunk` 消息类型 |
| B. SSE (Server-Sent Events) | 新增 HTTP SSE 端点，服务器通过 `StreamingResponse` 逐块推送 |
| C. REST 阻塞等待 | 普通 POST 请求，服务器生成完毕后一次性返回 |

### 2.2 方案 C 排除：REST 阻塞等待

LLM 生成可能耗时 30 秒以上。阻塞式 HTTP 请求存在以下问题：
- 用户无法看到中间输出，体验差
- 长时间挂起的 HTTP 连接容易超时（反向代理、负载均衡器通常有 60s 超时）
- 连接中断后无法恢复，只能重新请求

**结论**：排除。流式输出必须使用支持服务端推送的协议。

### 2.3 方案 A 分析：WebSocket 流式

**可行性**：技术上完全可行。在现有 `wsClient` 基础上新增消息类型即可。

**需要的改动**：

```
前端 wsClient.ts：
  - 新增 sendAndStream() 方法（替代 sendAndWait，接收多个 chunk）
  - 与现有 sendAndWait() 并存，两套逻辑

后端 ws.py：
  - 新增 create_chat 消息处理分支
  - 实现逐 chunk 发送循环

前端对话组件：
  - 调用 sendAndStream()，监听 chat_chunk 事件
```

**问题**：

1. **wsClient 核心机制改造**：现有 `sendAndWait` 是"发一个请求，等一个响应"语义。流式需要"发一个请求，收 N 个 chunk，然后结束"。这不是简单的加消息类型，而是对核心方法的扩展。两套逻辑（`sendAndWait` / `sendAndStream`）并存增加维护成本。

2. **职责边界模糊**：WebSocket 在项目中承担**任务型长连接**（创建任务 → 异步等待 → 推送结果），本质是发布/订阅模式。对话流式是**请求/响应 + 流式传输**，语义不同。混合在同一通道中模糊了协议的职责边界。

3. **server 模式下 Java 代理复杂**：Java 后端需要代理 WebSocket 连接时，要同时管理与前端和与 Python 的两段 WebSocket 连接，做消息路由和状态同步。相比 HTTP 代理，WebSocket 代理的实现复杂度显著更高。

### 2.4 方案 B 分析：SSE

**工作原理**：

```
前端 POST /api/v1/chat  { messages, profile_id? }
  ↓
后端 StreamingResponse(media_type="text/event-stream")
  ↓
前端 fetch() + ReadableStream 逐块读取
```

**优势**：

1. **天然适配流式场景**：SSE 就是为"服务器向客户端单向推送"设计的。HTTP 连接建立后，服务器逐块写入，客户端逐块读取，连接结束自动关闭。不需要 unsubscribe、不需要心跳。

2. **零改造现有代码**：SSE 是独立模块，不触碰 `wsClient.ts` 和 `ws.py`。现有 WebSocket 逻辑完全不受影响。

3. **后端实现简单**：FastAPI 的 `StreamingResponse` + `async for` 即可：

   ```python
   @router.post("/chat")
   async def chat(request: ChatRequest):
       async def generate():
           async for chunk in llm.astream(messages):
               yield f"data: {json.dumps({'content': chunk.content})}\n\n"
           yield "data: [DONE]\n\n"
       return StreamingResponse(generate(), media_type="text/event-stream")
   ```

4. **前端实现简单**：用 `fetch` + `ReadableStream` 读取，不需要引入新依赖：

   ```typescript
   const response = await fetch('/api/v1/chat', { method: 'POST', body: JSON.stringify(data) })
   const reader = response.body!.getReader()
   while (true) {
     const { done, value } = await reader.read()
     if (done) break
     // 解析 chunk，追加到消息列表
   }
   ```

5. **server 模式下 Java 代理简单**：Java 做 HTTP 流式代理是成熟模式（Spring WebFlux `WebClient`、Nginx 反向代理均原生支持），不需要管理连接状态。

**劣势**：

1. 引入第三种通信协议（WebSocket + REST + SSE），增加开发者心智负担。
2. SSE 是单向的（服务器 → 客户端），如果未来需要客户端中途取消生成，需要额外实现（可通过关闭 `AbortController` 实现，或配合 REST 请求）。

### 2.5 决策结论

**选择方案 B（SSE）**，理由：

| 维度 | WebSocket 流式 | SSE |
|------|---------------|-----|
| 现有代码影响 | 改造 wsClient 核心方法 | 独立模块，零影响 |
| 前端实现复杂度 | 中（新增 sendAndStream） | 低（fetch + ReadableStream） |
| 后端实现复杂度 | 中（ws.py 异步迭代） | 低（StreamingResponse） |
| server 模式 Java 代理 | 高（WS 连接池 + 消息路由） | 低（标准 HTTP 流式代理） |
| 协议职责 | 混合（任务 + 对话） | 清晰分离 |

虽然引入了第三种协议，但每种协议各司其职：

```
WebSocket  →  任务生命周期（创建、订阅、中断恢复）— 长连接、发布/订阅
REST       →  CRUD 操作（设置、任务列表、删除）— 短连接、请求/响应
SSE        →  对话流式输出 — 短连接、单向流
```

## 三、双端架构设计

### 3.1 Standalone 模式（桌面端）

```
┌─────────────┐         ┌─────────────────────┐
│   Frontend  │ ──SSE──→│   Python 后端        │
│  (Electron) │ ←─chunk─│  (FastAPI)           │
└─────────────┘         └─────────────────────┘
     直连，无中间层
```

- 前端直接请求 Python 后端的 SSE 端点
- Python 后端调用 `LLMFactory` 获取 LLM 实例，流式生成
- 无认证（standalone 模式不鉴权）

### 3.2 Server 模式（网页端）

```
┌─────────────┐    SSE     ┌──────────────┐    SSE     ┌─────────────────────┐
│   Frontend  │ ──────────→│  Java 后端    │ ──────────→│   Python 后端        │
│  (Browser)  │ ←─chunk────│  (Spring)    │ ←─chunk────│  (FastAPI)           │
└─────────────┘            └──────────────┘            └─────────────────────┘
                           代理透传，不阻塞
```

- 前端请求 Java 后端的 SSE 端点
- Java 后端验证身份后，向 Python 后端发起 SSE 请求
- Java 使用 `WebClient`（Spring WebFlux）逐块读取 Python 响应，逐块写回前端
- **不阻塞**：数据到了即转发，延迟为一跳网络开销（毫秒级）

Java 代理伪代码：

```java
@PostMapping("/api/v1/chat/stream")
public SseEmitter chatStream(@RequestBody ChatRequest request) {
    SseEmitter emitter = new SseEmitter();
    webClient.post()
        .uri("/internal/chat/stream")
        .bodyValue(request)
        .retrieve()
        .bodyToFlux(String.class)
        .subscribe(
            chunk -> emitter.send(chunk),
            error -> emitter.completeWithError(error),
            () -> emitter.complete()
        );
    return emitter;
}
```

### 3.3 Python 端点设计

Python 后端暴露两个端点（同一实现，不同路径）：

| 路径 | 模式 | 说明 |
|------|------|------|
| `POST /api/v1/chat` | standalone | 前端直接访问 |
| `POST /internal/chat/stream` | server | Java 代理访问（内部端点） |

两个端点指向同一个处理函数，差异仅在路径和鉴权：
- standalone 路径：无鉴权
- server 内部路径：Java 内网调用，通过内部 token 或网络隔离保证安全

## 四、数据流设计

### 4.1 前端消息模型

```typescript
interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}
```

前端在内存中维护 `messages: ChatMessage[]`，关闭页面自然丢弃，不做持久化。

### 4.2 请求格式

```typescript
POST /api/v1/chat
Content-Type: application/json

{
  "messages": [
    { "role": "user", "content": "你好，请介绍一下自己" }
  ],
  "profile_id": "optional-llm-profile-id"
}
```

- `messages`：完整的对话历史（多轮上下文由前端维护，后端无状态）
- `profile_id`：可选，指定使用哪个 LLM Profile。不传则使用默认 Profile

### 4.3 响应格式（SSE 流）

```
data: {"content": "你", "done": false}

data: {"content": "好", "done": false}

data: {"content": "！", "done": false}

data: {"content": "", "done": true}

```

- `content`：本次 chunk 的文本内容
- `done`：是否生成完毕（`true` 时前端停止读取）
- 末尾以 `data: [DONE]\n\n` 结束（OpenAI SSE 惯例，便于兼容）

### 4.4 错误处理

错误不通过 SSE 流返回，而是直接返回 HTTP 错误响应：

| 状态码 | 场景 | 响应体 |
|--------|------|--------|
| 400 | messages 为空或格式错误 | `{"error": "messages is required"}` |
| 404 | profile_id 不存在 | `{"error": "profile not found"}` |
| 500 | LLM 调用失败 | `{"error": "LLM provider error", "detail": "..."}` |
| 503 | LLM 未配置 | `{"error": "no LLM profile configured"}` |

如果流已经开始（已返回 200），中途 LLM 报错：
- 发送 `data: {"error": "...", "done": true}` 通知前端
- 前端展示错误信息，标记该条消息为失败

## 五、前端实现设计

### 5.1 模块结构

```
src/
├── api/
│   ├── chat.ts              # 对话 API（SSE 流式请求，入口 B）
│   └── settings.ts          # 改动：新增 testLlmProfile()（REST 测试，入口 A）
├── composables/
│   └── useChat.ts            # 对话 composable（消息管理 + 流式控制）
├── components/
│   └── settings/
│       └── LlmProfileList.vue  # 改动：卡片增加 [测试连接] + [对话] 按钮
└── views/
    └── Chat.vue              # 对话页面（新增，详见第七章入口 B）
```

### 5.2 API 层 (`api/chat.ts`)

```typescript
interface ChatRequest {
  messages: ChatMessage[]
  profile_id?: string
}

interface ChatChunk {
  content: string
  done: boolean
  error?: string
}

/**
 * 发起流式对话请求
 * 使用 AbortController 支持中途取消
 */
async function streamChat(
  request: ChatRequest,
  onChunk: (chunk: ChatChunk) => void,
  signal?: AbortSignal
): Promise<void>
```

- 用 `fetch` 发起 POST 请求，读取 `ReadableStream`
- 逐行解析 `data: {...}` 格式
- 通过 `onChunk` 回调将 chunk 传给调用方
- 支持 `AbortSignal` 用于取消生成

### 5.3 Composable (`useChat.ts`)

```typescript
function useChat() {
  const messages = ref<ChatMessage[]>([])
  const isStreaming = ref(false)
  const error = ref<string | null>(null)

  /** 发送消息并流式接收回复 */
  async function send(content: string, profileId?: string): Promise<void>

  /** 取消当前流式生成 */
  function cancel(): void

  /** 清空对话历史 */
  function clear(): void

  return { messages, isStreaming, error, send, cancel, clear }
}
```

### 5.4 对话页面 (`Chat.vue`)

页面布局和交互详见第七章入口 B 部分。此处列出核心实现要点：

- 顶部：Profile 选择器（下拉框） + 清空按钮
- 中部：消息列表（用户右对齐、AI 左对齐，AI 消息使用 `MarkdownRenderer` 渲染）
- 底部：输入框 + 发送按钮 + 工具栏（清空、复制对话）
- 流式输出时显示打字光标动画，发送按钮变为"停止"按钮
- 支持 `?profile_id=xxx` query 参数，从设置页跳转时自动选中指定 Profile
- 页面关闭时对话自然丢弃（内存管理，不持久化）

## 六、后端实现设计

### 6.1 新增文件

```
craftflow-backend/app/
├── api/v1/
│   ├── chat.py              # 对话 SSE 端点（入口 B）
│   └── settings.py          # 改动：新增测试端点（入口 A）
├── schemas/
│   └── chat.py              # ChatRequest / ChatChunk / TestRequest DTO
└── services/
    └── chat_svc.py           # 对话服务（流式生成 + 连接测试）
```

### 6.2 Schema 定义 (`schemas/chat.py`)

```python
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    """SSE 流式对话请求（入口 B）。"""
    messages: list[ChatMessage]
    profile_id: str | None = None  # 不传则用默认 Profile

class TestProfileRequest(BaseModel):
    """LLM Profile 连接测试请求（入口 A）。"""
    pass  # 无参数，使用固定测试消息

class TestProfileResponse(BaseModel):
    """LLM Profile 连接测试响应。"""
    success: bool
    reply: str | None = None
    error: str | None = None
```

### 6.3 对话服务 (`services/chat_svc.py`)

```python
class ChatService:
    """对话服务，负责 LLM 对话和连接测试。"""

    TEST_MESSAGE = "请回复OK，确认连接正常。"

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        profile_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式生成对话响应（入口 B）。

        Yields:
            SSE 格式的 chunk 字符串
        """
        llm = self._get_llm(profile_id)
        langchain_messages = self._convert_messages(messages)

        async for chunk in llm.astream(langchain_messages):
            yield f"data: {json.dumps({'content': chunk.content, 'done': False})}\n\n"

        yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"
        yield "data: [DONE]\n\n"

    async def test_profile(self, profile_id: str) -> TestProfileResponse:
        """
        测试 LLM Profile 连接（入口 A）。
        发送固定测试消息，返回完整响应。
        """
        try:
            llm = self._get_llm(profile_id)
            response = await llm.ainvoke(
                [HumanMessage(content=self.TEST_MESSAGE)]
            )
            return TestProfileResponse(success=True, reply=response.content)
        except Exception as e:
            return TestProfileResponse(success=False, error=str(e))
```

- 复用 `LLMFactory` 获取 LLM 实例
- `stream_chat`：通过 `profile_id` 指定 LLM Profile，使用 LangChain 的 `astream()` 流式输出
- `test_profile`：使用 `ainvoke()` 一次性获取完整响应，用于快速验证

### 6.4 API 端点

**对话端点** (`api/v1/chat.py`，新增文件)：

```python
@router.post("/chat")
async def chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
):
    """SSE 流式对话端点（入口 B）。"""
    return StreamingResponse(
        service.stream_chat(request.messages, request.profile_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )
```

**测试端点** (`api/v1/settings.py`，已有文件新增路由)：

```python
@router.post("/settings/llm-profiles/{profile_id}/test")
async def test_llm_profile(
    profile_id: str,
    service: ChatService = Depends(get_chat_service),
) -> TestProfileResponse:
    """
    测试 LLM Profile 连接（入口 A）。
    发送固定测试消息，返回完整响应。
    """
    return await service.test_profile(profile_id)
```

测试端点放在 Settings 路由下，因为它本质上是设置验证功能，而非对话功能。

## 七、入口设计（A + B 组合方案）

LLM 对话功能有两个不同层次的需求：
- **快速验证**："我的 API Key / Model 配置对不对？" — 需要即时反馈，不需要多轮对话
- **通用对话**："我想和模型聊几句" — 需要完整对话体验，流式输出，多轮上下文

这两个需求的使用频率、交互深度、用户心态完全不同，不应塞进同一个入口。采用 A + B 组合方案，将它们拆成两个独立入口。

### 7.1 入口 A：设置页内嵌测试（快速验证）

#### 位置

设置页 → LLM 配置 Tab → 每个 Profile 卡片底部。

```
┌──────────────────────────────────────────────────────┐
│ ⚙ GPT-4o                          [默认] [编辑] [删除] │
│ API: https://api.openai.com/v1/v1                     │
│ Model: gpt-4o    Temperature: 0.7                     │
│                                                      │
│ [测试连接]                                             │
└──────────────────────────────────────────────────────┘
```

点击 [测试连接] 后，卡片底部展开内嵌测试区域：

```
┌──────────────────────────────────────────────────────┐
│ ⚙ GPT-4o                          [默认] [编辑] [删除] │
│ API: https://api.openai.com/v1/v1                     │
│ Model: gpt-4o    Temperature: 0.7                     │
│                                                      │
│ ┌──────────────────────────────────────────────────┐ │
│ │  🔄 正在测试...                                    │ │
│ │                                                  │ │
│ │  发送: 请回复OK，确认连接正常。                     │ │
│ │  收到: OK. 连接正常。 ✓                           │ │
│ │                                                  │ │
│ │  [关闭]  [重新测试]                                │ │
│ └──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

#### 交互流程

```
用户点击 [测试连接]
  → 展开内嵌区域，显示"正在测试..."
  → 自动发送固定测试消息: "请回复OK，确认连接正常。"
  → 等待完整响应（非流式，REST 请求）
  → 成功: 显示回复内容 + 绿色 ✓
  → 失败: 显示错误信息 + 红色 ✗ + 错误原因（如 API Key 无效、模型不存在）
```

#### 技术方案

使用 **REST 请求**（非 SSE），因为：
- 只有一问一答，不需要流式
- 实现最简单，用现有 Axios 实例即可
- 不需要引入 SSE 基础设施

```typescript
// api/settings.ts 中新增
/**
 * 测试 LLM Profile 连接
 * 发送固定消息，等待完整响应，用于验证配置是否正确
 */
async function testLlmProfile(profileId: string): Promise<{ success: boolean; reply: string; error?: string }>
```

后端新增 REST 端点：

```python
@router.post("/settings/llm-profiles/{profile_id}/test")
async def test_llm_profile(
    profile_id: str,
    adapter: BusinessAdapter = Depends(get_adapter),
):
    """
    测试 LLM Profile 连接。
    发送固定消息，返回完整响应，用于快速验证配置。
    """
    llm = llm_factory.get_llm(profile_id)
    response = await llm.ainvoke([HumanMessage(content="请回复OK，确认连接正常。")])
    return {"success": True, "reply": response.content}
```

#### 状态管理

内嵌测试的状态不需要全局管理，在 `LlmProfileList.vue` 组件内部用局部 `ref` 即可：

```typescript
// LlmProfileList.vue 内部
const testingProfileId = ref<string | null>(null)   // 正在测试的 Profile ID
const testResult = ref<{ success: boolean; reply: string; error?: string } | null>(null)
const testLoading = ref(false)
```

#### 错误场景

| 场景 | 展示 |
|------|------|
| API Key 无效 | 红色 ✗ + "API Key 无效，请检查配置" |
| API Base URL 不可达 | 红色 ✗ + "无法连接到 {url}，请检查网络或地址" |
| 模型名称不存在 | 红色 ✗ + "模型 {model} 不存在，请检查模型名称" |
| 请求超时（30s） | 红色 ✗ + "请求超时，请检查网络连接" |
| 其他错误 | 红色 ✗ + 后端返回的错误详情 |

### 7.2 入口 B：侧边栏完整对话页（通用对话）

#### 位置

侧边栏新增"对话"导航项，与创作、润色、历史并列。

```
┌──────────────┐
│   CraftFlow  │
│              │
│  ▶ 创作      │
│  ▶ 润色      │
│  ▶ 对话  ← 新增
│  ▶ 历史      │
│              │
│  ───────────  │
│  ⚙ 设置      │
│  v0.1.0      │
└──────────────┘
```

#### 路由

```typescript
// router/index.ts 新增
{
  path: '/chat',
  name: 'chat',
  component: () => import('@/views/Chat.vue'),
}
```

#### 页面布局

```
┌──────────────────────────────────────────────────────────┐
│ 对话                                     [Profile ▾] [清空] │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────────────────────────────────────┐        │
│  │ 👤  你好，请介绍一下自己                        │        │
│  └─────────────────────────────────────────────┘        │
│                                                          │
│  ┌─────────────────────────────────────────────┐        │
│  │ 🤖  你好！我是一个 AI 助手，可以帮你回答问题、    │        │
│  │    写作、编程等任务。有什么可以帮你的吗？         │        │
│  │    █ ← 流式光标动画                             │        │
│  └─────────────────────────────────────────────┘        │
│                                                          │
├──────────────────────────────────────────────────────────┤
│ [复制对话]                                                │
│ ┌──────────────────────────────────────────────┐ ┌────┐ │
│ │ 输入消息...                                    │ │发送│ │
│ └──────────────────────────────────────────────┘ └────┘ │
└──────────────────────────────────────────────────────────┘
```

#### 顶部功能区

| 元素 | 说明 |
|------|------|
| 标题 "对话" | 固定文字 |
| Profile 选择器 | 下拉框，列出所有已配置的 LLM Profile，默认选中 `is_default=true` 的 Profile |
| 清空按钮 | 清空当前对话历史（内存中的 `messages[]`） |

#### Profile 选择器

```typescript
// 从 settings store 获取 profile 列表
const { profiles } = useSettingsStore()
const selectedProfileId = ref<string>(
  profiles.find(p => p.is_default)?.id ?? profiles[0]?.id ?? ''
)
```

- 下拉显示 Profile 名称 + 模型名（如 "GPT-4o (gpt-4o)"）
- 切换 Profile 时不清空对话历史（用户可能想用不同模型继续同一话题）
- 如果没有配置任何 Profile，显示提示并引导去设置页

#### 消息列表

- 用户消息：右对齐，背景色使用 `--color-accent`
- AI 消息：左对齐，使用 `MarkdownRenderer` 组件渲染（复用现有组件）
- 流式输出时显示打字光标动画（CSS `@keyframes blink`）
- 消息列表自动滚动到底部（`scrollIntoView`）
- 支持 `BackToTop` 组件（复用现有组件）

#### 输入区域

| 行为 | 说明 |
|------|------|
| Enter 发送 | 单行时 Enter 发送，Shift+Enter 换行 |
| 流式中禁用 | AI 正在输出时，输入框禁用，发送按钮变为"停止"按钮 |
| 空消息禁止 | 内容为空时发送按钮置灰 |
| 最大长度 | 单条消息不超过 4000 字符（防止超出 LLM 上下文窗口） |

#### 工具栏

| 按钮 | 功能 |
|------|------|
| 复制对话 | 将整个对话历史格式化为 Markdown，复制到剪贴板 |
| 清空 | 清空 `messages[]`，重置对话 |

#### 设置页"测试"按钮联动

设置页 Profile 卡片上的 [测试连接] 按钮旁边增加一个 [对话] 按钮：

```
[测试连接]  [对话]
```

点击 [对话] 后跳转到 `/chat`，并自动选中该 Profile：

```
/chat?profile_id=xxx
```

`Chat.vue` 检测到 `profile_id` query 参数后，自动设置 Profile 选择器。不清空对话，用户可以直接开始聊天。

### 7.3 两个入口的关系

```
设置页（入口 A - 快速验证）              对话页（入口 B - 完整对话）
┌─────────────────────────┐           ┌─────────────────────────┐
│ LLM Profile 卡片         │           │ 消息列表（流式输出）       │
│                         │           │                         │
│ [测试连接] → 内嵌一问一答  │  [对话]→  │ Profile 选择器            │
│ （REST，非流式）          │  跳转     │ 输入框 + 发送             │
│                         │           │ （SSE 流式）              │
│ 用途: 验证配置           │           │ 用途: 通用对话             │
│ 交互: 轻量，点一下就完    │           │ 交互: 沉浸，多轮交流       │
└─────────────────────────┘           └─────────────────────────┘
```

| 维度 | 入口 A（测试连接） | 入口 B（对话页） |
|------|-------------------|-----------------|
| 目的 | 验证配置是否正确 | 与模型自由对话 |
| 位置 | 设置页 Profile 卡片内 | 侧边栏独立页面 |
| 通信协议 | REST（一次性请求/响应） | SSE（流式输出） |
| 对话轮数 | 1 轮（固定测试消息） | 多轮（用户自定义） |
| 消息持久化 | 不需要 | 不需要（内存） |
| Profile 选择 | 自动使用当前卡片的 Profile | 用户通过下拉框切换 |
| 离开页面 | 不影响（在设置页内） | 对话丢失（内存清空） |

### 7.4 前端模块结构（更新）

```
src/
├── api/
│   ├── chat.ts              # 对话 API（SSE 流式请求）
│   └── settings.ts          # 新增 testLlmProfile()（REST 测试请求）
├── composables/
│   └── useChat.ts            # 对话 composable（消息管理 + 流式控制）
├── components/
│   └── settings/
│       └── LlmProfileList.vue  # 改动：卡片增加 [测试连接] + [对话] 按钮
└── views/
    └── Chat.vue              # 对话页面（新增）
```

### 7.5 侧边栏改动

`AppSidebar.vue` 的导航列表新增"对话"项：

```typescript
const navItems = [
  { name: '创作', route: '/creation', icon: 'creation' },
  { name: '润色', route: '/polishing', icon: 'polishing' },
  { name: '对话', route: '/chat', icon: 'chat' },       // 新增
  { name: '历史', route: '/history', icon: 'history' },
]
```

需要新增一个 `chat` SVG 图标（如对话气泡样式）。

## 八、不做的事

| 不做 | 原因 |
|------|------|
| 对话持久化 | 测试工具定位，页面关闭即丢弃。standalone 模式无用户概念，server 模式持久化需 Java 后端新建对话表，投入产出比不合适 |
| 上下文窗口管理 | 前端传完整 messages 数组，由 LLM 自身的上下文窗口限制。超出时后端返回错误，前端提示用户清空对话 |
| 多会话管理 | 单页面一个会话，不做会话列表。需要新对话时点"清空"即可 |
| 流式取消（后端中断） | v1 版本通过前端 `AbortController` 断开连接实现取消，后端检测到连接断开后停止生成。不做精确的后端中断控制 |
| 设置页测试的历史记录 | 设置页的"测试连接"是一次性验证，不需要保留测试结果历史。每次点击重新测试 |
