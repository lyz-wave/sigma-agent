from dataclasses import dataclass, field

from sigma.registry import SkillRegistry
from sigma.skill import QueryResult, Skill


# --- Router ---

@dataclass
class RouteResult:
    selected: Skill | None = None
    candidates: list[QueryResult] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)


class Router:
    """Two-stage Skill router: Stage 1 recall → Stage 2 scoring ranking."""

    def __init__(self, registry: SkillRegistry):
        self._registry = registry

    def route(self, intent_class: str = "", tags: list[str] | None = None) -> RouteResult:
        """Full route cycle: recall candidates → score → select best."""
        tags = tags or []
        candidates = self._recall(intent_class, tags)
        if not candidates:
            return RouteResult()

        scores: dict[str, float] = {}
        for c in candidates:
            scores[c.skill.id] = self._score(c, intent_class, tags)

        best_id = max(scores, key=scores.get)  # type: ignore
        best = next(c for c in candidates if c.skill.id == best_id)
        return RouteResult(
            selected=best.skill,
            candidates=candidates,
            scores=scores,
        )

    def _recall(self, intent_class: str, tags: list[str]) -> list[QueryResult]:
        """Stage 1: query registry for candidate Skills."""
        return self._registry.query(intent_class, tags)

    def _score(self, candidate: QueryResult, intent_class: str, tags: list[str]) -> float:
        """Stage 2 scoring function — deterministic, no LLM call.

        Weighted combination:
          - intent match confidence: 0.5 if exact match, 0.0 otherwise
          - tag overlap ratio: percentage of query tags present in skill tags
          - example similarity: simple keyword overlap ratio
        """
        intent_weight = 0.5
        tag_weight = 0.3
        example_weight = 0.2

        # Intent match
        intent_score = 1.0 if candidate.intent_matched else 0.0

        # Tag overlap
        skill_tags = candidate.skill.metadata.get("tags", [])
        tag_score = (
            len(candidate.matched_tags) / len(tags)
            if tags and len(tags) > 0
            else 0.0
        )

        # Example similarity — simple keyword overlap
        query_words = set(
            w.lower() for w in intent_class.split("_") + tags
            if w.strip()
        )
        example_text = " ".join(candidate.skill.examples).lower()
        example_words = set(example_text.split())
        common = query_words & example_words
        example_score = len(common) / len(query_words) if query_words else 0.0

        return (
            intent_weight * intent_score
            + tag_weight * tag_score
            + example_weight * example_score
        )
