# docs/dev 文档索引

> 本目录包含 CraftFlow 设置系统和适配器架构的设计文档。四篇文档各司其职，执行时以 `implementation-plan.md` 为主线，其余文档作为设计参考。

## 文档关系

```
implementation-plan.md          ← 执行主线：什么时候做、按什么顺序做
    │
    ├──→ backend-adapter-pattern.md   ← Step 1-2 参考：适配器接口、Service 层改造
    ├──→ settings-architecture.md     ← Step 3-7 参考：LLM Profile、Settings API、前端设置页
    └──→ data-ownership.md            ← 设计依据：数据归属权、通信协议、架构演进方向
```

## 文档清单

| 文档 | 职责 | 何时参考 |
|------|------|----------|
| [implementation-plan.md](implementation-plan.md) | 实施计划：7 个 Step 的执行顺序、依赖关系、验证标准 | **始终以此为主线** |
| [backend-adapter-pattern.md](backend-adapter-pattern.md) | 适配器架构：`BusinessAdapter` 接口、`StandaloneAdapter`/`ServerAdapter` 实现、Service 层改造方式 | Step 1-2 |
| [settings-architecture.md](settings-architecture.md) | 设置系统设计：三层设置模型、`llm_profiles` 表结构、Settings API 定义、前端设置页功能 | Step 3-7 |
| [data-ownership.md](data-ownership.md) | 数据归属权：standalone vs server 的数据 owner、Java ↔ Python 通信协议、架构演进路线 | 理解设计决策、server 端扩展时 |

## 执行规则

1. 按 `implementation-plan.md` 的 Step 顺序推进
2. 每个 Step 执行前，阅读对应的参考文档获取设计细节
3. 完成每个 Step 后，按计划中的"验证"标准确认
4. 遇到设计疑问时，优先查阅 `data-ownership.md` 理解决策背景

## 当前状态

- [ ] Step 1: BusinessAdapter 接口 + StandaloneAdapter
- [ ] Step 2: Service 层切换到 Adapter
- [ ] Step 3: LLM Profile 表 + CRUD
- [ ] Step 4: LLMFactory 改造
- [ ] Step 5: 后端 Settings API
- [ ] Step 6: 前端设置页
- [ ] Step 7: 清理旧配置
