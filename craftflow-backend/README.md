# CraftFlow Backend

> 基于 Agentic Workflow 的智能长文织造与多阶审校平台

## 项目简介

**CraftFlow** 是一个创新的 AI 内容创作平台，采用 LangGraph 驱动的双轨状态机架构，彻底解决大语言模型在长文生成中的质量失控问题。

### 核心特性

- 🎯 **渐进式织造 (Map-Reduce)**：大纲先行 + 并发撰写，突破上下文长度限制
- 🔄 **多阶审校流**：极速格式化 / 专家对抗 / 事实核查三档弹性算力
- 🤝 **强制人机协同 (HITL)**：关键决策点自动挂起，支持断点续传
- 🛠️ **工具链增强**：集成搜索、代码沙箱、链接验证等外部工具
- 📊 **长周期有状态任务**：基于 Checkpointer 的持久化状态管理
- 🔧 **配置驱动双模式**：一套代码，通过 `APP_MODE` 环境变量切换 standalone / server 模式

### 运行模式

| 特性 | standalone（桌面端） | server（服务端） |
|------|---------------------|-----------------|
| 存储 | SQLite（强制） | SQLite 或 PostgreSQL（可选） |
| 鉴权 | 无（强制禁用） | API Key（可选，建议开启） |
| WebSocket | 不启用 | 启用 |
| 配置 | 零配置启动 | 需配置 API_KEY，使用 PostgreSQL 时需配置 DATABASE_URL |

### 技术栈

- **后端框架**: Python 3.11+, FastAPI, Pydantic V2
- **AI 编排**: LangGraph, LangChain
- **持久化**: SQLite（桌面端）/ PostgreSQL + pgvector（服务端）
- **LLM**: OpenAI 格式

## 快速开始

### 环境要求

- Python 3.11+
- uv (推荐) 或 pip
- PostgreSQL 14+ (生产环境)
- Redis (可选，用于限流)

### 安装步骤

1. **克隆项目**

```bash
git clone https://github.com/Renhao-Wan/CraftFlow.git
cd CraftFlow/craftflow-backend
```

2. **安装依赖**

使用 uv（推荐）：

```bash
uv sync
uv sync --extra dev        # 含 pytest, black, ruff
```

3. **配置环境变量**

```bash
# 桌面端开发（推荐）
cp .env.standalone .env.dev

# 或服务端开发
cp .env.server .env.dev
```

编辑 `.env.dev`，填写必要的 API Key：
- `TAVILY_API_KEY`：Tavily 搜索 API（可选）
- `E2B_API_KEY`：E2B 代码沙箱 API（可选）

> LLM 配置通过前端设置页面管理（侧边栏设置按钮 → LLM 配置），无需在 `.env` 中填写。

4. **启动开发服务器**

```bash
# 使用启动脚本（推荐）
scripts/dev.ps1    # Windows PowerShell
scripts/dev.sh     # Linux/macOS

# 或手动启动
uv run uvicorn app.main:app --reload --env-file .env.dev --host 127.0.0.1 --port 8000
```

服务将在 `http://localhost:8000` 启动。

### 验证安装

访问 API 文档：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 项目结构

```
craftflow-backend/
├── app/
│   ├── api/                    # FastAPI 路由层
│   │   ├── dependencies.py     # 依赖注入（模式感知初始化）
│   │   └── v1/                 # API v1 版本
│   ├── core/                   # 基础设施层
│   │   ├── auth.py             # API Key 鉴权模块
│   │   ├── config.py           # 全局配置（APP_MODE 驱动）
│   │   ├── exceptions.py       # 异常处理（生产环境脱敏）
│   │   └── logger.py           # 日志配置
│   ├── graph/                  # LangGraph 核心编排
│   │   ├── common/             # 共享抽象（LLM 工厂、Prompt）
│   │   ├── tools/              # 外部工具封装
│   │   ├── creation/           # Creation Graph 模块
│   │   └── polishing/          # Polishing Graph 模块
│   ├── schemas/                # Pydantic 数据模型
│   ├── services/               # 业务服务层
│   │   ├── task_store.py       # TaskStore 抽象接口 + 工厂
│   │   ├── task_store_sqlite.py # SQLite 实现
│   │   └── task_store_postgres.py # PostgreSQL 实现
│   └── main.py                 # 应用入口
├── tests/                      # 测试目录
│   ├── test_standalone.py      # standalone 模式端到端测试
│   ├── test_server.py          # server 模式端到端测试
│   └── test_auth.py            # 鉴权模块测试
├── docs/                       # 文档目录
├── logs/                       # 日志目录
├── .env.example                # 环境变量配置说明
├── .env.standalone             # 桌面端配置模板
├── .env.server                 # 服务端配置模板
├── pyproject.toml              # 项目依赖配置
└── README.md                   # 本文件
```

