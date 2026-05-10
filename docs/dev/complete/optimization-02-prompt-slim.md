# 优化 2：精简 Prompt 体积

## 现状分析

### Prompt 构成

WriterNode 和 ReducerNode 的 system prompt 由 `create_base_system_prompt()` 组装，包含以下模块：

| 模块 | 文件位置 | 估算字符数 | 包含节点 |
|------|----------|-----------|----------|
| `CONTENT_STRATEGIST_ROLE` | `app/graph/common/prompts.py:32-37` | ~120 | PlannerNode |
| `PROFESSIONAL_WRITER_ROLE` | `app/graph/common/prompts.py:18-23` | ~120 | WriterNode |
| `PROFESSIONAL_EDITOR_ROLE` | `app/graph/common/prompts.py:25-30` | ~120 | ReducerNode |
| 各节点 task_description | `app/graph/creation/prompts.py` | ~350-500 | 各自不同 |
| `MARKDOWN_FORMAT_RULES` | `app/graph/common/prompts.py:43-90` | ~780 | Writer/Reducer |
| `ANTI_HALLUCINATION_RULES` | `app/graph/common/prompts.py:123-151` | ~580 | Writer/Reducer |
| `QUALITY_STANDARDS` | `app/graph/common/prompts.py:153-188` | ~530 | Writer/Reducer |

### 各节点 System Prompt 总长度

| 节点 | 总字符数 | 包含的规则模块 |
|------|----------|---------------|
| PlannerNode | ~620 | 无（仅 role + task_description） |
| WriterNode | ~2360 | 全部三个 |
| ReducerNode | ~2360 | 全部三个 |

### Token 消耗估算

对于中文内容，1 个 token ≈ 1-2 个汉字。假设 system prompt 约 2360 字符 ≈ 1200-1800 token。

当 `MAX_CONCURRENT_WRITERS=5` 且大纲有 5 个章节时：
- 5 个 writer 并发，每个发送相同的 system prompt
- system prompt 部分总计消耗：5 × 1500 ≈ **7500 token**（仅输入）

## 问题分析

### 1. MARKDOWN_FORMAT_RULES 冗余度最高

当前内容详细描述了 Markdown 的每种语法（标题、粗体、斜体、列表、代码块、链接、图片、表格、分隔线）。这些是 **LLM 基础能力**，无需显式教学。

实际上，只需一句 `"使用 Markdown 格式输出"` 即可，LLM 自然会使用正确的 Markdown 语法。

### 2. ANTI_HALLUCINATION_RULES 部分冗余

"只陈述你确信正确的事实"、"不确定时标注限定词"等规则，对现代 LLM（GPT-4 级别）来说是基础行为。真正有价值的约束只有：
- "不要编造具体的数据、日期、人名"
- "代码示例必须可运行"

### 3. QUALITY_STANDARDS 过于模糊

"结构清晰"、"逻辑连贯"、"语言流畅"等标准是主观描述，对 LLM 输出质量的约束力有限。真正有效的质量控制应通过 **具体的输出格式要求** 和 **示例** 来实现。

## 优化方案

### 方案：精简三个规则模块

#### MARKDOWN_FORMAT_RULES（~780 → ~150 字符）

```python
MARKDOWN_FORMAT_RULES = """## 输出格式要求

使用 Markdown 格式输出，遵循以下规范：
- 使用 `##` 作为章节标题，`###` 作为小节标题
- 重要概念使用 **粗体** 标注
- 代码使用反引号包裹，代码块需指定语言
- 段落之间空一行"""
```

#### ANTI_HALLUCINATION_RULES（~580 → ~120 字符）

```python
ANTI_HALLUCINATION_RULES = """## 准确性约束

- 不要编造具体的数据、日期、人名、引用来源
- 不确定的信息使用"可能"、"据报道"等限定词
- 代码示例必须语法正确、可运行"""
```

#### QUALITY_STANDARDS（~530 → 删除或保留 ~80 字符）

```python
QUALITY_STANDARDS = """## 质量要求

- 每个章节 800-1500 字，段落 3-6 个
- 论点明确，论据充分，使用案例或数据支撑
- 语言自然流畅，避免过于学术化的表达"""
```

### 精简后的 Prompt 长度对比

| 节点 | 改前 | 改后 | 减少 |
|------|------|------|------|
| PlannerNode | ~620 | ~620（不变） | 0% |
| WriterNode | ~2360 | ~950 | **60%** |
| ReducerNode | ~2360 | ~950 | **60%** |

### Token 节省估算（5 章节任务）

| 项目 | 改前 | 改后 |
|------|------|------|
| 单个 writer system prompt | ~1500 token | ~600 token |
| 5 个 writer 总 system prompt | ~7500 token | ~3000 token |
| 节省 | - | **~4500 token/任务** |

## 修改涉及的文件

| 文件 | 改动内容 |
|------|----------|
| `app/graph/common/prompts.py` | 精简 `MARKDOWN_FORMAT_RULES`、`ANTI_HALLUCINATION_RULES`、`QUALITY_STANDARDS` 三个常量 |
| `app/graph/creation/prompts.py` | 无需改动（调用方参数不变） |

## 预期收益

| 指标 | 效果 |
|------|------|
| Input token 节省 | 每个 writer 减少 ~900 token，每任务减少 ~4500 token |
| API 费用 | 约减少 15-20%（输入部分） |
| 网络传输 | 减少 system prompt 传输量 |
| LLM 处理速度 | 输入越短，首 token 延迟越低 |

## 难度与风险

| 维度 | 评估 |
|------|------|
| 实现成本 | **低** — 仅修改三个文本常量 |
| 风险 | **低** — 精简的是常识性约束，对 LLM 行为影响有限 |
| 验证成本 | 中 — 需要对比精简前后的输出质量 |

## 实施建议

1. 先对 `QUALITY_STANDARDS` 做最大胆的精简（删除或保留 1 行），因为它的约束力最弱
2. 对 `MARKDOWN_FORMAT_RULES` 保留核心格式要求（标题层级、粗体、代码块）
3. 对 `ANTI_HALLUCINATION_RULES` 保留"不编造数据"和"代码可运行"两条
4. 用同一个主题分别生成两篇文章（改前/改后），人工对比质量
5. 如果质量下降可接受，则保留精简版本；否则逐条恢复关键约束
