# Stage 8: Security and Human Approval System

## Overview

Stage 8 adds persistent approval workflows, security hardening, and secret filtering to Jarvis.

## Features

### Approval Service
- Persistent approval request lifecycle: create → pending → approved/denied/expired
- Database-backed via `approval_requests` table
- Event-driven: publishes `APPROVAL_REQUESTED`, `APPROVAL_APPROVED`, `APPROVAL_DENIED`, `APPROVAL_EXPIRED`
- Automatic expiration of stale requests

### Approval API
- `GET /approvals` — list approval requests (filter by status, task_id)
- `GET /approvals/{id}` — get full approval request details
- `POST /approvals/{id}/approve` — approve a pending request
- `POST /approvals/{id}/reject` — reject a pending request

### Enhanced Permission Gate
- Original sync `check()` remains for backward compatibility
- New async `check_with_approval()` checks in-memory pre-approvals first, then falls back to DB lookup via ApprovalService
- Tool execution endpoint auto-creates approval requests when `ApprovalRequiredError` is raised, returning the `approval_id` in the 403 response

### Security Hardening
- **Path traversal prevention**: `validate_working_dir()` resolves paths and checks against allowed roots
- **Shell injection detection**: `sanitize_tool_args()` detects `;`, `|`, `&&`, backticks, `$()` patterns
- **Secret filtering**: `filter_secrets()` redacts API keys, tokens, passwords, AWS keys, GitHub tokens, private keys, Slack tokens
- GitTool validates working directory before execution

### Audit Integration
- Approval events recorded with `approval_state` on `AuditEntry`

## Database

New table: `approval_requests`
- Migration: `d4e5f6a7b8c9` (chains from `c3d4e5f6a7b8`)

## Key Files

| File | Purpose |
|------|---------|
| `src/jarvis/models/approval.py` | Approval models (Full, Summary, Decision, errors) |
| `src/jarvis/db/tables.py` | `ApprovalRequestRow` ORM model |
| `src/jarvis/services/approval_service.py` | Approval lifecycle service |
| `src/jarvis/permissions/gate.py` | Enhanced PermissionGate with DB lookup |
| `src/jarvis/api/routes/approvals.py` | Approval REST endpoints |
| `src/jarvis/security/validators.py` | Path traversal & shell injection prevention |
| `src/jarvis/security/secrets.py` | Secret detection & filtering |
| `src/jarvis/events.py` | Approval event types |
