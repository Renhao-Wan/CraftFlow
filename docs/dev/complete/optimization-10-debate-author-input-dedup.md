# 优化 10：Debate AuthorNode 输入去重（P1）

## 现状分析

### AuthorNode 的输入构成

**文件**: `app/graph/polishing/debate/nodes.py` 第 72-138 行

```python
async def author_node(state: DebateState) -> dict[str, Any]:
    content = state.get("content", "")              # 原始文章
    editor_feedback = state.get("editor_feedback", "")  # 编辑反馈
    editor_score = state.get("editor_score", 0)      # 当前评分
    fact_check_result = state.get("fact_check_result", "")  # 事实核查报告

    human_message = AUTHOR_HUMAN_PROMPT.format(
        content=content,
        editor_feedback=editor_feedback,
        editor_score=editor_score,
        fact_check_context=fact_check_context,
    )
```

**文件**: `app/graph/polishing/debate/prompts.py` 第 56-68 行

```python
AUTHOR_HUMAN_PROMPT = """请根据以下反馈对文章进行深度重写：

**原始内容**：
{content}

**编辑反馈**：
{editor_feedback}

**当前评分**：{editor_score}/100

{fact_check_context}

请输出重写后的完整文章（Markdown 格式）。注意：你输出的必须是完整的文章，不是修改建议。"""
```

### 输入 Token 逐轮增长分析

以 Mode 2（专家对抗审查，3 轮 Debate）为例，假设原始文章 3000 字（约 2000 token）：

| 轮次 | content | editor_feedback | fact_check_context | 合计输入 |
|------|---------|----------------|-------------------|---------|
| 第 1 轮 | ~2000 token | ~150 token（默认首轮指令） | 0 | ~2150 token |
| 第 2 轮 | ~2000 token | ~600 token（第 1 轮反馈） | 0 | ~2600 token |
| 第 3 轮 | ~2000 token | ~1200 token（前 2 轮反馈累积） | 0 | ~3200 token |

以 Mode 3（事实核查+修正，3 轮 Debate）为例，假设原始文章 3000 字 + 核查报告 500 token：

| 轮次 | content | editor_feedback | fact_check_context | 合计输入 |
|------|---------|----------------|-------------------|---------|
| 第 1 轮 | ~2000 token | ~150 token | ~500 token | ~2650 token |
| 第 2 轮 | ~2000 token | ~600 token | ~500 token | ~3100 token |
| 第 3 轮 | ~2000 token | ~1200 token | ~500 token | ~3700 token |

### 问题

1. **content 重复传递** — 第 2、3 轮的 Author 调用中，`content`（原始文章）每轮都完整传递，但 Editor 的反馈已经具体指出了问题位置（如"第二段与第三段之间缺少过渡"）。Author 真正需要的是上一轮的重写结果，而非原始文章。

2. **fact_check_context 重复传递** — Mode 3 中，事实核查报告在每轮都完整传递。核查报告的内容不会随 Debate 轮次变化，属于静态上下文。

3. **editor_feedback 累积增长** — Editor 的反馈随轮次累积，第 3 轮的 feedback 包含前 2 轮的所有反馈。这有一定合理性（Author 需要看到历史反馈以检查改进落实），但也导致输入膨胀。

4. **输入逐轮增长 ~50%** — 第 3 轮的输入是第 1 轮的 1.5 倍（Mode 2）或 1.4 倍（Mode 3），费用递增。

## 优化方案

### 方案 A：传递上一轮重写结果替代原始文章（推荐）

将第 2 轮起的 `content` 从原始文章改为上一轮的 `author_output`（重写后的文章）。

#### 修改后的 AUTHOR_HUMAN_PROMPT

```python
AUTHOR_HUMAN_PROMPT = """请根据以下反馈对文章进行深度重写：

**待改进文章**：
{content}

**编辑反馈**：
{editor_feedback}

**当前评分**：{editor_score}/100

{fact_check_context}

请输出重写后的完整文章（Markdown 格式）。注意：你输出的必须是完整的文章，不是修改建议。"""
```

#### 修改后的 author_node

```python
async def author_node(state: DebateState) -> dict[str, Any]:
    editor_feedback = state.get("editor_feedback", "")
    editor_score = state.get("editor_score", 0)
    fact_check_result = state.get("fact_check_result", "")

    # 第 1 轮：使用原始 content
    # 第 2+ 轮：使用上一轮的 author_output（重写后的文章）
    content = state.get("author_output") or state.get("content", "")

    # ...
```

**Token 分析**：

