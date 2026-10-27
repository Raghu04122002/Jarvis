"""Jarvis Orchestrator — receives user requests, creates tasks, and manages planning."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.agents.base import AgentError, BaseAgent
from jarvis.agents.registry import AgentRegistry
from jarvis.agents.router import AgentRouter
from jarvis.config import AgentsConfig
from jarvis.events import Event, EventBus, EventType
from jarvis.models.agent import AgentExecutionStatus
from jarvis.models.project import ProjectNotFoundError
from jarvis.models.task import ChatRequest, ChatResponse, Task, TaskStatus
from jarvis.orchestrator.chat_prompt import build_system_prompt
from jarvis.orchestrator.intent import IntentResult, IntentType, classify
from jarvis.orchestrator.planner import BasePlanner, Plan, short_title
from jarvis.orchestrator.resolver import ProjectResolver
from jarvis.orchestrator.supervisor import Review, Supervisor
from jarvis.services.agent_execution_service import AgentExecutionService
from jarvis.services.ai_service import AIService, AIServiceError
from jarvis.services.chat_tools import (
    Tool,
    Toolbox,
    ToolHandler,
    WebSearchBackend,
    web_search_tool,
)
from jarvis.services.memory_service import MemoryService
from jarvis.services.project_service import ProjectService
from jarvis.services.task_service import TaskService

if TYPE_CHECKING:
    from starlette.background import BackgroundTasks

    from jarvis.db.engine import Database

logger = logging.getLogger(__name__)


class Orchestrator:
    """Core orchestration engine.

    Receives user requests, classifies intent, resolves projects,
    answers queries directly, and manages the task lifecycle including
    agent dispatch.
    """

    def __init__(
        self,
        task_service: TaskService,
        planner: BasePlanner,
        project_service: ProjectService | None = None,
        agent_execution_service: AgentExecutionService | None = None,
        agents_config: AgentsConfig | None = None,
        agent_registry: AgentRegistry | None = None,
        agent_router: AgentRouter | None = None,
        event_bus: EventBus | None = None,
        memory_service: MemoryService | None = None,
        db: Database | None = None,
        ai_service: AIService | None = None,
        supervisor: Supervisor | None = None,
        review_max_rounds: int = 1,
        search_backend: WebSearchBackend | None = None,
    ) -> None:
        self._task_service = task_service
        self._planner = planner
        self._project_service = project_service
        self._agent_execution_service = agent_execution_service
        self._agents_config = agents_config or AgentsConfig()
        self._agent_registry = agent_registry
        self._agent_router = agent_router
        self._event_bus = event_bus
        self._memory_service = memory_service
        self._db = db
        self._ai_service = ai_service
        self._supervisor = supervisor
        self._review_max_rounds = max(0, review_max_rounds)
        self._search_backend = search_backend
        self._active_agents: dict[str, BaseAgent] = {}

    async def handle_chat(
        self,
        session: AsyncSession,
        chat: ChatRequest,
        *,
        background_tasks: BackgroundTasks | None = None,
    ) -> ChatResponse:
        """Process a chat message and return the complete response.

        Non-streaming wrapper around :meth:`stream_chat`.
        """
        response: ChatResponse | None = None
        async for event in self.stream_chat(session, chat, background_tasks=background_tasks):
            if event["type"] == "done":
                response = event["response"]
        assert response is not None
        return response

    async def stream_chat(
        self,
        session: AsyncSession,
        chat: ChatRequest,
        *,
        background_tasks: BackgroundTasks | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Process a chat message, yielding progress events.

        Routing:

        1. Issue-number workflows ("fix issue #12") always create a task.
        2. If an AI model is configured, it answers with tools. Small talk and
           questions are answered inline; the model calls ``create_task`` only
           for real work. The keyword classifier just adds a hint.
        3. Without a model, the keyword classifier decides: QUERY gets a
           deterministic answer, ACTION creates a task.

        Events: ``token``, ``tool_start``, ``tool_end``, ``task_created`` and a
        final ``done`` carrying a :class:`ChatResponse` under ``response``.
        """
        intent = classify(chat.message)

        resolved_project_id = chat.project_id
        if self._project_service and intent.project_hint:
            resolver = ProjectResolver(self._project_service)
            resolved_project_id = await resolver.resolve(
                session, intent.project_hint, fallback_id=chat.project_id
            )

        workflow = intent.intent == IntentType.WORKFLOW and intent.issue_number is not None
        use_ai = self._ai_service is not None and self._ai_service.available and not workflow

        if not use_ai:
            if intent.intent == IntentType.QUERY:
                answer = await self._answer_query(
                    session, intent, resolved_project_id, chat.message
                )
                yield {"type": "token", "text": answer}
                yield {"type": "done", "response": self._answered(chat.message, answer)}
                return
            task, plan = await self._create_task(
                session,
                chat,
                request=chat.message,
                title=None,
                intent=intent,
                project_id=resolved_project_id,
                background_tasks=background_tasks,
            )
            yield {"type": "task_created", "task_id": task.id, "title": task.title}
            yield {
                "type": "done",
                "response": ChatResponse(
                    task_id=task.id,
                    title=task.title,
                    status="planning",
                    plan=plan.steps,
                    answer=_task_line(task.id, task.title),
                    message="Task created and dispatching.",
                ),
            }
            return

        # --- AI path: model answers, using tools when needed ---
        assert self._ai_service is not None
        created: list[tuple[Task, Plan]] = []

        async def create_task_tool(args: dict[str, Any]) -> str:
            if created:
                return f"Task {created[0][0].id} was already created for this message."
            request = str(args.get("request") or chat.message).strip()
            title = str(args.get("title") or "").strip() or None
            task, plan = await self._create_task(
                session,
                chat,
                request=request,
                title=title,
                intent=intent,
                project_id=resolved_project_id,
                background_tasks=background_tasks,
            )
            created.append((task, plan))
            agent = task.metadata.get("agent_name", "the default agent")
            return f"Created task {task.id} '{task.title}'. It is being dispatched to {agent}."

        toolbox = self._chat_toolbox(session, create_task_tool)
        context = await self._project_context(session, resolved_project_id)
        system = build_system_prompt(
            toolbox,
            datetime.now().astimezone(),
            project_context=context if resolved_project_id else "",
            action_hint=intent.intent == IntentType.ACTION,
        )
        messages = [{"role": t.role, "content": t.content} for t in chat.history[-20:]]
        messages.append({"role": "user", "content": chat.message})

        text_parts: list[str] = []
        tool_log: list[dict[str, Any]] = []
        error: str | None = None
        try:
            async for ev in self._ai_service.stream_chat(system, messages, toolbox):
                if ev["type"] == "token":
                    text_parts.append(ev["text"])
                elif ev["type"] == "tool_start":
                    tool_log.append(
                        {
                            "id": ev["id"],
                            "name": ev["name"],
                            "label": ev["label"],
                            "args": ev["args"],
                            "status": "running",
                            "output": "",
                        }
                    )
                elif ev["type"] == "tool_end":
                    for entry in tool_log:
                        if entry["id"] == ev["id"]:
                            entry["status"] = "done" if ev["ok"] else "error"
                            entry["output"] = ev["output"]
                yield ev
                if ev["type"] == "tool_end" and ev["name"] == "create_task" and created:
                    t = created[0][0]
                    yield {"type": "task_created", "task_id": t.id, "title": t.title}
        except AIServiceError as e:
            error = str(e)

        if error is not None and not created and intent.intent == IntentType.ACTION:
            # The model is unavailable, but the keyword router is confident
            # this is real work: create the task anyway.
            task, plan = await self._create_task(
                session,
                chat,
                request=chat.message,
                title=None,
                intent=intent,
                project_id=resolved_project_id,
                background_tasks=background_tasks,
            )
            created.append((task, plan))
            yield {"type": "task_created", "task_id": task.id, "title": task.title}
            error = None

        answer = "".join(text_parts).strip()
        searched = [c for c in tool_log if c["name"] == "web_search" and c["status"] == "done"]
        if searched:
            allowed = {u for c in searched for u in _URL_RE.findall(c["output"])}
            answer = _convert_citation_markers(answer, _search_urls(searched[-1]["output"]))
            answer = _strip_unverified_links(answer, allowed)
        if error is not None:
            sep = "\n\n" if answer else ""
            answer = f"{answer}{sep}{error}"
            yield {"type": "token", "text": f"{sep}{error}"}

        if created:
            task, plan = created[0]
            line = _task_line(task.id, task.title)
            sep = "\n\n" if answer else ""
            answer = f"{answer}{sep}{line}"
            yield {"type": "token", "text": f"{sep}{line}"}
            response = ChatResponse(
                task_id=task.id,
                title=task.title,
                status="planning",
                plan=plan.steps,
                answer=answer,
                message="Task created and dispatching.",
                tool_calls=tool_log,
            )
        else:
            response = self._answered(chat.message, answer, error=error is not None)
            response.tool_calls = tool_log
        yield {"type": "done", "response": response}

    def _answered(self, message: str, answer: str, *, error: bool = False) -> ChatResponse:
        if self._event_bus is not None and not error:
            self._event_bus.publish(
                Event(
                    type=EventType.QUERY_ANSWERED,
                    task_id="",
                    data={"message": message, "answer": answer},
                )
            )
        return ChatResponse(
            title=message[:100],
            status="error" if error else "answered",
            answer=answer,
            message="AI error." if error else "Query answered.",
        )

    def _chat_toolbox(
        self,
        session: AsyncSession,
        create_task_handler: ToolHandler,
    ) -> Toolbox:
        """The exact tools the chat model gets this turn."""
        toolbox = Toolbox()
        if self._search_backend is not None:
            toolbox.add(web_search_tool(self._search_backend))
        toolbox.add(
            Tool(
                name="create_task",
                label="Creating task",
                description=(
                    "Hand real work (code changes, file operations, running or deploying "
                    "things, multi-step jobs) to a coding agent. Not for questions."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Short title, max 8 words"},
                        "request": {
                            "type": "string",
                            "description": "Full instruction for the agent",
                        },
                    },
                    "required": ["title", "request"],
                },
                handler=create_task_handler,
            )
        )

        async def list_tasks(args: dict[str, Any]) -> str:
            status = str(args.get("status") or "")
            valid = status in TaskStatus._value2member_map_
            tasks = await self._task_service.list_tasks(
                session,
                status=TaskStatus(status) if valid else None,
                limit=20,
            )
            if not tasks:
                return "No tasks."
            return "\n".join(
                f"- {t.id} [{t.status.value}] {t.title} (created {t.created_at:%Y-%m-%d %H:%M})"
                for t in tasks
            )

        toolbox.add(
            Tool(
                name="list_tasks",
                label="Checking tasks",
                description="List the user's Jarvis tasks and their status.",
                parameters={
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "description": "Optional filter, e.g. running, completed, failed",
                        }
                    },
                },
                handler=list_tasks,
            )
        )

        if self._project_service is not None:
            project_service = self._project_service

            async def list_projects(args: dict[str, Any]) -> str:
                projects = await project_service.list_projects(session, limit=50)
                if not projects:
                    return "No projects registered."
                return "\n".join(f"- {p.name} ({p.id}): {p.local_path}" for p in projects)

            toolbox.add(
                Tool(
                    name="list_projects",
                    label="Checking projects",
                    description="List the user's registered projects and their paths.",
                    parameters={"type": "object", "properties": {}},
                    handler=list_projects,
                )
            )
        return toolbox

    async def _create_task(
        self,
        session: AsyncSession,
        chat: ChatRequest,
        *,
        request: str,
        title: str | None,
        intent: IntentResult,
        project_id: str | None,
        background_tasks: BackgroundTasks | None,
    ) -> tuple[Task, Plan]:
        """Create, plan and (in the background) dispatch a task."""
        metadata: dict[str, str] = {"intent": intent.intent.value}
        if chat.conversation_id:
            metadata["conversation_id"] = chat.conversation_id
        plan: Plan | None = None
        if self._supervisor is not None:
            context = await self._project_context(session, project_id)
            ai_plan = await self._supervisor.plan(request, context)
            if ai_plan is not None:
                plan = Plan(title=short_title(title or ai_plan.title), steps=ai_plan.steps)
                metadata["planned_by"] = "supervisor"
                if ai_plan.agent:
                    metadata["agent_name"] = ai_plan.agent
                    if ai_plan.reason:
                        metadata["agent_reason"] = ai_plan.reason
        if plan is None:
            plan = self._planner.create_plan(request, context={"project_id": project_id or ""})
            if title:
                plan = Plan(title=short_title(title), steps=plan.steps)
        if intent.issue_number is not None:
            metadata["issue_number"] = str(intent.issue_number)

        task = await self._task_service.create_task(
            session,
            request=request,
            title=plan.title,
            project_id=project_id,
            priority=chat.priority,
            metadata=metadata,
        )
        logger.info("Task created: %s (intent=%s)", task.id, intent.intent.value)

        await self._task_service.transition_task(session, task.id, TaskStatus.PLANNING)
        await self._task_service.update_task_plan(session, task.id, plan.steps)
        await self._task_service.add_steps(session, task.id, plan.steps)
        # Commit now so the background dispatcher (its own session) sees the task.
        await session.commit()

        if background_tasks is not None and self._db is not None:
            if intent.intent == IntentType.WORKFLOW and intent.issue_number is not None:
                background_tasks.add_task(
                    self._run_workflow_background, task.id, intent.issue_number, project_id
                )
            else:
                background_tasks.add_task(self._dispatch_in_background, task.id)
        return task, plan

    async def _project_context(self, session: AsyncSession, project_id: str | None) -> str:
        """Short project description for the supervisor, or "" if unknown."""
        if not project_id or self._project_service is None:
            return ""
        try:
            project = await self._project_service.get_project(session, project_id)
        except ProjectNotFoundError:
            return ""
        stack = ", ".join(project.stack) if project.stack else "not specified"
        return f"Project: {project.name}\nPath: {project.local_path}\nStack: {stack}"

    async def _answer_query(
        self,
        session: AsyncSession,
        intent: object,
        project_id: str | None,
        original_message: str = "",
    ) -> str:
        """Generate a direct answer for QUERY intents."""
        from jarvis.orchestrator.intent import IntentResult

        assert isinstance(intent, IntentResult)

        lower = original_message.lower().strip().rstrip("!?.")

        # Use AI service for intelligent responses
        if self._ai_service is not None and self._ai_service.available:
            # Build context from project info if available
            context_parts: list[str] = []
            if self._project_service is not None and project_id:
                try:
                    project = await self._project_service.get_project(session, project_id)
                    context_parts.append(
                        f"Current project: {project.name} "
                        f"(path: {project.local_path}, "
                        f"stack: {', '.join(project.stack) if project.stack else 'N/A'})"
                    )
                except ProjectNotFoundError:
                    pass

            context = "\n".join(context_parts) if context_parts else None
            return await self._ai_service.chat(original_message, context=context)

        # Fallback: no AI service configured
        # Only show project info for project-related queries
        _project_keywords = {"project", "projects", "list", "show", "status", "ci"}
        is_project_query = any(kw in lower for kw in _project_keywords)

        if is_project_query and self._project_service is not None:
            if project_id:
                try:
                    project = await self._project_service.get_project(session, project_id)
                    return (
                        f"Project: {project.name}\n"
                        f"Path: {project.local_path}\n"
                        f"Stack: {', '.join(project.stack) if project.stack else 'not specified'}\n"
                        f"Agent: {project.preferred_agent or 'default'}"
                    )
                except ProjectNotFoundError:
                    return f"Project '{project_id}' not found."

            projects = await self._project_service.list_projects(session, limit=20)
            if not projects:
                return "No projects registered yet."
            lines = [f"Found {len(projects)} project(s):"]
            for p in projects:
                lines.append(f"  - {p.name} ({p.id})")
            return "\n".join(lines)

        # Generic conversational fallback
        return (
            f'I\'m not sure how to answer "{original_message}" without an AI model. '
            "I work best with action commands like:\n"
            "- 'fix the login bug'\n"
            "- 'add dark mode to settings'\n"
            "- 'list my projects'\n\n"
            "For open-ended chat, set the ANTHROPIC_API_KEY environment variable."
        )

    async def _dispatch_in_background(self, task_id: str) -> None:
        """Dispatch a task in a background session."""
        if self._db is None:
            logger.warning("No database configured for background dispatch")
            return
        async with self._db.session() as bg_session:
            try:
                await self.dispatch_task(bg_session, task_id)
            except Exception:
                logger.exception("Background dispatch failed for task %s", task_id)

    async def _run_workflow_background(
        self, task_id: str, issue_number: int, project_id: str | None
    ) -> None:
        """Run a DevWorkflow in a background session."""
        if self._db is None:
            logger.warning("No database configured for background workflow")
            return
        async with self._db.session() as bg_session:
            try:
                await self.dispatch_task(bg_session, task_id)
            except Exception:
                logger.exception(
                    "Background workflow failed for task %s (issue #%d)",
                    task_id,
                    issue_number,
                )

    async def dispatch_task(self, session: AsyncSession, task_id: str) -> None:
        """Dispatch a task to an agent for execution.

        Uses AgentRouter to select the agent, with fallback on launch failure.
        """
        if self._agent_execution_service is None:
            raise RuntimeError("Agent execution service not configured")
        if self._project_service is None:
            raise RuntimeError("Project service not configured")
        if self._agent_registry is None:
            raise RuntimeError("Agent registry not configured")
        if self._agent_router is None:
            raise RuntimeError("Agent router not configured")

        task = await self._task_service.get_task(session, task_id)

        # Resolve project path (None-safe)
        working_dir = ""
        try:
            project = await self._project_service.get_project(session, task.project_id or "")
            working_dir = project.local_path
        except ProjectNotFoundError:
            logger.warning(
                "Project %r not found for task %s, using empty working_dir",
                task.project_id,
                task_id,
            )

        # Retrieve context from memory if available
        if self._memory_service is not None:
            try:
                memories = await self._memory_service.retrieve_context(
                    session,
                    task.request,
                    project_id=task.project_id,
                )
                if memories:
                    context_lines = [
                        f"[{m.memory_type.value}] {m.key}: {m.content}" for m in memories
                    ]
                    context_block = "\n".join(context_lines)
                    task = Task(
                        **{
                            **task.model_dump(),
                            "request": f"Context:\n{context_block}\n\nRequest:\n{task.request}",
                        }
                    )
            except Exception:
                logger.warning("Failed to retrieve context for task %s", task_id, exc_info=True)

        # Select agent via router
        agent_name = self._agent_router.select(task)

        # Try primary agent, then fallback on launch failure
        agent = await self._try_create_agent(
            session,
            task_id,
            task,
            agent_name,
            working_dir,
        )
        if agent is None:
            return  # task already failed

        # Transition task to RUNNING
        await self._task_service.transition_task(session, task_id, TaskStatus.RUNNING)
        await session.commit()

        # Create execution record and run
        await self._run_agent(session, task_id, task, agent, working_dir)

    async def _try_create_agent(
        self,
        session: AsyncSession,
        task_id: str,
        task: Task,
        agent_name: str,
        working_dir: str,
    ) -> BaseAgent | None:
        """Try to create the primary agent; on failure, try fallback.

        Returns the agent instance, or None if both primary and fallback fail.
        """
        assert self._agent_registry is not None
        assert self._agent_execution_service is not None
        assert self._agent_router is not None

        try:
            return self._agent_registry.create(agent_name, self._agents_config)
        except AgentError as e:
            logger.warning("Failed to create agent %r: %s", agent_name, e)

            # Record the failed creation as an execution
            execution = await self._agent_execution_service.create_execution(
                session,
                task_id=task_id,
                agent_name=agent_name,
                prompt=task.request,
                project_path=working_dir,
            )
            await self._agent_execution_service.fail_execution(
                session,
                execution.id,
                error=str(e),
            )
            await session.commit()

            # Try fallback
            fallback_name = self._agent_router.fallback_for(agent_name)
            if fallback_name is None:
                await self._task_service.transition_task(
                    session,
                    task_id,
                    TaskStatus.FAILED,
                    error=str(e),
                )
                await session.commit()
                return None

            # Emit fallback event
            if self._event_bus is not None:
                self._event_bus.publish(
                    Event(
                        type=EventType.AGENT_FALLBACK_TRIGGERED,
                        task_id=task_id,
                        data={
                            "primary_agent": agent_name,
                            "fallback_agent": fallback_name,
                            "reason": str(e),
                        },
                    )
                )

            logger.info(
                "Falling back from %r to %r for task %s",
                agent_name,
                fallback_name,
                task_id,
            )

            try:
                return self._agent_registry.create(fallback_name, self._agents_config)
            except AgentError as fallback_err:
                logger.warning("Fallback agent %r also failed: %s", fallback_name, fallback_err)
                fallback_exec = await self._agent_execution_service.create_execution(
                    session,
                    task_id=task_id,
                    agent_name=fallback_name,
                    prompt=task.request,
                    project_path=working_dir,
                )
                await self._agent_execution_service.fail_execution(
                    session,
                    fallback_exec.id,
                    error=str(fallback_err),
                )
                await self._task_service.transition_task(
                    session,
                    task_id,
                    TaskStatus.FAILED,
                    error=str(fallback_err),
                )
                await session.commit()
                return None

    async def _run_agent(
        self,
        session: AsyncSession,
        task_id: str,
        task: Task,
        agent: BaseAgent,
        working_dir: str,
    ) -> None:
        """Run the agent, have the supervisor verify the result, and follow up if needed.

        Each attempt is recorded as its own agent execution. The task stays in
        VERIFYING while the supervisor reviews and the agent does follow-ups.
        """
        assert self._agent_execution_service is not None

        self._active_agents[task_id] = agent
        execution = None
        prompt = task.request
        attempt = 1

        try:
            while True:
                execution = await self._agent_execution_service.create_execution(
                    session,
                    task_id=task_id,
                    agent_name=agent.agent_name,
                    prompt=prompt,
                    project_path=working_dir,
                )
                await self._agent_execution_service.mark_running(session, execution.id)
                await session.commit()

                exit_code, stdout, stderr = await agent.run(
                    working_dir=working_dir,
                    prompt=prompt,
                )
                elapsed = agent.elapsed_seconds() or 0.0
                await self._agent_execution_service.complete_execution(
                    session,
                    execution.id,
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                    duration_ms=elapsed * 1000,
                )

                # Cancelled from the API while the agent ran: the task is
                # already CANCELLED, so don't fail it or ask for a review.
                session.expire_all()  # re-read status written by the cancel request
                current = await self._task_service.get_task(session, task_id)
                if current.status == TaskStatus.CANCELLED:
                    await session.commit()
                    return

                if exit_code != 0:
                    await self._task_service.transition_task(
                        session,
                        task_id,
                        TaskStatus.FAILED,
                        error=stderr or f"Exit code: {exit_code}",
                    )
                    return

                if attempt == 1:
                    await self._task_service.transition_task(
                        session, task_id, TaskStatus.VERIFYING
                    )
                    await session.commit()

                review = await self._review(task, agent.agent_name, stdout, attempt)

                if review is None or review.done:
                    result = stdout
                    if review is not None and review.summary:
                        result = f"Supervisor: {review.summary}\n\n{stdout}"
                    await self._task_service.transition_task(
                        session, task_id, TaskStatus.COMPLETED, result=result
                    )
                    return

                if attempt > self._review_max_rounds:
                    await self._task_service.transition_task(
                        session,
                        task_id,
                        TaskStatus.FAILED,
                        error=f"Supervisor review: work not complete. {review.summary}".strip(),
                    )
                    return

                logger.info(
                    "Supervisor sent task %s back to %s (attempt %d): %s",
                    task_id,
                    agent.agent_name,
                    attempt + 1,
                    review.follow_up,
                )
                attempt += 1
                prompt = (
                    f"{task.request}\n\n"
                    "A reviewer checked your previous attempt in this project "
                    f"and found it incomplete: {review.summary}\n\n"
                    f"Finish the task now. Specifically: {review.follow_up}"
                )

        except TimeoutError:
            elapsed = agent.elapsed_seconds() or 0.0
            if execution is not None:
                await self._agent_execution_service.fail_execution(
                    session,
                    execution.id,
                    error="Agent execution timed out",
                    duration_ms=elapsed * 1000,
                    status=AgentExecutionStatus.TIMEOUT,
                )
            await self._task_service.transition_task(
                session, task_id, TaskStatus.FAILED, error="Agent execution timed out"
            )

        except asyncio.CancelledError:
            elapsed = agent.elapsed_seconds() or 0.0
            if execution is not None:
                await self._agent_execution_service.fail_execution(
                    session,
                    execution.id,
                    error="Agent execution cancelled",
                    duration_ms=elapsed * 1000,
                    status=AgentExecutionStatus.CANCELLED,
                )
            await self._task_service.transition_task(session, task_id, TaskStatus.CANCELLED)

        except Exception as e:
            logger.exception("Unexpected error during agent execution for task %s", task_id)
            if execution is not None:
                await self._agent_execution_service.fail_execution(
                    session, execution.id, error=str(e)
                )
            await self._task_service.transition_task(
                session, task_id, TaskStatus.FAILED, error=str(e)
            )

        finally:
            self._active_agents.pop(task_id, None)
            await session.commit()

    async def _review(
        self, task: Task, agent_name: str, output: str, attempt: int
    ) -> Review | None:
        """Ask the supervisor to verify the agent's work (None = no review)."""
        if self._supervisor is None:
            return None
        review = await self._supervisor.review(task.request, agent_name, output, attempt)
        if review is not None and self._event_bus is not None:
            self._event_bus.publish(
                Event(
                    type=EventType.TASK_REVIEWED,
                    task_id=task.id,
                    data={
                        "attempt": attempt,
                        "agent": agent_name,
                        "done": review.done,
                        "summary": review.summary,
                        "follow_up": review.follow_up,
                    },
                )
            )
        return review

    async def cancel_agent_for_task(self, task_id: str) -> None:
        """Cancel the active agent for a task, if any."""
        agent = self._active_agents.get(task_id)
        if agent is not None:
            await agent.cancel()

    @property
    def task_service(self) -> TaskService:
        return self._task_service

    @property
    def project_service(self) -> ProjectService | None:
        return self._project_service

    @property
    def agent_execution_service(self) -> AgentExecutionService | None:
        return self._agent_execution_service

    @property
    def memory_service(self) -> MemoryService | None:
        return self._memory_service


