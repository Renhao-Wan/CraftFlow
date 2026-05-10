# 优化 5：WriterNode 降低 max_tokens

## 现状分析

### 当前配置

**文件**: `app/graph/common/llm_factory.py`

writer_node 使用 `get_default_llm()` 获取 LLM 实例：

```python
@lru_cache
def get_default_llm() -> BaseChatModel:
    return LLMFactory.create_llm()  # 使用 settings.max_tokens = 4096
```

**文件**: `app/core/config.py`

```python
max_tokens: int = Field(default=4096, ge=1, le=128000, description="最大 Token 数")
```

### Prompt 中的长度要求

**文件**: `app/graph/creation/prompts.py` 中 `WRITER_SYSTEM_PROMPT` 的 task_description：

```
### 内容长度

- 每个章节的目标字数：800-1500 字
- 段落数量：3-6 个段落
- 确保内容充实，避免过于简略
```

### Token 换算

| 项目 | 数值 |
|------|------|
| 目标输出 | 800-1500 中文字/章节 |
| 1 个 token ≈ | 1-1.5 个中文字 |
| 800 字 ≈ | ~550-800 token |
| 1500 字 ≈ | ~1000-1500 token |
| 当前 max_tokens | 4096 |
| 实际需要 | ~1500 token |

**当前 max_tokens 是实际需要的 2.7 倍**。

### 问题

1. **过度生成** — LLM 可能生成超过 1500 字的内容（最大可达 4096 token ≈ 4000-6000 字），浪费 token 和时间
2. **不一致** — 不同章节的长度可能差异很大（有的 800 字，有的 3000 字），影响文章平衡性
3. **费用浪费** — 多生成的 token 直接增加 API 费用
4. **延迟增加** — 输出 token 越多，LLM 生成时间越长

## 优化方案

### 方案概述

为 writer_node 创建专用 LLM 实例，将 max_tokens 从 4096 降至 2048。

### 详细设计

#### 1. 新增 writer 专用 LLM 获取函数

**文件**: `app/graph/common/llm_factory.py`

```python
@lru_cache
def get_writer_llm() -> BaseChatModel:
    """获取 Writer 节点专用 LLM 实例（限制输出长度）

    Writer 节点目标输出 800-1500 字（约 500-1500 token），
    设置 max_tokens=2048 留出合理余量，避免过度生成。

    Returns:
        BaseChatModel: Writer 专用 LLM 实例
    """
    return LLMFactory.create_llm(max_tokens=2048)
```

#### 2. 修改 writer_node 使用专用实例

**文件**: `app/graph/creation/nodes.py`

```python
from app.graph.common.llm_factory import get_writer_llm  # 替换 get_default_llm

async def writer_node(state: CreationState) -> dict[str, Any]:
    # ...
    llm = get_writer_llm()  # 改为使用 writer 专用实例
    # ...
```

#### 3. （可选）在 Settings 中新增 writer_max_tokens 配置

**文件**: `app/core/config.py`

```python
writer_max_tokens: int = Field(
    default=2048, ge=512, le=8192,
    description="Writer 节点最大输出 Token 数"
)
```

这样可以通过环境变量调整，无需改代码。

### max_tokens 选择分析

| max_tokens | 约等于中文字数 | 是否足够 1500 字 | 风险 |
|------------|---------------|-----------------|------|
| 1024 | ~1000-1500 字 | 勉强 | 可能截断较长章节 |
| **2048** | **~2000-3000 字** | **充足** | **推荐** |
| 3072 | ~3000-4500 字 | 过于宽裕 | 仍可能过度生成 |
| 4096（当前） | ~4000-6000 字 | 远超需求 | 过度生成+费用浪费 |

**推荐 max_tokens=2048**：
- 覆盖 1500 字目标的 1.3-2 倍余量
- 硬性限制过度生成
- 比当前节省约 50% 的输出 token 上限

## 修改涉及的文件

| 文件 | 改动内容 |
|------|----------|
| `app/graph/common/llm_factory.py` | 新增 `get_writer_llm()` 函数 |
| `app/graph/creation/nodes.py` | writer_node 改用 `get_writer_llm()` |
| `app/core/config.py` | （可选）新增 `writer_max_tokens` 配置字段 |
| `.env.dev` | （可选）新增 `WRITER_MAX_TOKENS=2048` |

## 预期收益

| 指标 | 改前 | 改后 |
|------|------|------|
| 单个 writer 输出上限 | 4096 token | 2048 token |
| 5 个 writer 最大输出总量 | 20480 token | 10240 token |
| 章节长度一致性 | 差异可达 4x | 差异限制在 2x 以内 |
| API 费用（输出部分） | 基线 | 减少 ~50%（上限） |

### 实际节省估算

LLM 通常不会生成到 max_tokens 上限（除非 prompt 要求）。实际节省取决于 LLM 的行为：
- 如果 LLM 本就只生成 ~1200 字，则 max_tokens 降低无实际节省
- 如果 LLM 倾向于生成更多内容（如 2000+ 字），则 max_tokens=2048 会硬性截断，节省明显

## 难度与风险

| 维度 | 评估 |
|------|------|
| 实现成本 | **极低** — 新增 1 个函数 + 1 行调用改动 |
| 风险 | **低** — 2048 token 对 1500 字目标有充足余量 |
| 截断风险 | 低 — 只有当 LLM 生成超过 2048 token（~3000 字）时才会截断，而 prompt 要求 800-1500 字 |

### 潜在问题

1. **JSON 格式输出** — 如果 LLM 的输出包含 JSON 格式数据，token 消耗可能更高（JSON 的括号、引号等都是独立 token）。但 writer_node 的输出是 Markdown 文本，不存在此问题。

2. **中英文混合** — 英文单词的 token 密度更高（1 个英文单词 ≈ 1-2 token），如果章节包含大量英文代码或术语，可能需要更多 token。2048 的余量已足够覆盖。

3. **截断后的 LLM 行为** — 当 LLM 接近 max_tokens 时，有些模型会加速生成以尽快结束。这可能导致最后几句话不完整。可以在 prompt 中补充"请在接近结尾时自然收束"。

## 实施建议

1. 先将 max_tokens 设为 2048，观察日志中 LLM 实际生成的 token 数
2. 如果发现频繁触发 2048 上限（输出被截断），考虑提高到 2560 或 3072
3. 如果实际生成远低于 2048（如平均只有 800-1000 token），说明 max_tokens 不是瓶颈，优化收益有限
4. 结合 **优化 9（Token 监控）** 获取实际数据后再做精细调整
