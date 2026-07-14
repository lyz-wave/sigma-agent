from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sigma.executor import ExecutionResult, Tool, ToolResult


# --- Core Data Types ---

@dataclass
class Subtask:
    """A single unit of work assigned to a Worker."""
    id: str
    description: str
    tools_required: list[str]
    params: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)


@dataclass
class Plan:
    """A plan consisting of ordered subtasks."""
    subtasks: list[Subtask]


@dataclass
class WorkerResult:
    """Result from a Worker's subtask execution."""
    subtask_id: str
    success: bool
    output: str = ""
    step_outputs: list[str] = field(default_factory=list)
    error: str = ""


@dataclass
class Evaluation:
    """Orchestrator evaluation of a Worker result."""
    accepted: bool
    reason: str = ""


class ForkMode(Enum):
    SEQUENTIAL = "sequential"
    CONCURRENT = "concurrent"


# --- Worker (sub-Agent) ---

class Worker:
    """Worker Agent that executes subtasks with full Tool access.

    Lifecycle: create → execute → destroy. No state persists between subtasks.
    Memory access: read-only (not currently implemented; the Worker receives
    a memory_handle for future read-only memory system integration).
    """

    def __init__(self, agent_id: str, tools: dict[str, Tool]):
        self._agent_id = agent_id
        self._tools = tools

    def execute(self, subtask: Subtask) -> WorkerResult:
        """Self-plan and execute a subtask within its boundary.

        The Worker verifies it has the required tools, then executes them
        in the order specified by tools_required.
        """
        # Check required tools
        for tool_name in subtask.tools_required:
            if tool_name not in self._tools:
                return WorkerResult(
                    subtask_id=subtask.id,
                    success=False,
                    error=f"Required tool '{tool_name}' not available",
                )

        step_outputs: list[str] = []
        for tool_name in subtask.tools_required:
            tool = self._tools[tool_name]
            result = tool.execute(subtask.params)
            step_outputs.append(f"{tool_name}: {result.output}")
            if not result.success:
                return WorkerResult(
                    subtask_id=subtask.id,
                    success=False,
                    output="; ".join(step_outputs),
                    step_outputs=step_outputs,
                    error=result.error or f"Tool '{tool_name}' failed",
                )

        combined = "; ".join(step_outputs)
        return WorkerResult(
            subtask_id=subtask.id,
            success=True,
            output=combined,
            step_outputs=step_outputs,
        )


# --- Orchestrator ---

