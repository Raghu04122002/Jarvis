# Jarvis

A local-first personal AI orchestration system.

Jarvis acts as an orchestration layer over AI coding agents (Claude Code, Antigravity), developer tools (Git, GitHub), browser automation, and system capabilities. It decomposes natural-language commands into executable plans, routes tasks to the right agents/tools, enforces permissions, and maintains a complete audit trail.

## Status

**Stage 1 complete** — Task engine with PostgreSQL persistence, orchestrator, planner, 8-state machine, API, CLI, audit events, 104 tests.

## Quick Start

```bash
# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Create database and run migrations
psql -h localhost -c "CREATE DATABASE jarvis" postgres
alembic upgrade head

# Start the API server
jarvis serve

# Create a task
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Fix the login issue"}'

# Or use the CLI (requires running server)
jarvis task create "Fix the login issue"
jarvis task list
jarvis task get TASK-xxxxx

# Run tests
pytest tests/ -v

# Run linting and type checking
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/
```

## Requirements

- Python 3.12+
- PostgreSQL 15+ (required for task persistence)

## Configuration

Jarvis uses TOML configuration with environment variable overrides.

- Default config: `config/default.toml`
- Secrets via env vars: `JARVIS_DATABASE__USERNAME`, `JARVIS_DATABASE__PASSWORD`
- Example: `.env.example`

Environment variables use the pattern `JARVIS_SECTION__KEY` (double underscore separator).

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — System design and component overview
- [SECURITY.md](SECURITY.md) — Permission model, secrets management, approval workflow
- [DEVELOPMENT.md](DEVELOPMENT.md) — Development stages, directory structure, prerequisites
- [CHANGELOG.md](CHANGELOG.md) — Version history
- [docs/stage-0.md](docs/stage-0.md) — Stage 0 implementation details
- [docs/stage-1.md](docs/stage-1.md) — Stage 1 task engine details

## Architecture

```
USER → UI (CLI/Web/Desktop) → API (FastAPI) → Orchestrator
  → Planner → Agent Router → Agents/Tools → Permission Gate → Execution → Audit Log
```

## Key Principles

- **Local-first**: runs on your machine, your data stays local
- **Security-first**: centralized permissions, secrets never in LLM context
- **Human-in-the-loop**: dangerous actions require explicit approval
- **Modular**: agents and tools are pluggable adapters
- **Observable**: every action is audit-logged

## License

Private — not yet licensed for distribution.
