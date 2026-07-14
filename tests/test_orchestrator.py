import pytest
from sigma.executor import ExecutionResult, Tool, ToolResult
from sigma.orchestrator import (
    ForkMode,
    Orchestrator,
    Plan,
    Subtask,
    Worker,
    WorkerResult,
)


# --- Mock Tools ---

class MockBuild(Tool):
    def execute(self, params: dict) -> ToolResult:
        return ToolResult(success=True, output="build: compiled successfully")


class MockTest(Tool):
    def execute(self, params: dict) -> ToolResult:
        return ToolResult(success=True, output="test: all 42 tests passed")


class MockDeploy(Tool):
    def execute(self, params: dict) -> ToolResult:
        return ToolResult(success=True, output="deploy: deployed to staging")


class MockFailingTool(Tool):
    def execute(self, params: dict) -> ToolResult:
        return ToolResult(success=False, error="build failed: syntax error")


# --- Worker Tests ---

class TestWorker:
    """Seam: Worker agent — executes subtasks with full Tool access, read-only memory."""

    @pytest.fixture
    def tools(self):
        return {"build": MockBuild(), "test": MockTest()}

    def test_worker_executes_subtask(self, tools):
        worker = Worker(agent_id="worker_1", tools=tools)
        subtask = Subtask(
            id="build-src",
            description="Build the source code",
            tools_required=["build"],
            params={"target": "production"},
        )
        result = worker.execute(subtask)
        assert result.success is True
        assert "compiled" in result.output

    def test_worker_multiple_tools(self, tools):
        worker = Worker(agent_id="worker_1", tools=tools)
        subtask = Subtask(
            id="build-and-test",
            description="Build then test",
            tools_required=["build", "test"],
            params={"target": "production"},
        )
        result = worker.execute(subtask)
        assert result.success is True
        assert len(result.step_outputs) > 1

    def test_worker_missing_tool(self, tools):
        worker = Worker(agent_id="worker_1", tools=tools)
        subtask = Subtask(
            id="deploy",
            description="Deploy",
            tools_required=["deploy"],  # not in worker's tools
            params={},
        )
        result = worker.execute(subtask)
        assert result.success is False

    def test_worker_tool_failure(self, tools):
        tools["fail"] = MockFailingTool()
        worker = Worker(agent_id="worker_1", tools=tools)
        subtask = Subtask(
            id="fail-task",
            description="Will fail",
            tools_required=["fail"],
            params={},
        )
        result = worker.execute(subtask)
        assert result.success is False
        assert "failed" in result.error.lower()

    def test_worker_self_plans_execution(self):
        """Worker should determine execution order within subtask boundary."""
        worker = Worker(agent_id="planner", tools={"a": MockBuild(), "b": MockTest()})
        subtask = Subtask(
            id="ordered",
            description="Execute in logical order",
            tools_required=["a", "b"],
            params={},
        )
        result = worker.execute(subtask)
        assert result.success is True


# --- Orchestrator Plan + Dispatch Tests ---

