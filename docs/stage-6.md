# Stage 6: Browser Automation

## Overview

Stage 6 adds browser automation to Jarvis via a `BrowserTool` built on Playwright's async Python API. This enables automated web testing, form interaction, and page inspection through the existing tool infrastructure.

## Components

### BrowserSession

Manages the Playwright lifecycle (browser, context, page):

- `start()` — launches headless Chromium, creates browser context and page
- `close()` — tears down all resources safely (idempotent)
- `is_running` — whether the browser is connected
- `page` — the active Playwright page (raises `BrowserNotStartedError` if not started)

### BrowserTool

Extends `BaseTool` with 9 operations:

| Operation | Risk Level | Description |
|-----------|-----------|-------------|
| `navigate` | REQUIRES_APPROVAL | Navigate to a URL (lazy-starts session) |
| `click` | REQUIRES_APPROVAL | Click an element by CSS selector |
| `fill` | REQUIRES_APPROVAL | Fill an input field |
| `press` | REQUIRES_APPROVAL | Press a keyboard key |
| `screenshot` | SAFE | Capture page screenshot |
| `get_page_info` | SAFE | Get current URL and title |
| `inspect` | SAFE | Query elements and return tag/text/attributes |
| `wait` | SAFE | Wait for selector or load state |
| `close` | SAFE | Close the browser session |

### URL Security

The tool enforces domain restrictions:

- **Blocked domains**: Financial sites blocked by default (`*.bank.*`, `*.paypal.com`, etc.)
- **Allowed domains**: Optional allowlist — when non-empty, only matching domains are permitted
- **Defense-in-depth**: URLs checked before `navigate` and after `click` (in case click triggers navigation)
- **Wildcard support**: Uses `fnmatch` patterns (e.g., `*.example.com`)

## Configuration

```toml
[browser]
headless = true
default_timeout_ms = 30000
viewport_width = 1280
viewport_height = 720
allowed_domains = []
blocked_domains = ["*.bank.*", "*.paypal.com", "pay.google.com", "venmo.com"]
```

All settings can be overridden via environment variables: `JARVIS_BROWSER__HEADLESS=false`.

## Dependencies

- `playwright>=1.40,<2` (added to `pyproject.toml`)
- Requires `playwright install chromium` after installation

## Files

- `src/jarvis/tools/browser_tool.py` — BrowserSession + BrowserTool
- `src/jarvis/config.py` — BrowserConfig model
- `config/default.toml` — default browser settings
- `tests/test_tools/test_browser_tool.py` — ~30 tests with local FastAPI test server
