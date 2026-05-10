# LLM 调用链性能优化方案

本目录记录 CraftFlow 后端 LLM 调用链的性能优化方案。所有方案基于代码静态分析，仅记录分析结论，不包含代码修改。

## 优化清单

### Creation Graph 优化

| 序号 | 文件 | 优化项 | 优先级 | 实现成本 | 预期收益 |
|------|------|--------|--------|----------|----------|
| 01 | [optimization-01-llm-streaming.md](optimization-01-llm-streaming.md) | LLM Streaming 替代 ainvoke | P2 | 高 | 感知延迟降 10x |
| 02 | [optimization-02-prompt-slim.md](optimization-02-prompt-slim.md) | 精简 Prompt 体积 | P1 | 低 | 省 60% 系统 prompt token |
| 03 | [optimization-03-llm-timeout-retry.md](optimization-03-llm-timeout-retry.md) | 配置 LLM 超时和重试 | P0 | 极低 | 避免 10 分钟阻塞 |
| 04 | [optimization-04-reducer-simplification.md](optimization-04-reducer-simplification.md) | ReducerNode 任务简化 | P1 | 中 | 省 85% reducer token |
| 05 | [optimization-05-writer-max-tokens.md](optimization-05-writer-max-tokens.md) | WriterNode 降低 max_tokens | P1 | 极低 | 减少过度生成 |
| 06 | [optimization-06-prompt-caching.md](optimization-06-prompt-caching.md) | Prompt Caching（附录） | P2 | 零 | 省 50-90% 重复输入费 |

### Polishing Graph 优化

| 序号 | 文件 | 优化项 | 优先级 | 实现成本 | 预期收益 |
|------|------|--------|--------|----------|----------|
| 07 | [optimization-07-llm-timeout-retry-polishing.md](optimization-07-llm-timeout-retry-polishing.md) | Polishing Graph 超时和重试 | P0 | 极低 | 避免 80 分钟阻塞 |
| 08 | [optimization-08-editor-max-tokens.md](optimization-08-editor-max-tokens.md) | EditorNode 降低 max_tokens | P1 | 极低 | 省 75% Editor 输出上限 |
| 09 | [optimization-09-formatter-factchecker-max-tokens.md](optimization-09-formatter-factchecker-max-tokens.md) | FactCheckerNode 降低 max_tokens | P1 | 极低 | 省 50% FactChecker 输出上限 |
| 10 | [optimization-10-debate-author-input-dedup.md](optimization-10-debate-author-input-dedup.md) | Debate AuthorNode 输入去重 | P1 | 中 | 语义优化 + 省 ~1,350 token/Mode3 |
| 11 | [optimization-11-editor-prompt-slim.md](optimization-11-editor-prompt-slim.md) | Editor Prompt 精简 | P2 | 低 | 省 ~1,050 token/任务 |

## 建议执行顺序

### Phase 1：全局修复（Creation + Polishing 共享）

1. **优化 03 + 07**（超时重试）：同一代码修改，全局生效，零风险

### Phase 2：Creation Graph 低成本优化

2. **优化 05**（writer max_tokens）+ **优化 02**（prompt 精简）：纯配置/文本修改
3. **优化 04**（reducer 简化）：需验证输出质量

### Phase 3：Polishing Graph 低成本优化

4. **优化 08**（editor max_tokens）+ **优化 09**（factchecker max_tokens）：纯配置修改
5. **优化 11**（editor prompt 精简）：纯文本修改，需验证评分质量

### Phase 4：Polishing Graph 中成本优化

6. **优化 10**（author 输入去重）：需验证 Debate 重写质量

### Phase 5：全链路高收益优化

7. **优化 01**（streaming）：全链路改动，建议做 POC 后再推广
8. **优化 06**（prompt caching）：取决于 API 提供商支持

## 构建流程文档

| 文件 | 说明 |
|------|------|
| [Creation Graph 构建流程的详细梳理.md](Creation%20Graph%20构建流程的详细梳理.md) | Creation Graph 启动、依赖链、图结构、节点、Prompt、生命周期 |
| [Polishing Graph 构建流程的详细梳理.md](Polishing%20Graph%20构建流程的详细梳理.md) | Polishing Graph 三档模式、Debate 子图、Agent Loop、生命周期 |

## 关联文档

- [../architecture.md](../architecture.md) — 系统架构设计
- [../api-flow.md](../api-flow.md) — API 调用流程
