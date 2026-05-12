# CraftFlow 鉴权设计

> 本文档描述 CraftFlow Python 后端的鉴权机制，包括 API Key 验证、模式感知行为、REST/WebSocket 鉴权实现和生产环境安全措施。

## 一、鉴权架构

### 1.1 职责划分

CraftFlow 采用**两层鉴权**架构：

```
用户浏览器
    │  JWT Token
    ▼
Java 后端 ── 验证 JWT，管理用户身份
    │  X-API-Key
    ▼
Python 后端 ── 验证 API Key，确认调用方合法
```

**Python 后端只验证"谁在调用我"，不验证"用户是谁"**。

### 1.2 为什么不用 JWT？

| 考量 | 说明 |
|------|------|
| 职责分离 | JWT 签发/验证是业务层职责，Python 后端不应有用户信息 |
| 简化依赖 | API Key 验证无需 JWT 库，减少依赖和复杂度 |
| 内网安全 | API Key 足以保护内网服务，JWT 留给 Java 后端处理客户端鉴权 |
| 无状态 | API Key 验证是纯内存字符串比对，无 I/O，延迟 < 1ms |

## 二、模式感知行为

### 2.1 行为矩阵

| 模式 | ENABLE_AUTH | REST 行为 | WebSocket 行为 |
|------|-------------|-----------|----------------|
| standalone | 强制 false | 自动放行，无需 API Key | 自动放行 |
| server + auth=false | false | 自动放行 | 自动放行 |
| server + auth=true | true | 验证 X-API-Key 请求头 | 验证 api_key 查询参数 |

### 2.2 配置项

```bash
# standalone 模式（自动禁用鉴权，以下配置无效）
APP_MODE=standalone

# server 模式（建议启用鉴权）
APP_MODE=server
ENABLE_AUTH=true
API_KEY=your-strong-api-key-here
```

**注意**：standalone 模式下 `ENABLE_AUTH` 会被 `model_validator` 强制设为 `false`，即使手动配置为 `true` 也无效。

## 三、REST 鉴权

### 3.1 实现原理

```python
# app/core/auth.py

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(
    api_key: str | None = Depends(api_key_header),
) -> dict[str, Any]:
    if not settings.enable_auth:
        return {"caller": "local", "authenticated": True}

    if api_key is None:
        raise HTTPException(status_code=401, detail="未提供 API Key")

    if api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="无效的 API Key")

    return {"caller": "java-backend", "authenticated": True}
```

### 3.2 注入方式

所有 REST 端点通过 `Depends(verify_api_key)` 注入鉴权：

```python
@router.post("/creation")
async def create_creation_task(
    request: CreationRequest,
    caller: dict[str, Any] = Depends(verify_api_key),  # 鉴权注入
    service: CreationService = Depends(get_creation_service),
):
    ...
```

### 3.3 受保护端点

| 端点 | 方法 | 鉴权 |
|------|------|------|
| `/api/v1/creation` | POST | ✅ verify_api_key |
| `/api/v1/polishing` | POST | ✅ verify_api_key |
| `/api/v1/tasks` | GET | ✅ verify_api_key |
| `/api/v1/tasks/{task_id}` | GET | ✅ verify_api_key |
| `/api/v1/tasks/{task_id}/resume` | POST | ✅ verify_api_key |
| `/api/v1/tasks/{task_id}` | DELETE | ✅ verify_api_key |
| `/health` | GET | ❌ 无需鉴权 |

### 3.4 响应码

| 场景 | 状态码 | 说明 |
|------|--------|------|
| standalone 模式 | 200 | 自动放行 |
| server + 无 key | 401 | 未提供 API Key |
| server + 错误 key | 403 | 无效的 API Key |
| server + 正确 key | 200 | 验证通过 |

### 3.5 请求示例

