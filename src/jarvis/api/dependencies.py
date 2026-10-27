"""Shared application dependencies — singleton instances for the API layer."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.agents.registry import create_default_registry
from jarvis.agents.router import AgentRouter
from jarvis.audit.logger import AuditLogger
from jarvis.config import AgentsConfig, AIConfig, JarvisConfig, VoiceConfig, load_config
from jarvis.db.engine import Database
from jarvis.events import EventBus
from jarvis.notifications.base import NotificationProvider
from jarvis.orchestrator.orchestrator import Orchestrator
from jarvis.orchestrator.planner import BasicPlanner
from jarvis.orchestrator.supervisor import Supervisor
from jarvis.permissions.gate import PermissionGate
from jarvis.scheduler.engine import SchedulerEngine
from jarvis.services.agent_execution_service import AgentExecutionService
from jarvis.services.ai_service import AIService
from jarvis.services.approval_service import ApprovalService
from jarvis.services.chat_tools import make_search_backend
from jarvis.services.memory_service import MemoryService
from jarvis.services.notification_service import NotificationService
from jarvis.services.project_service import ProjectService
from jarvis.services.pxpipe_service import PxpipeService
from jarvis.services.scheduler_service import SchedulerService
from jarvis.services.task_service import TaskService
from jarvis.services.voice_service import VoiceService
from jarvis.tools.browser_tool import BrowserTool
from jarvis.tools.computer_tool import ComputerTool
from jarvis.tools.git_tool import GitTool
from jarvis.tools.github_tool import GitHubTool
from jarvis.tools.registry import ToolRegistry

_orchestrator: Orchestrator | None = None
_audit_logger: AuditLogger | None = None
_database: Database | None = None
_event_bus: EventBus | None = None
_project_service: ProjectService | None = None
_agent_execution_service: AgentExecutionService | None = None
_memory_service: MemoryService | None = None
_tool_registry: ToolRegistry | None = None
_permission_gate: PermissionGate | None = None
_approval_service: ApprovalService | None = None
_scheduler_service: SchedulerService | None = None
_scheduler_engine: SchedulerEngine | None = None
_notification_service: NotificationService | None = None
_ai_service: AIService | None = None
_pxpipe_service: PxpipeService | None = None
_voice_service: VoiceService | None = None


def init_dependencies(config: JarvisConfig | None = None) -> None:
    """Initialize shared application dependencies."""
    global _orchestrator, _audit_logger, _database, _event_bus, _project_service
    global _agent_execution_service, _memory_service, _tool_registry, _permission_gate
    global _approval_service, _scheduler_service, _scheduler_engine, _notification_service
    global _ai_service, _pxpipe_service, _voice_service

    if config is None:
        config = load_config()

    _event_bus = EventBus()
    _audit_logger = AuditLogger(_event_bus)
    _database = Database(config.database)
    task_service = TaskService(_event_bus)
    _project_service = ProjectService(_event_bus)
    _agent_execution_service = AgentExecutionService(_event_bus)
    _memory_service = MemoryService(_event_bus)
    _approval_service = ApprovalService(_event_bus)
    planner = BasicPlanner()

    # AI + pxpipe services
    _pxpipe_service = (
        PxpipeService()
        if config.ai.pxpipe_enabled and config.ai.provider == "anthropic"
        else None
    )
    _ai_service = AIService(config.ai)

    # Voice service
    _voice_service = VoiceService(config.voice)

    registry = create_default_registry()
    router = AgentRouter(registry, config.agents)

    # Supervisor: the chat model (e.g. Ollama) plans, delegates and verifies.
    supervisor = (
        Supervisor(_ai_service, registry.list_agents(), model=config.ai.supervisor_model)
        if config.ai.supervisor_enabled
        else None
    )

    _orchestrator = Orchestrator(
        task_service,
        planner,
        _project_service,
        _agent_execution_service,
        config.agents,
        agent_registry=registry,
        agent_router=router,
        event_bus=_event_bus,
        memory_service=_memory_service,
        db=_database,
        ai_service=_ai_service,
        supervisor=supervisor,
        review_max_rounds=config.ai.review_max_rounds,
        search_backend=make_search_backend(
            config.ai.web_search_provider, config.ai.ollama_api_key
        ),
    )

    _tool_registry = ToolRegistry()
    _tool_registry.register(GitTool())
    _tool_registry.register(GitHubTool())
    _tool_registry.register(BrowserTool(config.browser))
    _tool_registry.register(ComputerTool(config.computer))
    _permission_gate = PermissionGate(approval_service=_approval_service)

    # Scheduler & notifications
    _scheduler_service = SchedulerService(_event_bus)
    providers: list[NotificationProvider] = []
    if config.notification.desktop_enabled:
        from jarvis.notifications.desktop import DesktopNotificationProvider

        providers.append(DesktopNotificationProvider())
    _notification_service = NotificationService(_event_bus, providers)
    _scheduler_engine = SchedulerEngine(
        _scheduler_service,
        _orchestrator,
        _database,
        _event_bus,
        _notification_service,
        poll_interval_seconds=config.scheduler.poll_interval_seconds,
    )


def init_dependencies_with_db(db: Database) -> None:
    """Initialize dependencies with a pre-configured database (for tests)."""
    global _orchestrator, _audit_logger, _database, _event_bus, _project_service
    global _agent_execution_service, _memory_service, _tool_registry, _permission_gate
    global _approval_service, _scheduler_service, _scheduler_engine, _notification_service
    global _ai_service, _pxpipe_service, _voice_service

    _event_bus = EventBus()
    _audit_logger = AuditLogger(_event_bus)
    _database = db
    task_service = TaskService(_event_bus)
    _project_service = ProjectService(_event_bus)
    _agent_execution_service = AgentExecutionService(_event_bus)
    _memory_service = MemoryService(_event_bus)
    _approval_service = ApprovalService(_event_bus)
    planner = BasicPlanner()

    # No pxpipe in tests; AI service with defaults (will be unavailable without key)
    _pxpipe_service = None
    _ai_service = AIService(AIConfig(pxpipe_enabled=False))
    _voice_service = VoiceService(VoiceConfig())

    registry = create_default_registry()
    router = AgentRouter(registry, AgentsConfig())

    _orchestrator = Orchestrator(
        task_service,
        planner,
        _project_service,
        _agent_execution_service,
        agent_registry=registry,
        agent_router=router,
        event_bus=_event_bus,
        memory_service=_memory_service,
        ai_service=_ai_service,
    )

    _tool_registry = ToolRegistry()
    _tool_registry.register(GitTool())
    _tool_registry.register(GitHubTool())
    _tool_registry.register(BrowserTool())
    _tool_registry.register(ComputerTool())
    _permission_gate = PermissionGate(approval_service=_approval_service)

    _scheduler_service = SchedulerService(_event_bus)
    _notification_service = NotificationService(_event_bus)
    _scheduler_engine = SchedulerEngine(
        _scheduler_service,
        _orchestrator,
        _database,
        _event_bus,
        _notification_service,
    )


def get_orchestrator() -> Orchestrator:
    if _orchestrator is None:
        init_dependencies()
        assert _orchestrator is not None
    return _orchestrator


def get_audit_logger() -> AuditLogger:
    if _audit_logger is None:
        init_dependencies()
        assert _audit_logger is not None
    return _audit_logger


def get_database() -> Database:
    if _database is None:
        init_dependencies()
        assert _database is not None
    return _database


def get_project_service() -> ProjectService:
    if _project_service is None:
        init_dependencies()
        assert _project_service is not None
    return _project_service


def get_memory_service() -> MemoryService:
    if _memory_service is None:
        init_dependencies()
        assert _memory_service is not None
    return _memory_service


def get_agent_execution_service() -> AgentExecutionService:
    if _agent_execution_service is None:
        init_dependencies()
        assert _agent_execution_service is not None
    return _agent_execution_service


def get_tool_registry() -> ToolRegistry:
    if _tool_registry is None:
        init_dependencies()
        assert _tool_registry is not None
    return _tool_registry


def get_permission_gate() -> PermissionGate:
    if _permission_gate is None:
        init_dependencies()
        assert _permission_gate is not None
    return _permission_gate


def get_approval_service() -> ApprovalService:
    if _approval_service is None:
        init_dependencies()
        assert _approval_service is not None
    return _approval_service


def get_event_bus() -> EventBus:
    if _event_bus is None:
        init_dependencies()
        assert _event_bus is not None
    return _event_bus


def get_scheduler_service() -> SchedulerService:
    if _scheduler_service is None:
        init_dependencies()
        assert _scheduler_service is not None
    return _scheduler_service


def get_scheduler_engine() -> SchedulerEngine:
    if _scheduler_engine is None:
        init_dependencies()
        assert _scheduler_engine is not None
    return _scheduler_engine


def get_ai_service() -> AIService:
    if _ai_service is None:
        init_dependencies()
        assert _ai_service is not None
    return _ai_service


def get_pxpipe_service() -> PxpipeService | None:
    return _pxpipe_service


def get_voice_service() -> VoiceService:
    if _voice_service is None:
        init_dependencies()
        assert _voice_service is not None
    return _voice_service


def get_notification_service() -> NotificationService:
    if _notification_service is None:
        init_dependencies()
        assert _notification_service is not None
    return _notification_service


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield an async database session for request scope."""
    db = get_database()
    async with db.session() as session:
        yield session
        await session.commit()


def reset_dependencies() -> None:
    """Reset all dependencies. Used in tests."""
    global _orchestrator, _audit_logger, _database, _event_bus, _project_service
    global _agent_execution_service, _memory_service, _tool_registry, _permission_gate
    global _approval_service, _scheduler_service, _scheduler_engine, _notification_service
    global _ai_service, _pxpipe_service, _voice_service
    if _event_bus is not None:
        _event_bus.clear()
    _orchestrator = None
    _audit_logger = None
    _database = None
    _event_bus = None
    _project_service = None
    _agent_execution_service = None
    _memory_service = None
    _tool_registry = None
    _permission_gate = None
    _approval_service = None
    _scheduler_service = None
    _scheduler_engine = None
    _notification_service = None
    _ai_service = None
    _pxpipe_service = None
    _voice_service = None
