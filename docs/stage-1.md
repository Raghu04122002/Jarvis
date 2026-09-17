# Stage 1 — Task Engine and Core Orchestrator

## What Was Done

### Database Persistence
Tasks and execution steps are now persisted to PostgreSQL via SQLAlchemy async ORM.

- **SQLAlchemy table models** (`src/jarvis/db/tables.py`): `TaskRow`, `TaskStepRow` with proper column types, indexes on `status` and `priority`
- **Alembic migrations** (`alembic/`): async-compatible migration environment, initial migration creates `tasks` and `task_steps` tables
- **Database engine** (`src/jarvis/db/engine.py`): async connection manager supporting both PostgreSQL (production) and SQLite (tests)
- **Async TaskService**: all methods accept `AsyncSession`, flush within transaction boundaries
- Tests use `aiosqlite` with in-memory SQLite for isolation and speed

### Database Schema

```sql
-- tasks table
id            VARCHAR(32)   PRIMARY KEY
request       TEXT          NOT NULL
title         VARCHAR(200)  NOT NULL
description   TEXT
status        VARCHAR(30)   NOT NULL  (indexed)
priority      VARCHAR(20)   NOT NULL  (indexed)
project_id    VARCHAR(100)
parent_task_id VARCHAR(32)
plan          JSON          (list of step descriptions)
current_step  INTEGER
result        TEXT
error         TEXT
metadata      JSON
version       INTEGER       NOT NULL  (optimistic concurrency control)
created_at    TIMESTAMP WITH TZ  NOT NULL
updated_at    TIMESTAMP WITH TZ  NOT NULL
started_at    TIMESTAMP WITH TZ
completed_at  TIMESTAMP WITH TZ

-- task_steps table
id            VARCHAR(32)   PRIMARY KEY
task_id       VARCHAR(32)   NOT NULL  (indexed)
sequence      INTEGER       NOT NULL
description   TEXT          NOT NULL
status        VARCHAR(20)   NOT NULL
depends_on    JSON
result        TEXT
error         TEXT
created_at    TIMESTAMP WITH TZ  NOT NULL
started_at    TIMESTAMP WITH TZ
completed_at  TIMESTAMP WITH TZ
```

### Task Domain Model
- `Task` model with: `request`, `title`, `plan`, `priority`, `metadata`, `version` (OCC), `current_step`
- `TaskSummary` for lightweight list responses
- `TaskPriority` enum: LOW, NORMAL, HIGH, URGENT
- `TaskStep` model with sequence, status, dependencies, timing fields
- `StepStatus` enum: PENDING, RUNNING, COMPLETED, FAILED, SKIPPED, CANCELLED

### State Machine
Centralized in `src/jarvis/models/task.py`:

```
CREATED → PLANNING, CANCELLED
PLANNING → WAITING_FOR_APPROVAL, RUNNING, FAILED, CANCELLED
WAITING_FOR_APPROVAL → RUNNING, CANCELLED
RUNNING → VERIFYING, FAILED, CANCELLED
VERIFYING → COMPLETED, FAILED, CANCELLED
COMPLETED → (terminal)
FAILED → PLANNING (retry)
CANCELLED → (terminal)
```

- `VALID_TRANSITIONS` dict defines all allowed transitions
- `validate_transition()` enforces the state machine
- `InvalidTransitionError` raised on invalid transitions
- `TERMINAL_STATES` frozenset for boundary checks

### TaskService
`src/jarvis/services/task_service.py` — all methods are async and accept `AsyncSession`:
- `create_task()` — creates with unique TASK-{hex} ID, persists to DB
- `get_task()` / `list_tasks()` — retrieval with optional status/priority filters
- `transition_task()` — enforced state machine, version increment, timestamp updates
- `cancel_task()` — validates cancellability, cancels pending steps
- `complete_task()` / `fail_task()` — convenience methods
- `add_steps()` / `get_steps()` — step management
- `update_task_plan()` — stores plan on task
- Version field incremented on each transition (optimistic concurrency control)

### Orchestrator
`src/jarvis/orchestrator/orchestrator.py`:
- Receives `ChatRequest`, creates task, transitions to PLANNING
- Delegates to Planner for plan generation
- Stores plan steps as `TaskStep` objects in database
- Returns task with plan for API response

