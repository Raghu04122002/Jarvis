"""DevWorkflow — multi-step orchestration for the full software engineering lifecycle.

Orchestrates: fetch issue → implement → test → commit → PR → monitor CI → fix → report.
Composes existing tools, agents, and services — no new infrastructure.
"""

import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.agents.base import BaseAgent
from jarvis.agents.registry import AgentRegistry
from jarvis.agents.router import AgentRouter
from jarvis.config import AgentsConfig, WorkflowConfig
from jarvis.events import Event, EventBus, EventType
from jarvis.models.approval import ApprovalStatus, RiskLevel
from jarvis.models.task import TaskPriority, TaskStatus
from jarvis.services.agent_execution_service import AgentExecutionService
from jarvis.services.approval_service import ApprovalService
from jarvis.services.memory_service import MemoryService
from jarvis.services.project_service import ProjectService
from jarvis.services.task_service import TaskService
from jarvis.tools.registry import ToolRegistry
from jarvis.workflows.models import (
    WorkflowResult,
    WorkflowStatus,
    WorkflowStepResult,
    WorkflowStepStatus,
)

logger = logging.getLogger(__name__)


def _slugify(text: str, max_length: int = 40) -> str:
    """Convert text to a URL-safe slug for branch names."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_length].rstrip("-")


class DevWorkflow:
    """Multi-step orchestration engine for software engineering tasks.

    Takes all existing services/registries as dependencies and composes them
    into a full dev lifecycle: issue → implement → test → commit → PR → CI.
    """

    def __init__(
        self,
        task_service: TaskService,
        agent_execution_service: AgentExecutionService,
        project_service: ProjectService,
        memory_service: MemoryService,
        approval_service: ApprovalService,
        tool_registry: ToolRegistry,
        agent_registry: AgentRegistry,
        agent_router: AgentRouter,
        event_bus: EventBus,
        workflow_config: WorkflowConfig,
        agents_config: AgentsConfig,
    ) -> None:
        self._task_service = task_service
        self._agent_execution_service = agent_execution_service
        self._project_service = project_service
        self._memory_service = memory_service
        self._approval_service = approval_service
        self._tool_registry = tool_registry
        self._agent_registry = agent_registry
        self._agent_router = agent_router
        self._event_bus = event_bus
        self._config = workflow_config
        self._agents_config = agents_config

    async def run(
        self,
        session: AsyncSession,
        request_issue: int,
        project_id: str,
        priority: str = "normal",
    ) -> WorkflowResult:
        """Run the full dev workflow for a GitHub issue."""
        steps: list[WorkflowStepResult] = []
        task_id = ""
        repo = ""
        working_dir = ""
        branch = ""
        pr_url: str | None = None
        ci_status: str | None = None
        changes_summary = ""
        test_summary = ""
        issue_title = ""
        issue_body = ""

        try:
            task_priority = TaskPriority(priority)
        except ValueError:
            task_priority = TaskPriority.NORMAL

        # --- Step 1: Create task ---
        step, task_id = await self._run_step(
            "create_task",
            steps,
            task_id="",
            coro_fn=lambda: self._create_task(session, request_issue, project_id, task_priority),
        )
        if step.status == WorkflowStepStatus.FAILED:
            return self._build_result(
                task_id, request_issue, repo, WorkflowStatus.FAILED, steps=steps, error=step.error
            )

        self._event_bus.publish(
            Event(
                type=EventType.WORKFLOW_STARTED,
                task_id=task_id,
                data={"issue_number": request_issue},
            )
        )

        # Transition to PLANNING then RUNNING
        await self._task_service.transition_task(session, task_id, TaskStatus.PLANNING)
        await self._task_service.transition_task(session, task_id, TaskStatus.RUNNING)

        # --- Step 2: Fetch issue ---
        step, issue_data = await self._run_step(
            "fetch_issue",
            steps,
            task_id=task_id,
            coro_fn=lambda: self._fetch_issue(request_issue, working_dir=""),
        )
        if step.status == WorkflowStepStatus.FAILED:
            return await self._fail_workflow(
                session,
                task_id,
                request_issue,
                repo,
                steps,
                step.error,
            )

        # --- Step 3: Resolve project ---
        step, project_data = await self._run_step(
            "resolve_project",
            steps,
            task_id=task_id,
            coro_fn=lambda: self._resolve_project(session, project_id),
        )
        if step.status == WorkflowStepStatus.FAILED:
            return await self._fail_workflow(
                session,
                task_id,
                request_issue,
                repo,
                steps,
                step.error,
            )

        working_dir = project_data.get("working_dir", "")
        repo = project_data.get("repo", "")
        issue_title = issue_data.get("title", f"Issue #{request_issue}")
        issue_body = issue_data.get("body", "")

        # Re-fetch issue with correct working_dir for gh CLI
        if working_dir:
            step2, issue_data2 = await self._run_step(
                "fetch_issue_with_repo",
                steps,
                task_id=task_id,
                coro_fn=lambda: self._fetch_issue(request_issue, working_dir),
            )
            if step2.status == WorkflowStepStatus.COMPLETED:
                issue_title = issue_data2.get("title", issue_title)
                issue_body = issue_data2.get("body", issue_body)

        # --- Step 4: Retrieve memory context ---
        step, context_memories = await self._run_step(
            "retrieve_memory",
            steps,
            task_id=task_id,
            coro_fn=lambda: self._retrieve_memory(session, issue_title, project_id),
        )
        # Memory retrieval failure is non-fatal
        if step.status == WorkflowStepStatus.FAILED:
            context_memories = []

        # --- Step 5: Create branch ---
        slug = _slugify(issue_title)
        branch = f"{self._config.branch_prefix}/issue-{request_issue}-{slug}"
        step, _ = await self._run_step(
            "create_branch",
            steps,
            task_id=task_id,
            coro_fn=lambda: self._create_branch(working_dir, branch),
        )
        if step.status == WorkflowStepStatus.FAILED:
            return await self._fail_workflow(
                session,
                task_id,
                request_issue,
                repo,
                steps,
                step.error,
            )

        # --- Step 6: Implementation loop ---
        implementation_succeeded = False
        test_errors: list[str] = []

        for attempt in range(self._config.max_implementation_retries):
            # Build prompt with context
            prompt = self._build_implementation_prompt(
                issue_title, issue_body, context_memories, test_errors if test_errors else None
            )

            # Run agent
            step, agent_output = await self._run_step(
                f"implement_attempt_{attempt + 1}",
                steps,
                task_id=task_id,
                coro_fn=lambda p=prompt: self._run_agent(session, task_id, p, working_dir),
            )
            if step.status == WorkflowStepStatus.FAILED:
                if attempt < self._config.max_implementation_retries - 1:
                    test_errors.append(f"Agent error: {step.error}")
                    continue
                return await self._fail_workflow(
                    session, task_id, request_issue, repo, steps, step.error, branch=branch
                )

            # Run tests
            test_prompt = f"Run the test suite: {self._config.test_command}"
            step, test_output = await self._run_step(
                f"test_attempt_{attempt + 1}",
                steps,
                task_id=task_id,
                coro_fn=lambda tp=test_prompt: self._run_agent(session, task_id, tp, working_dir),
            )
            test_summary = test_output if isinstance(test_output, str) else str(test_output)

            if step.status == WorkflowStepStatus.COMPLETED:
                implementation_succeeded = True
                break
            else:
                error_msg = step.error or "Tests failed"
                test_errors.append(error_msg)
                if attempt >= self._config.max_implementation_retries - 1:
                    return await self._fail_workflow(
                        session,
                        task_id,
                        request_issue,
                        repo,
                        steps,
                        f"Tests failed after {self._config.max_implementation_retries} attempts",
                        branch=branch,
                        test_summary=test_summary,
                    )

        if not implementation_succeeded:
            return await self._fail_workflow(
                session,
                task_id,
                request_issue,
                repo,
                steps,
                "Implementation failed",
                branch=branch,
            )

        # --- Step 7: Inspect diff ---
        step, diff_output = await self._run_step(
            "inspect_diff",
            steps,
            task_id=task_id,
            coro_fn=lambda: self._git_operation(working_dir, "diff"),
        )
        changes_summary = diff_output if isinstance(diff_output, str) else ""

        # --- Step 8: Commit ---
        commit_message = f"feat: resolve issue #{request_issue} — {issue_title}"
        step, _ = await self._run_step(
            "commit",
            steps,
            task_id=task_id,
            coro_fn=lambda: self._git_operation(working_dir, "commit", message=commit_message),
        )
        if step.status == WorkflowStepStatus.FAILED:
            return await self._fail_workflow(
                session, task_id, request_issue, repo, steps, step.error, branch=branch
            )

        # --- Step 9: Push (approval-gated) ---
        if self._config.require_approval_before_push:
            step, approved = await self._run_step(
                "approval_for_push",
                steps,
                task_id=task_id,
                coro_fn=lambda: self._request_push_approval(session, task_id, branch, repo),
            )
            if step.status == WorkflowStepStatus.FAILED or not approved:
                return await self._finish_workflow(
                    session,
                    task_id,
                    request_issue,
                    repo,
                    WorkflowStatus.NEEDS_HUMAN,
                    steps,
                    branch=branch,
                    changes_summary=changes_summary,
                    test_summary=test_summary,
                    error="Push approval denied or failed",
                )

        step, _ = await self._run_step(
            "push",
            steps,
            task_id=task_id,
            coro_fn=lambda: self._git_operation(working_dir, "push"),
        )
        if step.status == WorkflowStepStatus.FAILED:
            return await self._fail_workflow(
                session, task_id, request_issue, repo, steps, step.error, branch=branch
            )

        # --- Step 10: Create PR ---
        pr_body = f"Resolves #{request_issue}\n\n{changes_summary[:500]}"
        step, pr_result = await self._run_step(
            "create_pr",
            steps,
            task_id=task_id,
            coro_fn=lambda: self._create_pr(working_dir, issue_title, pr_body, repo),
        )
        if step.status == WorkflowStepStatus.COMPLETED and isinstance(pr_result, str):
            pr_url = pr_result

        # --- Step 11: CI monitoring loop ---
        ci_fix_attempts = 0
        for poll in range(self._config.ci_poll_max_attempts):
            await asyncio.sleep(self._config.ci_poll_interval_seconds)

            step, ci_result = await self._run_step(
                f"ci_poll_{poll + 1}",
                steps,
                task_id=task_id,
                coro_fn=lambda: self._check_ci_status(working_dir, branch, repo),
            )
            ci_status = ci_result if isinstance(ci_result, str) else None

            if ci_status == "passing":
                break
            elif ci_status == "failing":
                if ci_fix_attempts >= self._config.max_ci_fix_retries:
                    return await self._finish_workflow(
                        session,
                        task_id,
                        request_issue,
                        repo,
                        WorkflowStatus.NEEDS_HUMAN,
                        steps,
                        branch=branch,
                        pr_url=pr_url,
                        ci_status=ci_status,
                        changes_summary=changes_summary,
                        test_summary=test_summary,
                        error="CI failed after max fix retries",
                    )
                ci_fix_attempts += 1
                fix_prompt = f"CI is failing on branch {branch}. Fix the failures and commit."
                step, _ = await self._run_step(
                    f"ci_fix_{ci_fix_attempts}",
                    steps,
                    task_id=task_id,
                    coro_fn=lambda fp=fix_prompt: self._run_agent(
                        session,
                        task_id,
                        fp,
                        working_dir,
                    ),
                )
                if step.status == WorkflowStepStatus.COMPLETED:
                    await self._run_step(
                        f"ci_fix_push_{ci_fix_attempts}",
                        steps,
                        task_id=task_id,
                        coro_fn=lambda: self._git_operation(working_dir, "push"),
                    )
            # "pending" → continue polling
        else:
            # Polling exhausted without pass
            ci_status = "timeout"

        # --- Step 12: Build final result ---
        if ci_status == "passing":
            final_status = WorkflowStatus.COMPLETED
        else:
            final_status = WorkflowStatus.NEEDS_HUMAN
        return await self._finish_workflow(
            session,
            task_id,
            request_issue,
            repo,
            final_status,
            steps,
            branch=branch,
            pr_url=pr_url,
            ci_status=ci_status,
            changes_summary=changes_summary,
            test_summary=test_summary,
        )

    # --- Step helper ---

    async def _run_step(
        self,
        name: str,
        steps: list[WorkflowStepResult],
        *,
        task_id: str,
        coro_fn: Callable[[], Awaitable[object]],
    ) -> tuple[WorkflowStepResult, object]:
        """Wrap a step coroutine with timing, events, and error capture."""
        self._event_bus.publish(
            Event(
                type=EventType.WORKFLOW_STEP_STARTED,
                task_id=task_id or "pending",
                data={"step": name},
            )
        )
        start = time.monotonic()
        try:
            result = await coro_fn()
            duration_ms = (time.monotonic() - start) * 1000
            step = WorkflowStepResult(
                name=name,
                status=WorkflowStepStatus.COMPLETED,
                output=str(result)[:2000] if result else "",
                duration_ms=duration_ms,
            )
            steps.append(step)
            self._event_bus.publish(
                Event(
                    type=EventType.WORKFLOW_STEP_COMPLETED,
                    task_id=task_id or "pending",
                    data={"step": name, "duration_ms": duration_ms},
                )
            )
            return step, result
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            error_str = str(exc)
            step = WorkflowStepResult(
                name=name,
                status=WorkflowStepStatus.FAILED,
                error=error_str,
                duration_ms=duration_ms,
            )
            steps.append(step)
            self._event_bus.publish(
                Event(
                    type=EventType.WORKFLOW_STEP_FAILED,
                    task_id=task_id or "pending",
                    data={"step": name, "error": error_str},
                )
            )
            logger.warning("Workflow step %r failed: %s", name, error_str)
            return step, None

    # --- Internal step implementations ---

    async def _create_task(
        self, session: AsyncSession, issue_number: int, project_id: str, priority: TaskPriority
    ) -> str:
        """Create a task for this workflow and return its ID."""
        task = await self._task_service.create_task(
            session,
            request=f"Resolve GitHub issue #{issue_number}",
            title=f"Dev workflow: issue #{issue_number}",
            project_id=project_id,
            priority=priority,
            metadata={"workflow": "dev", "issue_number": str(issue_number)},
        )
        return task.id

    async def _fetch_issue(self, issue_number: int, working_dir: str) -> dict[str, str]:
        """Fetch issue details via GitHubTool."""
        github_tool = self._tool_registry.get("github")
        result = await github_tool.execute("issue_view", working_dir or ".", number=issue_number)
        if not result.success:
            raise RuntimeError(f"Failed to fetch issue: {result.error}")
        # Parse title from first line, body from rest
        lines = result.output.strip().split("\n", 1)
        title = lines[0].strip() if lines else f"Issue #{issue_number}"
        body = lines[1].strip() if len(lines) > 1 else ""
        return {"title": title, "body": body}

    async def _resolve_project(self, session: AsyncSession, project_id: str) -> dict[str, str]:
        """Resolve project to get working directory and repo."""
        project = await self._project_service.get_project(session, project_id)
        return {
            "working_dir": project.local_path,
            "repo": project.github_repo or "",
        }

    async def _retrieve_memory(
        self, session: AsyncSession, query: str, project_id: str
    ) -> list[str]:
        """Retrieve relevant memories for context."""
        memories = await self._memory_service.retrieve_context(
            session, query, project_id=project_id
        )
        return [m.content for m in memories]

    async def _create_branch(self, working_dir: str, branch_name: str) -> str:
        """Create a new git branch."""
        git_tool = self._tool_registry.get("git")
        result = await git_tool.execute("create_branch", working_dir, branch=branch_name)
        if not result.success:
            raise RuntimeError(f"Failed to create branch: {result.error}")
        return branch_name

    async def _run_agent(
        self, session: AsyncSession, task_id: str, prompt: str, working_dir: str
    ) -> str:
        """Run an agent and track execution. Returns stdout on success."""
        # Select agent
        task = await self._task_service.get_task(session, task_id)
        agent_name = self._agent_router.select(task)

        # Create agent, with fallback
        agent: BaseAgent | None = None
        try:
            agent = self._agent_registry.create(agent_name, self._agents_config)
        except Exception:
            fallback = self._agent_router.fallback_for(agent_name)
            if fallback:
                agent = self._agent_registry.create(fallback, self._agents_config)
                agent_name = fallback
            else:
                raise

        assert agent is not None

        # Track execution
        execution = await self._agent_execution_service.create_execution(
            session, task_id, agent_name, prompt, working_dir
        )
        await self._agent_execution_service.mark_running(session, execution.id)

        start = time.monotonic()
        try:
            exit_code, stdout, stderr = await agent.run(prompt, working_dir)
            duration_ms = (time.monotonic() - start) * 1000
            await self._agent_execution_service.complete_execution(
                session,
                execution.id,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration_ms,
            )
            if exit_code != 0:
                raise RuntimeError(f"Agent exited with code {exit_code}: {stderr[:500]}")
            return stdout
        except Exception:
            duration_ms = (time.monotonic() - start) * 1000
            await self._agent_execution_service.complete_execution(
                session,
                execution.id,
                exit_code=-1,
                stdout="",
                stderr=str(Exception),
                duration_ms=duration_ms,
            )
            raise

    async def _git_operation(self, working_dir: str, operation: str, **kwargs: str) -> str:
        """Execute a git operation and return its output."""
        git_tool = self._tool_registry.get("git")
        result = await git_tool.execute(operation, working_dir, **kwargs)
        if not result.success:
            raise RuntimeError(f"Git {operation} failed: {result.error}")
        return result.output

    async def _request_push_approval(
        self, session: AsyncSession, task_id: str, branch: str, repo: str
    ) -> bool:
        """Request approval before pushing. Returns True if approved."""
        approval = await self._approval_service.create_request(
            session,
            task_id=task_id,
            tool_name="git",
            operation="push",
            risk_level=RiskLevel.REQUIRES_APPROVAL,
            description=f"Push branch {branch} to {repo}",
            context={"branch": branch, "repo": repo},
        )
        # Poll for approval decision
        for _ in range(120):  # 10 minutes at 5s intervals
            await asyncio.sleep(5)
            updated = await self._approval_service.get_request(session, approval.id)
            if updated.status == ApprovalStatus.APPROVED:
                return True
            if updated.status in (ApprovalStatus.DENIED, ApprovalStatus.EXPIRED):
                return False
        return False

    async def _create_pr(self, working_dir: str, title: str, body: str, repo: str) -> str:
        """Create a pull request and return its URL."""
        github_tool = self._tool_registry.get("github")
        result = await github_tool.execute("pr_create", working_dir, title=title, body=body)
        if not result.success:
            raise RuntimeError(f"PR creation failed: {result.error}")
        return result.output.strip()

    async def _check_ci_status(self, working_dir: str, branch: str, repo: str) -> str:
        """Check CI status. Returns 'passing', 'failing', or 'pending'."""
        github_tool = self._tool_registry.get("github")
        result = await github_tool.execute("ci_status", working_dir, branch=branch)
        if not result.success:
            return "pending"
        output = result.output.strip().lower()
        if "pass" in output or "success" in output:
            return "passing"
        if "fail" in output or "error" in output:
            return "failing"
        return "pending"

    # --- Prompt building ---

    def _build_implementation_prompt(
        self,
        issue_title: str,
        issue_body: str,
        context_memories: list[str],
        test_errors: list[str] | None = None,
    ) -> str:
        """Build enriched prompt for the implementation agent."""
        parts = [
            f"# Task: {issue_title}",
            "",
            issue_body,
        ]
        if context_memories:
            parts.extend(["", "# Relevant Context", ""])
            for mem in context_memories:
                parts.append(f"- {mem}")
        if test_errors:
            parts.extend(["", "# Previous Errors (fix these)", ""])
            for err in test_errors:
                parts.append(f"- {err}")
        parts.extend(
            [
                "",
                "Implement the changes needed to resolve this issue.",
                "Make sure all existing tests continue to pass.",
            ]
        )
        return "\n".join(parts)

    # --- Result builders ---

    def _build_result(
        self,
        task_id: str,
        issue_number: int,
        repo: str,
        status: WorkflowStatus,
        *,
        steps: list[WorkflowStepResult],
        branch: str | None = None,
        pr_url: str | None = None,
        ci_status: str | None = None,
        changes_summary: str = "",
        test_summary: str = "",
        error: str | None = None,
    ) -> WorkflowResult:
        return WorkflowResult(
            task_id=task_id,
            issue_number=issue_number,
            repo=repo,
            status=status,
            branch=branch,
            pr_url=pr_url,
            ci_status=ci_status,
            changes_summary=changes_summary,
            test_summary=test_summary,
            steps=steps,
            error=error,
        )

    async def _fail_workflow(
        self,
        session: AsyncSession,
        task_id: str,
        issue_number: int,
        repo: str,
        steps: list[WorkflowStepResult],
        error: str | None,
        *,
        branch: str | None = None,
        test_summary: str = "",
    ) -> WorkflowResult:
        """Mark task as failed and return failure result."""
        return await self._finish_workflow(
            session,
            task_id,
            issue_number,
            repo,
            WorkflowStatus.FAILED,
            steps,
            branch=branch,
            error=error,
            test_summary=test_summary,
        )

    async def _finish_workflow(
        self,
        session: AsyncSession,
        task_id: str,
        issue_number: int,
        repo: str,
        status: WorkflowStatus,
        steps: list[WorkflowStepResult],
        *,
        branch: str | None = None,
        pr_url: str | None = None,
        ci_status: str | None = None,
        changes_summary: str = "",
        test_summary: str = "",
        error: str | None = None,
    ) -> WorkflowResult:
        """Transition task and emit final workflow event."""
        result = self._build_result(
            task_id,
            issue_number,
            repo,
            status,
            steps=steps,
            branch=branch,
            pr_url=pr_url,
            ci_status=ci_status,
            changes_summary=changes_summary,
            test_summary=test_summary,
            error=error,
        )

        # Transition task to terminal state
        if status == WorkflowStatus.COMPLETED:
            target_status = TaskStatus.COMPLETED
        else:
            target_status = TaskStatus.FAILED
        try:
            await self._task_service.transition_task(
                session,
                task_id,
                target_status,
                error=error,
                result=result.model_dump_json(),
            )
        except Exception:
            logger.exception("Failed to transition task %s", task_id)

        # Emit workflow event
        if status == WorkflowStatus.COMPLETED:
            event_type = EventType.WORKFLOW_COMPLETED
        else:
            event_type = EventType.WORKFLOW_FAILED
        self._event_bus.publish(
            Event(
                type=event_type,
                task_id=task_id,
                data={"status": status.value, "issue_number": issue_number},
            )
        )

        return result
