# Spec: 分层路由与自进化记忆 Agent 框架

## Problem Statement

现有 AI Coding Agent 框架在 Tool 数量增长后面临三个核心问题：

1. **检索噪声与功能重叠** — 大量 Tool 堆积导致 Agent 无法准确选择合适的能力单元，匹配率下降
2. **经验无法跨会话复用** — Agent 每次启动都从零开始，同样的错误反复出现，成功经验无法沉淀
3. **长会话上下文退化** — 随执行轮数增加，关键上下文被稀释，Agent 推理准确率衰减

这些问题的根源在于：当前框架缺乏 Skill 的组织层次、自动化的经验沉淀机制、以及结构化的上下文治理手段。

## Solution

设计并实现一个 AI Coding Agent 框架，以 Query Loop + Tool Use 构建任务执行闭环。核心创新点：

- **Skill 分层路由** — 原子 Tool → 高层 Skill → Skill 目录三层结构，两阶段（召回+精排）确保高精度匹配
- **自进化记忆沉淀** — 执行→反思→提炼→存储→索引→复用的闭环，自动积累跨会话经验
- **分层上下文压缩** — 四阶段逐级 pipeline，在大工具结果外置化基础上保持关键上下文稳定
- **中心化多 Agent 协作** — 主 Agent 统一规划审批，子 Agent 受控执行，避免复杂的协调基础设施

## User Stories

1. As a developer using the framework, I want the framework to automatically select the correct Skill for my task, so that I don't need to manually pick from dozens of tools.
2. As a developer using the framework, I want the framework to learn from past execution failures, so that the same error doesn't recur across sessions.
3. As a developer using the framework, I want the framework to retain successful execution patterns as reusable memory, so that common tasks get faster over time.
4. As a developer using the framework, I want the framework to compress large execution contexts automatically, so that long-running sessions remain stable.
5. As a developer using the framework, I want the orchestrator Agent to decompose a complex task into subtasks and dispatch them to worker Agents, so that I can get parallel execution.
6. As a developer using the framework, I want worker Agents to plan their own execution details within the orchestrator's plan, so that each subtask is handled optimally.
7. As a developer, I want the Skill routing system to use a scoring function (not LLM) for the final ranking stage, so that routing decisions are fast and have predictable token cost.
8. As a developer, I want the memory system to distinguish between factual, procedural, and episodic memory, so that I can query the right kind of experience.
9. As a developer, I want context compression to trigger on either Agent introspection, turn count threshold, or token threshold (whichever comes first), so that the system adapts to varying workloads.
10. As a developer, I want the compression pipeline to execute stage-by-stage (summary → placeholder → retrieval → fallback), so that no information is lost prematurely.
11. As a developer, I want the framework to support both Fork and Worktree collaboration modes for parallel execution, so that worker Agents don't interfere with each other's state.
12. As a developer, I want the framework to provide a Skill Catalog for registering and discovering available Skills, so that the system can grow organically.
13. As a developer, I want each Skill to carry metadata tags, applicability boundaries, and usage examples, so that the router can make precise matching decisions.
14. As a developer, I want worker Agents to use the memory system in read-only mode, so that they can learn from past experience without corrupting shared memory.
15. As a developer, I want reflection to happen on both success and failure paths, so that both positive and negative experiences are captured as memory assets.

## Implementation Decisions

### Module Architecture

The framework is organized into the following modules:

| Module | Responsibility |
|--------|---------------|
| **Orchestrator** | Central coordinator — plan decomposition, worker dispatch, quality control, result aggregation |
| **Router** | Stage 1 intent classification + tag matching → Stage 2 scoring function ranking → Skill selection |
| **Skill Registry** | Skill Catalog — register, discover, and retrieve Skill definitions with metadata |
| **Skill Executor** | Execute a selected Skill's Tool orchestration sequence, handle parameter passing and error propagation |
| **Memory System** | Execute→reflect→extract→classify→index→retrieve lifecycle for all three memory types |
| **Context Compressor** | Stage pipeline: summary → placeholder → retrieval → fallback; triggered on introspection OR turn threshold OR token threshold |

### Skill Definition Shape

```
Skill:
  - id: string
  - name: string
  - description: string
  - metadata:
      - tags: string[]          # for stage 1 matching
      - intent_class: string    # primary intent category
      - applicability_boundary: string
  - examples: string[]          # usage examples for matching accuracy
  - tools: ToolRef[]            # ordered orchestration sequence
  - pipeline:
      - steps: ExecutionStep[]  # the actual orchestration logic
```

### Routing Protocol

```
Input: user_query
Stage 1 (Recall):
  intent = classify(query)
  candidates = registry.query(intent_class=intent, tags=extract_tags(query))
  → candidate_set: Skill[]

Stage 2 (Rank):
  for each candidate:
    score = scoring_function(query, candidate.metadata, candidate.examples)
  best = argmax(candidates, score)
  → selected: Skill

Skill Executor.run(selected, query)
```