class TestOrchestrator:
    """Seam: Orchestrator — plan decomposition, dispatch, evaluate, aggregate."""

    @pytest.fixture
    def tools(self):
        return {
            "build": MockBuild(),
            "test": MockTest(),
            "deploy": MockDeploy(),
            "fail": MockFailingTool(),
        }

    @pytest.fixture
    def orchestrator(self, tools):
        return Orchestrator(tools=tools)

    def test_plan_creates_subtasks(self, orchestrator):
        plan = orchestrator.plan("Build, test, and deploy the application")
        assert len(plan.subtasks) >= 2
        assert all(isinstance(s, Subtask) for s in plan.subtasks)

    def test_plan_dependency_order(self, orchestrator):
        plan = orchestrator.plan("Build and test")
        assert len(plan.subtasks) >= 2
        # Build should come before test
        build_idx = next(i for i, s in enumerate(plan.subtasks) if "build" in s.id)
        test_idx = next(i for i, s in enumerate(plan.subtasks) if "test" in s.id)
        assert build_idx < test_idx

    def test_dispatch_subtask(self, orchestrator):
        subtask = Subtask(
            id="build", description="Build", tools_required=["build"], params={}
        )
        result = orchestrator.dispatch(subtask, mode=ForkMode.SEQUENTIAL)
        assert result.success is True

    def test_dispatch_all_subtasks(self, orchestrator):
        plan = orchestrator.plan("Build and test")
        results = orchestrator.execute_plan(plan, mode=ForkMode.SEQUENTIAL)
        assert len(results) == len(plan.subtasks)
        assert all(r.success for r in results)

    def test_evaluate_accepts_success(self, orchestrator):
        result = WorkerResult(
            subtask_id="build",
            success=True,
            output="build successful",
            step_outputs=["build: OK"],
        )
        evaluation = orchestrator.evaluate(result)
        assert evaluation.accepted is True

    def test_evaluate_rejects_failure(self, orchestrator):
        result = WorkerResult(
            subtask_id="build",
            success=False,
            output="",
            step_outputs=[],
            error="build failed",
        )
        evaluation = orchestrator.evaluate(result)
        assert evaluation.accepted is False

    def test_aggregate_collects_results(self, orchestrator):
        results = [
            WorkerResult(subtask_id="build", success=True, output="build: OK"),
            WorkerResult(subtask_id="test", success=True, output="test: PASS"),
        ]
        final = orchestrator.aggregate(results)
        assert "build" in final
        assert "test" in final
        assert "PASS" in final

    def test_aggregate_includes_failure_info(self, orchestrator):
        results = [
            WorkerResult(subtask_id="build", success=True, output="build: OK"),
            WorkerResult(subtask_id="test", success=False, output="",
                         error="tests failed"),
        ]
        final = orchestrator.aggregate(results)
        assert "failed" in final.lower() or "error" in final.lower()

    def test_execute_plan_failing_subtask(self, orchestrator):
        tools = {"build": MockBuild(), "fail": MockFailingTool(), "deploy": MockDeploy()}
        orch = Orchestrator(tools=tools)
        plan = Plan(subtasks=[
            Subtask(id="build", description="Build", tools_required=["build"], params={}),
            Subtask(id="fail", description="Fail", tools_required=["fail"], params={}),
            Subtask(id="deploy", description="Deploy", tools_required=["deploy"], params={}),
        ])
        results = orch.execute_plan(plan, mode=ForkMode.SEQUENTIAL)
        assert results[1].success is False  # fail step
        # deploy should still run since it's not blocked by fail
        assert any(r.subtask_id == "deploy" for r in results)

    def test_destroy_on_completion(self, orchestrator):
        """Worker is destroyed after execution — new worker needed for each subtask."""
        subtask = Subtask(id="t1", description="Task 1", tools_required=["build"], params={})
        worker = Worker(agent_id="ephemeral", tools=orchestrator._tools)
        result1 = worker.execute(subtask)
        assert result1.success is True
        # Worker is "destroyed" — no state carries over
        assert not hasattr(worker, "_state")


class TestForkExecution:
    """Seam: Fork mode — in-process parallel execution."""

    def test_fork_sequential_execution(self, orchestrator_tools):
        tools = orchestrator_tools
        orch = Orchestrator(tools=tools)
        plan = Plan(subtasks=[
            Subtask(id="build", description="Build", tools_required=["build"], params={}),
            Subtask(id="test", description="Test", tools_required=["test"], params={}),
        ])
        results = orch.execute_plan(plan, mode=ForkMode.SEQUENTIAL)
        assert all(r.success for r in results)

    def test_fork_concurrent_execution(self, orchestrator_tools):
        tools = orchestrator_tools
        orch = Orchestrator(tools=tools)
        plan = Plan(subtasks=[
            Subtask(id="build", description="Build", tools_required=["build"], params={}),
            Subtask(id="test", description="Test", tools_required=["test"], params={}),
            Subtask(id="deploy", description="Deploy", tools_required=["deploy"], params={}),
        ])
        results = orch.execute_plan(plan, mode=ForkMode.CONCURRENT)
        assert all(r.success for r in results)
        assert len(results) == 3


@pytest.fixture
def orchestrator_tools():
    return {
        "build": MockBuild(),
        "test": MockTest(),
        "deploy": MockDeploy(),
    }


class TestIntegration:
    """Seam A: Integration — full task lifecycle."""

    def test_complex_task_end_to_end(self):
        tools = {
            "build": MockBuild(),
            "test": MockTest(),
            "deploy": MockDeploy(),
        }
        orch = Orchestrator(tools=tools)
        plan = orch.plan("Build, test, and deploy")
        results = orch.execute_plan(plan, mode=ForkMode.SEQUENTIAL)
        final = orch.aggregate(results)

        assert all(r.success for r in results)
        assert "build" in final.lower() or "build" in str(results).lower()

    def test_partial_failure_graceful(self):
        tools = {
            "build": MockBuild(),
            "fail": MockFailingTool(),
            "deploy": MockDeploy(),
        }
        orch = Orchestrator(tools=tools)
        plan = Plan(subtasks=[
            Subtask(id="build", description="Build", tools_required=["build"], params={}),
            Subtask(id="fail", description="Fail step", tools_required=["fail"], params={}),
        ])
        results = orch.execute_plan(plan, mode=ForkMode.SEQUENTIAL)
        # Other subtasks should still complete
        assert results[0].success is True  # build succeeded
        assert results[1].success is False  # fail step failed
