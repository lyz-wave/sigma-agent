import tempfile
from pathlib import Path

import pytest
from sigma.executor import ExecutionResult
from sigma.memory import EpisodicMemory, ProceduralMemory
from sigma.reflection import ReflectionEngine
from sigma.storage import SQLiteStorageBackend


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield Path(f.name)


@pytest.fixture
def storage(db_path):
    backend = SQLiteStorageBackend(db_path)
    yield backend
    backend.close()


@pytest.fixture
def engine(storage):
    return ReflectionEngine(storage)


class TestReflectionEngine:
    """Seam: ReflectionEngine — post-execution reflection pipeline."""

    def test_success_extracts_procedural_memory(self, engine):
        result = ExecutionResult(
            success=True,
            outputs=["tool_a: generated key=abc123", "tool_b: deployed to staging"],
        )
        engine.reflect(result, intent_class="deployment", query_context="deploy to staging")

        mems = engine.storage.query(memory_type="procedural", tags=[])
        assert len(mems) >= 1
        for m in mems:
            assert isinstance(m, ProceduralMemory)
            assert "deploy" in m.key

    def test_failure_extracts_episodic_and_procedural(self, engine):
        result = ExecutionResult(
            success=False,
            outputs=["tool_a: config loaded"],
            error="Tool B failed: connection refused",
        )
        engine.reflect(result, intent_class="deployment", query_context="deploy to staging")

        episodics = engine.storage.query(memory_type="episodic", tags=[])
        procedurals = engine.storage.query(memory_type="procedural", tags=[])

        assert len(episodics) >= 1
        assert len(procedurals) >= 1

        for m in episodics:
            assert isinstance(m, EpisodicMemory)
            assert m.outcome == "failure"
            assert m.context.get("error") is not None

    def test_success_extracts_tags_from_context(self, engine):
        result = ExecutionResult(
            success=True,
            outputs=["tool_a: passed"],
        )
        engine.reflect(result, intent_class="testing", query_context="run unit tests")
        mems = engine.storage.query(memory_type="procedural", tags=["testing"])
        assert len(mems) >= 1

    def test_disabled_reflection(self, storage):
        engine = ReflectionEngine(storage, enabled=False)
        result = ExecutionResult(success=True, outputs=["done"])
        engine.reflect(result, intent_class="test", query_context="test")
        mems = storage.query(memory_type="procedural", tags=[])
        assert len(mems) == 0

    def test_reflection_includes_steps_from_outputs(self, engine):
        result = ExecutionResult(
            success=True,
            outputs=[
                "tool_a: checked syntax",
                "tool_b: generated report",
                "tool_c: sent notification",
            ],
        )
        engine.reflect(result, intent_class="code_review", query_context="review PR")
        mems = engine.storage.query(memory_type="procedural", tags=[])
        for m in mems:
            if isinstance(m, ProceduralMemory):
                assert len(m.steps) > 0

    def test_multiple_reflections_accumulate(self, engine):
        for i in range(3):
            result = ExecutionResult(
                success=True,
                outputs=[f"tool_a: result_{i}"],
            )
            engine.reflect(result, intent_class="testing", query_context=f"test run {i}")

        mems = engine.storage.query(memory_type="procedural", tags=[])
        assert len(mems) >= 3

    def test_failure_stores_error_context(self, engine):
        result = ExecutionResult(
            success=False,
            outputs=["tool_a: started"],
            error="TimeoutError: connection timed out after 30s",
        )
        engine.reflect(result, intent_class="deployment", query_context="deploy")
        episodics = engine.storage.query(memory_type="episodic", tags=[])
        for m in episodics:
            if m.outcome == "failure":
                assert "TimeoutError" in str(m.context) or "timeout" in str(m.context).lower()

    def test_memory_record_self_contained(self, engine):
        """Memory record must be retrievable and readable without external context."""
        result = ExecutionResult(
            success=True,
            outputs=["tool_a: completed analysis on PR #42"],
        )
        engine.reflect(result, intent_class="code_review", query_context="review PR #42")
        mems = engine.storage.query(memory_type="procedural", tags=[])
        for m in mems:
            assert m.content
            assert m.key
            assert "code_review" in m.tags or "review" in m.tags


class TestReflectionIntegration:
    """Seam A: Integration — route → execute → reflect → store → query."""

    def test_full_cycle(self, db_path):
        from sigma.executor import SkillExecutor
        from sigma.registry import SkillRegistry
        from sigma.router import Router
        from sigma.skill import ExecutionStep, Skill, ToolRef

        # Setup
        storage = SQLiteStorageBackend(db_path)
        engine = ReflectionEngine(storage)

        registry = SkillRegistry()
        registry.register(Skill(
            id="test-skill",
            name="Test",
            description="",
            metadata={"tags": ["test"], "intent_class": "testing"},
            examples=["run test"],
            tools=[ToolRef(name="mock")],
            pipeline=[ExecutionStep(tool="mock", params={"input": "hello"})],
        ))
        executor = SkillExecutor()

        class MockTool:
            def execute(self, params):
                from sigma.executor import ToolResult
                return ToolResult(success=True, output="mock completed")

        executor.register_tool("mock", MockTool())
        router = Router(registry)

        # Route
        route_result = router.route(intent_class="testing", tags=[])
        assert route_result.selected is not None

        # Execute
        exec_result = executor.run(route_result.selected)
        assert exec_result.success is True

        # Reflect
        engine.reflect(exec_result, intent_class="testing", query_context="run test")

        # Query
        mems = storage.query(memory_type="procedural", tags=[])
        assert len(mems) >= 1
        assert mems[0].key.startswith("proc_")
        storage.close()
