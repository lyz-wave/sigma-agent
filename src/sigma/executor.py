from dataclasses import dataclass, field
from typing import Any

from sigma.skill import Skill


@dataclass
class ToolResult:
    success: bool
    output: str = ""
    error: str = ""


class Tool:
    """Base class for executable tools."""

    def execute(self, params: dict[str, Any]) -> ToolResult:
        raise NotImplementedError


@dataclass
class ExecutionResult:
    success: bool
    outputs: list[str] = field(default_factory=list)
    error: str = ""


class SkillExecutor:
    """Execute a Skill's Tool orchestration sequence."""

    def __init__(self, tools: dict[str, Tool] | None = None):
        self._tools: dict[str, Tool] = {}
        if tools:
            self._tools.update(tools)

    def register_tool(self, name: str, tool: Tool) -> None:
        self._tools[name] = tool

    def run(self, skill: Skill) -> ExecutionResult:
        outputs: list[str] = []
        for step in skill.pipeline:
            tool = self._tools.get(step.tool)
            if tool is None:
                return ExecutionResult(
                    success=False,
                    outputs=outputs,
                    error=f"Tool '{step.tool}' not found in executor",
                )
            result = tool.execute(step.params)
            outputs.append(f"{step.tool}: {result.output}")
            if not result.success:
                return ExecutionResult(
                    success=False,
                    outputs=outputs,
                    error=result.error or f"Tool '{step.tool}' failed",
                )
        return ExecutionResult(success=True, outputs=outputs)
