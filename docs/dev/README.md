# LLM 调用链性能优化方案

本目录记录 CraftFlow 后端 LLM 调用链的性能优化方案。

- ✅ 已完成的优化方案移至 [complete/](complete/) 目录
- 未完成的优化方案保留在本目录

## 优化清单

### Creation Graph 优化

| 序号 | 文件 | 优化项 | 优先级 | 状态 |
|------|------|--------|--------|------|
| 01 | [complete/optimization-01-llm-streaming.md](complete/optimization-01-llm-streaming.md) | LLM Streaming 替代 ainvoke | P2 | ✅ 已完成 |
| 02 | [complete/optimization-02-prompt-slim.md](complete/optimization-02-prompt-slim.md) | 精简 Prompt 体积 | P1 | ✅ 已完成 |
| 03 | [complete/optimization-03-llm-timeout-retry.md](complete/optimization-03-llm-timeout-retry.md) | 配置 LLM 超时和重试 | P0 | ✅ 已完成 |
| 04 | [optimization-04-reducer-simplification.md](optimization-04-reducer-simplification.md) | ReducerNode 任务简化 | P1 | 待实施 |
| 05 | [complete/optimization-05-writer-max-tokens.md](complete/optimization-05-writer-max-tokens.md) | WriterNode 降低 max_tokens | P1 | ✅ 已完成 |

### Polishing Graph 优化

| 序号 | 文件 | 优化项 | 优先级 | 状态 |
|------|------|--------|--------|------|
| 07 | [complete/optimization-07-llm-timeout-retry-polishing.md](complete/optimization-07-llm-timeout-retry-polishing.md) | Polishing Graph 超时和重试 | P0 | ✅ 已完成 |
| 08 | [complete/optimization-08-editor-max-tokens.md](complete/optimization-08-editor-max-tokens.md) | EditorNode 降低 max_tokens | P1 | ✅ 已完成 |
| 09 | [complete/optimization-09-formatter-factchecker-max-tokens.md](complete/optimization-09-formatter-factchecker-max-tokens.md) | FactCheckerNode 降低 max_tokens | P1 | ✅ 已完成 |
| 10 | [complete/optimization-10-debate-author-input-dedup.md](complete/optimization-10-debate-author-input-dedup.md) | Debate AuthorNode 输入去重 | P1 | ✅ 已完成 |
| 11 | [complete/optimization-11-editor-prompt-slim.md](complete/optimization-11-editor-prompt-slim.md) | Editor Prompt 精简 | P2 | ✅ 已完成 |

## 建议执行顺序

### Phase 1：全局修复（Creation + Polishing 共享） ✅

1. ~~**优化 03 + 07**（超时重试）~~ ✅ 已完成

### Phase 2：Creation Graph 低成本优化

2. ~~**优化 05**（writer max_tokens）~~ ✅ 已完成 + ~~**优化 02**（prompt 精简）~~ ✅ 已完成
3. **优化 04**（reducer 简化）：待实施，需验证输出质量

### Phase 3：Polishing Graph 低成本优化

4. ~~**优化 08 + 09**（editor/factchecker max_tokens）~~ ✅ 已完成
5. ~~**优化 11**（editor prompt 精简）~~ ✅ 已完成

### Phase 4：Polishing Graph 中成本优化

6. ~~**优化 10**（author 输入去重）~~ ✅ 已完成

### Phase 5：全链路高收益优化

7. ~~**优化 01**（streaming）~~ ✅ 已完成
8. **优化 06**（prompt caching）：取决于 API 提供商支持

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
