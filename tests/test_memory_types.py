import pytest
from sigma.memory import MemoryRecord, FactualMemory, ProceduralMemory, EpisodicMemory


class TestMemoryTypes:
    """Seam: MemoryRecord type hierarchy — three distinct memory types."""

    def test_create_factual_memory(self):
        mem = FactualMemory(
            key="api_key_format",
            content="API key is a 32-char hex string",
            source="documentation",
        )
        assert mem.type == "factual"
        assert mem.key == "api_key_format"
        assert isinstance(mem, MemoryRecord)

    def test_create_procedural_memory(self):
        mem = ProceduralMemory(
            key="deploy_steps",
            content="1. Build\n2. Test\n3. Deploy",
            domain="deployment",
            steps=["Build", "Test", "Deploy"],
        )
        assert mem.type == "procedural"
        assert len(mem.steps) == 3

    def test_create_episodic_memory(self):
        mem = EpisodicMemory(
            key="failed_deploy_20260714",
            content="Deploy failed due to missing env var",
            context={"project": "sigma", "error": "ENV_VAR_NOT_SET"},
            outcome="failure",
        )
        assert mem.type == "episodic"
        assert mem.outcome == "failure"

    def test_factual_default_tags(self):
        mem = FactualMemory(key="k", content="c", source="doc")
        assert mem.tags == []

    def test_procedural_default_tags(self):
        mem = ProceduralMemory(key="k", content="c", domain="d", steps=["s"])
        assert len(mem.steps) == 1

    def test_episodic_default_tags(self):
        mem = EpisodicMemory(key="k", content="c", context={}, outcome="success")
        assert mem.outcome == "success"