| 轮次 | content（改后） | editor_feedback | 合计 | 节省 |
|------|----------------|----------------|------|------|
| 第 1 轮 | ~2000 token（原始） | ~150 token | ~2150 | 0 |
| 第 2 轮 | ~2000 token（第 1 轮重写） | ~600 token | ~2600 | 0 |
| 第 3 轮 | ~2000 token（第 2 轮重写） | ~1200 token | ~3200 | 0 |

**分析**：此方案的 token 节省有限，因为重写后的文章长度与原始文章相近。但**语义更准确** — Author 第 2 轮应该基于自己的上一轮输出来改进，而非回到原始文章重新开始。

**收益**：主要是语义优化，减少 Author 的困惑（不需要在原始文章和编辑反馈之间来回对照）。

### 方案 B：editor_feedback 只传最近一轮（激进）

将 editor_feedback 从"累积全部反馈"改为"只传最近一轮反馈"。

```python
# 当前：累积全部反馈
editor_feedback = state.get("editor_feedback", "")  # 包含前 N 轮所有反馈

# 优化后：只传最近一轮
# 需要修改 DebateState，新增 last_editor_feedback 字段
editor_feedback = state.get("last_editor_feedback", "")
```

**Token 分析**：

| 轮次 | editor_feedback（改后） | 节省 |
|------|------------------------|------|
| 第 1 轮 | ~150 token | 0 |
| 第 2 轮 | ~400 token（仅第 1 轮反馈） | ~200 token |
| 第 3 轮 | ~400 token（仅第 2 轮反馈） | ~800 token |

**风险**：Author 看不到历史反馈，无法检查"上一轮指出的问题是否已解决"。Editor Prompt 中明确要求"下一轮必须逐条检查落实"，如果 Author 看不到历史反馈，这个要求无法满足。

**不推荐此方案** — 会破坏 Debate 的改进追踪机制。

### 方案 C：fact_check_context 只传摘要（Mode 3）

将事实核查报告从完整文本改为摘要版本。

```python
# 当前：完整核查报告
fact_check_context = f"**事实核查报告**（请优先修正报告中标注的问题）：\n{fact_check_result}"

# 优化后：只传 issues 列表，省去 verified_facts 和 summary
fact_check_context = f"**核查发现的问题**（请优先修正）：\n{issues_only}"
```

**Token 分析**：

| 项目 | 完整报告 | 摘要版本 | 节省 |
|------|---------|---------|------|
| overall_accuracy | ~10 token | - | 10 |
| issues（3-5 个） | ~200-400 token | ~200-400 token | 0 |
| verified_facts | ~50-100 token | - | 50-100 |
| summary | ~50-100 token | - | 50-100 |
| **合计** | ~310-610 token | ~200-400 token | ~110-210 token |

每轮节省 ~150 token，3 轮累计节省 ~450 token。

**风险**：低。Author 只需要知道"哪些地方有问题"来修正，不需要知道"哪些地方已验证正确"。

## 推荐方案

**方案 A + 方案 C 组合**：
1. 第 2 轮起，content 改为上一轮 author_output（语义优化）
2. fact_check_context 只传 issues 列表（token 节省）

## 修改涉及的文件

| 文件 | 改动内容 |
|------|----------|
| `app/graph/polishing/debate/nodes.py` | 修改 `author_node` 的 content 来源逻辑 |
| `app/graph/polishing/debate/prompts.py` | 修改 `AUTHOR_HUMAN_PROMPT` 模板变量 |

## 预期收益

| 指标 | 改前 | 改后 |
|------|------|------|
| 第 2-3 轮 Author 输入 | 每轮含完整原始文章 + 完整核查报告 | 上一轮重写结果 + issues 摘要 |
| Mode 2 三轮 Author 累计输入 | ~7,950 token | ~7,950 token（主要节省在语义优化） |
| Mode 3 三轮 Author 累计输入 | ~9,450 token | ~8,100 token（节省 ~1,350 token） |
| 语义准确性 | Author 每轮从原始文章重新开始 | Author 基于自己的上一轮输出改进 |

## 难度与风险

| 维度 | 评估 |
|------|------|
| 实现成本 | **中** — 需修改 author_node 逻辑和 prompt 模板 |
| 风险 | **中** — 改变了 Author 的输入语义，需验证重写质量 |
| 方案 A 风险 | 低 — 语义更合理，Author 基于自己的输出改进 |
| 方案 C 风险 | 低 — Author 不需要 verified_facts 信息 |

## 实施建议

1. 先实施方案 A（content 改为上一轮 author_output），用同一主题对比改前/改后的重写质量
2. 重点关注：
   - Author 是否能正确理解"这是上一轮自己的输出"
   - Editor 反馈中的具体问题定位是否仍然有效
   - 整体 Debate 质量是否提升或保持
3. 确认方案 A 无问题后，再实施方案 C（fact_check_context 精简）
