from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolRef:
    """Reference to an atomic tool used in Skill orchestration."""
    name: str
    description: str = ""


@dataclass
class ExecutionStep:
    """A single step in a Skill's orchestration pipeline."""
    tool: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class Skill:
    """A Skill is an orchestrated sequence of Tool calls with routing metadata."""
    id: str
    name: str
    description: str
    metadata: dict[str, Any]
    examples: list[str]
    tools: list[ToolRef]
    pipeline: list[ExecutionStep]


@dataclass
class QueryResult:
    """A Skill matched by registry query with relevance context."""
    skill: Skill
    matched_tags: list[str] = field(default_factory=list)
    intent_matched: bool = False
