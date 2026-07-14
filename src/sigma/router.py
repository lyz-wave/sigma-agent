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
    """Two-stage Skill router: Stage 1 recall → Stage 2 scoring ranking.

    The scoring weights are configurable via __init__ (defaults optimised
    for intent-precision-heavy workloads).
    """

    def __init__(
        self,
        registry: SkillRegistry,
        intent_weight: float = 0.5,
        tag_weight: float = 0.3,
        example_weight: float = 0.2,
    ):
        self._registry = registry
        self._intent_weight = intent_weight
        self._tag_weight = tag_weight
        self._example_weight = example_weight

    def route(
        self,
        intent_class: str = "",
        tags: list[str] | None = None,
        query_text: str = "",
    ) -> RouteResult:
        """Full route cycle: recall candidates → score → select best.

        Args:
            intent_class: Primary intent category from classification.
            tags: Metadata tags from query extraction.
            query_text: Raw user query text (used for example similarity scoring).
        """
        tags = tags or []
        candidates = self._recall(intent_class, tags)
        if not candidates:
            return RouteResult()

        scores: dict[str, float] = {}
        for c in candidates:
            scores[c.skill.id] = self._score(c, intent_class, tags, query_text)

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

    def _score(
        self,
        candidate: QueryResult,
        intent_class: str,
        tags: list[str],
        query_text: str = "",
    ) -> float:
        """Stage 2 scoring function — deterministic, no LLM call.

        Weighted combination:
          - intent match confidence: self._intent_weight if exact match, 0.0 otherwise
          - tag overlap ratio: percentage of query tags present in skill tags
          - example similarity: keyword overlap between query_text and skill examples
        """
        # Intent match
        intent_score = 1.0 if candidate.intent_matched else 0.0

        # Tag overlap
        tag_score = (
            len(candidate.matched_tags) / len(tags)
            if tags and len(tags) > 0
            else 0.0
        )

        # Example similarity — compare query_text (or intent_class as fallback)
        # against Skill example text to measure real semantic keyword overlap
        source_text = query_text or intent_class.replace("_", " ")
        query_words = set(
            w.lower() for w in source_text.split()
            if len(w) > 2  # skip very short words
        )
        example_text = " ".join(candidate.skill.examples).lower()
        example_words = set(example_text.split())
        common = query_words & example_words
        example_score = len(common) / len(query_words) if query_words else 0.0

        return (
            self._intent_weight * intent_score
            + self._tag_weight * tag_score
            + self._example_weight * example_score
        )