## 核心 API

### 1. 创作流 (Creation)

**发起创作任务**

```bash
POST /api/v1/creation
Content-Type: application/json

{
  "topic": "微服务架构演进",
  "description": "面向后端工程师，深度技术文章"
}
```

**响应**

```json
{
  "task_id": "c-uuid-xxx",
  "status": "running"
}
```

**查询任务状态**

```bash
GET /api/v1/tasks/{task_id}
```

**恢复执行（修改大纲后）**

```bash
POST /api/v1/tasks/{task_id}/resume
Content-Type: application/json

{
  "action": "confirm_outline",
  "data": {
    "outline": [...]
  }
}
```

### 2. 润色流 (Polishing)

**发起润色任务**

```bash
POST /api/v1/polishing
Content-Type: application/json

{
  "content": "文章正文...",
  "mode": 3
}
```

模式说明：
- `mode=1`: 极速格式化（单次 LLM 调用）
- `mode=2`: 专家对抗循环（Author-Editor 博弈）
- `mode=3`: 事实核查 + 对抗循环（最高质量）

## 开发指南

### 运行测试

```bash
# 运行所有测试
uv run pytest

# 运行特定测试文件
uv run pytest tests/test_graph/test_creation_graph.py

# 查看覆盖率
uv run pytest --cov=app --cov-report=html
```

### 代码格式化

```bash
# 使用 black 格式化
uv run black app/ tests/

# 使用 ruff 检查
uv run ruff check app/ tests/
```

## 部署

### 生产环境配置（server 模式）

1. 复制服务端配置模板：

```bash
cp .env.server .env
```

2. 编辑 `.env`，修改以下关键配置：
   - `API_KEY`：设置强密钥（Java 后端调用时需要携带）
   - `DATABASE_URL`：PostgreSQL 连接串
   - `ENVIRONMENT=production`：隐藏 API 文档

   > LLM 配置通过 Settings API 或前端设置页面管理。

3. 使用 Gunicorn 部署：

```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --env-file .env
```

### 桌面端部署（standalone 模式）

桌面端使用 standalone 模式，SQLite 存储，零配置：

```bash
cp .env.standalone .env
uv run uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000
```

### API Key 鉴权

server 模式下，所有 REST API 需要在请求头中携带 API Key：

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/tasks
```

WebSocket 连接通过查询参数传递：

```bash
ws://localhost:8000/ws?api_key=your-api-key
```

standalone 模式下无需鉴权，所有端点直接放行。

### Docker 部署（计划中）

Docker 支持尚在规划中，敬请期待。

## 架构设计

详细架构文档请参考：

- [后端架构总览](docs/architecture/architecture-overview.md) — 后端整体架构设计
- [数据存储架构](docs/architecture/database-design.md) — 四层存储架构设计
- [API 接口参考](docs/api/api-reference.md) — REST 和 WebSocket 接口详细说明
- [接口流程图解](docs/api/api-flow.md) — API 接口流程图
- [WebSocket 通信架构](docs/api/WebSocket-architecture.md) — WebSocket 通信设计
- [鉴权设计](docs/api/authentication-design.md) — API Key 鉴权机制
- [Creation Graph 流程](docs/graph/creation-graph.md) — 创作图详细流程
- [Polishing Graph 流程](docs/graph/polishing-graph.md) — 润色图详细流程
- [核心开发蓝图](docs/guide/core-dev-guide.md) — 核心开发规范
- [Prompt 策略](docs/guide/prompt-strategy.md) — Prompt 模板组织原则
- [工具调用说明](docs/guide/tool-calling.md) — 工具链调用说明
- [部署指南](docs/deployment/deployment-guide.md) — 不同场景部署方案
- [环境变量配置](docs/deployment/env-configuration-guide.md) — 配置项完整说明

### 核心设计理念

1. **双图解耦**：Creation Graph 和 Polishing Graph 物理分离
2. **Map-Reduce 并发**：利用 LangGraph `Send` API 实现章节并发生成
3. **子图复用**：Debate Subgraph 作为独立组件被 Polishing Graph 调用
4. **异步优先**：所有 I/O 操作使用 async/await

## 贡献指南

欢迎贡献代码、报告问题或提出建议！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 许可证

本项目采用 Apache-2.0 许可证 - 详见 [LICENSE](../../LICENSE) 文件

## 联系方式

- 项目主页: https://github.com/Renhao-Wan/CraftFlow
- 问题反馈: https://github.com/Renhao-Wan/CraftFlow/issues

---

**文档版本**: v2.1
**最后更新**: 2026-05-13
**维护者**: Renhao-Wan
