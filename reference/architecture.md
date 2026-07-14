# Reference: Sigma Agent 架构速查

## 模块速览

| 模块 | 职责 | 关键类 |
|------|------|--------|
| Router | 两阶段路由：召回 → 精排 | `Router` |
| Registry | Skill 注册与查询 | `SkillRegistry` |
| Executor | Tool 编排执行 | `SkillExecutor`, `Tool` |
| Memory | 三种记忆类型 | `FactualMemory`, `ProceduralMemory`, `EpisodicMemory` |
| Storage | 可插拔存储 | `StorageBackend`, `SQLiteStorageBackend` |
| Reflection | 执行后反思 | `ReflectionEngine` |
| Compressor | 上下文压缩 | `CompressorPipeline`, `Stage1-4` |
| Orchestrator | 多 Agent 协作 | `Orchestrator`, `Worker` |

## 记忆类型

- **Factual**: 静态知识，从 key=value 模式自动提取
- **Procedural**: How-to 步骤，成功执行产物
- **Episodic**: 失败归因 + 上下文，失败执行产物

## 路由公式

```
score = intent_match * 0.5 + tag_overlap * 0.3 + example_similarity * 0.2
```

## 压缩触发（OR）

Agent 自省 → `signal_introspect()` ｜ 轮数 > `turn_threshold` ｜ Token > `token_threshold`

## ForkMode

- `SEQUENTIAL` — 串行执行，依赖检查
- `CONCURRENT` — 并行执行，按依赖拓扑分批
- `WORKTREE` — 隔离临时目录执行
