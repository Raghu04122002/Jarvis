# Jarvis Architecture

## System Overview

Jarvis is a local-first personal AI orchestration system. It sits above AI agents (Claude Code, Antigravity) and coordinates them to execute software engineering tasks. Jarvis is not a replacement for AI agents — it is the routing, planning, and lifecycle layer above them.

```
User (CLI / Desktop / API)
         │
    ┌────▼────┐
    │  FastAPI │  ← HTTP + SSE
    └────┬────┘
         │
    ┌────▼──────────┐
    │  Orchestrator  │  ← Intent classification, project resolution, routing
    └────┬──────────┘
         │
    ┌────▼────────────────────────────────────┐
    │  Services Layer                          │
    │  TaskService · ProjectService            │
    │  AgentExecutionService · MemoryService   │
    │  ApprovalService · SchedulerService      │
    └────┬────────────────────────────────────┘
         │
    ┌────▼────────────────────────────────────┐
    │  Agents / Tools / Workflows              │
    │  ClaudeCode · Antigravity · GitTool      │
    │  GitHubTool · BrowserTool · DevWorkflow  │
    └────┬────────────────────────────────────┘
         │
    ┌────▼────────┐
    │  PostgreSQL  │  ← Tasks, projects, executions, approvals, memories
    └─────────────┘
```

## Chat Flow — Intent Classification

When a message arrives at `POST /chat`, the orchestrator classifies it:

```
User Message
     │
     ▼
 classify()  ← regex + keyword matching (no LLM)
     │
     ├─ QUERY ───► Answer directly (list projects, status)
     │             No task created. Returns ChatResponse(answer=...)
     │
     ├─ WORKFLOW ─► Issue # + workflow keyword detected
     │              Creates task → auto-dispatches DevWorkflow
     │
     └─ ACTION ──► Everything else
                    Creates task → plans → auto-dispatches agent
```

### Intent Rules

| Intent   | Trigger                                    | Example                    |
|----------|--------------------------------------------|----------------------------|
| QUERY    | Matches query regex (status, projects, etc)| "check my projects"        |
| WORKFLOW | Issue number + workflow keyword             | "fix issue #72"            |
| ACTION   | Default fallback                           | "deploy staging"           |

### Project Resolution

Before creating a task, the orchestrator resolves project references:

1. Extract project hint from message (e.g., "test **MinaarTech**" → "MinaarTech")
2. If hint starts with `PROJ-` → exact ID lookup
3. Else → case-insensitive substring search via `find_by_name()`
4. Fall back to `chat.project_id` if provided
5. Fall back to `None` if no match

## Task State Machine

```
CREATED → PLANNING → WAITING_FOR_APPROVAL → RUNNING → VERIFYING → COMPLETED
                   ↘ RUNNING ─────────────────────────↗
                     ↓                                  ↓
                   FAILED ← ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┘
                     ↓
                   PLANNING  (retry)

Any non-terminal state → CANCELLED
```

Terminal states: `COMPLETED`, `CANCELLED`. `FAILED` allows retry back to `PLANNING`.

## Agent Routing

The `AgentRouter` selects which agent handles a task:

1. Check project's `preferred_agent` setting
2. Fall back to default agent (claude-code)
3. On agent creation failure → try fallback agent
4. On fallback failure → task transitions to FAILED

Agents are registered in `AgentRegistry` via factory functions. Each agent runs as a subprocess with sanitized environment variables.

## DevWorkflow Lifecycle

For WORKFLOW intents (issue-based tasks):

1. Create task
2. Fetch GitHub issue details
3. Resolve project (working directory, repo)
4. Retrieve memory context
5. Create git branch (`jarvis/issue-N-slug`)
6. Implementation loop (agent runs, test, retry on failure)
7. Inspect diff
8. Commit changes
9. Push (approval-gated if configured)
10. Create pull request
11. Monitor CI (poll, auto-fix on failure)
12. Report result

## Event Bus and Audit Logging

All state changes publish events through the in-process `EventBus`:

- Task lifecycle: `TASK_CREATED`, `TASK_STATE_CHANGED`, `TASK_COMPLETED`, `TASK_FAILED`
- Agent events: `AGENT_EXECUTION_STARTED`, `AGENT_EXECUTION_COMPLETED`, `AGENT_FALLBACK_TRIGGERED`
- Workflow events: `WORKFLOW_STARTED`, `WORKFLOW_STEP_*`, `WORKFLOW_COMPLETED`
- Query events: `QUERY_ANSWERED`

The `AuditLogger` subscribes to all events and logs them. SSE endpoint (`GET /events/stream`) streams events to the desktop client.

## Security Model

- **Permission Gate**: Tools are classified by risk level (SAFE, REQUIRES_APPROVAL, BLOCKED)
- **Approval Service**: High-risk operations require human approval before execution
- **Input Validation**: Pydantic models validate all API inputs
- **Working Directory Validation**: Path traversal protection via `validate_working_dir()`
- **Secret Filtering**: Agent output is scanned and secrets are redacted
- **Environment Sanitization**: Agent subprocesses receive only allowlisted env vars

## Configuration

TOML-based configuration (`jarvis.toml`) with environment variable overrides:

```
JARVIS_DATABASE__URL=postgresql+asyncpg://...
JARVIS_AGENTS__DEFAULT_AGENT=claude-code
JARVIS_AGENTS__TIMEOUT_SECONDS=300
JARVIS_WORKFLOW__BRANCH_PREFIX=jarvis
JARVIS_SCHEDULER__POLL_INTERVAL_SECONDS=60
```

Key config sections: `database`, `agents`, `browser`, `computer`, `workflow`, `scheduler`, `notification`.

## Testing Strategy

- **Unit tests**: Services, models, intent classifier, resolver — all use SQLite in-memory
- **Integration tests**: Orchestrator with real DB, mocked agents
- **API tests**: Full HTTP round-trips via `httpx.AsyncClient` + `ASGITransport`
- **680+ tests**, all async via `pytest-asyncio`
- No external dependencies required for testing (no Docker, no real agents)
