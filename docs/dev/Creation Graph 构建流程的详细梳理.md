# Creation Graph 构建流程梳理

## 1. 应用启动流程

`app/main.py` 的 `lifespan` 按顺序初始化：

```python
setup_logger()
↓
init_checkpointer()      # 根据配置创建 SQLite/Memory/PostgreSQL 持久化
↓
init_services()          # 创建 TaskStore + CreationService，并从 SQLite 加载中断任务到内存
↓
init_ws_services()       # 创建 ConnectionManager + TaskBroadcaster
```

---

## 2. 依赖链

`app/api/dependencies.py` 管理单例：

```
Checkpointer (AI 层状态持久化)
+
TaskStore (业务层数据持久化)
↓
CreationService(checkpointer, task_store)
↓
CreationService._get_graph() → 惰性编译 Creation Graph
```

---

## 3. Graph 构建细节

### 3.1 State 定义 — `state.py`

```python
class CreationState(TypedDict):
    topic: str                              # 用户主题
    description: Optional[str]              # 补充描述
    outline: list[OutlineItem]              # 大纲 [{title, summary}]
    sections: Annotated[list[SectionContent], operator.add]  # ← 关键：add reducer
    final_draft: Optional[str]              # 最终文稿
    messages: Annotated[list[BaseMessage], operator.add]  # 消息追加
    current_node: Optional[str]             # 当前执行节点
    error: Optional[str]                    # 错误信息
```

> `operator.add` 的作用：`sections` 字段配置了 add reducer，当多个并发 `WriterNode` 各自返回 `{"sections": [单章内容]}` 时，LangGraph 自动将它们合并为完整列表。这是 Map-Reduce 模式的核心机制。

---

### 3.2 图结构 — `builder.py`

```
START
↓
planner_node                # 调用 LLM 生成大纲
↓ (条件路由)
├── 有 error → END
└── 无 error → outline_confirmation (虚拟节点)
↓
interrupt_before ← HITL 中断点
↓ (用户确认后)
_fan_out_writers()          # 使用 Send API 扇出
↓
┌───────────┬───────────┬───────────┐
↓           ↓           ↓
writer_0  writer_1  writer_2  ← 并发执行
↓           ↓           ↓
└───────────┴───────────┴───────────┘
↓ (sections 自动合并)
reducer_node                # 合并润色
↓
END
```

---

### 3.3 关键路由函数

```python
def _fan_out_writers(state) -> list[Send]:
    """
    - 遍历 outline 中的每个章节
    - 为每个章节创建 Send("writer", writer_state) 对象
    - writer_state 中通过 sections 字段预填充前面章节的空壳（仅 title + index），供 writer 感知上下文
    """

def _route_after_planner(state) -> str:
    """
    - 检查 state.get("error")，有错则 END
    - 否则进入 outline_confirmation 中断点
    """

def _route_after_writing(state) -> str:
    """
    - 所有并发 writer 完成后进入 reducer
    """
```

---

### 3.4 编译配置

```python
compiled_graph = graph.compile(
    checkpointer=checkpointer,           # 注入状态持久化
    interrupt_before=["outline_confirmation"],  # HITL 中断点
)
```

---

## 4. 节点实现 — `nodes.py`

| 节点          | LLM 调用                  | 输入                          | 输出                                          |
|---------------|---------------------------|-------------------------------|-----------------------------------------------|
| `planner_node`| `get_custom_llm(max_tokens=8192)` | `topic + description`         | `{"outline": [...], "messages": [...]}`       |
| `writer_node`  | `get_default_llm()`       | 章节 `title/summary + topic`   | `{"sections": [单章], "messages": [...]}`     |
| `reducer_node`| `get_default_llm()`       | 全部 `sections + topic`        | `{"final_draft": "...", "messages": [...]}`    |

### PlannerNode 特殊处理：

- 调用 `_extract_json_from_response()` 从 LLM 响应中提取 JSON（支持直接解析、markdown 代码块、裸 JSON 对象三种格式）
- 调用 `_normalize_outline()` 标准化大纲结构（兼容 `outline` / `sections` / `title+sections` 多种变体）
- 解析失败时使用默认 4 章节大纲

---

## 5. Prompt 架构 — `prompts.py` + `common/prompts.py`

```python
create_base_system_prompt(role, task_description, ...)
├── role: PROFESSIONAL_WRITER_ROLE / PROFESSIONAL_EDITOR_ROLE / CONTENT_STRATEGIST_ROLE
├── task_description: 各节点专属任务描述
├── MARKDOWN_FORMAT_RULES (可选)
├── ANTI_HALLUCINATION_RULES (可选)
└── QUALITY_STANDARDS (可选)
```

| 节点     | 角色                     | Markdown | 防幻觉 | 质量标准 |
|----------|--------------------------|----------|--------|----------|
| Planner  | `CONTENT_STRATEGIST`     | 否       | 否     | 否       |
| Writer   | `PROFESSIONAL_WRITER`    | 是       | 是     | 是       |
| Reducer  | `PROFESSIONAL_EDITOR`    | 是       | 是     | 是       |

> Planner 的 prompt 最精简（只要 JSON 输出），Writer/Reducer 的 prompt 最完整（含格式、防幻觉、质量约束）。

---

## 6. 任务生命周期 — `creation_svc.py`

### REST 模式 (`start_task` / `resume_task`)

```python
start_task(topic, description)
→ 生成 task_id, 保存到 _tasks dict
→ graph.ainvoke(initial_state, config)
→ 正常返回 → completed → _persist_and_cleanup (SQLite + 清理 checkpoint + 释放内存)
→ GraphInterrupt → interrupted → _persist_interrupted (SQLite, 保留 checkpoint 和内存)
→ Exception → failed → _persist_and_cleanup
```

### WebSocket 流式模式 (`start_task_streaming` / `resume_task_streaming`)

```python
start_task_streaming(topic, description, broadcaster, client_id)
→ asyncio.create_task(_run())       # 后台异步执行
→ graph.astream(initial_state, config)  # 逐节点 yield
→ 每个节点完成 → broadcaster.broadcast_update()  # 实时推送
→ 检查 snapshot.tasks 判断是否有 pending interrupt
→ 完成 → broadcast_result / 中断 → broadcast_update(interrupted)
```

---

## 数据持久化策略

| 状态         | `_tasks` dict | SQLite TaskStore | Checkpointer       |
|--------------|---------------|------------------|--------------------|
| `running`    | 有            | 无               | 有                 |
| `interrupted`| 有            | 有               | 有（保留）         |
| `completed`  | 移除          | 有               | 清理               |
| `failed`     | 移除          | 有               | 清理               |

> 中断任务的 checkpoint 必须保留，因为恢复时需要图状态。

---

## 7. WebSocket 通信流程

```
前端 wsClient.sendAndWait('create_creation', {topic, description})
↓ (JSON + requestId)
后端 ws_endpoint → handle_message → _handle_create_creation
↓
asyncio.create_task(service.start_task_streaming(...))
↓ (立即返回，不阻塞 WS 连接)
service 内部通过 broadcaster 实时推送：
  task_created → task_update（多次）→ task_result / task_error
↓
前端 wsClient 通过 requestId 匹配初始响应
↓
wsClient.on('task_update') → taskStore.handleTaskUpdate()
wsClient.on('task_result') → taskStore.handleTaskResult()
```
