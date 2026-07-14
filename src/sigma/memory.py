from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class MemoryRecord:
    """Base class for all memory records. Each subclass sets its own type."""
    key: str
    content: str
    tags: list[str] = field(default_factory=list)
    type: str = ""


@dataclass
class FactualMemory(MemoryRecord):
    """Factual knowledge: API params, project config, static facts."""
    source: str = ""
    type: str = "factual"  # type: ignore[assignment]


@dataclass
class ProceduralMemory(MemoryRecord):
    """Procedural knowledge: how-to steps, patterns."""
    domain: str = ""
    steps: list[str] = field(default_factory=list)
    type: str = "procedural"  # type: ignore[assignment]


@dataclass
class EpisodicMemory(MemoryRecord):
    """Episodic knowledge: past execution experiences."""
    context: dict[str, Any] = field(default_factory=dict)
    outcome: str = ""
    type: str = "episodic"  # type: ignore[assignment]
