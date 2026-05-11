# 优化 7：Polishing Graph LLM 请求超时和重试配置（P0）

## 概述

此优化与 Creation Graph 的 [optimization-03-llm-timeout-retry.md](optimization-03-llm-timeout-retry.md) 共享同一修复。Polishing Graph 无 HITL 中断，全链路自动执行，超时问题的影响更为严重。

## 现状分析

### 当前配置

**文件**: `app/graph/common/llm_factory.py` 第 104-109 行

```python
kwargs = {
    "model": model,
    "temperature": temperature,
    "max_tokens": max_tokens,
    "api_key": settings.llm_api_key,
}
return ChatOpenAI(**kwargs)
```

缺失 `request_timeout` 和 `max_retries`，使用 LangChain 默认值（超时 600s，重试 2 次）。

### 对 Polishing Graph 的影响

Polishing Graph 没有 HITL 中断点，任务创建后直接执行至完成。这意味着用户提交任务后，只能等待整个流程结束，无法中途干预。

| 模式 | 最大 LLM 调用次数 | 最坏情况阻塞时间（当前） | 最坏情况阻塞时间（优化后） |
|------|-------------------|------------------------|--------------------------|
| Mode 1 | 1 次 | 10 分钟 | 60s + 重试 |
| Mode 2 | 6 次 | 60 分钟 | 3-5 分钟 |
| Mode 3 | 8 次 LLM + 3 次工具 | 80 分钟 + 工具超时 | 5-8 分钟 |

### 与 Creation Graph 的对比

| 维度 | Creation Graph | Polishing Graph |
|------|---------------|-----------------|
| HITL 中断 | 有（大纲确认） | 无 |
| 用户感知 | 中断时可等待/离开 | 提交后只能等结果 |
| 最大 LLM 调用 | 3 次（planner+writer+reducer） | 最多 8 次（Mode 3） |
| 阻塞影响 | 单节点阻塞 10 分钟 | 全链路累积阻塞 80 分钟 |

## 优化方案

### 方案概述

与 Creation Graph 优化 3 完全相同的修改 — 在 `Settings` 中新增超时/重试配置，在 `LLMFactory` 创建时传入。

### 详细设计

#### 1. 新增配置字段

**文件**: `app/core/config.py`

```python
class Settings(BaseSettings):
    # 现有字段...
    llm_request_timeout: int = Field(
        default=60, ge=10, le=300,
        description="LLM 请求超时时间（秒）"
    )
    llm_max_retries: int = Field(
        default=3, ge=0, le=10,
        description="LLM 请求失败重试次数"
    )
```

#### 2. 修改 LLM 工厂

**文件**: `app/graph/common/llm_factory.py`

```python
kwargs = {
    "model": model,
    "temperature": temperature,
    "max_tokens": max_tokens,
    "api_key": settings.llm_api_key,
    "request_timeout": settings.llm_request_timeout,  # 新增
    "max_retries": settings.llm_max_retries,           # 新增
}
```

#### 3. 环境变量配置

**文件**: `.env.dev`

```bash
LLM_REQUEST_TIMEOUT=60
LLM_MAX_RETRIES=3
```

### Polishing Graph 特殊考虑

#### FactChecker 的工具调用超时

`fact_checker_node` 中工具调用已有独立的 30 秒超时（`asyncio.wait_for(timeout=30)`），不受 LLM 超时配置影响。这是正确的 — 搜索工具的超时应独立于 LLM 超时。

#### 不同模式的合理超时

| 模式 | 节点 | 建议超时 | 理由 |
|------|------|---------|------|
| Mode 1 | formatter | 60-90s | 全文重排，输出较长 |
| Mode 2 | author | 60-90s | 全文重写，输出最长 |
| Mode 2 | editor | 30-60s | JSON 评分，输出短 |
| Mode 3 | fact_checker | 60s | 含工具调用，但单次 LLM 输出短 |

**简化方案**：统一使用 60 秒超时。editor 和 fact_checker 的实际响应通常在 10-20 秒内完成，60 秒已留出充足余量。

## 修改涉及的文件

| 文件 | 改动内容 |
|------|----------|
| `app/core/config.py` | 新增 `llm_request_timeout` 和 `llm_max_retries` 字段 |
| `app/graph/common/llm_factory.py` | 创建 ChatOpenAI 时传入 `request_timeout` 和 `max_retries` |
| `.env.dev` | 新增对应环境变量 |

## 预期收益

| 场景 | 改前 | 改后 |
|------|------|------|
| Mode 2 单节点 LLM 慢响应 | 阻塞 10 分钟 | 60s 超时 + 3 次重试 |
| Mode 3 全链路 LLM 不可用 | 任务阻塞 80 分钟 | 任务 5-8 分钟内失败 |
| 网络抖动 | 等待 10 分钟 | 60s 超时 + 自动重试 |
| 429 限流 | 重试 2 次 | 重试 3 次（指数退避） |

## 难度与风险

| 维度 | 评估 |
|------|------|
| 实现成本 | **极低** — 新增 2 个配置字段 + 2 行代码 |
| 风险 | **极低** — 只是配置参数，不改变业务逻辑 |
| 向后兼容 | 完全兼容 — 使用默认值时行为与改前接近 |

## 实施建议

1. 与 Creation Graph 优化 3 合并实施（同一代码修改）
2. 先用 60s 超时 + 3 次重试作为默认值上线
3. 观察日志中的超时/重试频率，尤其关注 Mode 3 的 fact_checker 阶段
