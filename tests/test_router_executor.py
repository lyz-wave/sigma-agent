import pytest
from sigma.skill import ExecutionStep, Skill, ToolRef
from sigma.registry import SkillRegistry
from sigma.router import Router, RouteResult
from sigma.executor import SkillExecutor, Tool, ToolResult


# --- Mock Tools ---

class MockToolA(Tool):
    def execute(self, params: dict) -> ToolResult:
        return ToolResult(success=True, output=f"tool_a result: {params}")


class MockToolB(Tool):
    def execute(self, params: dict) -> ToolResult:
        return ToolResult(success=True, output=f"tool_b result: {params}")


class MockToolFailing(Tool):
    def execute(self, params: dict) -> ToolResult:
        return ToolResult(success=False, error="Tool B failed")


# --- Fixtures ---

@pytest.fixture
def registry():
    r = SkillRegistry()
    r.register(Skill(
        id="code-review",
        name="Code Review",
        description="Review code for quality issues",
        metadata={
            "tags": ["code", "review", "quality", "python"],
            "intent_class": "code_review",
            "applicability_boundary": "Python/TS projects",
        },
        examples=["review this PR for bugs", "check this code for style issues"],
        tools=[ToolRef(name="check"), ToolRef(name="report")],
        pipeline=[
            ExecutionStep(tool="check", params={"mode": "quick"}),
            ExecutionStep(tool="report", params={"format": "markdown"}),
        ],
    ))
    r.register(Skill(
        id="deploy",
        name="Deploy",
        description="Deploy application to server",
        metadata={
            "tags": ["deploy", "devops", "infra"],
            "intent_class": "deployment",
            "applicability_boundary": "production/staging",
        },
        examples=["deploy to production", "rollback to previous version"],
        tools=[ToolRef(name="build"), ToolRef(name="push")],
        pipeline=[
            ExecutionStep(tool="build", params={"target": "production"}),
            ExecutionStep(tool="push", params={"target": "production"}),
        ],
    ))
    r.register(Skill(
        id="test-runner",
        name="Test Runner",
        description="Run tests and collect results",
        metadata={
            "tags": ["test", "python", "quality"],
            "intent_class": "testing",
            "applicability_boundary": "Python projects",
        },
        examples=["run all tests", "run unit tests only"],
        tools=[ToolRef(name="run_tests")],
        pipeline=[ExecutionStep(tool="run_tests", params={"scope": "all"})],
    ))
    return r


@pytest.fixture
def router(registry):
    return Router(registry)


@pytest.fixture
def executor():
    tools = {"tool_a": MockToolA(), "tool_b": MockToolB()}
    return SkillExecutor(tools)


class TestRouter:
    """Seam: Router — Stage 1 recall + Stage 2 scoring ranking."""

    def test_recall_by_intent(self, router):
        result = router.route(intent_class="code_review", tags=[])
        assert len(result.candidates) > 0
        assert result.selected is not None
        assert result.selected.id == "code-review"

    def test_recall_by_tags(self, router):
        result = router.route(intent_class="", tags=["deploy", "devops"])
        assert result.selected is not None
        assert result.selected.id == "deploy"

    def test_rank_top_score_wins(self, router):
        # "testing" intent matches test-runner exactly, but "quality" tag also matches code-review
        result = router.route(intent_class="testing", tags=["quality"])
        assert result.selected is not None
        assert result.selected.id == "test-runner"  # intent match > tag-only match

    def test_ambiguous_query(self, router):
        # Multiple skills match, top score should win
        result = router.route(intent_class="", tags=["quality"])
        assert result.selected is not None
        assert result.selected.id in ("code-review", "test-runner")

    def test_no_match(self, router):
        result = router.route(intent_class="unknown_intent", tags=[])
        assert result.selected is None
        assert len(result.candidates) == 0

    def test_scoring_function_scores(self, router):
        candidates = router._recall(intent_class="testing", tags=[])
        assert len(candidates) > 0
        scores = [router._score(c, intent_class="testing", tags=[]) for c in candidates]
        for s in scores:
            assert 0.0 <= s <= 1.0
        # The matching skill should have highest score
        best_idx = max(range(len(scores)), key=lambda i: scores[i])
        assert candidates[best_idx].skill.id == "test-runner"

    def test_no_llm_at_rank_time(self, router):
        """Verification: scoring function is pure math, no LLM."""
        import inspect
        source = inspect.getsource(router._score)  # type: ignore[arg-type]
        assert "openai" not in source.lower()
        assert "anthropic" not in source.lower()
        assert ".chat" not in source.lower()


