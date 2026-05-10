# Polishing Graph 构建流程梳理

## 1. 应用启动流程

`app/main.py` 的 `lifespan` 按顺序初始化：

```python
setup_logger()
↓
init_checkpointer()      # 根据配置创建 SQLite/Memory/PostgreSQL 持久化
↓
init_services()          # 创建 TaskStore + CreationService + PolishingService，并从 SQLite 加载中断任务到内存
↓
init_ws_services()       # 创建 ConnectionManager + TaskBroadcaster
```

> PolishingService 与 CreationService 在 `init_services()` 中一同创建，共享同一个 Checkpointer 和 TaskStore 实例。

---

## 2. 依赖链

`app/api/dependencies.py` 管理单例：

```
Checkpointer (AI 层状态持久化)
+
TaskStore (业务层数据持久化)
↓
PolishingService(checkpointer, task_store)
↓
PolishingService._get_graph() → 惰性编译 Polishing Graph
```

---

## 3. Graph 构建细节

### 3.1 State 定义 — `state.py`

```python
class ScoreDetail(TypedDict):
    dimension: str
    score: float
    comment: str

class DebateRound(TypedDict):
    round_number: int
    author_content: str
    editor_feedback: str
    editor_score: float

class PolishingState(TypedDict):
    # 输入字段
    content: str                              # 待润色文章
    mode: Literal[1, 2, 3]                    # 润色模式

    # 流程控制
    current_node: Optional[str]
    error: Optional[str]
    needs_revision: bool                      # Mode 3: 核查发现问题后需要进入修正流程

    # 中间结果
    formatted_content: Optional[str]          # Mode 1: 格式化结果
    fact_check_result: Optional[str]          # Mode 3: 事实核查报告
    debate_history: list[DebateRound]         # Mode 2/3: 对抗轮次记录

    # 最终输出
    final_content: Optional[str]              # 最终润色结果
    scores: list[ScoreDetail]                 # 评分详情
    overall_score: Optional[float]            # 综合评分

    # 消息流
    messages: Annotated[list[BaseMessage], operator.add]  # ← add reducer

    # 内部标识（用于进度回调，不参与图逻辑）
    task_id: Optional[str]
```

> 与 CreationState 的关键差异：PolishingState 没有 `operator.add` reducer 的 `sections` 字段（无 Map-Reduce），`debate_history` 是普通 list 而非 add reducer（由 debate_node 整体赋值）。`messages` 字段同样使用 `operator.add` 实现消息追加。

---

### 3.2 Debate 子图 State 定义 — `debate/state.py`

```python
class DebateState(TypedDict):
    # 输入字段
    content: str                              # 待润色文章
    topic: Optional[str]                      # 主题（可选）
    fact_check_result: Optional[str]          # Mode 3: 事实核查报告

    # 对抗循环控制
    current_iteration: int                    # 当前轮次
    max_iterations: int                       # 最大迭代次数（默认 3）
    pass_score: float                         # 通过分数（默认 90）

    # 当前轮次内容
    author_output: Optional[str]              # Author 重写结果
    editor_feedback: Optional[str]            # Editor 反馈
    editor_score: float                       # Editor 评分

    # 历史记录
    debate_history: Annotated[list[DebateRound], operator.add]  # ← add reducer

    # 最终结果
    final_content: Optional[str]
    is_passed: bool                           # 是否通过评分

    # 消息流
    messages: Annotated[list[BaseMessage], operator.add]

    # 错误处理
    error: Optional[str]
```

> DebateState 的 `debate_history` 使用 `operator.add` reducer，每轮 Editor 返回 `[debate_round]` 时自动追加到列表。主图的 `PolishingState.debate_history` 是普通 list，由 `debate_node` 包装节点整体赋值。

---

### 3.3 图结构 — `builder.py`

**主图结构**：

```
START
↓
router_node                 # 路由决策：根据 mode 分发
↓ (条件路由: route_by_mode)
├── mode=1 → formatter_node        # 极速格式化
├── mode=2 → debate_node           # 专家对抗审查（Debate 子图）
└── mode=3 → fact_checker_node     # 事实核查
                                    ↓ (条件路由: route_after_fact_check)
                                    ├── needs_revision=True  → debate_node
                                    └── needs_revision=False → END

formatter_node → END
debate_node → END
```

**Debate 子图结构**：

```
START
↓
author_node                 # 根据编辑反馈重写文章
↓
editor_node                 # 多维度评估打分
↓
increment_iteration_node    # 递增迭代计数器
↓ (条件路由: should_continue_debate)
├── is_passed=True 或 current_iteration >= max_iterations → finalize_debate_node → END
└── 否则 → author_node（继续下一轮）
```

---

### 3.4 关键路由函数

```python
# 主图路由
def route_by_mode(state) -> str:
    """
    - mode=1 → "formatter"
    - mode=2 → "author"（映射到 debate_node）
    - mode=3 → "fact_checker"
    - 默认 → "author"
    """

def route_after_fact_check(state) -> str:
    """
    - needs_revision=True  → "debate"（进入修正流程）
    - needs_revision=False → "end"（核查通过，直接结束）
    """

# 子图路由
def should_continue_debate(state) -> str:
    """
    - is_passed=True → "end"（评分达标）
    - current_iteration >= max_iterations → "end"（达到最大轮次）
    - 否则 → "author"（继续下一轮）
    """
```

