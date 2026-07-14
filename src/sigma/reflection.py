import uuid
from typing import Any

from sigma.executor import ExecutionResult
from sigma.memory import EpisodicMemory, ProceduralMemory
from sigma.storage import StorageBackend


class ReflectionEngine:
    """Post-execution reflection pipeline.

    After a Skill execution completes (success or failure), reflects on
    the outcome, extracts structured knowledge, classifies by memory type,
    and stores it via the configured StorageBackend.
    """

    def __init__(self, storage: StorageBackend, enabled: bool = True):
        self.storage = storage
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def reflect(
        self,
        result: ExecutionResult,
        intent_class: str = "",
        query_context: str = "",
    ) -> None:
        """Run reflection on an execution result.

        Args:
            result: The execution result from SkillExecutor.
            intent_class: The intent class that was used for routing.
            query_context: The original user query or context.
        """
        if not self._enabled:
            return

        if result.success:
            self._reflect_success(result, intent_class, query_context)
        else:
            self._reflect_failure(result, intent_class, query_context)

    def _reflect_success(
        self,
        result: ExecutionResult,
        intent_class: str,
        query_context: str,
    ) -> None:
        """Extract procedural steps from successful execution."""
        suffix = uuid.uuid4().hex[:6]
        steps = []
        for output in result.outputs:
            # Extract tool name and action from output like "tool_a: action details"
            parts = output.split(":", 1)
            if len(parts) == 2:
                steps.append(f"{parts[0].strip()}: {parts[1].strip()[:80]}")
            else:
                steps.append(output[:80])

        content = "; ".join(steps) if steps else query_context
        tags = [intent_class] if intent_class else []
        if "deploy" in query_context.lower():
            tags.append("deployment")
        if "test" in query_context.lower():
            tags.append("testing")
        if "review" in query_context.lower():
            tags.append("review")

        mem = ProceduralMemory(
            key=f"proc_{intent_class}_{suffix}",
            content=content,
            domain=intent_class,
            steps=steps,
            tags=tags,
        )
        self.storage.store(mem)

    def _reflect_failure(
        self,
        result: ExecutionResult,
        intent_class: str,
        query_context: str,
    ) -> None:
        """Extract root cause + fix steps from failed execution."""
        suffix = uuid.uuid4().hex[:6]

        # Store as episodic memory with error context
        epi_mem = EpisodicMemory(
            key=f"epi_{intent_class}_{suffix}",
            content=f"Execution failed: {result.error}",
            context={
                "error": result.error,
                "intent_class": intent_class,
                "query_context": query_context,
                "completed_steps": len(result.outputs),
            },
            outcome="failure",
            tags=[intent_class, "failure"] if intent_class else ["failure"],
        )
        self.storage.store(epi_mem)

        # Store procedural memory with fix guidance
        steps = [
            "1. Review the error details above",
            "2. Check the failing step configuration",
            f"3. Fix the issue and retry ({intent_class})",
        ]
        proc_mem = ProceduralMemory(
            key=f"proc_{intent_class}_fix_{suffix}",
            content=f"Fix for {intent_class} failure: {result.error}",
            domain=intent_class,
            steps=steps,
            tags=[intent_class, "fix"] if intent_class else ["fix"],
        )
        self.storage.store(proc_mem)
