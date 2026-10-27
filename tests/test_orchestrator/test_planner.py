"""Tests for the planner."""

import pytest

from jarvis.orchestrator.planner import BasicPlanner, short_title


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
        assert len(plan.title) <= 60
        assert plan.title.endswith("…")

    def test_plan_has_structured_steps(self) -> None:
        planner = BasicPlanner()
        plan = planner.create_plan("Deploy the app")
        assert isinstance(plan.steps, list)
        assert all(isinstance(s, str) for s in plan.steps)


@pytest.mark.parametrize(
    ("request_text", "expected"),
    [
        ("Fix the login issue", "Fix the login issue"),
        (
            "can you please add a dark mode toggle to the settings page?",
            "Add a dark mode toggle to the settings…",
        ),
        (
            "hey jarvis, refactor the auth module to use async. Then run tests",
            "Refactor the auth module to use async",
        ),
        ("I want you to deploy the staging server", "Deploy the staging server"),
        (
            "update the readme with install steps for windows mac and linux users",
            "Update the readme with install steps for windows…",
        ),
        ("please", "Untitled task"),
        ("", "Untitled task"),
        ("first line\nsecond line", "First line"),
    ],
)
def test_short_title(request_text: str, expected: str) -> None:
    assert short_title(request_text) == expected
