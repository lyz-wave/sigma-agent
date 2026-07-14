# Learning Record 001 — 项目整体架构

**日期**：2026-07-14

**学到什么**：
- Sigma Agent 的 6 模块架构和 4 大技术支柱
- 每个支柱解决的具体问题和技术方案
- 关键设计决策及其背后的权衡

**关键洞察**：
- "打分函数而非 LLM 做精排"这个决策是项目最核心的设计哲学——每个环节都要问"这笔 Token 花得值不值"
- Memory 系统的双路径策略（成功/失败都反思）确保了正负样本平衡
- 中心化协作模式的设计原则是"避免引入比解决的问题更复杂的基建"

**后续问题**：
- 什么时候应该从 SEQUENTIAL 切换到 CONCURRENT 或 WORKTREE？
- Context Compressor 的四阶段在真实 Claude Code 会话中如何配合 Prompt Cache？
