import pytest
from sigma.skill import QueryResult, Skill, ToolRef, ExecutionStep
from sigma.registry import SkillRegistry


@pytest.fixture
def registry():
    return SkillRegistry()


@pytest.fixture
def sample_skill():
    return Skill(
        id="code-review-skill",
        name="Code Review",
        description="Review code for issues",
        metadata={
            "tags": ["code", "review", "quality"],
            "intent_class": "code_review",
            "applicability_boundary": "Python projects",
        },
        examples=["review this PR for bugs"],
        tools=[ToolRef(name="grep"), ToolRef(name="analyze")],
        pipeline=[
            ExecutionStep(tool="grep", params={"pattern": "TODO"}),
            ExecutionStep(tool="analyze", params={"depth": "full"}),
        ],
    )


class TestSkillRegistry:
    """Seam: SkillRegistry — can register, discover, and query Skills by metadata."""

    def test_register_and_discover(self, registry, sample_skill):
        registry.register(sample_skill)
        all_skills = registry.discover()
        assert len(all_skills) == 1
        assert all_skills[0].id == "code-review-skill"

    def test_query_by_intent_class(self, registry, sample_skill):
        registry.register(sample_skill)
        results = registry.query(intent_class="code_review", tags=[])
        assert len(results) == 1
        assert results[0].skill.id == "code-review-skill"
        assert results[0].intent_matched is True
        assert results[0].matched_tags == []

    def test_query_by_tags(self, registry, sample_skill):
        registry.register(sample_skill)
        results = registry.query(intent_class="", tags=["code", "review"])
        assert len(results) == 1
        assert results[0].skill.id == "code-review-skill"
        assert "code" in results[0].matched_tags

    def test_query_no_match(self, registry, sample_skill):
        registry.register(sample_skill)
        results = registry.query(intent_class="deployment", tags=[])
        assert len(results) == 0

    def test_query_empty_registry(self, registry):
        results = registry.query(intent_class="anything", tags=[])
        assert len(results) == 0

    def test_unregister(self, registry, sample_skill):
        registry.register(sample_skill)
        registry.unregister("code-review-skill")
        assert len(registry.discover()) == 0

    def test_discover_empty(self, registry):
        assert registry.discover() == []

    def test_query_skills_convenience(self, registry, sample_skill):
        registry.register(sample_skill)
        results = registry.query_skills(intent_class="code_review", tags=[])
        assert len(results) == 1
        assert results[0].id == "code-review-skill"
