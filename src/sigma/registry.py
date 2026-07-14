from sigma.skill import QueryResult, Skill


class SkillRegistry:
    """Catalog for registering, discovering, and querying Skill definitions."""

    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.id] = skill

    def unregister(self, skill_id: str) -> None:
        self._skills.pop(skill_id, None)

    def discover(self) -> list[Skill]:
        return list(self._skills.values())

    def query(
        self, intent_class: str = "", tags: list[str] | None = None
    ) -> list[QueryResult]:
        """Stage 1 recall: filter Skills by intent class and metadata tags.

        Returns QueryResult objects that include relevance context
        (which tags matched, whether intent matched).
        """
        tags = tags or []
        results: list[QueryResult] = []
        for skill in self._skills.values():
            matched_tags = (
                [t for t in tags if t in skill.metadata.get("tags", [])]
                if tags
                else []
            )
            intent_matched = (
                skill.metadata.get("intent_class", "") == intent_class
                if intent_class
                else True
            )
            if intent_class:
                if intent_matched:
                    results.append(
                        QueryResult(
                            skill=skill,
                            matched_tags=matched_tags,
                            intent_matched=True,
                        )
                    )
            else:
                if matched_tags:
                    results.append(
                        QueryResult(
                            skill=skill,
                            matched_tags=matched_tags,
                            intent_matched=False,
                        )
                    )
        return results

    def query_skills(
        self, intent_class: str = "", tags: list[str] | None = None
    ) -> list[Skill]:
        """Convenience: return matched Skill objects directly."""
        return [qr.skill for qr in self.query(intent_class, tags)]
