---
Title: Settings (environment variables)
Description: Every environment variable Windows-MCP reads - screenshots and coordinates, UI-tree reading limits, server and security options, telemetry, debug and the focus watchdog - plus the Claude Desktop extension's settings screen and how to set variables in a client config.
---

# Settings

All settings are optional. In most clients you set them in the server's `env` block:

```json
{
  "mcpServers": {
    "windows-mcp": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/farazpawle/Windows-MCP@v0.9.0", "windows-mcp", "serve"],
      "env": { "WINDOWS_MCP_SCREENSHOT_SCALE": "0.5" }
    }
  }
}
```

Switches accept `1`, `true`, `yes` or `on`.

## Claude Desktop extension

The extension's settings screen covers the common switches: anonymous telemetry, performance
logging for screenshots, the screenshot method, debug logging, and the focus watchdog. The
variables below that are not on that screen need a manual config
([install guide](install.md#option-b-manual-config)).

## Screenshots and coordinates

| Variable | Default | What it does |
|---|---|---|
| `WINDOWS_MCP_SCREENSHOT_SCALE` | `1.0` | Shrinks screenshots (`0.1`-`1.0`). Lower it on 1440p or 4K screens to stay under Claude Desktop's 1 MB limit; `0.5` quarters the file size. |
| `WINDOWS_MCP_RAW_COORDINATES` | off | By default, when a full screenshot is shrunk, the image's own pixels become the coordinates (click where you see a thing). On keeps every coordinate in real screen pixels. |
| `WINDOWS_MCP_SCREENSHOT_BACKEND` | `auto` | Capture method: `auto`, `dxcam`, `mss`, `pillow`. `mss` is not installed by default; a method that cannot run warns and falls back to `pillow`. |
| `WINDOWS_MCP_DISABLE_FLASH` | off | Hides the orange-red border that briefly marks the captured area after each screenshot (it is drawn after capture, so it never appears in the image). |
| `WINDOWS_MCP_PROFILE_SNAPSHOT` | off | Logs how long each stage of a Screenshot or Snapshot took. |

## Reading the UI tree

| Variable | Default | What it does |
|---|---|---|
| `WINDOWS_MCP_MAX_TREE_ELEMENTS` | `500` | Most elements one Snapshot or WaitFor may collect. Stops huge lists (thousands of rows) from making calls slow and replies enormous; the reply says when it was cut. |
| `WINDOWS_MCP_READ_VSCODE` | off | Lets Snapshot and WaitFor read VS Code-family windows (VS Code, Cursor, Windsurf, Antigravity, VSCodium). **Leave it off:** one read freezes VS Code at 100% CPU until it is restarted, and returns nothing. |

## Server and security

Each of these can also be given as a `serve` flag; see
[Remote access and security](remote-access.md).

| Variable | Flag |
|---|---|
| `WINDOWS_MCP_AUTH_KEY` | `--auth-key` |
| `WINDOWS_MCP_IP_ALLOWLIST` | `--ip-allowlist` |
| `WINDOWS_MCP_CORS_ORIGINS` | `--cors-origins` |
| `WINDOWS_MCP_SSL_CERTFILE`, `WINDOWS_MCP_SSL_KEYFILE` | `--ssl-certfile`, `--ssl-keyfile` |
| `WINDOWS_MCP_OAUTH_CLIENT_ID`, `WINDOWS_MCP_OAUTH_CLIENT_SECRET` | `--oauth-client-id`, `--oauth-client-secret` |
| `WINDOWS_MCP_STATELESS_HTTP` | `--stateless-http` |
| `WINDOWS_MCP_TOOLS` | `--tools` |
| `WINDOWS_MCP_EXCLUDE_TOOLS` | `--exclude-tools` |
| `WINDOWS_MCP_ACTION_LOG` | `--action-log` |

## Telemetry

Anonymous usage data (which tools ran and whether they failed) helps improve the server. Tool
arguments, outputs and personal data are never sent.

| Variable | Default | What it does |
|---|---|---|
| `ANONYMIZED_TELEMETRY` | `true` | `false` turns telemetry off. |
| `POSTHOG_API_KEY` | project default | A different PostHog key; an empty string skips PostHog entirely. |
| `POSTHOG_HOST` | `https://us.i.posthog.com` | A different PostHog host, such as a self-hosted one. |

More in the [Security Policy](../SECURITY.md#telemetry-and-data-privacy).

## Debugging

| Variable | Default | What it does |
|---|---|---|
| `WINDOWS_MCP_DEBUG` | off | Verbose logging. Same as `--debug`. |
| `WINDOWS_MCP_WATCHDOG` | off | Runs the focus watchdog thread. It only writes debug logs today and can crash the server on unstable systems, so leave it off unless asked. |
