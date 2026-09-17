"""Jarvis Orchestrator — receives user requests, creates tasks, and manages planning."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.agents.base import AgentError, BaseAgent
from jarvis.agents.registry import AgentRegistry
from jarvis.agents.router import AgentRouter
from jarvis.config import AgentsConfig
from jarvis.events import Event, EventBus, EventType
from jarvis.models.agent import AgentExecutionStatus
from jarvis.models.task import ChatRequest, Task, TaskStatus
from jarvis.orchestrator.planner import BasePlanner
from jarvis.services.agent_execution_service import AgentExecutionService
from jarvis.services.memory_service import MemoryService
from jarvis.services.project_service import ProjectService
from jarvis.services.task_service import TaskService

logger = logging.getLogger(__name__)


class Orchestrator:
    """Core orchestration engine.

    Receives user requests, creates tasks, generates plans,
    and manages the task lifecycle including agent dispatch.
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
        self._active_agents: dict[str, BaseAgent] = {}

    async def handle_chat(self, session: AsyncSession, chat: ChatRequest) -> Task:
        """Process a user chat request.

        1. Create a task from the request.
        2. Transition to PLANNING.
        3. Generate a plan.
        4. Store the plan steps.

        Returns the task with its plan.
        """
        # 1. Generate the plan
        plan = self._planner.create_plan(
            chat.message,
            context={"project_id": chat.project_id or ""},
        )

        # 2. Create the task
        task = await self._task_service.create_task(
            session,
            request=chat.message,
            title=plan.title,
            project_id=chat.project_id,
            priority=chat.priority,
        )
        logger.info("Task created: %s", task.id)

        # 3. Transition to PLANNING
        await self._task_service.transition_task(session, task.id, TaskStatus.PLANNING)

        # 4. Store the plan
        await self._task_service.update_task_plan(session, task.id, plan.steps)
        await self._task_service.add_steps(session, task.id, plan.steps)

        return await self._task_service.get_task(session, task.id)

    async def dispatch_task(self, session: AsyncSession, task_id: str) -> None:
        """Dispatch a task to an agent for execution.

        Uses AgentRouter to select the agent, with fallback on launch failure.

        1. Load task + project
        2. Router selects agent
        3. Create execution record
        4. Transition task -> RUNNING
        5. Launch agent
        6. On success: RUNNING -> VERIFYING -> COMPLETED
        7. On non-zero exit: FAILED
        8. On agent launch failure: try fallback agent
        9. On timeout: execution=TIMEOUT, task=FAILED
        10. On cancel: execution=CANCELLED, task=CANCELLED
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

        # Resolve project path
        project = await self._project_service.get_project(session, task.project_id or "")
        working_dir = project.local_path

        # Retrieve context from memory if available
        if self._memory_service is not None:
            try:
                memories = await self._memory_service.retrieve_context(
                    session, task.request, project_id=task.project_id,
                )
                if memories:
                    context_lines = [
                        f"[{m.memory_type.value}] {m.key}: {m.content}"
                        for m in memories
                    ]
                    context_block = "\n".join(context_lines)
                    task = Task(
                        **{
                            **task.model_dump(),
                            "request": f"Context:\n{context_block}\n\nRequest:\n{task.request}",
                        }
                    )
            except Exception:
                logger.warning(
                    "Failed to retrieve context for task %s", task_id, exc_info=True
                )

        # Select agent via router
        agent_name = self._agent_router.select(task)

        # Try primary agent, then fallback on launch failure
        agent = await self._try_create_agent(
            session, task_id, task, agent_name, working_dir,
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
                session, execution.id, error=str(e),
            )
            await session.commit()

            # Try fallback
            fallback_name = self._agent_router.fallback_for(agent_name)
            if fallback_name is None:
                await self._task_service.transition_task(
                    session, task_id, TaskStatus.FAILED, error=str(e),
                )
                await session.commit()
                return None

            # Emit fallback event
            if self._event_bus is not None:
                self._event_bus.publish(Event(
                    type=EventType.AGENT_FALLBACK_TRIGGERED,
                    task_id=task_id,
                    data={
                        "primary_agent": agent_name,
                        "fallback_agent": fallback_name,
                        "reason": str(e),
                    },
                ))

            logger.info(
                "Falling back from %r to %r for task %s",
                agent_name, fallback_name, task_id,
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
                    session, fallback_exec.id, error=str(fallback_err),
                )
                await self._task_service.transition_task(
                    session, task_id, TaskStatus.FAILED, error=str(fallback_err),
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
        """Run the agent and handle the result."""
        assert self._agent_execution_service is not None

        execution = await self._agent_execution_service.create_execution(
            session,
            task_id=task_id,
            agent_name=agent.agent_name,
            prompt=task.request,
            project_path=working_dir,
        )

        await self._agent_execution_service.mark_running(session, execution.id)
        await session.commit()

        self._active_agents[task_id] = agent

        try:
            exit_code, stdout, stderr = await agent.run(
                working_dir=working_dir, prompt=task.request,
            )
            elapsed = agent.elapsed_seconds() or 0.0
            duration_ms = elapsed * 1000

            await self._agent_execution_service.complete_execution(
                session,
                execution.id,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration_ms,
            )

            if exit_code == 0:
                await self._task_service.transition_task(
                    session, task_id, TaskStatus.VERIFYING
                )
                await self._task_service.transition_task(
                    session, task_id, TaskStatus.COMPLETED, result=stdout
                )
            else:
                await self._task_service.transition_task(
                    session, task_id, TaskStatus.FAILED, error=stderr or f"Exit code: {exit_code}"
                )

        except TimeoutError:
            elapsed = agent.elapsed_seconds() or 0.0
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
            await self._agent_execution_service.fail_execution(
                session,
                execution.id,
                error="Agent execution cancelled",
                duration_ms=elapsed * 1000,
                status=AgentExecutionStatus.CANCELLED,
            )
            await self._task_service.transition_task(
                session, task_id, TaskStatus.CANCELLED
            )

        except Exception as e:
            logger.exception("Unexpected error during agent execution for task %s", task_id)
            await self._agent_execution_service.fail_execution(
                session, execution.id, error=str(e)
            )
            await self._task_service.transition_task(
                session, task_id, TaskStatus.FAILED, error=str(e)
            )

        finally:
            self._active_agents.pop(task_id, None)
            await session.commit()

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
