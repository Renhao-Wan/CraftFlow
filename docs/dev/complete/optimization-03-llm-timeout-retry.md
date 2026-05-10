# 优化 3：配置 LLM 请求超时和重试

## 现状分析

### ChatOpenAI 创建参数

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

**缺失的参数**：
- `request_timeout` — 未设置，使用 LangChain 默认值 **600 秒（10 分钟）**
- `max_retries` — 未设置，使用 LangChain 默认值 **2 次**

### 配置层缺失

**文件**: `app/core/config.py`

LLM 相关配置字段中没有 `request_timeout` 和 `max_retries`，无法通过环境变量控制。

### 问题场景

| 场景 | 当前行为 | 影响 |
|------|----------|------|
| LLM API 响应慢（>60s） | 继续等待，最长 600s | 单节点阻塞 10 分钟 |
| LLM API 返回 429（限流） | 重试 2 次，间隔由 LangChain 决定 | 可能不够，需更多重试 |
| LLM API 返回 502/503 | 重试 2 次 | 同上 |
| LLM API 完全不可用 | 等待 600s 后超时，重试 2 次 | 任务阻塞 30 分钟才失败 |
| 网络抖动 | 无即时超时检测 | 用户长时间无反馈 |

### LangChain 默认行为

`ChatOpenAI` 继承自 `BaseChatModel`，默认值：
- `request_timeout`: 600 秒（通过 httpx 传递给 OpenAI SDK）
- `max_retries`: 2 次（使用 LangChain 内置的指数退避重试）

这些默认值适合长时间运行的 completion，但对实时交互式应用过于宽松。

## 优化方案

### 方案概述

1. 在 `Settings` 中新增 LLM 超时/重试配置字段
2. 在 `LLMFactory` 创建 `ChatOpenAI` 时传入这些参数
3. 根据节点类型使用不同的超时策略

### 详细设计

#### 1. 新增配置字段

**文件**: `app/core/config.py`

```python
class Settings(BaseSettings):
    # 现有字段...
    llm_api_key: str = Field(default="", description="LLM API 密钥")
    llm_api_base: str = Field(default="", description="LLM API 基础 URL")
    llm_model: str = Field(default="gpt-4-turbo", description="默认 LLM 模型")
    max_tokens: int = Field(default=4096, ge=1, le=128000, description="最大 Token 数")

    # 新增字段
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
# LLM 请求配置
LLM_REQUEST_TIMEOUT=60
LLM_MAX_RETRIES=3
```

### 超时策略建议

不同节点的合理超时时间不同，取决于输入/输出长度：

| 节点 | 输入长度 | 输出长度 | 建议超时 | 理由 |
|------|----------|----------|----------|------|
| planner_node | 短（~700 字符） | 中（JSON 大纲） | 30-60s | 输入短，输出结构化 |
| writer_node | 中（~2500 字符） | 长（800-1500 字） | 60-90s | 输出较长 |
| reducer_node | 长（全部章节内容） | 长（完整文章） | 90-120s | 输入+输出都长 |
| debate author/editor | 中 | 中 | 60s | 对抗轮次，中等长度 |

**简化方案**：如果不想按节点区分超时，统一使用 60-90 秒是合理折中。

### 重试策略建议

LangChain 的重试机制内置指数退避，但需注意：

| 错误类型 | HTTP 状态码 | 是否应重试 | 建议 |
|----------|------------|-----------|------|
| 限流 | 429 | 是 | 等待后重试，最多 3 次 |
| 服务端错误 | 502/503/504 | 是 | 短暂故障，重试有效 |
| 请求超时 | - | 是 | 网络抖动，重试可能成功 |
| 参数错误 | 400 | 否 | 重试无意义 |
| 认证失败 | 401/403 | 否 | 重试无意义 |
| 模型不存在 | 404 | 否 | 重试无意义 |

LangChain 默认会区分可重试/不可重试错误，`max_retries=3` 是合理默认值。

## 修改涉及的文件

| 文件 | 改动内容 |
|------|----------|
| `app/core/config.py` | 新增 `llm_request_timeout` 和 `llm_max_retries` 字段 |
| `app/graph/common/llm_factory.py` | 创建 `ChatOpenAI` 时传入 `request_timeout` 和 `max_retries` |
| `.env.dev` | 新增对应环境变量 |

## 预期收益

| 场景 | 改前 | 改后 |
|------|------|------|
| LLM API 响应慢 | 阻塞 10 分钟 | 阻塞 60s 后超时 |
| LLM API 完全不可用 | 任务阻塞 30 分钟 | 任务 3 分钟内失败（60s × 3 次重试 + 退避） |
| 网络抖动 | 等待 10 分钟 | 60s 超时 + 自动重试 |
| 429 限流 | 重试 2 次 | 重试 3 次（指数退避） |

## 难度与风险

| 维度 | 评估 |
|------|------|
| 实现成本 | **极低** — 新增 2 个配置字段 + 2 行代码 |
| 风险 | **极低** — 只是配置参数，不改变业务逻辑 |
| 向后兼容 | 完全兼容 — 使用默认值时行为与改前接近 |

## 实施建议

1. 先用 60s 超时 + 3 次重试作为默认值上线
2. 观察日志中的超时/重试频率
3. 根据实际情况调整各节点的超时时间
4. 如果 LLM API 经常需要 >60s，考虑切换到更快的模型或提供商