class TestExecutor:
    """Seam: SkillExecutor — execute Tool orchestration sequence."""

    def test_execute_single_tool(self, executor):
        skill = Skill(
            id="single", name="Single", description="",
            metadata={}, examples=[],
            tools=[ToolRef(name="tool_a")],
            pipeline=[ExecutionStep(tool="tool_a", params={"input": "hello"})],
        )
        result = executor.run(skill)
        assert result.success is True
        assert "tool_a" in result.outputs[0]

    def test_execute_multi_tool_sequence(self, executor):
        skill = Skill(
            id="multi", name="Multi", description="",
            metadata={}, examples=[],
            tools=[ToolRef(name="tool_a"), ToolRef(name="tool_b")],
            pipeline=[
                ExecutionStep(tool="tool_a", params={"step": 1}),
                ExecutionStep(tool="tool_b", params={"step": 2}),
            ],
        )
        result = executor.run(skill)
        assert result.success is True
        assert len(result.outputs) == 2
        assert "tool_a" in result.outputs[0]
        assert "tool_b" in result.outputs[1]

    def test_parameter_passing(self, executor):
        # Parameter from step 1 output passed to step 2 input
        skill = Skill(
            id="param-pass", name="ParamPass", description="",
            metadata={}, examples=[],
            tools=[ToolRef(name="tool_a"), ToolRef(name="tool_b")],
            pipeline=[
                ExecutionStep(tool="tool_a", params={"generate": "key"}),
                ExecutionStep(tool="tool_b", params={"use_key": "{{steps[0].output}}"}),
            ],
        )
        result = executor.run(skill)
        assert result.success is True

    def test_error_propagation(self, executor):
        failing = SkillExecutor({"fail": MockToolFailing()})
        skill = Skill(
            id="fail-skill", name="Fail", description="",
            metadata={}, examples=[],
            tools=[ToolRef(name="fail")],
            pipeline=[ExecutionStep(tool="fail", params={})],
        )
        result = failing.run(skill)
        assert result.success is False
        assert "failed" in result.error.lower() or "Tool B" in result.error

    def test_step_failure_skips_remaining(self, executor):
        executor.register_tool("fail", MockToolFailing())
        skill = Skill(
            id="fail-chain", name="FailChain", description="",
            metadata={}, examples=[],
            tools=[ToolRef(name="tool_a"), ToolRef(name="fail"), ToolRef(name="tool_b")],
            pipeline=[
                ExecutionStep(tool="tool_a", params={}),
                ExecutionStep(tool="fail", params={}),
                ExecutionStep(tool="tool_b", params={}),
            ],
        )
        result = executor.run(skill)
        assert result.success is False
        assert len(result.outputs) == 2  # step 0 + failing step output

    def test_execute_unknown_tool(self, executor):
        skill = Skill(
            id="missing", name="Missing", description="",
            metadata={}, examples=[],
            tools=[ToolRef(name="nonexistent")],
            pipeline=[ExecutionStep(tool="nonexistent", params={})],
        )
        result = executor.run(skill)
        assert result.success is False
        assert "not found" in result.error.lower()


class TestRouteAndExecute:
    """Seam A: Integration — full route→execute cycle."""

    def test_full_route_and_execute(self, registry):
        router = Router(registry)
        route_result = router.route(intent_class="code_review", tags=[])
        assert route_result.selected is not None

        executor = SkillExecutor({"check": MockToolA(), "report": MockToolB()})
        exec_result = executor.run(route_result.selected)
        assert exec_result.success is True

    def test_route_then_execute_wrong_intent(self, registry, executor):
        router = Router(registry)
        route_result = router.route(intent_class="unknown", tags=[])
        assert route_result.selected is None

    def test_route_then_execute_failing_tool(self, registry):
        router = Router(registry)
        executor = SkillExecutor({"check": MockToolFailing()})
        route_result = router.route(intent_class="code_review", tags=[])
        assert route_result.selected is not None

        exec_result = executor.run(route_result.selected)
        assert exec_result.success is False
