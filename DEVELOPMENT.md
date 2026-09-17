# Jarvis — Development Stages

## Stage 0: Project Scaffolding
- Initialize git repo, Python project (pyproject.toml), directory structure
- Set up PostgreSQL database and migrations (Alembic)
- Basic configuration system (TOML)
- Logging and secrets abstraction
- CI-ready test structure (pytest)

## Stage 1: Task Engine & Core Orchestrator ✅
- Task domain model with 8-state machine and enforced transitions
- Async TaskService with PostgreSQL persistence (SQLAlchemy async ORM)
- Alembic migrations for tasks and task_steps tables
- Orchestrator with Planner abstraction (BasicPlanner deterministic impl)
- TaskStep model for structured execution plans
- In-process EventBus for lifecycle events
- AuditLogger integrated with EventBus
- API: /chat, /tasks, /tasks/{id}, /tasks/{id}/cancel, /tasks/{id}/retry, /tasks/{id}/steps
- CLI: jarvis task create/list/get/cancel
- Optimistic concurrency control via version field
- 104 tests (state machine, service, orchestrator, API, events, persistence, concurrency)

## Stage 2: Tool System
- Tool base class and registry
- Implement: TerminalTool, FileSystemTool, GitTool
- Permission gate (SAFE/REQUIRES_APPROVAL/BLOCKED)
- Tool execution with permission checks
- Tests for permission enforcement

## Stage 3: Agent Abstraction
- Agent base class
- ClaudeCodeAdapter (subprocess wrapper for `claude` CLI)
- Agent status tracking and result collection
- Integration test with Claude Code

## Stage 4: Orchestrator & Planner
- Orchestrator: receives intent, creates task, delegates
- Planner: decomposes tasks into steps using LLM
- Task state machine implementation
- Execution engine: runs steps sequentially/in parallel
- Error handling and retry logic

## Stage 5: CLI Interface
- Click-based CLI: `jarvis run "fix the login bug"`
- Rich terminal output (status, logs, progress)
- Interactive approval prompts in terminal
- `jarvis status`, `jarvis history`, `jarvis projects`

## Stage 6: WebSocket & Real-time
- WebSocket endpoint for live task updates
- Approval request/response via WebSocket
- Streaming logs from agent execution

## Stage 7: GitHub & Browser Tools
- GitHubTool (issues, PRs, reviews via `gh` CLI)
- BrowserTool (Playwright-based)
- Integration tests

## Stage 8: Memory System
- Per-project memory store
- Memory CRUD API
- Context injection into planner/agents
- Prepare schema for pgvector

## Stage 9: Web UI
- React frontend (Vite)
- Task dashboard, project selector
- Live logs and approval UI
- Settings and configuration

## Stage 10: Desktop App (Tauri)
- Wrap web UI in Tauri shell
- System tray, notifications
- Global hotkey for voice/text input

## Stage 11: Advanced Features
- Scheduler (cron-like task scheduling)
- Multi-agent coordination
- pgvector semantic memory search
- Voice input (Whisper)
- Computer control capabilities

---

## Prerequisites

### Required
- Python 3.10+ (3.9.6 available but 3.10+ recommended for modern typing)
- PostgreSQL 15 (installed)
- Node.js 22 (installed)
- Docker (installed)
- GitHub CLI (installed)
- Claude Code CLI (installed)

### Recommended to Install
- **Rust + Cargo** — needed for Tauri (Stage 10)
- **Python 3.11+** — better performance, modern syntax
- **Playwright** — `pip install playwright && playwright install`

### Python Dependencies (initial)
```
fastapi
uvicorn
pydantic
sqlalchemy
alembic
asyncpg
httpx
click
rich
python-dotenv
toml
pytest
pytest-asyncio
```

## Directory Structure

```
jarvis/
├── README.md
├── ARCHITECTURE.md
├── SECURITY.md
├── DEVELOPMENT.md
├── CHANGELOG.md
├── pyproject.toml
├── alembic.ini
├── alembic/
│   └── versions/
├── config/
│   └── default.toml
├── src/
│   └── jarvis/
│       ├── __init__.py
│       ├── main.py                 # FastAPI app entry
│       ├── config.py               # Configuration loader
│       ├── models/
│       │   ├── __init__.py
│       │   ├── task.py
│       │   ├── project.py
│       │   ├── audit.py
│       │   ├── approval.py
│       │   └── memory.py
│       ├── db/
│       │   ├── __init__.py
│       │   ├── engine.py
│       │   ├── tables.py
│       │   └── migrations/
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes/
│       │   │   ├── tasks.py
│       │   │   ├── projects.py
│       │   │   └── health.py
│       │   └── websocket.py
│       ├── orchestrator/
│       │   ├── __init__.py
│       │   ├── orchestrator.py
│       │   ├── planner.py
│       │   ├── router.py
│       │   └── executor.py
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── claude_code.py
│       │   └── antigravity.py
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── registry.py
│       │   ├── terminal.py
│       │   ├── filesystem.py
│       │   ├── git.py
│       │   ├── github.py
│       │   └── browser.py
│       ├── permissions/
│       │   ├── __init__.py
│       │   ├── gate.py
│       │   └── levels.py
│       ├── memory/
│       │   ├── __init__.py
│       │   └── store.py
│       ├── audit/
│       │   ├── __init__.py
│       │   └── logger.py
│       ├── secrets/
│       │   ├── __init__.py
│       │   └── vault.py
│       └── cli/
│           ├── __init__.py
│           └── main.py
├── tests/
│   ├── conftest.py
│   ├── test_models/
│   ├── test_api/
│   ├── test_tools/
│   ├── test_agents/
│   ├── test_permissions/
│   └── test_orchestrator/
├── ui/                             # Stage 9+
│   ├── package.json
│   └── src/
├── docker/
│   └── docker-compose.yml
└── .env.example
```