The scoring function is deterministic — a configurable weighted combination of intent match confidence, tag overlap ratio, and example similarity. No LLM call at rank time.

### Memory Lifecycle

```
For each Skill execution (success or failure):
  Step 1 Reflect:
    - SUCCESS: extract procedural steps as positive pattern
    - FAILURE: extract root cause + fix steps as negative pattern
    - Always classify the extracted knowledge by type (factual/procedural/episodic)
  Step 2 Extract:
    - Condense reflection into a structured memory record
    - Assign metadata tags for future retrieval
  Step 3 Store:
    - Categorize by memory type
    - Update index with new memory record
  Step 4 Index:
    - Maintain separate indexes for each memory type
    - Cross-reference related memories
```

### Context Compression Pipeline

```
Stage 1 Summary Preview:
  - Compress large tool outputs into structured notes
  - Generate summaries with key information preserved

Stage 2 Placeholder Replacement:
  - Replace large context blocks with cache-friendly placeholders
  - Store full content in external cache with retrievable keys

Stage 3 On-Demand Retrieval:
  - When a placeholder's content is needed, retrieve from external cache
  - Replace placeholder with full content inline

Stage 4 Fallback:
  - When context exceeds hard limit, apply aggressive pruning
  - Preserve only the most recent N critical context items
  - All prior context remains retrievable from memory system
```

Trigger: `Agent introspects("context needs cleanup") OR turn_count > THRESHOLD OR token_usage > THRESHOLD`

### Multi-Agent Collaboration

```
Orchestrator.plan(task)
  → P1: break task into subtasks with dependency graph
  → P2: for each subtask, assign worker Agent via Tool Call
  → P3: each worker receives (plan_subset, read_only_memory_handle)
  → P4: worker self-plans execution within its subtask boundary
  → P5: worker executes → returns result
  → P6: orchestrator evaluates → approve or rework
  → P7: aggregate results → final output
```

- Worker Agent: full Tool access, destroy-on-completion lifecycle, read-only memory
- Supports Fork (in-process parallelism) and Worktree (isolated workspace) modes
- No inter-worker coordination protocol — all coordination goes through the orchestrator

### Technology Constraints

- Primary implementation: Python 3.10+
- Claude Code as the reference Agent runtime
- Prompt Cache optimization as a cross-cutting concern

## Testing Decisions

### What makes a good test

- Test external behavior only, not implementation details
- The seam is the observable task outcome: "given input X, the framework produces output Y"
- Memory state changes (did a record get stored?) are tested via the public query interface, not by inspecting internal data structures
- Routing decisions are tested by asserting the selected Skill identity, not by probing internal ranking weights

### Test Seams

**Seam A — End-to-End Integration (Primary)**

Simulate a complete execution cycle: user intent → route → execute → reflect → memorize. Verify:
- Correct Skill selected for given query
- Successful Skill execution produces expected output
- Memory records created with correct type classification
- Context compression does not lose critical information

**Seam B — Router Module**

Test Stage 1 recall precision/recall across varied intent categories. Test Stage 2 ranking correctness when candidates overlap. Verify scoring function output matches expected rankings. Separate tests for edge cases: ambiguous queries, unknown intent, empty candidate set.

**Seam C — Memory Module**

Test the full lifecycle loop for both success and failure paths. Verify:
- Factual memory vs procedural memory vs episodic memory all store and retrieve correctly
- Cross-session retrieval returns relevant past experience
- Index update after new memory addition does not corrupt existing entries

**Seam D — Context Compressor Module**

Test each compression stage independently and the full pipeline:
- Summary preview stage: verify key information preserved
- Placeholder→retrieval round-trip: content integrity after compress→decompress
- Fallback stage: verify survival of most recent critical items under hard limit
- All three trigger methods (introspection / turn count / token threshold)

**Seam E — Skill Executor Module**

Test Tool orchestration sequence correctness: proper ordering, parameter passing between steps, error propagation when a step fails, graceful degradation.

### Prior Art

This project is starting from scratch — there is no prior test artifact. The recommended testing framework is pytest (Python standard in the ecosystem). Integration tests use mocked Tool calls to keep tests deterministic and fast.

## Out of Scope

- **Graphical UI** — initial release is a framework library, not a desktop/web application
- **Third-party Tool ecosystem** — the initial release ships with reference Tool implementations only; a public Tool SDK is future work
- **Multi-language support** — initial release targets Python only
- **Distributed execution** — worker Agents run on the same host; distributed worker pools are future work
- **User-facing dashboard** — observability is via structured logs; a dashboard is future work
- **Automated Skill evolution** — Skills are registered manually in v1; automated Skill generation from execution patterns is future work

## Further Notes

- The framework is open source from day one
- The Skill scoring function should be configurable so that downstream projects can tune routing behavior without modifying core code
- Memory durability between sessions relies on a local storage backend (SQLite in v1, with a pluggable storage interface for future backends)
- Context compression's Prompt Cache benefit is a key design metric — the placeholder stage is specifically designed to maximize cache hit rate across compression boundaries
