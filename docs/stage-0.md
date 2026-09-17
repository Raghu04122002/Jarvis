# Stage 0 — Foundation, Environment, and Project Scaffolding

## What Was Done

### Environment
- Installed Python 3.12.14 via Homebrew (system had only 3.9.6)
- Created project virtual environment with Python 3.12
- Initialized git repository on `main` branch

### Project Setup
- `pyproject.toml` with hatchling build system, all dependencies pinned to ranges
- `.gitignore` covering Python, venv, IDE, secrets, and build artifacts
- `.env.example` documenting required environment variables

### Source Structure
```
src/jarvis/
├── __init__.py          # Package root, version
├── config.py            # TOML + env var config loading
├── logging.py           # Structured logging, secret redaction awareness
├── main.py              # FastAPI app factory
├── api/routes/health.py # GET /health endpoint
├── cli/main.py          # Click CLI with `serve` command
├── models/
│   ├── task.py          # Task, TaskStatus, TaskCreate
│   ├── project.py       # Project registry model
│   ├── audit.py         # AuditEntry model
│   └── approval.py      # ApprovalRequest, RiskLevel, ApprovalStatus
├── db/engine.py         # Async SQLAlchemy engine + session manager
├── secrets/vault.py     # Environment-based secrets resolution
├── orchestrator/        # Placeholder for Stage 4
├── agents/              # Placeholder for Stage 3
├── tools/               # Placeholder for Stage 2
├── permissions/         # Placeholder for Stage 2
├── memory/              # Placeholder for Stage 8
└── audit/               # Placeholder for Stage 1
```

### Configuration
- TOML-based with `config/default.toml`
- Environment variable overrides: `JARVIS_SECTION__KEY` pattern
- Validated via Pydantic models
- Secrets (database password, etc.) are never in TOML files

### API
- FastAPI with app factory pattern (`create_app()`)
- Lifespan management (startup/shutdown logging)
- Global exception handler
- `GET /health` returns status, version, timestamp

### CLI
- `jarvis --help` and `jarvis --version`
- `jarvis serve` starts uvicorn with configurable host/port/reload

### Models
- `Task` with full state machine enum (CREATED through CANCELLED)
- `Project` with registry metadata
- `AuditEntry` for action logging
- `ApprovalRequest` with risk levels (SAFE, REQUIRES_APPROVAL, BLOCKED)

### Database
- Async SQLAlchemy engine wrapper
- Session factory with `asyncpg` driver
- Connection URL construction (with/without auth)
- No schema or migrations yet (deferred to Stage 1)

### Testing
- pytest with async support
- 15 tests covering: health endpoint, config loading, env overrides, validation, CLI, secrets vault
- All passing

### Code Quality
- ruff linter (E, F, I, N, W, UP rules)
- ruff formatter
- mypy strict mode
- All checks passing with zero errors

## How to Verify

```bash
source .venv/bin/activate
pytest tests/ -v              # 15 tests pass
ruff check src/ tests/        # No errors
ruff format --check src/ tests/  # All formatted
mypy src/                     # No issues
jarvis --help                 # Shows CLI
jarvis serve --port 8111      # Starts server
curl http://127.0.0.1:8111/health  # Returns JSON
```

## Known Limitations

- No database schema or migrations (Stage 1)
- No tool system or permission enforcement (Stage 2)
- No agent adapters (Stage 3)
- No orchestrator or planner (Stage 4)
- No WebSocket support (Stage 6)
- PostgreSQL not yet required to run the app

## Dependencies

| Package | Purpose |
|---------|---------|
| fastapi | HTTP API framework |
| uvicorn | ASGI server |
| pydantic | Data validation and models |
| pydantic-settings | Settings management |
| sqlalchemy | Database ORM (async) |
| asyncpg | PostgreSQL async driver |
| alembic | Database migrations (prepared, not used yet) |
| click | CLI framework |
| rich | Terminal formatting |
| pytest | Test framework |
| pytest-asyncio | Async test support |
| httpx | Async HTTP client (testing) |
| ruff | Linter and formatter |
| mypy | Type checker |
