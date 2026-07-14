from sigma.skill import Skill, ToolRef, ExecutionStep


class TestSkillDefinition:
    """Seam: Skill data type — can define a Skill with required metadata."""

    def test_create_minimal_skill(self):
        skill = Skill(
            id="test-skill",
            name="Test Skill",
            description="A minimal test skill",
            metadata={
                "tags": ["test", "utility"],
                "intent_class": "testing",
                "applicability_boundary": "test only",
            },
            examples=["example 1"],
            tools=[ToolRef(name="tool_a")],
            pipeline=[ExecutionStep(tool="tool_a", params={})],
        )
        assert skill.id == "test-skill"
        assert skill.name == "Test Skill"
        assert "test" in skill.metadata["tags"]
        assert len(skill.tools) == 1
