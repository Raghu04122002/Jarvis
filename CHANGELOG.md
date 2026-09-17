# Changelog

## [0.2.0] — 2026-09-15

### Added
- Task engine with full lifecycle management (Stage 1)
- Task state machine: 8 states with enforced transitions and retry support
- TaskService: async create, get, list, transition, cancel, complete, fail operations
- Orchestrator: receives user requests, creates tasks, generates plans
- Planner abstraction with BasicPlanner (provider-agnostic, LLM-ready)
- TaskStep model for structured execution plans
- In-process EventBus for task lifecycle events
- AuditLogger integrated with EventBus
- API: POST /chat, GET /tasks, GET /tasks/{id}, POST /tasks/{id}/cancel, POST /tasks/{id}/retry, GET /tasks/{id}/steps
- CLI: jarvis task create/list/get/cancel commands with Rich output
- Optimistic concurrency control via task version field
- PostgreSQL persistence via SQLAlchemy async ORM with Alembic migrations
- Database tables: tasks, task_steps with proper indexes
- FastAPI dependency injection for database sessions
- 104 tests covering state machine, service, orchestrator, planner, API, events, audit, persistence, concurrency

## [0.1.0] — 2026-09-10

### Added
- Project foundation (Stage 0)
- Python 3.12 virtual environment with hatchling build system
- FastAPI application with `GET /health` endpoint
- TOML configuration system with environment variable overrides
- Structured logging with secret-aware redaction helpers
- SecretsVault abstraction (environment variable backed)
- Pydantic models: Task, Project, AuditEntry, ApprovalRequest
- Async database layer (SQLAlchemy + asyncpg)
- Click + Rich CLI with `jarvis serve` command
- 15 tests (health, config, CLI, secrets)
- Code quality: ruff linter/formatter, mypy strict mode
- Documentation: README, ARCHITECTURE, SECURITY, DEVELOPMENT, stage-0

## [0.0.0] — 2026-09-08

### Added
- ARCHITECTURE.md — system design, component overview, data model, key decisions
- SECURITY.md — permission levels, secrets management, approval workflow
- DEVELOPMENT.md — 12-stage development plan, directory structure, prerequisites
- README.md — project overview
