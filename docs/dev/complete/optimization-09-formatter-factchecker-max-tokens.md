# 优化 9：FormatterNode / FactCheckerNode 降低 max_tokens（P1）

## 概述

FormatterNode 和 FactCheckerNode 的输出都有明确的结构和长度预期，但当前统一使用 max_tokens=4096，存在过度生成的浪费。

## 现状分析

### FormatterNode

**文件**: `app/graph/polishing/nodes.py` 第 172-215 行

```python
async def formatter_node(state: PolishingState) -> dict[str, Any]:
    llm = get_default_llm()  # max_tokens=4096
    response = await llm.ainvoke(messages)
    formatted_content = response.content
    return {"formatted_content": formatted_content, "final_content": formatted_content, ...}
```

Formatter 的任务是**保持原文内容不变，仅调整 Markdown 格式**。输出长度应与输入长度基本一致。

**Token 分析**：

| 项目 | 数值 |
|------|------|
| 输入（待格式化文章） | 任意长度（取决于用户提交） |
| 输出（格式化后文章） | ≈ 输入长度（仅格式调整，不增删内容） |
| 当前 max_tokens | 4096 |

**问题**：如果输入文章超过 4096 token（约 4000-6000 中文字），Formatter 的输出会被截断。但实际上，Formatter 不需要额外的 token 预算 — 它只是重新排版，输出量约等于输入量。

**关键点**：Formatter 的 max_tokens 应基于输入文章的长度来设置，而非固定值。对于长文章（如 8000+ 字），4096 token 的 max_tokens 反而**不够用**。

### FactCheckerNode

**文件**: `app/graph/polishing/nodes.py` 第 226-372 行

FactChecker 的最终响应是 JSON 格式的核查报告：

```json
{
  "overall_accuracy": "high/medium/low",
  "issues": [
    {
      "type": "data/time/reference/technical/logic",
      "location": "问题所在段落或句子",
      "description": "问题描述",
      "suggestion": "修改建议"
    }
  ],
  "verified_facts": ["已验证的事实列表"],
  "summary": "核查总结"
}
```

**Token 分析**：

| 项目 | 数值 |
|------|------|
| overall_accuracy + summary | ~50-100 token |
| issues（每个 ~50-80 token） | ~150-400 token（3-5 个问题） |
| verified_facts | ~50-100 token |
| JSON 结构符号 | ~50 token |
| **实际输出总计** | **~300-650 token** |
| 当前 max_tokens | 4096 |
| 浪费倍数 | 6-13x |

**注意**：FactChecker 的 Agent Loop 过程中，LLM 调用（中间轮次）可能输出 tool_calls 而非文本，这些不消耗 max_tokens 的文本预算。只有最终的文本响应（核查报告 JSON）受 max_tokens 限制。

## 优化方案

### FormatterNode：保持 max_tokens=4096 或适当提高

**建议**：FormatterNode **不降低 max_tokens**，反而应确保 max_tokens 足够覆盖输入文章的长度。

理由：
1. Formatter 的输出长度 ≈ 输入长度，不能人为截断
2. 用户提交的文章可能很长（5000-10000+ 字），需要足够的输出空间
3. 如果要优化，应根据输入长度动态设置 max_tokens，而非固定降低

**可选优化**：在 `formatter_node` 中根据输入长度动态设置 max_tokens：

```python
# 估算输入 token 数（粗略：1 中文字 ≈ 1-1.5 token）
input_tokens = len(content) // 1.5
# 输出上限 = 输入长度 × 1.2（留出格式调整余量）
dynamic_max_tokens = max(2048, int(input_tokens * 1.2))
llm = get_custom_llm(max_tokens=min(dynamic_max_tokens, 8192))
```

但这增加了复杂度，收益有限。**建议暂不修改 Formatter 的 max_tokens**。

### FactCheckerNode：降低最终响应的 max_tokens

**方案**：为 FactChecker 的最终响应（核查报告 JSON）设置较低的 max_tokens。

但 FactChecker 使用 Agent Loop，中间轮次和最终轮次共用同一个 LLM 实例。如果降低 max_tokens，中间轮次的 tool_calls 也可能受影响。

**折中方案**：在 Agent Loop 的最后一轮（获取最终文本响应时）使用独立的 LLM 调用：

```python
# Agent Loop 中间轮次：使用默认 max_tokens（可能输出 tool_calls）
for round_num in range(MAX_TOOL_ROUNDS + 1):
    response = await llm_with_tools.ainvoke(messages)
    if not response.tool_calls:
        break
    # ... 执行工具 ...

# 达到最大轮次时的最终响应：使用较低 max_tokens
if round_num >= MAX_TOOL_ROUNDS:
    final_llm = get_custom_llm(max_tokens=2048)
    final_response = await final_llm.ainvoke(messages)
```

但这增加了代码复杂度，且 Agent Loop 中间轮次的 LLM 输出通常是 tool_calls（不受 max_tokens 文本限制影响），降低 max_tokens 对中间轮次无实际影响。

**最终建议**：将 FactChecker 的整体 max_tokens 从 4096 降至 2048。这个值：
- 足够覆盖核查报告 JSON（~300-650 token）的 3-6 倍余量
- 足够覆盖 Agent Loop 中间轮次的 tool_calls 输出
- 对于特别长的核查报告（如 10+ 个 issues），2048 token 可容纳约 15 个问题的详细描述

## 修改涉及的文件

| 文件 | 改动内容 |
|------|----------|
| `app/graph/polishing/nodes.py` | fact_checker_node 中使用专用 LLM（max_tokens=2048） |
| `app/graph/common/llm_factory.py` | 新增 `get_factchecker_llm()` 函数（可选） |

## 预期收益

| 节点 | 改前 max_tokens | 改后 max_tokens | 节省 |
|------|----------------|----------------|------|
| formatter | 4096 | 4096（不改） | 0 |
| fact_checker | 4096 | 2048 | ~50% 输出上限 |

Mode 3 单次任务节省：fact_checker 的 1 次最终响应节省 ~2000 token 上限。

## 难度与风险

| 维度 | 评估 |
|------|------|
| 实现成本 | **极低** — 新增 1 个 LLM 获取函数或传入参数 |
| 风险 | **低** — 2048 token 对核查报告有充足余量 |
| Formatter 风险 | **无** — 不修改 Formatter 的配置 |

### 潜在问题

1. **长文章的核查报告** — 如果文章包含大量事实性内容（如技术文档），issues 列表可能很长。2048 token 可容纳约 15 个问题的详细描述，通常足够。
2. **Agent Loop 中间轮次** — 降低 max_tokens 不影响中间轮次的 tool_calls 输出（tool_calls 是结构化数据，不计入 max_tokens 文本预算）。

## 实施建议

1. 优先实施 FactChecker 的 max_tokens 降低（2048）
2. Formatter 暂不修改 — 长文章需要足够的输出空间
3. 观察日志中 FactChecker 最终响应的实际 token 数，如果频繁触发 2048 上限，考虑提高到 2560