def _task_line(task_id: str, title: str) -> str:
    return f"Created task: {title} → [{task_id}](/tasks/{task_id})"


_URL_RE = re.compile(r"https?://[^\s\"'<>)\]]+")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def _strip_unverified_links(answer: str, allowed: set[str]) -> str:
    """Remove Markdown links whose URL did not come from this turn's search results.

    A small model can still invent a source; this guarantees every link shown
    to the user is one the search tool actually returned.
    """
    norm = {u.rstrip("/.,") for u in allowed}

    def repl(m: re.Match[str]) -> str:
        if m.group(2).rstrip("/.,") in norm:
            return m.group(0)
        return f"{m.group(1)} *(unverified source removed)*"

    return _MD_LINK_RE.sub(repl, answer)


# gpt-oss cites as 【3†Source name】 or 【3】, where 3 indexes the search results.
_CITE_RE = re.compile(r"\s?【(\d+)(?:†([^】]*))?】")


def _search_urls(output: str) -> list[str]:
    try:
        data = json.loads(output)
    except ValueError:
        return []
    return [str(r.get("url", "")) for r in data if isinstance(r, dict)]


def _convert_citation_markers(answer: str, urls: list[str]) -> str:
    def repl(m: re.Match[str]) -> str:
        idx = int(m.group(1))
        name = (m.group(2) or "").strip() or "source"
        if 0 <= idx < len(urls) and urls[idx]:
            return f" ([{name}]({urls[idx]}))"
        return ""

    return _CITE_RE.sub(repl, answer)
