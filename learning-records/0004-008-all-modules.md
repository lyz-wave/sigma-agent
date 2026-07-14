# Learning Record 004-008 — 全部模块深入

**日期**：2026-07-14

**覆盖范围**：
- 004: Skill Executor — Tool 编排序列、错误传播、关注点分离
- 005: Memory System — 三种记忆类型、可插拔存储、跨会话复用
- 006: ReflectionEngine — 双路径策略、FactualMemory 提取、成功/失败都学习
- 007: Context Compressor — 4 阶段 pipeline、OR 触发、信息分层
- 008: Orchestrator — 中心化协作、3 种 ForkMode、依赖拓扑、Worker 无状态

**关键洞察**：
- Executor 只做事，不管对错——失败传播到上层处理（关注点分离模式贯穿整个框架）
- 三种记忆类型对应三种学习方式：记事实、记步骤、记教训
- 压缩是分层不是丢弃——热数据在上下文，温数据在占位符，冷数据在记忆库
- Worker 无状态设计是框架中最具前瞻性的决策——为分布式执行铺平道路
