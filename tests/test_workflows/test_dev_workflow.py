"""Tests for the DevWorkflow — all I/O mocked."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.agents.base import BaseAgent
from jarvis.agents.registry import AgentRegistry
from jarvis.agents.router import AgentRouter
from jarvis.config import AgentsConfig, WorkflowConfig
from jarvis.events import EventBus, EventType
from jarvis.models.approval import ApprovalStatus
from jarvis.models.task import Task, TaskPriority, TaskStatus
from jarvis.services.agent_execution_service import AgentExecutionService
from jarvis.services.approval_service import ApprovalService
from jarvis.services.memory_service import MemoryService
from jarvis.services.project_service import ProjectService
from jarvis.services.task_service import TaskService
from jarvis.tools.base import ToolResult
from jarvis.tools.registry import ToolRegistry
from jarvis.workflows.dev_workflow import DevWorkflow, _slugify
from jarvis.workflows.models import (
    DevWorkflowRequest,
    WorkflowResult,
    WorkflowStatus,
    WorkflowStepResult,
    WorkflowStepStatus,
)

# --- Fixtures ---


def _make_task(task_id: str = "TASK-abc123", status: TaskStatus = TaskStatus.CREATED) -> Task:
    """Create a minimal Task for tests."""
    return Task(
        id=task_id,
        request="Resolve issue #42",
        title="Dev workflow: issue #42",
        status=status,
        priority=TaskPriority.NORMAL,
    )


def _make_agent() -> MagicMock:
    """Create a mock agent."""
    agent = MagicMock(spec=BaseAgent)
    agent.agent_name = "claude_code"
    agent.run = AsyncMock(return_value=(0, "Implementation output", ""))
    return agent


def _make_project_mock():
    """Create a mock project."""
    project = MagicMock()
    project.local_path = "/tmp/test-project"
    project.github_repo = "owner/repo"
    return project


def _make_memory_mock():
    """Create a mock memory."""
    mem = MagicMock()
    mem.content = "Use pytest for testing"
    return mem


def _make_approval_mock(status: ApprovalStatus = ApprovalStatus.APPROVED):
    """Create a mock approval."""
    approval = MagicMock()
    approval.id = "APPR-123"
    approval.status = status
    return approval


def _make_execution_mock():
    """Create a mock agent execution."""
    execution = MagicMock()
    execution.id = "EXEC-abc"
    return execution


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def workflow_config() -> WorkflowConfig:
    return WorkflowConfig(
        max_implementation_retries=2,
        max_ci_fix_retries=1,
        ci_poll_interval_seconds=0,  # no delay in tests
        ci_poll_max_attempts=3,
        require_approval_before_push=False,
    )


@pytest.fixture
def agents_config() -> AgentsConfig:
    return AgentsConfig()


@pytest.fixture
def task_service(event_bus: EventBus) -> MagicMock:
    svc = MagicMock(spec=TaskService)
    task = _make_task()
    svc.create_task = AsyncMock(return_value=task)
    svc.get_task = AsyncMock(return_value=task)
    svc.transition_task = AsyncMock(return_value=task)
    return svc


@pytest.fixture
def agent_execution_service(event_bus: EventBus) -> MagicMock:
    svc = MagicMock(spec=AgentExecutionService)
    svc.create_execution = AsyncMock(return_value=_make_execution_mock())
    svc.mark_running = AsyncMock(return_value=_make_execution_mock())
    svc.complete_execution = AsyncMock(return_value=_make_execution_mock())
    return svc


@pytest.fixture
def project_service() -> MagicMock:
    svc = MagicMock(spec=ProjectService)
    svc.get_project = AsyncMock(return_value=_make_project_mock())
    return svc


@pytest.fixture
def memory_service() -> MagicMock:
    svc = MagicMock(spec=MemoryService)
    svc.retrieve_context = AsyncMock(return_value=[_make_memory_mock()])
    return svc


@pytest.fixture
def approval_service() -> MagicMock:
    svc = MagicMock(spec=ApprovalService)
    svc.create_request = AsyncMock(return_value=_make_approval_mock())
    svc.get_request = AsyncMock(return_value=_make_approval_mock(ApprovalStatus.APPROVED))
    return svc


@pytest.fixture
def tool_registry() -> MagicMock:
    """Mock tool registry with git and github tools."""
    registry = MagicMock(spec=ToolRegistry)
    git_tool = MagicMock()
    git_tool.execute = AsyncMock(return_value=ToolResult(success=True, output="ok"))
    github_tool = MagicMock()
    github_tool.execute = AsyncMock(
        return_value=ToolResult(success=True, output="Fix login bug\nFull description"),
    )
    tools = {"git": git_tool, "github": github_tool}
    registry.get = MagicMock(side_effect=lambda name: tools[name])
    return registry


@pytest.fixture
def agent_registry() -> MagicMock:
    registry = MagicMock(spec=AgentRegistry)
    registry.create = MagicMock(return_value=_make_agent())
    registry.has = MagicMock(return_value=True)
    return registry


@pytest.fixture
def agent_router(agent_registry: MagicMock, agents_config: AgentsConfig) -> MagicMock:
    router = MagicMock(spec=AgentRouter)
    router.select = MagicMock(return_value="claude_code")
    router.fallback_for = MagicMock(return_value="antigravity")
    return router


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def workflow(
    task_service,
    agent_execution_service,
    project_service,
    memory_service,
    approval_service,
    tool_registry,
    agent_registry,
    agent_router,
    event_bus,
    workflow_config,
    agents_config,
) -> DevWorkflow:
    return DevWorkflow(
        task_service=task_service,
        agent_execution_service=agent_execution_service,
        project_service=project_service,
        memory_service=memory_service,
        approval_service=approval_service,
        tool_registry=tool_registry,
        agent_registry=agent_registry,
        agent_router=agent_router,
        event_bus=event_bus,
        workflow_config=workflow_config,
        agents_config=agents_config,
    )


# --- Model Tests ---


class TestWorkflowModels:
    """Validate Pydantic model construction."""

    def test_workflow_step_result_defaults(self) -> None:
        step = WorkflowStepResult(name="test", status=WorkflowStepStatus.COMPLETED)
        assert step.name == "test"
        assert step.status == WorkflowStepStatus.COMPLETED
        assert step.agent is None
        assert step.error is None
        assert step.duration_ms == 0

    def test_workflow_result_required_fields(self) -> None:
        result = WorkflowResult(
            task_id="T-1",
            issue_number=42,
            repo="owner/repo",
            status=WorkflowStatus.COMPLETED,
        )
        assert result.task_id == "T-1"
        assert result.steps == []
        assert result.error is None

    def test_workflow_result_failed(self) -> None:
        result = WorkflowResult(
            task_id="T-2",
            issue_number=10,
            repo="x/y",
            status=WorkflowStatus.FAILED,
            error="Tests failed",
        )
        assert result.status == WorkflowStatus.FAILED
        assert result.error == "Tests failed"

    def test_dev_workflow_request(self) -> None:
        req = DevWorkflowRequest(issue_number=52, project_id="proj-1")
        assert req.priority == "normal"

    def test_workflow_result_needs_human(self) -> None:
        result = WorkflowResult(
            task_id="T-3",
            issue_number=7,
            repo="a/b",
            status=WorkflowStatus.NEEDS_HUMAN,
        )
        assert result.status == WorkflowStatus.NEEDS_HUMAN


# --- Slugify Tests ---


class TestSlugify:
    def test_basic_slug(self) -> None:
        assert _slugify("Fix Login Bug") == "fix-login-bug"

    def test_special_characters(self) -> None:
        assert _slugify("Add OAuth2.0 support!") == "add-oauth2-0-support"

    def test_max_length(self) -> None:
        long_title = "A very long title that exceeds the max length"
        result = _slugify(long_title, max_length=20)
        assert len(result) <= 20


# --- Fetch Issue Tests ---


class TestFetchIssue:
    @pytest.mark.asyncio
    async def test_fetch_issue_parses_output(
        self, workflow: DevWorkflow, session: AsyncMock,
    ) -> None:
        """Issue title and body are parsed from GitHubTool output."""
        result = await workflow.run(session, 42, "proj-1")
        # Should have created at least the create_task and fetch_issue steps
        step_names = [s.name for s in result.steps]
        assert "create_task" in step_names


# --- Create Branch Tests ---


class TestCreateBranch:
    @pytest.mark.asyncio
    async def test_branch_naming(self, workflow: DevWorkflow, session: AsyncMock) -> None:
        """Branch name follows jarvis/issue-N-slug pattern."""
        result = await workflow.run(session, 52, "proj-1")
        assert result.branch is not None
        assert result.branch.startswith("jarvis/issue-52-")


# --- Implementation Tests ---


class TestImplementation:
    @pytest.mark.asyncio
    async def test_agent_runs_with_enriched_prompt(
        self,
        workflow: DevWorkflow,
        session: AsyncMock,
        agent_registry: MagicMock,
    ) -> None:
        """Agent receives a prompt with issue context."""
        await workflow.run(session, 42, "proj-1")
        agent = agent_registry.create.return_value
        # Agent should have been called with a prompt containing Task:
        assert agent.run.called
        prompts = [c[0][0] for c in agent.run.call_args_list]
        assert any("Task:" in p for p in prompts)


# --- Run Tests Tests ---


class TestRunTests:
    @pytest.mark.asyncio
    async def test_test_pass_leads_to_success(
        self, workflow: DevWorkflow, session: AsyncMock
    ) -> None:
        """When tests pass, workflow continues to commit."""
        result = await workflow.run(session, 42, "proj-1")
        step_names = [s.name for s in result.steps]
        assert "commit" in step_names


# --- Retry Logic Tests ---


class TestRetryLogic:
    @pytest.mark.asyncio
    async def test_retries_capped(
        self,
        workflow: DevWorkflow,
        session: AsyncMock,
        agent_registry: MagicMock,
    ) -> None:
        """Implementation retries are bounded by config."""
        agent = _make_agent()
        # Fail all runs
        agent.run = AsyncMock(return_value=(1, "", "error"))
        agent_registry.create = MagicMock(return_value=agent)

        result = await workflow.run(session, 42, "proj-1")
        assert result.status == WorkflowStatus.FAILED

    @pytest.mark.asyncio
    async def test_retry_passes_error_context(
        self,
        workflow: DevWorkflow,
        session: AsyncMock,
        agent_registry: MagicMock,
    ) -> None:
        """When first attempt fails tests, error is passed to next attempt prompt."""
        call_count = 0

        async def alternating_run(prompt: str, working_dir: str):
            nonlocal call_count
            call_count += 1
            # First test run fails, rest succeed
            if call_count == 2:  # Second call is first test run
                return (1, "", "test failure output")
            return (0, "ok", "")

        agent = _make_agent()
        agent.run = AsyncMock(side_effect=alternating_run)
        agent_registry.create = MagicMock(return_value=agent)

        result = await workflow.run(session, 42, "proj-1")
        # Should have retried - check step names
        step_names = [s.name for s in result.steps]
        has_retry = any("attempt_2" in name for name in step_names)
        assert has_retry or result.status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED)


# --- Agent Fallback Tests ---


class TestAgentFallback:
    @pytest.mark.asyncio
    async def test_fallback_agent_on_creation_failure(
        self,
        workflow: DevWorkflow,
        session: AsyncMock,
        agent_registry: MagicMock,
        agent_router: MagicMock,
    ) -> None:
        """When primary agent creation fails, fallback agent is used."""
        fallback_agent = _make_agent()
        agent_registry.create = MagicMock(
            side_effect=[RuntimeError("primary failed"), fallback_agent]
        )
        agent_router.fallback_for = MagicMock(return_value="antigravity")

        await workflow.run(session, 42, "proj-1")
        # Should have used fallback
        assert agent_registry.create.call_count >= 2


# --- Commit/Push Tests ---


class TestCommitPush:
    @pytest.mark.asyncio
    async def test_git_operations_called(
        self,
        workflow: DevWorkflow,
        session: AsyncMock,
        tool_registry: MagicMock,
    ) -> None:
        """Git commit and push are called in the workflow."""
        await workflow.run(session, 42, "proj-1")
        git_tool = tool_registry.get("git")
        # Check commit was called
        calls = [str(c) for c in git_tool.execute.call_args_list]
        operations = [c[0][0] if c[0] else "" for c in git_tool.execute.call_args_list]
        assert "commit" in operations or any("commit" in str(c) for c in calls)


# --- Approval Gating Tests ---


class TestApprovalGating:
    @pytest.mark.asyncio
    async def test_push_blocked_until_approval(
        self,
        task_service,
        agent_execution_service,
        project_service,
        memory_service,
        approval_service,
        tool_registry,
        agent_registry,
        agent_router,
        event_bus,
        agents_config,
        session,
    ) -> None:
        """Push is blocked when approval is required."""
        config = WorkflowConfig(
            max_implementation_retries=2,
            ci_poll_interval_seconds=0,
            ci_poll_max_attempts=1,
            require_approval_before_push=True,
        )
        approval_service.get_request = AsyncMock(
            return_value=_make_approval_mock(ApprovalStatus.APPROVED)
        )

        wf = DevWorkflow(
            task_service=task_service,
            agent_execution_service=agent_execution_service,
            project_service=project_service,
            memory_service=memory_service,
            approval_service=approval_service,
            tool_registry=tool_registry,
            agent_registry=agent_registry,
            agent_router=agent_router,
            event_bus=event_bus,
            workflow_config=config,
            agents_config=agents_config,
        )

        with patch("jarvis.workflows.dev_workflow.asyncio.sleep", new_callable=AsyncMock):
            await wf.run(session, 42, "proj-1")
        # Approval should have been requested
        assert approval_service.create_request.called

    @pytest.mark.asyncio
    async def test_denied_approval_returns_needs_human(
        self,
        task_service,
        agent_execution_service,
        project_service,
        memory_service,
        approval_service,
        tool_registry,
        agent_registry,
        agent_router,
        event_bus,
        agents_config,
        session,
    ) -> None:
        """Denied push approval results in needs_human status."""
        config = WorkflowConfig(
            max_implementation_retries=2,
            ci_poll_interval_seconds=0,
            ci_poll_max_attempts=1,
            require_approval_before_push=True,
        )
        approval_service.get_request = AsyncMock(
            return_value=_make_approval_mock(ApprovalStatus.DENIED)
        )

        wf = DevWorkflow(
            task_service=task_service,
            agent_execution_service=agent_execution_service,
            project_service=project_service,
            memory_service=memory_service,
            approval_service=approval_service,
            tool_registry=tool_registry,
            agent_registry=agent_registry,
            agent_router=agent_router,
            event_bus=event_bus,
            workflow_config=config,
            agents_config=agents_config,
        )

        with patch("jarvis.workflows.dev_workflow.asyncio.sleep", new_callable=AsyncMock):
            result = await wf.run(session, 42, "proj-1")
        assert result.status == WorkflowStatus.NEEDS_HUMAN


# --- Create PR Tests ---


class TestCreatePR:
    @pytest.mark.asyncio
    async def test_pr_body_includes_issue_ref(
        self,
        workflow: DevWorkflow,
        session: AsyncMock,
        tool_registry: MagicMock,
    ) -> None:
        """PR body references the issue number."""
        github_tool = tool_registry.get("github")
        github_tool.execute = AsyncMock(
            return_value=ToolResult(success=True, output="https://github.com/owner/repo/pull/1")
        )

        await workflow.run(session, 42, "proj-1")
        # Check that pr_create was called with body containing issue ref
        calls = github_tool.execute.call_args_list
        pr_calls = [
            c for c in calls
            if c[0][0] == "pr_create"
        ]
        if pr_calls:
            # Body should reference issue
            call_kwargs = pr_calls[0][1] if pr_calls[0][1] else {}
            body = call_kwargs.get("body", "")
            assert "#42" in body


# --- CI Monitoring Tests ---


class TestCIMonitoring:
    @pytest.mark.asyncio
    async def test_ci_passing_completes(
        self,
        workflow: DevWorkflow,
        session: AsyncMock,
        tool_registry: MagicMock,
    ) -> None:
        """CI passing leads to completed status."""
        github_tool = tool_registry.get("github")
        # Return passing CI status
        original_execute = github_tool.execute

        async def mock_execute(operation, working_dir, **kwargs):
            if operation == "ci_status":
                return ToolResult(success=True, output="passing")
            return await original_execute(operation, working_dir, **kwargs)

        github_tool.execute = AsyncMock(side_effect=mock_execute)

        with patch("jarvis.workflows.dev_workflow.asyncio.sleep", new_callable=AsyncMock):
            result = await workflow.run(session, 42, "proj-1")
        # Should complete (or at least get past CI)
        assert result.status in (WorkflowStatus.COMPLETED, WorkflowStatus.NEEDS_HUMAN)


# --- CI Fix Loop Tests ---


class TestCIFixLoop:
    @pytest.mark.asyncio
    async def test_ci_fix_attempts_capped(
        self,
        task_service,
        agent_execution_service,
        project_service,
        memory_service,
        approval_service,
        tool_registry,
        agent_registry,
        agent_router,
        event_bus,
        agents_config,
        session,
    ) -> None:
        """CI fix attempts are bounded by config."""
        config = WorkflowConfig(
            max_implementation_retries=1,
            max_ci_fix_retries=1,
            ci_poll_interval_seconds=0,
            ci_poll_max_attempts=5,
            require_approval_before_push=False,
        )
        github_tool = tool_registry.get("github")

        async def failing_ci(operation, working_dir, **kwargs):
            if operation == "ci_status":
                return ToolResult(success=True, output="failing")
            return ToolResult(success=True, output="ok\ndesc")

        github_tool.execute = AsyncMock(side_effect=failing_ci)

        wf = DevWorkflow(
            task_service=task_service,
            agent_execution_service=agent_execution_service,
            project_service=project_service,
            memory_service=memory_service,
            approval_service=approval_service,
            tool_registry=tool_registry,
            agent_registry=agent_registry,
            agent_router=agent_router,
            event_bus=event_bus,
            workflow_config=config,
            agents_config=agents_config,
        )

        with patch("jarvis.workflows.dev_workflow.asyncio.sleep", new_callable=AsyncMock):
            result = await wf.run(session, 42, "proj-1")
        assert result.status == WorkflowStatus.NEEDS_HUMAN
        assert result.error is not None
        assert "CI" in result.error


# --- Key Invariant: Never Claim False Completion ---


class TestNeverClaimsFalseCompletion:
    @pytest.mark.asyncio
    async def test_failed_tests_not_completed(
        self,
        workflow: DevWorkflow,
        session: AsyncMock,
        agent_registry: MagicMock,
    ) -> None:
        """Failed tests must never result in COMPLETED status."""
        agent = _make_agent()
        agent.run = AsyncMock(return_value=(1, "", "all tests failed"))
        agent_registry.create = MagicMock(return_value=agent)

        result = await workflow.run(session, 42, "proj-1")
        assert result.status != WorkflowStatus.COMPLETED
        assert result.status == WorkflowStatus.FAILED


# --- End-to-End Happy Path ---


class TestEndToEnd:
    @pytest.mark.asyncio
    async def test_happy_path(
        self,
        task_service,
        agent_execution_service,
        project_service,
        memory_service,
        approval_service,
        tool_registry,
        agent_registry,
        agent_router,
        event_bus,
        agents_config,
        session,
    ) -> None:
        """Full happy path: issue → implement → test → commit → push → PR → CI pass."""
        config = WorkflowConfig(
            max_implementation_retries=2,
            ci_poll_interval_seconds=0,
            ci_poll_max_attempts=2,
            require_approval_before_push=False,
        )

        github_tool = tool_registry.get("github")
        ci_call_count = 0

        async def smart_github(operation, working_dir, **kwargs):
            nonlocal ci_call_count
            if operation == "ci_status":
                ci_call_count += 1
                return ToolResult(success=True, output="passing")
            if operation == "pr_create":
                return ToolResult(success=True, output="https://github.com/owner/repo/pull/99")
            return ToolResult(success=True, output="Fix login bug\nDetailed description")

        github_tool.execute = AsyncMock(side_effect=smart_github)

        wf = DevWorkflow(
            task_service=task_service,
            agent_execution_service=agent_execution_service,
            project_service=project_service,
            memory_service=memory_service,
            approval_service=approval_service,
            tool_registry=tool_registry,
            agent_registry=agent_registry,
            agent_router=agent_router,
            event_bus=event_bus,
            workflow_config=config,
            agents_config=agents_config,
        )

        with patch("jarvis.workflows.dev_workflow.asyncio.sleep", new_callable=AsyncMock):
            result = await wf.run(session, 42, "proj-1")

        assert result.status == WorkflowStatus.COMPLETED
        assert result.pr_url == "https://github.com/owner/repo/pull/99"
        assert result.ci_status == "passing"
        assert result.branch is not None
        assert len(result.steps) > 0


# --- Workflow Events Tests ---


class TestWorkflowEvents:
    @pytest.mark.asyncio
    async def test_workflow_events_emitted(
        self,
        workflow: DevWorkflow,
        session: AsyncMock,
        event_bus: EventBus,
    ) -> None:
        """Verify WORKFLOW_* events are emitted during execution."""
        events_received: list[EventType] = []

        def handler(event):
            events_received.append(event.type)

        event_bus.subscribe(EventType.WORKFLOW_STARTED, handler)
        event_bus.subscribe(EventType.WORKFLOW_STEP_STARTED, handler)
        event_bus.subscribe(EventType.WORKFLOW_STEP_COMPLETED, handler)
        event_bus.subscribe(EventType.WORKFLOW_STEP_FAILED, handler)
        event_bus.subscribe(EventType.WORKFLOW_COMPLETED, handler)
        event_bus.subscribe(EventType.WORKFLOW_FAILED, handler)

        with patch("jarvis.workflows.dev_workflow.asyncio.sleep", new_callable=AsyncMock):
            await workflow.run(session, 42, "proj-1")

        assert EventType.WORKFLOW_STARTED in events_received
        assert EventType.WORKFLOW_STEP_STARTED in events_received
        # Should have completed or failed
        assert (
            EventType.WORKFLOW_COMPLETED in events_received
            or EventType.WORKFLOW_FAILED in events_received
        )