class Orchestrator:
    """Central orchestrator — plan decomposition, dispatch, evaluate, aggregate.

    Architecture:
      - plan(task) → Plan with dependency-ordered subtasks
      - execute_plan(plan, mode) → execute all subtasks
      - evaluate(result) → accept or request rework
      - aggregate(results) → merged final output

    Worker Agents are created per-subtask (destroy-on-completion lifecycle).
    """

    def __init__(self, tools: dict[str, Tool] | None = None):
        self._tools: dict[str, Tool] = {}
        if tools:
            self._tools.update(tools)

    def plan(self, task_description: str) -> Plan:
        """Decompose a task description into ordered subtasks.

        Uses a simple rule-based planner that recognizes common CI/CD patterns.
        In production, this would use intent classification (via the Router).
        """
        desc = task_description.lower()
        subtasks: list[Subtask] = []

        # Rule-based decomposition
        if "build" in desc or "compile" in desc:
            subtasks.append(Subtask(
                id="build", description="Build the application",
                tools_required=["build"] if "build" in self._tools else [],
                params={"target": "production"},
            ))

        if "test" in desc or "check" in desc:
            subtasks.append(Subtask(
                id="test", description="Run tests",
                tools_required=["test"] if "test" in self._tools else [],
                params={"scope": "all"},
                depends_on=["build"] if any(s.id == "build" for s in subtasks) else [],
            ))

        if "deploy" in desc or "release" in desc:
            subtasks.append(Subtask(
                id="deploy", description="Deploy the application",
                tools_required=["deploy"] if "deploy" in self._tools else [],
                params={"target": "staging"},
                depends_on=["test"] if any(s.id == "test" for s in subtasks) else [],
            ))

        if not subtasks:
            # Fallback: use all available tools as a single subtask
            tool_names = list(self._tools.keys())
            if tool_names:
                subtasks.append(Subtask(
                    id="default", description=task_description,
                    tools_required=tool_names,
                    params={},
                ))

        return Plan(subtasks=subtasks)

    def dispatch(self, subtask: Subtask, mode: ForkMode = ForkMode.SEQUENTIAL) -> WorkerResult:
        """Dispatch a subtask to a new Worker instance."""
        worker = Worker(agent_id=f"worker_{subtask.id}", tools=self._tools)
        return worker.execute(subtask)
        # Worker goes out of scope → destroyed (destroy-on-completion lifecycle)

    def execute_plan(self, plan: Plan, mode: ForkMode = ForkMode.SEQUENTIAL) -> list[WorkerResult]:
        """Execute all subtasks in a plan according to the specified mode."""
        if mode == ForkMode.CONCURRENT:
            return self._execute_concurrent(plan)
        return self._execute_sequential(plan)

    def _are_dependencies_satisfied(
        self, subtask: Subtask, completed: dict[str, WorkerResult]
    ) -> bool:
        """Check whether all dependencies of a subtask have completed successfully."""
        for dep_id in subtask.depends_on:
            if dep_id not in completed:
                return False
            if not completed[dep_id].success:
                return False
        return True

    def _execute_sequential(self, plan: Plan) -> list[WorkerResult]:
        results: list[WorkerResult] = []
        completed: dict[str, WorkerResult] = {}
        for subtask in plan.subtasks:
            if not self._are_dependencies_satisfied(subtask, completed):
                # Dependency failed — mark as skipped
                result = WorkerResult(
                    subtask_id=subtask.id,
                    success=False,
                    error=f"Skipped: dependency not satisfied ({', '.join(subtask.depends_on)})",
                )
                results.append(result)
                completed[subtask.id] = result
                continue
            result = self.dispatch(subtask)
            results.append(result)
            completed[subtask.id] = result
        return results

    def _execute_concurrent(self, plan: Plan) -> list[WorkerResult]:
        """Execute eligible subtasks concurrently, respecting dependency ordering."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: dict[str, WorkerResult] = {}
        pending = {s.id: s for s in plan.subtasks}
        completed: dict[str, WorkerResult] = {}

        while pending:
            # Collect subtasks whose dependencies are satisfied
            eligible = [
                s for s in pending.values()
                if self._are_dependencies_satisfied(s, completed)
            ]
            if not eligible:
                # Remaining subtasks have unfulfilled dependencies — mark as skipped
                for s_id, s in pending.items():
                    dep_failed = any(
                        d in completed and not completed[d].success
                        for d in s.depends_on
                    )
                    if dep_failed:
                        results[s_id] = WorkerResult(
                            subtask_id=s_id,
                            success=False,
                            error=f"Skipped: dependency failed ({', '.join(s.depends_on)})",
                        )
                    else:
                        results[s_id] = WorkerResult(
                            subtask_id=s_id,
                            success=False,
                            error=f"Blocked: dependencies not met ({', '.join(s.depends_on)})",
                        )
                break

            with ThreadPoolExecutor(max_workers=len(eligible)) as executor:
                future_map = {
                    executor.submit(self.dispatch, s): s.id for s in eligible
                }
                for future in as_completed(future_map):
                    s_id = future_map[future]
                    result = future.result()
                    results[s_id] = result
                    completed[s_id] = result
                    del pending[s_id]

        return list(results.values())

    def evaluate(self, result: WorkerResult) -> Evaluation:
        """Evaluate a Worker's result — accept or request rework."""
        if result.success:
            return Evaluation(accepted=True, reason="Subtask completed successfully")
        return Evaluation(
            accepted=False,
            reason=f"Subtask failed: {result.error}",
        )

    def aggregate(self, results: list[WorkerResult]) -> str:
        """Merge all Worker outputs into a final summary."""
        parts: list[str] = []
        failures = 0
        for r in results:
            if r.success:
                if r.output:
                    parts.append(f"[{r.subtask_id}] {r.output}")
                else:
                    parts.append(f"[{r.subtask_id}] completed")
            else:
                failures += 1
                parts.append(f"[{r.subtask_id}] FAILED: {r.error}")

        summary = "\n".join(parts)
        if failures:
            summary += f"\n\n{failures} subtask(s) failed"
        return summary
