# Stage 7: Memory and Context

## Overview

Persistent memory system for Jarvis that stores project info, user preferences, task history, decisions, and conversation summaries across sessions. Memories are automatically injected into agent prompts as context during task dispatch.

## Architecture

### Domain Model

- **MemoryType**: `project_memory`, `user_preference`, `task_history`, `decision`, `conversation_summary`
- **MemoryScope**: `global` (no project) or `project` (tied to a project_id)
- **Memory**: Full representation with content, tags, metadata, versioning
- **MemorySummary**: Lightweight view for list endpoints

### Database

New `memories` table with columns:
- `id` (PK), `memory_type`, `scope`, `project_id`, `key`, `content`
- `embedding` (nullable JSON — reserved for future vector search)
- `tags` (JSON array), `metadata` (JSON object)
- `version`, `created_at`, `updated_at`

Indexed on: `memory_type`, `scope`, `project_id`, `key`.

### Service Layer

`MemoryService` follows the same patterns as `ProjectService`:
- Session as first argument, flush (not commit)
- Module-level `_row_to_memory()` converter
- Event publishing on create/update/delete

Key methods:
- `create_memory` — auto-derives scope from project_id presence
- `get_by_key` — lookup by key with optional type/project filters
- `search` — ILIKE on content and key columns
- `retrieve_context` — project-scoped results first, then global, deduped

### Context Injection

The `Orchestrator.dispatch_task` method calls `retrieve_context()` before agent creation. Matching memories are prepended to the task request as a context block:

```
Context:
[user_preference] editor: vim
[project_memory] stack: Python + FastAPI

Request:
<original request>
```

This is backward-compatible — if no `MemoryService` is configured, dispatch works as before.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/memories` | Create a memory |
| GET | `/memories` | List memories (filter by type, project) |
| GET | `/memories/search` | Search by content/key |
| GET | `/memories/{id}` | Get memory details |
| PATCH | `/memories/{id}` | Update memory fields |
| DELETE | `/memories/{id}` | Delete a memory |

## Configuration

```toml
[memory]
max_context_memories = 10
search_limit = 20
```

## Future: Vector Search

The `embedding` column is nullable JSON, ready for storing vector embeddings. When added:
1. Populate embeddings on create/update via an embedding model
2. Add a vector similarity search method to `MemoryService`
3. Use it in `retrieve_context` alongside or instead of ILIKE search
