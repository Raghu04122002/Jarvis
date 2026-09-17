# Jarvis — Architecture

## System Overview

Jarvis is a local-first personal AI orchestration system. It does not replace AI coding agents — it **orchestrates** them alongside developer tools, browser automation, and system capabilities.

```
┌─────────────────────────────────────────────────┐
│                   USER                          │
│         (Voice / CLI / Web UI / Desktop)        │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│               JARVIS UI LAYER                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Tauri    │  │ Web UI   │  │ CLI          │  │
│  │ Desktop  │  │ (React)  │  │ (Click/Rich) │  │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘  │
└───────┼──────────────┼───────────────┼──────────┘
        │              │               │
┌───────▼──────────────▼───────────────▼──────────┐
│                  API LAYER                      │
│              FastAPI + WebSocket                │
│  ┌──────────────────────────────────────────┐   │
│  │ REST endpoints + WS for real-time events │   │
│  └──────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│               ORCHESTRATOR                      │
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Planner  │  │ Task     │  │ Agent        │  │
│  │          │  │ Manager  │  │ Router       │  │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘  │
│       │              │               │          │
│  ┌────▼─────────────▼───────────────▼───────┐  │
│  │          Execution Engine                 │  │
│  │  (async task runner, retry, escalation)   │  │
│  └──────────────────┬───────────────────────┘  │
└─────────────────────┼──────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
┌───────▼───┐  ┌──────▼──┐  ┌──────▼──────┐
│ Permission│  │ Approval│  │ Audit       │
│ Gate      │  │ Workflow│  │ Logger      │
└───────┬───┘  └────┬────┘  └─────────────┘
        │           │
┌───────▼───────────▼─────────────────────────────┐
│              AGENT / TOOL LAYER                 │
│                                                 │
│  Agents:                                        │
│  ┌────────────┐ ┌────────────┐ ┌─────────────┐  │
│  │ClaudeCode  │ │Antigravity │ │ Future      │  │
│  │Adapter     │ │Adapter     │ │ Adapters    │  │
│  └────────────┘ └────────────┘ └─────────────┘  │
│                                                 │
│  Tools:                                         │
│  ┌─────┐ ┌─────┐ ┌──────┐ ┌────────┐ ┌──────┐  │
│  │Term │ │Git  │ │GitHub│ │Browser │ │FS    │  │
│  └─────┘ └─────┘ └──────┘ └────────┘ └──────┘  │
└─────────────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│              DATA LAYER                         │
│  ┌────────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ PostgreSQL │ │ Memory   │ │ Secrets      │   │
│  │ (tasks,    │ │ Store    │ │ Vault        │   │
│  │  audit,    │ │          │ │              │   │
│  │  projects) │ │          │ │              │   │
│  └────────────┘ └──────────┘ └──────────────┘   │
└─────────────────────────────────────────────────┘
```

## Core Components

### 1. API Layer (FastAPI)
- REST endpoints for task CRUD, project management, configuration
- WebSocket for real-time task status, logs, approval requests
- Authentication for local access (token-based)

### 2. Orchestrator
- Receives user intent (natural language or structured command)
- Delegates to Planner for task decomposition
- Routes subtasks to appropriate agents/tools via Agent Router
- Manages task lifecycle (create → plan → approve → execute → verify → complete)
- Handles errors, retries, and escalation

### 3. Planner
- Decomposes high-level requests into executable steps
- Uses an LLM (configurable) to generate plans
- Returns structured plan with steps, dependencies, and risk levels
- Plans are presented to user before execution

### 4. Agent Router
- Selects the best agent for a given subtask
- Considers: project config, task type, agent availability, past performance
- Supports fallback chains (e.g., try Claude Code, fall back to Antigravity)

### 5. Agent Adapters
- Common interface: `run(task)`, `status()`, `cancel()`, `get_result()`
- Each adapter wraps a specific AI agent's CLI/API
- ClaudeCodeAdapter: invokes `claude` CLI in subprocess
- AntigravityAdapter: invokes Antigravity CLI
- Adapters are stateless wrappers; state lives in TaskManager