---

### 3.5 Debate 包装节点 — `builder.py`

`debate_node` 是主图与子图的桥梁，负责双向状态映射：

```python
async def debate_node(state: PolishingState) -> dict:
    # 1. PolishingState → DebateState 映射
    debate_input: DebateState = {
        "content": state["content"],
        "fact_check_result": state.get("fact_check_result"),  # Mode 3 核查报告
        "current_iteration": 0,
        "max_iterations": 3,
        "pass_score": 90,
        "debate_history": [],
        "messages": [],
        ...
    }

    # 2. 调用编译后的 Debate 子图
    result = await get_debate_graph().ainvoke(debate_input)

    # 3. DebateState → PolishingState 映射（提取新增消息避免重复累加）
    new_messages = result["messages"][messages_before:]
    return {
        "final_content": result["final_content"],
        "debate_history": result["debate_history"],
        "overall_score": result["editor_score"],
        "messages": new_messages,
    }
```

---

### 3.6 编译配置

```python
# 主图编译（无 HITL 中断）
compiled_graph = graph.compile(checkpointer=checkpointer)

# 子图编译（单例缓存）
@lru_cache(maxsize=1)
def get_debate_graph():
    graph = _build_debate_graph()
    return graph.compile()  # 无 checkpointer
```

> 与 Creation Graph 的关键差异：Polishing Graph 没有 `interrupt_before`（无 HITL 中断点），全链路自动执行。Debate 子图不注入 Checkpointer，状态由主图的 `debate_node` 包装节点管理。

---

## 4. 节点实现

### 4.1 主图节点 — `nodes.py`

| 节点                | LLM 调用                  | 输入                           | 输出                                                    |
|---------------------|---------------------------|--------------------------------|---------------------------------------------------------|
| `router_node`       | `get_default_llm()`       | `content`（截取前 2000 字符）  | `{"mode": N, "messages": [...]}`                        |
| `formatter_node`    | `get_default_llm()`       | `content`                      | `{"formatted_content": "...", "final_content": "...", "messages": [...]}` |
| `fact_checker_node` | `get_default_llm()` + `bind_tools(SEARCH_TOOLS)` | `content` | `{"fact_check_result": "...", "needs_revision": bool, "messages": [...]}` |

### 4.2 Debate 子图节点 — `debate/nodes.py`

| 节点                       | LLM 调用              | 输入                                              | 输出                                                       |
|----------------------------|-----------------------|---------------------------------------------------|------------------------------------------------------------|
| `author_node`              | `get_default_llm()`   | `content + editor_feedback + editor_score + fact_check_result` | `{"author_output": "...", "messages": [...]}`              |
| `editor_node`              | `get_editor_llm()`    | `author_output + iteration`                       | `{"editor_feedback": "...", "editor_score": N, "debate_history": [...], "is_passed": bool, "messages": [...]}` |
| `increment_iteration_node` | 无 LLM 调用           | `current_iteration`                               | `{"current_iteration": N+1, "messages": [...]}`            |
| `finalize_debate_node`     | 无 LLM 调用           | `author_output + is_passed + editor_score`        | `{"final_content": "...", "messages": [...]}`              |

### 4.3 FactCheckerNode Agent Loop

`fact_checker_node` 实现了完整的 Agent Loop，是唯一使用外部工具的节点：

```
LLM 调用（bind_tools）
↓
有 tool_calls?
├── 是 → 执行工具（30s 超时）→ ToolMessage 喂回 LLM → 重复（最多 3 轮）
└── 否 → 最终响应 → 解析 JSON → 判断 needs_revision
```

- 最多 `MAX_TOOL_ROUNDS = 3` 轮工具调用
- 每次工具执行有 30 秒超时（`asyncio.wait_for`）
- 工具来源：`SEARCH_TOOLS`（Tavily 搜索工具）
- 最终判断：`overall_accuracy == "high"` → `needs_revision = False`，否则 `True`

### 4.4 RouterNode 特殊处理：

- 如果用户已指定 `mode`（1/2/3），直接使用，**不调用 LLM**
- 仅当 mode 未指定时才调用 LLM 分析推荐
- 解析失败时默认使用 mode=2（专家对抗审查）

---

## 5. Prompt 架构 — `prompts.py` + `debate/prompts.py` + `common/prompts.py`

```python
create_base_system_prompt(role, task_description, ...)
├── role: PROFESSIONAL_WRITER_ROLE / PROFESSIONAL_EDITOR_ROLE
├── task_description: 各节点专属任务描述
├── MARKDOWN_FORMAT_RULES (可选)
├── ANTI_HALLUCINATION_RULES (可选)
├── QUALITY_STANDARDS (可选)
└── SEARCH_TOOL_USAGE_INSTRUCTION (可选，仅 FactChecker)
```