### Planner
`src/jarvis/orchestrator/planner.py`:
- `BasePlanner` abstract class with `create_plan(request, context)` interface
- `BasicPlanner` deterministic implementation (placeholder for LLM-powered planner)
- Returns structured `Plan` dataclass with title and steps
- Provider-agnostic — no hardcoded AI model references

### Event System
`src/jarvis/events.py`:
- `EventBus` — synchronous in-process pub/sub
- `EventType` enum: TASK_CREATED, TASK_UPDATED, TASK_STATE_CHANGED, TASK_STEP_STARTED, TASK_STEP_COMPLETED, TASK_FAILED, TASK_CANCELLED, TASK_COMPLETED
- Handler errors logged but don't propagate
- Events published by TaskService on state transitions

### Audit Integration
`src/jarvis/audit/logger.py`:
- `AuditLogger` subscribes to all event types on the EventBus
- Creates `AuditEntry` records for each lifecycle event
- Logs audit events at INFO level (never logs secrets)
- Filterable by task_id

### API Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check (Stage 0) |
| `/chat` | POST | Accept natural-language request, create task with plan |
| `/tasks` | GET | List tasks with optional status/priority/limit filters |
| `/tasks/{id}` | GET | Full task details including plan |
| `/tasks/{id}/cancel` | POST | Cancel a task (validates state) |
| `/tasks/{id}/retry` | POST | Retry a failed task (back to PLANNING) |
| `/tasks/{id}/steps` | GET | List execution steps |

Error responses: 404 (not found), 409 (invalid state/transition), 422 (validation)

All API routes use FastAPI dependency injection for database sessions.

### CLI Commands
| Command | Purpose |
|---------|---------|
| `jarvis serve` | Start API server (Stage 0) |
| `jarvis task create "message"` | Create task via API |
| `jarvis task list [--status] [--limit]` | List tasks with Rich table |
| `jarvis task get TASK_ID` | Show task details |
| `jarvis task cancel TASK_ID` | Cancel a task |

### Architecture Diagram
```
USER
│
├── CLI (Click + Rich)
│   └── HTTP Client (httpx)
│
└── API (FastAPI)
    │
    └── Orchestrator
        │
        ├── Planner (BasicPlanner)
        │   └── Plan (title + steps)
        │
        └── TaskService (async)
            ├── Task State Machine
            ├── TaskStep Management
            ├── Event Publishing
            │
            ├── Database (SQLAlchemy async)
            │   ├── TaskRow
            │   └── TaskStepRow
            │
            └── EventBus
                └── AuditLogger
```

### Task Lifecycle
```
USER → POST /chat
         │
    Orchestrator.handle_chat()
         │
    ┌────┴────┐
    │ Planner │ → Plan (title + steps)
    └────┬────┘
         │
    TaskService.create_task()     → CREATED
    TaskService.transition()      → PLANNING
    TaskService.update_task_plan()
    TaskService.add_steps()
         │
    Return task with plan
```

### Cancellation Behavior
1. Validates the current task state is not terminal (COMPLETED, CANCELLED)
2. Cancels all PENDING and RUNNING steps
3. Transitions the task to CANCELLED
4. Publishes TASK_CANCELLED event
5. Records audit entry

### Concurrency
- Optimistic concurrency control via `version` field on tasks
- Each state transition increments the version
- Database-level isolation via SQLAlchemy session transactions
- Asyncio single-threaded event loop prevents in-process races

## How to Verify

```bash
source .venv/bin/activate

# Create PostgreSQL database
psql -h localhost -c "CREATE DATABASE jarvis" postgres

# Run migrations
alembic upgrade head

# Run tests (104 tests, uses in-memory SQLite)
pytest tests/ -v

# Quality checks
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/

# Start server and test
jarvis serve --port 8112

# In another terminal:
curl -X POST http://127.0.0.1:8112/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Fix the login issue"}'

curl http://127.0.0.1:8112/tasks
curl http://127.0.0.1:8112/tasks/TASK-xxxxx
curl http://127.0.0.1:8112/tasks/TASK-xxxxx/steps
curl -X POST http://127.0.0.1:8112/tasks/TASK-xxxxx/cancel
```

## Known Limitations

- **BasicPlanner** — deterministic, not LLM-powered (LLM integration in Stage 4)
- **No agent execution** — tasks are planned but not executed
- **No WebSocket streaming** — events are internal only
- **No authentication** — API is open on localhost
- **Single-process** — no distributed task coordination
- **AuditLogger is in-memory** — audit entries not persisted to database yet
