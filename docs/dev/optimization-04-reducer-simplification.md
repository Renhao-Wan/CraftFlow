# 优化 4：ReducerNode 输入压缩与任务简化

## 现状分析

### ReducerNode 的职责

**文件**: `app/graph/creation/nodes.py` 第 279-340 行

ReducerNode 的当前任务描述（来自 `REDUCER_SYSTEM_PROMPT`）要求 LLM 执行以下操作：

1. **顺序整合** — 按章节顺序整合内容
2. **过渡段落** — 在章节之间添加过渡段落
3. **统一风格** — 检查并统一写作风格和术语
4. **去除冗余** — 删除重复内容
5. **添加开头** — 撰写文章引言
6. **添加结尾** — 撰写文章总结

这意味着 ReducerNode 需要**阅读并可能重写全部章节内容**，然后输出一篇完整的文章。

### 输入 Token 消耗

**文件**: `app/graph/creation/nodes.py` 第 308-314 行

```python
sections_content = format_sections_for_reducer(sections)
human_message = REDUCER_HUMAN_PROMPT.format(
    topic=topic,
    sections_content=sections_content,
)
```

`format_sections_for_reducer` 将所有章节内容拼接为一个字符串，格式为：

```
### 第 0 章：章节标题

章节内容...

---

### 第 1 章：章节标题

章节内容...

---
```

假设 5 个章节各 1000 字（中文），拼接后的 `sections_content` 约 5000-6000 字符 ≈ 3000-4000 token。

### ReducerNode 的 Token 预算

| 项目 | Token 估算 |
|------|-----------|
| System prompt（含三个规则模块） | ~1500 token |
| Human message（topic + 全部章节） | ~3500 token |
| 输出（完整文章，含引言/过渡/总结） | ~3000-4000 token |
| **总计** | **~8000-9500 token** |

这是**单次 Creation 任务中 token 消耗最大的节点**。

### 问题

1. **输入过长** — ReducerNode 必须读取全部章节内容，输入 token 消耗高
2. **输出冗余** — ReducerNode 输出完整文章，但 writer 已经写好了各章节内容。Reducer 的输出中大部分是 writer 内容的复制
3. **重写风险** — Prompt 要求"统一风格"、"去除冗余"，可能导致 LLM 过度修改 writer 的原始内容，反而降低质量
4. **延迟集中** — ReducerNode 是串行执行的（在所有 writer 完成之后），其延迟直接叠加到总耗时

## 优化方案

### 方案 A：简化 Reducer 任务（推荐）

将 ReducerNode 的职责从"合并重写全文"简化为"生成引言/总结 + 过渡语句"。

#### 改后的 REDUCER_SYSTEM_PROMPT

```python
REDUCER_SYSTEM_PROMPT = create_base_system_prompt(
    role=PROFESSIONAL_EDITOR_ROLE,
    task_description="""## 任务：生成引言、过渡段和总结

你是一位资深编辑。你的任务是为一篇已有的文章补充以下内容：

1. **引言**（100-200 字）：概述文章主旨，吸引读者兴趣
2. **过渡段**（每个 1-2 句话）：在相邻章节之间添加承上启下的过渡语
3. **总结**（100-200 字）：归纳核心观点，给出未来展望

### 输出格式（严格遵守）

你必须且只能输出以下 JSON 格式：

```json
{
  "introduction": "引言内容...",
  "transitions": ["过渡语 1...", "过渡语 2...", ...],
  "conclusion": "总结内容..."
}
```

**重要**：
- transitions 数组的长度 = 章节数 - 1
- 不要修改、重写或评价各章节的内容
- 只输出 JSON，不要输出其他内容""",
    include_markdown_rules=False,
    include_anti_hallucination=False,
    include_quality_standards=False,
)
```

#### 改后的 REDUCER_HUMAN_PROMPT

```python
REDUCER_HUMAN_PROMPT = """文章主题：{topic}

章节标题列表：
{section_titles}

请为上述文章生成引言、各章节之间的过渡语、和总结。严格输出 JSON 格式。"""
```

#### 改后的 reducer_node 实现

