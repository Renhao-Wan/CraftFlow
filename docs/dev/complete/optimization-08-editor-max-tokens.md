# 优化 8：EditorNode 降低 max_tokens（P1）

## 现状分析

### 当前配置

**文件**: `app/graph/common/llm_factory.py`

`editor_node` 使用 `get_editor_llm()` 获取 LLM 实例：

```python
@lru_cache
def get_editor_llm() -> BaseChatModel:
    return LLMFactory.create_llm(temperature=0.2)  # 使用 settings.max_tokens = 4096
```

### Editor 的输出结构

**文件**: `app/graph/polishing/debate/prompts.py` 中 `EDITOR_SYSTEM_PROMPT` 要求的 JSON 输出：

```json
{
  "scores": [
    {"dimension": "逻辑性", "score": 18, "comment": "..."},
    {"dimension": "可读性", "score": 16, "comment": "..."},
    {"dimension": "准确性", "score": 20, "comment": "..."},
    {"dimension": "专业性", "score": 17, "comment": "..."}
  ],
  "total_score": 71,
  "feedback": "文章整体框架尚可，但存在以下关键问题需要改进...",
  "highlights": ["亮点1"],
  "improvements": ["改进1", "改进2", "改进3"]
}
```

### Token 换算

| 项目 | 数值 |
|------|------|
| 4 个维度评分（含 comment） | ~150-250 token |
| total_score + feedback | ~50-100 token |
| highlights + improvements | ~50-100 token |
| JSON 结构符号 | ~50 token |
| **实际输出总计** | **~300-500 token** |
| 当前 max_tokens | 4096 |
| 浪费倍数 | 8-13x |

### 问题

1. **过度生成** — LLM 可能生成冗长的 feedback 或过多的 improvements，浪费 token
2. **延迟增加** — 输出 token 越多，LLM 生成时间越长。Editor 每轮都调用，延迟累积显著
3. **费用浪费** — Mode 2 的 3 轮 Debate 中，Editor 调用 3 次，累计多生成 ~10,000 token

### Editor 在不同模式下的调用次数

| 模式 | Editor 调用次数 | 当前最大输出总量 | 优化后最大输出总量 |
|------|----------------|-----------------|-------------------|
| Mode 1 | 0 次 | - | - |
| Mode 2 | 最多 3 次 | 3 × 4096 = 12,288 token | 3 × 1024 = 3,072 token |
| Mode 3（需修正） | 最多 3 次 | 3 × 4096 = 12,288 token | 3 × 1024 = 3,072 token |

## 优化方案

### 方案概述

为 Editor 节点创建专用 LLM 实例，将 max_tokens 从 4096 降至 1024。

### 详细设计

#### 1. 修改 editor LLM 获取函数

**文件**: `app/graph/common/llm_factory.py`

```python
@lru_cache
def get_editor_llm() -> BaseChatModel:
    """获取编辑节点专用 LLM 实例（低温度 + 限制输出长度）

    编辑节点输出结构化 JSON 评分（~300-500 token），
    设置 max_tokens=1024 留出合理余量，避免过度生成。

    Returns:
        BaseChatModel: 编辑专用 LLM 实例
    """
    return LLMFactory.create_llm(
        temperature=settings.editor_node_temperature,
        max_tokens=1024,
    )
```

#### 2. （可选）在 Settings 中新增 editor_max_tokens 配置

**文件**: `app/core/config.py`

```python
editor_max_tokens: int = Field(
    default=1024, ge=256, le=4096,
    description="Editor 节点最大输出 Token 数"
)
```

### max_tokens 选择分析

| max_tokens | 约等于输出量 | 是否足够 JSON 评分 | 风险 |
|------------|-------------|-------------------|------|
| 512 | ~500 token | 勉强 | feedback 较长时可能截断 |
| **1024** | **~1000 token** | **充足** | **推荐** |
| 2048 | ~2000 token | 过于宽裕 | 仍可能过度生成 |
| 4096（当前） | ~4000 token | 远超需求 | 过度生成+费用浪费 |

**推荐 max_tokens=1024**：
- 覆盖实际输出（300-500 token）的 2-3 倍余量
- feedback 字段可容纳 ~300 字的详细反馈
- improvements 列表可容纳 5-8 条建议
- 硬性限制过度生成，迫使 LLM 输出精炼的评估

### 注意事项

**输入不受限制**：此优化仅限制 Editor 的**输出** token 数。Editor 的输入（待评估的完整文章）可以任意长，不受 max_tokens 影响。即使输入文章有 10,000 字，Editor 只需输出 ~300-500 token 的 JSON 评分。

## 修改涉及的文件

| 文件 | 改动内容 |
|------|----------|
| `app/graph/common/llm_factory.py` | 修改 `get_editor_llm()` 传入 `max_tokens=1024` |
| `app/core/config.py` | （可选）新增 `editor_max_tokens` 配置字段 |
| `.env.dev` | （可选）新增 `EDITOR_MAX_TOKENS=1024` |

## 预期收益

| 指标 | 改前 | 改后 |
|------|------|------|
| 单次 Editor 输出上限 | 4096 token | 1024 token |
| Mode 2（3 轮）Editor 最大输出总量 | 12,288 token | 3,072 token |
| Editor 输出费用上限 | 基线 | 减少 ~75% |
| Editor 生成延迟 | 基线 | 减少 ~50-70%（输出 token 越少越快） |

### 实际节省估算

LLM 通常不会生成到 max_tokens 上限。实际节省取决于 LLM 行为：
- 如果 LLM 本就只生成 ~400 token 的 JSON，则 max_tokens 降低无实际节省
- 如果 LLM 倾向于生成冗长的 feedback（如 1000+ token），则 max_tokens=1024 会硬性截断，节省明显

## 难度与风险

| 维度 | 评估 |
|------|------|
| 实现成本 | **极低** — 修改 1 个函数的参数 |
| 风险 | **低** — 1024 token 对 JSON 评分有充足余量 |
| 截断风险 | 低 — 只有当 feedback 极长（>800 字）时才会截断 |

### 潜在问题

1. **feedback 过长被截断** — 如果 Editor 生成的 feedback 超过 ~800 字，JSON 可能不完整导致解析失败。可通过 prompt 中约束 feedback 长度来缓解。

2. **improvements 列表过多** — Editor 可能列出 10+ 条改进建议。1024 token 可容纳约 8 条详细建议，超出部分会被截断。可在 prompt 中限制为"最多 5 条"。

## 实施建议

1. 先将 max_tokens 设为 1024，观察日志中 Editor 实际生成的 token 数
2. 如果发现频繁触发 1024 上限（JSON 被截断），考虑提高到 1536
3. 结合 Editor Prompt 优化（优化 11），约束 feedback 和 improvements 的长度
