# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Windows-MCP is a Python MCP (Model Context Protocol) server that bridges AI LLM agents with the Windows OS, enabling direct desktop automation. It exposes 21 tools via FastMCP:

| Group | Tools |
|---|---|
| Capture | `Screenshot`, `Snapshot`, `Scrape`, `DisplayInventory`, `FindText` (OCR) |
| Input | `Click`, `Type`, `Scroll`, `Move` (also drag-and-drop via `drag=True`), `Shortcut`, `MultiSelect`, `MultiEdit` |
| Timing | `Wait`, `WaitFor` |
| System | `App`, `PowerShell`, `FileSystem`, `Registry`, `Process`, `Clipboard`, `Notification` |

Tool names are defined by the `name=` argument of each `@mcp.tool(...)` in `src/windows_mcp/tools/`; that directory is the source of truth. Note the shell tool is registered as `PowerShell`, not `Shell`. Any subset can be removed at startup with `--exclude-tools` (e.g. `--exclude-tools PowerShell,Registry`), or `--tools` lists the only ones to keep.

## Build & Development Commands

```bash
uv sync                          # Install dependencies
uv run windows-mcp serve         # Run the MCP server (stdio; --transport sse|streamable-http for HTTP)
ruff format .                    # Format code
ruff check .                     # Lint code
ruff check --fix .               # Lint and auto-fix
pytest                           # Run all tests
pytest tests/test_foo.py         # Run a single test file
python scripts/check_versions.py # Check the four version strings agree (run before a release)
```

`windows-mcp` is a click command group: `serve`, `install` / `uninstall` (run the server as a background scheduled task) and `auth` (generate HTTP credentials; `--with-tls` adds a self-signed cert). Bare `windows-mcp` does not start the server, and serve flags placed before the subcommand are rejected with a hint. `serve` also reads `~/.windows-mcp/config.toml` (`--config` to override); explicit flags win.