```python
async def reducer_node(state: CreationState) -> dict[str, Any]:
    sections = state.get("sections", [])
    topic = state.get("topic", "未命名主题")

    # 只传章节标题，不传完整内容
    section_titles = "\n".join(
        f"{i+1}. {s.get('title', '未命名')}" for i, s in enumerate(sections)
    )

    llm = get_default_llm()
    human_message = REDUCER_HUMAN_PROMPT.format(
        topic=topic,
        section_titles=section_titles,
    )
    messages = [
        SystemMessage(content=REDUCER_SYSTEM_PROMPT),
        HumanMessage(content=human_message),
    ]

    response = await llm.ainvoke(messages)
    # 解析 JSON，组装最终文章
    result = json.loads(response.content)
    # 使用 transitions 和 sections 拼接完整文章
    final_draft = assemble_article(
        introduction=result["introduction"],
        sections=sections,
        transitions=result["transitions"],
        conclusion=result["conclusion"],
    )

    return {"final_draft": final_draft, ...}
```

#### 新增组装函数

```python
def assemble_article(
    introduction: str,
    sections: list[SectionContent],
    transitions: list[str],
    conclusion: str,
) -> str:
    """将引言、章节、过渡语、总结组装为完整文章"""
    parts = [f"# {sections[0].get('topic', '')}\n", introduction + "\n"]

    for i, section in enumerate(sorted(sections, key=lambda x: x["index"])):
        if i > 0 and i - 1 < len(transitions):
            parts.append(f"\n{transitions[i - 1]}\n")
        parts.append(f"\n## {section['title']}\n\n{section['content']}")

    parts.append(f"\n## 总结\n\n{conclusion}")
    return "\n".join(parts)
```

### 方案 B：删除 ReducerNode，由前端组装

将引言/总结/过渡的生成分散到其他节点或直接由前端拼接。但这会改变图结构，影响较大。

### 方案 C：ReducerNode 只生成过渡段

最简化方案 — ReducerNode 只生成章节之间的过渡语句（每个 1-2 句），引言和总结由前端或额外节点生成。

## Token 对比

| 项目 | 改前 | 改后（方案 A） |
|------|------|---------------|
| System prompt | ~1500 token | ~500 token |
| Human message | ~3500 token（全部章节内容） | ~200 token（仅标题列表） |
| 输出 | ~3000-4000 token（完整文章） | ~500 token（JSON：引言+过渡+总结） |
| **总计** | **~8000-9500 token** | **~1200 token** |
| **节省** | - | **~85%** |

## 修改涉及的文件

| 文件 | 改动内容 |
|------|----------|
| `app/graph/creation/nodes.py` | 重写 `reducer_node`，新增 `assemble_article` 函数 |
| `app/graph/creation/prompts.py` | 重写 `REDUCER_SYSTEM_PROMPT` 和 `REDUCER_HUMAN_PROMPT`，删除 `format_sections_for_reducer` |
| `app/graph/common/prompts.py` | 无需改动 |

## 预期收益

| 指标 | 效果 |
|------|------|
| ReducerNode token 消耗 | 减少 ~85% |
| ReducerNode 延迟 | 减少 ~60-70%（输入短 + 输出短） |
| API 费用 | 单次任务减少 ~20-30%（reducer 是最大消耗点） |
| 输出质量 | 需验证 — 避免了 reducer 重写导致的质量下降 |

## 难度与风险

| 维度 | 评估 |
|------|------|
| 实现成本 | **中** — 需重写 reducer_node 逻辑和 prompt |
| 风险 | **中** — 改变了文章组装方式，需验证最终输出质量 |
| JSON 解析 | 存在 LLM 输出非标准 JSON 的风险，需复用 `_extract_json_from_response` |

## 实施建议

1. 先实现方案 A，用同一主题对比改前/改后的文章质量
2. 重点关注：
   - 过渡语是否自然流畅
   - 引言/总结是否与章节内容匹配
   - 整体文章的连贯性是否下降
3. 如果质量可接受，保留方案 A
4. 如果质量下降明显，考虑折中方案：ReducerNode 读取章节摘要（而非全文），生成引言+过渡+总结后组装