### 6. Tool Registry
- Tools register with: name, description, input schema, risk level, permission requirements
- Tools are invoked by agents or directly by the orchestrator
- Built-in tools: Terminal, FileSystem, Git, GitHub, Browser, Notification

### 7. Permission System
- Centralized gate checked before every tool execution
- Three levels: SAFE (auto-approve), REQUIRES_APPROVAL (ask user), BLOCKED (never)
- Configurable per-project overrides
- Approval requests sent via WebSocket to UI

### 8. Task Manager
- Tracks all tasks and their state machine
- States: CREATED → PLANNING → WAITING_FOR_APPROVAL → RUNNING → VERIFYING → COMPLETED/FAILED/CANCELLED
- Stores execution history, logs, and results
- Supports long-running tasks with periodic status updates

### 9. Audit Logger
- Records every significant action
- Fields: timestamp, task_id, agent, tool, args_metadata, result, success, duration, approval_state
- Secrets are never logged
- Queryable via API

### 10. Memory Store
- Per-project persistent context
- Stores: decisions, patterns, lessons learned, user preferences
- Designed for future pgvector integration (semantic search)

### 11. Project Registry
- Manages multiple projects with metadata
- Fields: name, path, repo, branch, stack, preferred agent, deploy info, env metadata, instructions

### 12. Secrets Vault
- Abstracts secret storage (env vars initially, keychain later)
- Secrets never appear in logs, prompts, or API responses
- Accessed by tools via reference, not value

## Data Model (PostgreSQL)

### Implemented (Stage 1)

```
tasks
  id            VARCHAR(32)   PK
  request       TEXT          NOT NULL
  title         VARCHAR(200)  NOT NULL
  description   TEXT
  status        VARCHAR(30)   NOT NULL  (indexed)
  priority      VARCHAR(20)   NOT NULL  (indexed)
  project_id    VARCHAR(100)
  parent_task_id VARCHAR(32)
  plan          JSON
  current_step  INTEGER
  result        TEXT
  error         TEXT
  metadata      JSON
  version       INTEGER       NOT NULL  (OCC)
  created_at    TIMESTAMP WITH TZ
  updated_at    TIMESTAMP WITH TZ
  started_at    TIMESTAMP WITH TZ
  completed_at  TIMESTAMP WITH TZ

task_steps
  id            VARCHAR(32)   PK
  task_id       VARCHAR(32)   NOT NULL  (indexed)
  sequence      INTEGER       NOT NULL
  description   TEXT          NOT NULL
  status        VARCHAR(20)   NOT NULL
  depends_on    JSON
  result        TEXT
  error         TEXT
  created_at    TIMESTAMP WITH TZ
  started_at    TIMESTAMP WITH TZ
  completed_at  TIMESTAMP WITH TZ
```

### Planned (Future Stages)

```
projects
  id, name, path, github_repo, default_branch, stack, preferred_agent,
  deploy_config, env_metadata, instructions, created_at, updated_at

audit_logs
  id, task_id, timestamp, agent, tool, action, args_metadata,
  result_summary, success, duration_ms, approval_state

memory
  id, project_id, category, key, content, embedding (future),
  created_at, updated_at

approvals
  id, task_id, step_id, action, risk_level, status, requested_at,
  responded_at, response
```

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent communication | CLI subprocess | Claude Code and Antigravity are CLI tools; subprocess is simplest |
| Real-time updates | WebSocket | Low latency for approval prompts and live logs |
| Task persistence | PostgreSQL | Relational integrity, future pgvector, proven reliability |
| Secret storage | Env vars + abstraction | Simple start, upgrade path to system keychain |
| Desktop app | Tauri | Native feel, low resource usage, Rust + web stack |
| CLI interface | Click + Rich | Python-native, good UX for terminal users |
| Config format | TOML | Human-readable, good Python support |