The version lives in `pyproject.toml`, `uv.lock`, `manifest.json` and `server.json` `packages[].version` (not the top-level `server.json` version, which is the registry entry's own 1.x line). Bump all of them together; `scripts/check_versions.py` catches drift.

On this PC Avast breaks TLS to PyPI (`invalid peer certificate: BadSignature`, even with `--native-tls`), so refresh the lock after a dependency edit with `uv lock --offline` (works when every package is already cached). While a windows-mcp server from this `.venv` is running, `uv run` cannot reinstall the project (`windows-mcp.exe` is locked) after `pyproject.toml` changes; use `uv run --no-sync ...`.

**Package manager**: UV (not pip). **Python**: 3.14+ (`requires-python = ">=3.14"`; `.python-version` is `3.14`, any patch release: a pinned 3.14.7 could not be downloaded by this PC's uv and made every `uv run` warn "incompatible environment"; use `uv sync --extra dev`, since pytest/ruff live in the `dev` extra). **Build backend**: Hatchling.

## Architecture

The codebase follows a layered service architecture under `src/windows_mcp/`:

**Entry point** — `__main__.py`: Builds the FastMCP server, parses CLI flags, and selects the transport. Tool registration is delegated to `tools.register_all()`; an async lifespan initializes the Desktop, WatchDog, and Analytics singletons, which tools resolve lazily through the `get_desktop` / `get_analytics` callables.

**Tools layer** — `tools/`: One module per tool group, each exposing `register(mcp, *, get_desktop, get_analytics)`. `tools/__init__.py` holds the module list and `register_all()`. Tool functions are thin — they normalize arguments and delegate to a service package. The `@with_analytics` decorator wraps each one for telemetry, making it the existing precedent for cross-cutting concerns at the tool boundary. A failure must reach the client as a tool error (`is_error=True`), never as returned text: raise, or put `@raise_error_replies` (`tools/_output.py`, inside `@with_analytics`) on tools whose service reports failures as text starting with "Error". Long replies go through `cap_text` (50,000 characters). Input tools also carry `@note_new_windows` (`tools/_new_windows.py`), which names windows that appeared since the previous input action, and dialogs drawn inside the front window of a XAML app (Notepad's "save changes?"; UIA search limited to XAML apps because it costs up to ~0.18 s elsewhere); a new input tool needs it too.

**Desktop service** — `desktop/service.py`: High-level orchestrator. Manages window operations (launch, resize, switch), screenshots, mouse/keyboard actions, and clipboard. Interfaces with Tree service for UI element discovery. App's window modes (minimize/maximize/restore/close/list/move) live in `desktop/window_control.py`, acting on the window `Desktop.pick_window` chose (handle, name, or the live front window). `desktop/views.py` defines data models: `DesktopState`, `Window`, `Size`, `BoundingBox`, `Status`.

**Tree service** — `tree/service.py`: Captures the Windows accessibility tree from active and background windows. Identifies interactive elements and scrollable areas. Uses `ThreadPoolExecutor` for multi-threaded UI traversal. `tree/views.py` defines `TreeElementNode`, `ScrollElementNode`, `TreeState`. `tree/config.py` has control type configurations.

**UIAutomation wrapper** — `uia/`: Low-level abstraction over the Windows UIAutomation COM API via `comtypes`. `core.py` wraps the main automation object, `controls.py` has control-specific logic, `patterns.py` wraps UIAutomation patterns, `enums.py` has COM enumerations, `events.py` handles event subscriptions. `controls.py`, `core.py`, `patterns.py` and `enums.py` (2,000–6,400 lines each) derive from yinkaisheng's Python-UIAutomation-for-Windows (Apache 2.0): keep edits surgical and do not split them for size.

**WatchDog** — `watchdog/service.py`: Runs in a separate thread monitoring UI focus changes via UIAutomation events. Notifies the Tree service of focus changes so the accessibility tree stays current.

**Virtual Desktop Manager** — `vdm/core.py`: Tracks which windows belong to which Windows virtual desktop (Win10/11).

**Domain services** — thin packages backing the system tools: `filesystem/` (read/write/copy/move/delete/list/search/info), `registry/` (get/set/delete/list, implemented via PowerShell cmdlets), `powershell/` (`PowerShellExecutor` plus environment resolution), `process/` (list/kill), `notifications/`, `clipboard/` (text, images, file lists; pywin32's `CountClipboardFormats` raises on an empty clipboard, so emptiness is checked with `EnumClipboardFormats(0)`). Registry and PowerShell tools shell out, so their latency is dominated by process startup. `ocr/` (FindText, WaitFor `screen_text`) runs `Windows.Media.Ocr` through Windows PowerShell 5.1 on a temporary PNG, pinned to `powershell` because pwsh 7 cannot load WinRT types (no WinRT Python package is installed).

**Infrastructure** — `infrastructure/`: cross-cutting concerns. `analytics.py` (optional PostHog telemetry, disabled with `ANONYMIZED_TELEMETRY=false`; records tool names and errors only, never arguments or outputs), `auth.py` and `oauth.py` (bearer-token and OAuth middleware for HTTP transports), `security.py` (SSRF validation, IP allowlist middleware), `config.py` (server configuration), `action_log.py` (opt-in per-call log; `with_analytics` labels differ from four tool names, so the log maps them back). Note `windows_mcp/config.py` at the package root is unrelated — it only holds the `WINDOWS_MCP_DEBUG` helpers.

## Code Style

- Formatter/linter: **Ruff** (line length 100, double quotes)
- Naming: PEP 8 — `snake_case` functions/variables, `PascalCase` classes, `UPPER_CASE` constants
- Type hints required on function signatures
- Google-style docstrings for public functions/classes

## Key Design Details

- Screenshots are capped to 1920x1080 for token efficiency
- Mouse/keyboard input uses UIA (same coordinate space as BoundingRectangle; no DPI mismatch)
- Screenshot is the preferred fast visual-context tool; Snapshot is the heavier path for UI element ids and DOM extraction
- Browser detection (Chrome, Edge, Firefox) triggers special DOM extraction mode in Snapshot
- Fuzzy string matching (`thefuzz`) is used for element name matching
- UI element fetching has retry logic (`THREAD_MAX_RETRIES=3` in tree service)
- The server supports stdio, SSE, and streamable HTTP transports
- `serve()` drops `SSLKEYLOGFILE` at startup (`_drop_ssl_keylog_env`): Avast/AVG inject it into every process, and this Python's OpenSSL then aborts the whole server on the first HTTPS request. Keep it. Test scripts that act as HTTP(S) clients (e.g. the FastMCP client) hit the same abort (`OPENSSL_Uplink ... no OPENSSL_Applink`); run them with `SSLKEYLOGFILE` unset (`env -u SSLKEYLOGFILE ...`).
- Docs live in `docs/` (test reports in `docs/testing/`); plans and task files in `Plan/`.
- A local, unversioned `.git/hooks/post-commit` refreshes the GitNexus index in the background after each commit (`gitnexus analyze --skip-agents-md --skip-skills`; log `.git/gitnexus-analyze.log`, lock dir `.git/gitnexus-analyze.lock`). A fresh clone does not have it.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `WINDOWS_MCP_SCREENSHOT_SCALE` | `1.0` | Scale factor for screenshots (range `0.1`–`1.0`). Lower on 1440p/4K to stay under Claude Desktop's 1 MB limit. Resolved in `tools/_snapshot_helpers.py`. |
| `WINDOWS_MCP_RAW_COORDINATES` | _(off)_ | Set to `1`/`true`/`yes`/`on` to keep every coordinate in screen pixels. Off: a full screenshot shrunk by `s` makes image pixels the coordinate space (input divided by `s`, printed positions multiplied by `s`; App window_loc/size and DisplayInventory excluded). Resolved in `tools/_coords.py`. |
| `WINDOWS_MCP_SCREENSHOT_BACKEND` | `auto` | Screenshot backend: `auto`, `dxcam`, `mss`, `pillow`. `mss` is optional and not installed by default; a pinned backend that cannot run warns and uses `pillow`. Resolved in `desktop/screenshot.py`. |
| `WINDOWS_MCP_MAX_TREE_ELEMENTS` | `500` | Max UI elements a single Snapshot/WaitFor tree capture may collect before it stops descending and returns a truncated tree (with a note in the output). Bounds both traversal time and response size on huge flat lists/grids (e.g. an unfiltered inventory view with thousands of rows). Resolved in `tree/budget.py`. |
| `WINDOWS_MCP_PROFILE_SNAPSHOT` | _(off)_ | Set to `1`/`true`/`yes`/`on` to log per-stage timing for Screenshot/Snapshot. Checked in `tools/_snapshot_helpers.py` and `desktop/service.py`. |
| `ANONYMIZED_TELEMETRY` | `true` | Set to `false` to disable PostHog telemetry. Checked in `__main__.py` and `infrastructure/analytics.py`. |
| `POSTHOG_API_KEY` | Project default | Override the PostHog project write key used for anonymous telemetry. Set to an empty string to skip PostHog client initialization. Checked in `infrastructure/analytics.py`. |
| `POSTHOG_HOST` | `https://us.i.posthog.com` | Override the PostHog host for anonymous telemetry, such as for a self-hosted PostHog deployment. Checked in `infrastructure/analytics.py`. |
| `WINDOWS_MCP_WATCHDOG` | _(off)_ | Set to `on`/`1`/`true`/`yes`/`enabled` to start the UIA focus WatchDog thread. Unset, or any other value, leaves it off. Opt-in because it only emits debug logging today but can crash the server via the UIA event pump (#332). Resolved in `__main__.py`. |
| `WINDOWS_MCP_DEBUG` | `false` | Set to `1`/`true`/`yes`/`on` to enable debug mode. Checked in `config.py`. Also available as `--debug` CLI flag. |
| `WINDOWS_MCP_READ_VSCODE` | _(off)_ | Set to `1`/`true`/`yes`/`on` to let Snapshot/WaitFor read the UI tree of VS Code-family windows (Code, Cursor, Windsurf, Antigravity, VSCodium). Off because one read pins VS Code at 100% CPU, "Not Responding" until restart, and returns nothing. Resolved in `tree/utils.py`. |
| `WINDOWS_MCP_DISABLE_FLASH` | _(off)_ | Set to `1`/`true`/`yes`/`on` to suppress the orange-red glowing border that briefly appears after every screenshot. Resolved in `desktop/flash_overlay.py`. |

`serve` flags can also be set by environment variable (click `envvar=` in `__main__.py`): `WINDOWS_MCP_AUTH_KEY`, `WINDOWS_MCP_IP_ALLOWLIST`, `WINDOWS_MCP_CORS_ORIGINS`, `WINDOWS_MCP_SSL_CERTFILE`, `WINDOWS_MCP_SSL_KEYFILE`, `WINDOWS_MCP_OAUTH_CLIENT_ID`, `WINDOWS_MCP_OAUTH_CLIENT_SECRET`, `WINDOWS_MCP_STATELESS_HTTP`, `WINDOWS_MCP_TOOLS`, `WINDOWS_MCP_EXCLUDE_TOOLS`, `WINDOWS_MCP_ACTION_LOG`. See `windows-mcp serve --help` for each one's meaning.

## Working Conventions

- This repo is a fork of `CursorTouch/Windows-MCP`. The open bug backlog is the active (not `completed/`) file in `Plan/`.
- Commits use a type prefix (`fix:`, `docs:`, `style:`, `test:`) and cite the backlog item: `fix: Registry reads the (Default) value (round-2 3.25)`. When `ruff format` rewrites a file wholesale, commit that alone first as `style: ...` with "no behaviour change" in the body, then the fix on top.
- Zero warnings (user rule, 2026-09-24): a pytest, ruff, uv, git or live-test run counts as clean only with no warnings, not just no failures. Fix each warning's cause; never hide it with a filter, `noqa`, ignore setting or `2>/dev/null`. A warning that cannot be fixed here is reported to the user with the reason. Files are LF (`.gitattributes`): a script that rewrites a file must use `write_bytes` or `newline="\n"`, since Python's `write_text` writes CRLF on Windows and git then warns.
- Unit tests never send real input: `tests/conftest.py` `_no_real_input` stubs user32's `SendInput`/`keybd_event`/`mouse_event`/`SetCursorPos` for every test. Keep it; before it, tests typed "hi"/"new" into whatever window was in front (a user's Notepad note, 2026-09-28).
- Unit tests cannot prove input, focus or UI-tree behaviour. Prove those live with the `windows-mcp-live-test` skill: throwaway test window, in-process server, never a tree read of a VS Code-family window.
- Never put personal details (user or machine names, private folder paths) in tracked files.

## Skills and Keeping Them Current

| Skill | Use |
|---|---|
| `.claude/skills/windows-mcp-tool-tester/` | Black-box test one tool through its MCP schema, with a structured report. |
| `.claude/skills/windows-mcp-live-test/` | Prove a code change on the real desktop with a guarded test window. |
| `Skills/windows-mcp/` | Field guide Claude Desktop reads before using the tools: a short `SKILL.md` plus `references/` per tool group; PyPI-release differences only in `references/pypi-differences.md`, open problems in `references/known-gaps.md`. |

**Mandatory:** when a task teaches something new (a tool behaviour, a testing pitfall, a workaround) or makes any of these skills wrong or incomplete, update that skill in the same task, and name the change in the reply to the user. A fix that changes what a tool does, accepts or replies must update that tool's entry in `Skills/windows-mcp/references/`, and remove its line from `known-gaps.md` if it had one. Likewise, update this file when commands, environment variables, architecture or conventions change. Keep both short: record what is non-obvious, not what the code already says. (Skills outside this repo still need the user's approval before editing.)

## Security Context

This server has **full system access** with no sandboxing. `PowerShell`, `FileSystem`, `Registry`, `Process`, and `App` can all perform irreversible operations, and there is no rollback; an opt-in action log (`--action-log`, `infrastructure/action_log.py`, written from inside `with_analytics` so every tool is covered) records each call with secrets hidden. The recommended deployment target is a VM or Windows Sandbox. Use `--exclude-tools` (or `--tools`) to drop the tools a given deployment does not need.
