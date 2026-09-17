# Jarvis — Security Model

## Principles

1. **Least privilege** — tools get only the access they need
2. **No secrets in context** — API keys and credentials never appear in LLM prompts, logs, or API responses
3. **Human in the loop** — destructive or external-facing actions require user approval
4. **Audit everything** — every action is logged (excluding secret values)
5. **Defense in depth** — multiple layers of validation before execution

## Permission Levels

### SAFE (auto-approved)
| Action | Examples |
|--------|----------|
| Read files | cat, read, search |
| Search files | grep, glob, find |
| Git read operations | status, diff, log, branch list |
| Run tests | pytest, jest, cargo test |
| Run linters | ruff, eslint, clippy |
| Read GitHub info | issue list, PR list, repo info |
| Read project config | settings, metadata |

### REQUIRES_APPROVAL (user must confirm)
| Action | Examples |
|--------|----------|
| Git push | push to any remote |
| Create pull request | gh pr create |
| Merge pull request | gh pr merge |
| Deploy | any deploy command |
| Install dependencies | pip install, npm install |
| Modify env config | .env changes, config changes |
| Database migrations | schema changes |
| Delete files | rm, unlink |
| External communication | notifications, webhooks |
| Write/modify files | create, edit, overwrite |

### BLOCKED (never allowed)
| Action | Why |
|--------|-----|
| Unrestricted destructive system ops | rm -rf /, format, etc. |
| Credential extraction | reading keychain, password stores |
| Secret disclosure | printing/logging secrets |
| Arbitrary network access | unconstrained outbound requests |
| Privilege escalation | sudo, chmod 777, etc. |

## Secrets Management

### Architecture
```
┌─────────────────┐
│ Tool requests    │
│ secret by name   │──→ SecretsVault.get("GITHUB_TOKEN")
└─────────────────┘              │
                                 ▼
                    ┌─────────────────────┐
                    │ SecretsVault        │
                    │  - env vars         │
                    │  - .env files       │
                    │  - (future) keychain│
                    └──────────┬──────────┘
                               │
                               ▼
                    Returns value directly to tool
                    (never to LLM context or logs)
```

### Rules
- Secrets are referenced by name in tool configurations
- The SecretsVault resolves names to values at execution time
- Values are passed directly to the tool, never through the orchestrator's LLM context
- Audit logs record "secret_ref: GITHUB_TOKEN" not the value
- `.env` files are in `.gitignore`

## Approval Workflow

1. Tool declares its risk level via the Tool Registry
2. Before execution, the Permission Gate checks the risk level
3. If REQUIRES_APPROVAL:
   - Approval request sent to UI via WebSocket
   - Task pauses in WAITING_FOR_APPROVAL state
   - User sees: action, tool, arguments (secrets redacted), risk level
   - User approves or denies
   - Decision is logged in audit trail
4. If BLOCKED: execution is refused, user is notified
5. If SAFE: execution proceeds

## Input Validation

- All API inputs validated via Pydantic models
- Tool arguments validated against declared schemas
- File paths are sanitized (no path traversal)
- Command arguments are escaped (no injection)

## Network Security

- API listens on localhost only by default
- Optional token-based auth for remote access
- No sensitive data in URL parameters
- HTTPS required for any non-localhost communication
