# 优化 1：LLM Streaming 替代 ainvoke

## 现状分析

所有 LangGraph 节点（planner_node、writer_node、reducer_node）均使用 `llm.ainvoke()` 调用 LLM。该方式为**阻塞式调用**，必须等待 LLM 完整生成所有 token 后才返回结果。

### 当前调用链

```
用户提交任务
  → WebSocket 发送 create_creation
  → 后端 asyncio.create_task 启动异步执行
  → graph.astream() 逐节点 yield（LangGraph 图级流式）
     → planner_node: llm.ainvoke() → 等待 10-30s → 返回完整大纲
     → writer_node ×N: llm.ainvoke() → 等待 15-45s → 返回完整章节（并发）
     → reducer_node: llm.ainvoke() → 等待 10-30s → 返回完整文稿
  → broadcast_result 推送最终结果
```

### 问题

- `graph.astream()` 只是 LangGraph **图级**流式（逐节点 yield），不是 LLM **token 级**流式
- 用户在单个节点执行期间（10-45 秒）完全无感知，只能看到进度条百分比变化
- planner_node 完成后才能看到大纲，writer_node 完成后才能看到章节内容

## 优化方案

将节点内的 `llm.ainvoke()` 替换为 `llm.astream()`，通过 LangGraph 的 `astream_events` 桥接到 WebSocket，实现 token 级实时推送。

### 技术路径

#### 1. 修改 LLM 实例创建

**文件**: `app/graph/common/llm_factory.py`

在 `ChatOpenAI` 创建时启用 streaming：

```python
kwargs = {
    "model": model,
    "temperature": temperature,
    "max_tokens": max_tokens,
    "api_key": settings.llm_api_key,
    "streaming": True,  # 启用流式
}
```

#### 2. 修改节点内部调用

**文件**: `app/graph/creation/nodes.py`

以 `writer_node` 为例，将 `ainvoke` 改为 `astream`：

```python
# 改前
response = await llm.ainvoke(messages)
content = response.content

# 改后
chunks = []
async for chunk in llm.astream(messages):
    chunks.append(chunk.content)
content = "".join(chunks)
```

#### 3. 利用 LangGraph astream_events 桥接 token 流

**文件**: `app/services/creation_svc.py`

将 `graph.astream()` 改为 `graph.astream_events(version="v2")`，监听 LLM 的 `on_chat_model_stream` 事件：

```python
async for event in graph.astream_events(initial_state, config, version="v2"):
    if event["event"] == "on_chat_model_stream":
        chunk = event["data"]["chunk"].content
        await broadcaster.broadcast_token(task_id, chunk)
```

#### 4. 新增 WebSocket 消息类型

**后端**: `app/services/task_broadcaster.py` 新增 `broadcast_token` 方法

```python
async def broadcast_token(self, task_id: str, token: str) -> None:
    message = {"type": "task_token", "taskId": task_id, "token": token}
    await self._send_to_subscribers(task_id, message)
```

**前端**: `src/api/wsClient.ts` 新增 `task_token` 消息类型

```typescript
export type ServerMessageType =
  | 'task_created'
  | 'task_update'
  | 'task_token'   // 新增
  | 'task_result'
  | 'task_error'
  | 'task_status'
  | 'error'
  | 'pong'
```

#### 5. 前端流式渲染

**文件**: `src/stores/task.ts`

新增流式文本拼接逻辑：

```typescript
function handleTaskToken(message: WsMessage): void {
  const taskId = message.taskId as string
  const token = message.token as string
  if (!taskId || !currentTask.value || currentTask.value.task_id !== taskId) return

  // 拼接流式文本到临时字段
  currentTask.value = {
    ...currentTask.value,
    streaming_content: (currentTask.value.streaming_content ?? '') + token,
  }
}
```

**文件**: `src/components/common/MarkdownRenderer.vue`

支持流式渲染模式，对增量内容做 debounce 后再触发 `marked.parse()`。

## 预期收益

| 指标 | 改前 | 改后 |
|------|------|------|
| 用户首次看到内容的时间 | 30-90s（等所有节点完成） | 1-3s（首个 token 到达） |
| 感知延迟 | 高 | 极低 |
| 实际总耗时 | 不变 | 不变（仅改变体验） |

## 难度与风险

| 维度 | 评估 |
|------|------|
| 实现成本 | **高** — 涉及节点层、服务层、WebSocket 层、前端渲染层的全链路改动 |
| 风险 | 中 — `astream_events` 的事件模型较复杂，需仔细测试边界情况 |
| 前端改动 | 大 — MarkdownRenderer 需支持增量渲染，避免频繁全量重绘 |
| 联调成本 | 高 — 前后端需联调消息格式和渲染时机 |

## 实施建议

1. 先在 planner_node 上做 POC（只有一个 LLM 调用，逻辑最简单）
2. 验证 `astream_events` 的 `on_chat_model_stream` 事件能否正常工作
3. 确认 WebSocket 消息频率不会造成前端卡顿
4. 逐步推广到 writer_node 和 reducer_node