```bash
# server 模式下携带 API Key
curl -X GET http://localhost:8000/api/v1/tasks \
  -H "X-API-Key: your-strong-api-key-here"

# 创建任务
curl -X POST http://localhost:8000/api/v1/creation \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-strong-api-key-here" \
  -d '{"topic": "微服务架构演进"}'
```

## 四、WebSocket 鉴权

### 4.1 实现原理

WebSocket 无法使用标准 HTTP 请求头，因此通过**查询参数**传递 API Key：

```python
# app/core/auth.py

async def verify_ws_api_key(websocket: WebSocket) -> bool:
    if not settings.enable_auth:
        return True

    api_key = websocket.query_params.get("api_key")

    if api_key is None:
        await websocket.close(code=4001, reason="未提供 API Key")
        return False

    if api_key != settings.api_key:
        await websocket.close(code=4001, reason="无效的 API Key")
        return False

    return True
```

### 4.2 使用方式

```python
# app/api/v1/ws.py

async def ws_endpoint(websocket: WebSocket):
    if not await verify_ws_api_key(websocket):
        return  # 连接已关闭
    await websocket.accept()
    # ... 后续逻辑
```

### 4.3 连接示例

```javascript
// JavaScript 客户端
const ws = new WebSocket('ws://localhost:8000/ws?api_key=your-strong-api-key-here');

ws.onclose = (event) => {
    if (event.code === 4001) {
        console.error('API Key 验证失败:', event.reason);
    }
};
```

### 4.4 关闭码

| 代码 | 含义 | 场景 |
|------|------|------|
| 4001 | 未提供 API Key | 查询参数中缺少 `api_key` |
| 4001 | 无效的 API Key | `api_key` 值不匹配 |

## 五、生产环境安全措施

### 5.1 异常信息脱敏

生产环境（`ENVIRONMENT=production`）下，异常响应隐藏内部实现细节：

```python
# CraftFlowException handler
detail = exc.details if settings.is_development else {}

# 通用 Exception handler
detail = {"exception_type": type(exc).__name__} if settings.is_development else {}
```

**对比**：

| 环境 | CraftFlowException 响应 | 通用 Exception 响应 |
|------|------------------------|---------------------|
| development | `{"error": "...", "message": "...", "detail": {...}}` | `{"error": "...", "detail": {"exception_type": "..."}}` |
| production | `{"error": "...", "message": "...", "detail": {}}` | `{"error": "...", "detail": {}}` |

### 5.2 日志记录

所有鉴权失败事件均记录到日志：

```python
logger.warning("API Key 验证失败：未提供 API Key")
logger.warning("API Key 验证失败：无效的 API Key")
logger.warning("WebSocket API Key 验证失败：未提供 api_key 参数")
logger.warning("WebSocket API Key 验证失败：无效的 api_key")
```

### 5.3 API Key 管理建议

| 场景 | 建议 |
|------|------|
| 开发环境 | 使用默认值 `craftflow-dev-key` |
| 测试环境 | 使用随机生成的 key |
| 生产环境 | 使用 32+ 字符的随机强密钥，定期轮换 |
| 多后端实例 | 所有 Python 后端实例共享同一个 API Key |

## 六、测试覆盖

鉴权模块有完整的测试覆盖（`tests/test_auth.py` + `tests/test_server.py`）：

| 测试类 | 测试数 | 覆盖内容 |
|--------|--------|----------|
| TestVerifyApiKey | 5 | standalone 放行、server 401/403/200 |
| TestVerifyWsApiKey | 4 | standalone 放行、server 401/403/200 |
| TestRestAuthIntegration | 4 | REST 端点集成测试 |
| TestServerMissingApiKey | 5 | 所有端点 401 |
| TestServerInvalidApiKey | 4 | 所有端点 403 |
| TestServerValidApiKey | 5 | 所有端点 200 |
| TestServerErrorSanitization | 2 | 错误响应格式 |

---

**文档版本**: v1.0  
**创建日期**: 2026-05-12  
**维护者**: Renhao-Wan