### 主图节点 Prompt 配置

| 节点            | 角色                  | Markdown | 防幻觉 | 质量标准 | 搜索工具指令 |
|-----------------|-----------------------|----------|--------|----------|-------------|
| Router          | 无（独立 Prompt）      | 否       | 否     | 否       | 否          |
| Formatter       | `PROFESSIONAL_WRITER` | 是       | 否     | 否       | 否          |
| FactChecker     | `PROFESSIONAL_EDITOR` | 否       | 是     | 否       | 是          |

### Debate 子图节点 Prompt 配置

| 节点   | 角色                  | Markdown | 防幻觉 | 质量标准 |
|--------|-----------------------|----------|--------|----------|
| Author | `PROFESSIONAL_WRITER` | 是       | 否     | 是       |
| Editor | 无（独立 Prompt）      | 否       | 否     | 否       |

> Editor 的 Prompt 独立于 `create_base_system_prompt` 体系，直接定义为完整的系统消息，包含严格的评分纪律（首轮不超过 80 分、四维度各 25 分、逐条检查改进落实）。

---

## 6. 任务生命周期 — `polishing_svc.py`

### REST 模式 (`start_task`)

```python
start_task(content, mode)
→ 生成 task_id, 保存到 _tasks dict
→ graph.ainvoke(initial_state, config)
→ 正常返回 → completed → _persist_and_cleanup (SQLite + 清理 checkpoint + 释放内存)
→ Exception → failed → _persist_and_cleanup
```

> Polishing Graph 无 HITL 中断，不存在 `interrupted` 状态。

### WebSocket 流式模式 (`start_task_streaming`)

```python
start_task_streaming(content, mode, broadcaster, client_id)
→ asyncio.create_task(_run())                  # 后台异步执行
→ register_progress_callback(task_id, cb)      # 注册进度回调
→ graph.astream_events(initial_state, config)  # 监听节点完成事件
→ 每个节点完成 → broadcaster.broadcast_update()  # 实时推送
→ 完成 → broadcast_result / 异常 → broadcast_error
→ unregister_progress_callback(task_id)        # 注销回调
```

> 与 CreationService 的差异：PolishingService 使用 `astream_events`（而非 `astream`），因为需要监听更细粒度的事件（如 Debate 子图内部的 author/editor 轮次）。同时注册进度回调让 `fact_checker_node` 能推送 Agent Loop 的中间进度。

---

## 数据持久化策略

| 状态        | `_tasks` dict | SQLite TaskStore | Checkpointer       |
|-------------|---------------|------------------|--------------------|
| `running`   | 有            | 无               | 有                 |
| `completed` | 移除          | 有               | 清理               |
| `failed`    | 移除          | 有               | 清理               |

> Polishing Graph 没有 `interrupted` 状态（无 HITL），所有任务要么完成要么失败。

---

## 7. 三档模式执行路径

### Mode 1：极速格式化

```
router（不调用 LLM，直接使用 mode=1）
→ formatter（1 次 LLM 调用）
→ END
```

- LLM 调用次数：**1 次**
- Token 消耗：最少（仅格式化指令 + 文章内容）

### Mode 2：专家对抗审查

```
router（不调用 LLM，直接使用 mode=2）
→ debate_node（包装节点）
    → author（1 次 LLM）→ editor（1 次 LLM）→ increment_iteration → should_continue
    → author（1 次 LLM）→ editor（1 次 LLM）→ increment_iteration → should_continue
    → author（1 次 LLM）→ editor（1 次 LLM）→ increment_iteration → should_continue
    → finalize
→ END
```

- LLM 调用次数：**最多 6 次**（3 轮 × 2 节点）
- 终止条件：`editor_score >= 90` 或 `current_iteration >= 3`

### Mode 3：事实核查

```
router（不调用 LLM，直接使用 mode=3）
→ fact_checker（1 次 LLM + 最多 3 轮工具调用）
→ needs_revision?
    ├── True  → debate_node（同 Mode 2，最多 6 次 LLM）
    └── False → END
```

- LLM 调用次数：**最多 8 次**（fact_checker 1+3 次 + debate 最多 6 次）+ 工具调用最多 3 次
- 这是 token 消耗和延迟最高的路径

---

## 8. WebSocket 通信流程

```
前端 wsClient.sendAndWait('create_polishing', {content, mode})
↓ (JSON + requestId)
后端 ws_endpoint → handle_message → _handle_create_polishing
↓
asyncio.create_task(service.start_task_streaming(...))
↓ (立即返回，不阻塞 WS 连接)
service 内部通过 broadcaster 实时推送：
  task_created → task_update（多次，含 debate 轮次进度）→ task_result / task_error
↓
前端 wsClient 通过 requestId 匹配初始响应
↓
wsClient.on('task_update') → taskStore.handleTaskUpdate()
wsClient.on('task_result') → taskStore.handleTaskResult()
```

> 与 Creation Graph 的差异：Polishing 的 `task_update` 推送更频繁，尤其是 Mode 2/3 的 Debate 子图每轮 author/editor 完成都会推送一次进度更新。
