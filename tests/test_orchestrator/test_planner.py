"""Tests for the planner."""

from jarvis.orchestrator.planner import BasicPlanner


class TestBasicPlanner:
    def test_creates_plan(self) -> None:
        planner = BasicPlanner()
        plan = planner.create_plan("Fix the login issue")
        assert plan.title == "Fix the login issue"
        assert len(plan.steps) > 0

    def test_truncates_long_title(self) -> None:
        planner = BasicPlanner()
        long_request = "x" * 200
        plan = planner.create_plan(long_request)
        assert len(plan.title) <= 100
        assert plan.title.endswith("...")

    def test_plan_has_structured_steps(self) -> None:
        planner = BasicPlanner()
        plan = planner.create_plan("Deploy the app")
        assert isinstance(plan.steps, list)
        assert all(isinstance(s, str) for s in plan.steps)
