"""Tests for the task state machine transitions."""

import pytest

from jarvis.models.task import (
    VALID_TRANSITIONS,
    InvalidTransitionError,
    TaskStatus,
    validate_transition,
)


class TestValidTransitions:
    """Test every valid state transition."""

    @pytest.mark.parametrize(
        "current,target",
        [
            (TaskStatus.CREATED, TaskStatus.PLANNING),
            (TaskStatus.CREATED, TaskStatus.CANCELLED),
            (TaskStatus.PLANNING, TaskStatus.WAITING_FOR_APPROVAL),
            (TaskStatus.PLANNING, TaskStatus.RUNNING),
            (TaskStatus.PLANNING, TaskStatus.FAILED),
            (TaskStatus.PLANNING, TaskStatus.CANCELLED),
            (TaskStatus.WAITING_FOR_APPROVAL, TaskStatus.RUNNING),
            (TaskStatus.WAITING_FOR_APPROVAL, TaskStatus.CANCELLED),
            (TaskStatus.RUNNING, TaskStatus.VERIFYING),
            (TaskStatus.RUNNING, TaskStatus.FAILED),
            (TaskStatus.RUNNING, TaskStatus.CANCELLED),
            (TaskStatus.VERIFYING, TaskStatus.COMPLETED),
            (TaskStatus.VERIFYING, TaskStatus.FAILED),
            (TaskStatus.VERIFYING, TaskStatus.CANCELLED),
            (TaskStatus.FAILED, TaskStatus.PLANNING),  # retry
        ],
    )
    def test_valid_transition(self, current: TaskStatus, target: TaskStatus) -> None:
        validate_transition(current, target)  # should not raise


class TestInvalidTransitions:
    """Test that invalid transitions are rejected."""

    @pytest.mark.parametrize(
        "current,target",
        [
            (TaskStatus.CREATED, TaskStatus.RUNNING),
            (TaskStatus.CREATED, TaskStatus.COMPLETED),
            (TaskStatus.COMPLETED, TaskStatus.RUNNING),
            (TaskStatus.COMPLETED, TaskStatus.CANCELLED),
            (TaskStatus.COMPLETED, TaskStatus.PLANNING),
            (TaskStatus.CANCELLED, TaskStatus.RUNNING),
            (TaskStatus.CANCELLED, TaskStatus.PLANNING),
            (TaskStatus.RUNNING, TaskStatus.PLANNING),
            (TaskStatus.RUNNING, TaskStatus.CREATED),
            (TaskStatus.FAILED, TaskStatus.COMPLETED),
            (TaskStatus.FAILED, TaskStatus.RUNNING),
        ],
    )
    def test_invalid_transition(self, current: TaskStatus, target: TaskStatus) -> None:
        with pytest.raises(InvalidTransitionError):
            validate_transition(current, target)

    def test_error_contains_states(self) -> None:
        with pytest.raises(InvalidTransitionError) as exc_info:
            validate_transition(TaskStatus.COMPLETED, TaskStatus.RUNNING)
        assert "completed" in str(exc_info.value)
        assert "running" in str(exc_info.value)


def test_all_states_have_transition_entries() -> None:
    """Every TaskStatus value must have an entry in VALID_TRANSITIONS."""
    for status in TaskStatus:
        assert status in VALID_TRANSITIONS
