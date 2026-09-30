---
Title: Installing Windows-MCP
Description: How to install this version of Windows-MCP in Claude Desktop (one-click extension from GitHub Releases, or a manual config), Claude Code (also from WSL), Gemini CLI, Codex CLI, Qwen Code, Perplexity Desktop and Autohand Code; running it from source; starting it at login; and adding the agent field guide. This version installs from GitHub, not from PyPI (uvx windows-mcp is the original project).
---

# Installing Windows-MCP

**Needs:** Windows 10 or 11. For every option except the Claude Desktop extension you also
need [uv](https://docs.astral.sh/uv/getting-started/installation/); uv fetches Python 3.14 by
itself when it is missing.

The first start takes a minute or two while the parts it needs are downloaded. A client may
time out on that first start: restart it once.

> **This version installs from GitHub, not PyPI.** `uvx windows-mcp` installs the original
> CursorTouch release, which lacks the tools and fixes listed in [What's new](whats-new.md).
> Everywhere below, the server command is:
>
> ```shell
> uvx --from git+https://github.com/farazpawle/Windows-MCP@v0.9.0 windows-mcp serve
> ```
>
> Replace `v0.9.0` with the latest tag on the
> [Releases page](https://github.com/farazpawle/Windows-MCP/releases) to update.

## Claude Desktop

### Option A: the extension (recommended)

1. Download `windows-mcp-<version>.mcpb` from the
   [latest release](https://github.com/farazpawle/Windows-MCP/releases/latest).
2. Double-click it, or drag it onto Claude Desktop (**Settings → Extensions**).
3. Click **Install**. Claude Desktop sets up Python and everything else itself.

Its settings screen lets you turn off telemetry, pick the screenshot method, and turn on debug
logging (see [Settings](settings.md)). To update, install the newer file the same way. If an
older Windows-MCP is already installed (for example the original one from Claude's directory),
turn it off so the two do not run side by side.

### Option B: manual config

Add this to `claude_desktop_config.json` (**Settings → Developer → Edit Config**), then fully
quit Claude Desktop (tray icon → Quit) and reopen it:

```json
{
  "mcpServers": {
    "windows-mcp": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/farazpawle/Windows-MCP@v0.9.0",
        "windows-mcp", "serve"
      ]
    }
  }
}
```

### Microsoft Store version of Claude Desktop

The Store version keeps its config at
`%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json`
and does not see your `PATH`, so give the full path to `uvx.exe`:

```json
{
  "mcpServers": {
    "windows-mcp": {
      "command": "C:\\Users\\<you>\\.local\\bin\\uvx.exe",
      "args": [
        "--from", "git+https://github.com/farazpawle/Windows-MCP@v0.9.0",
        "windows-mcp", "serve"
      ]
    }
  }
}
```

Run `where uvx` to find the path. If the extension (Option A) does not start on the Store
version, use this config instead.

## Claude Code

```shell
claude mcp add --transport stdio --scope user windows-mcp -- uvx --from git+https://github.com/farazpawle/Windows-MCP@v0.9.0 windows-mcp serve
```

Check it with `claude mcp list`, or `/mcp` inside Claude Code. If you see "Connection closed",
use the full path to `uvx.exe` (`C:\Users\<you>\.local\bin\uvx.exe`).

**From WSL:** the server must run on the Windows side. Install uv on Windows
(`irm https://astral.sh/uv/install.ps1 | iex` in PowerShell), then from WSL:

```shell
claude mcp add windows-mcp --transport stdio -s user -- powershell.exe -Command "C:\Users\<you>\.local\bin\uvx.exe --from git+https://github.com/farazpawle/Windows-MCP@v0.9.0 windows-mcp serve"
```

## Gemini CLI, Qwen Code

Add this to `%USERPROFILE%\.gemini\settings.json` (Gemini CLI) or
`%USERPROFILE%\.qwen\settings.json` (Qwen Code), then restart it:

```json
{
  "mcpServers": {
    "windows-mcp": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/farazpawle/Windows-MCP@v0.9.0",
        "windows-mcp", "serve"
      ]
    }
  }
}
```

## Codex CLI

Add this to `%USERPROFILE%\.codex\config.toml`, then restart Codex:

```toml
[mcp_servers.windows-mcp]
command = "uvx"
args = ["--from", "git+https://github.com/farazpawle/Windows-MCP@v0.9.0", "windows-mcp", "serve"]
```

## Perplexity Desktop

**Settings → Connectors → Add Connector → Advanced**, name it `Windows-MCP`, paste:

```json
{
  "command": "uvx",
  "args": [
    "--from", "git+https://github.com/farazpawle/Windows-MCP@v0.9.0",
    "windows-mcp", "serve"
  ]
}
```

## Autohand Code

```shell
autohand mcp add windows-mcp uvx --from git+https://github.com/farazpawle/Windows-MCP@v0.9.0 windows-mcp serve
```

## From source

```shell
git clone https://github.com/farazpawle/Windows-MCP.git
cd Windows-MCP
uv run windows-mcp serve
```

In a client config, use `"command": "uv"` with
`"args": ["--directory", "<path to Windows-MCP>", "run", "windows-mcp", "serve"]`.

## Start at login (background server)

To run it as an HTTP server that starts with Windows:

```shell
windows-mcp install                                       # start now and at every login
windows-mcp install --transport sse --host 127.0.0.1 --port 8000
windows-mcp uninstall                                     # remove it
```

This creates a per-user Scheduled Task named `windows-mcp-server`. Logs go to
`~/.windows-mcp/server.log` and `server.error.log`. Before exposing it to other machines, read
[Remote access and security](remote-access.md).

## Add the field guide (recommended for agents)

[`Skills/windows-mcp`](../Skills/windows-mcp/SKILL.md) is a skill that teaches an agent how to
use the tools well: which tool to pick, how to avoid focus stolen by approval prompts, and
what to do when a click lands in the wrong place.

- **Claude Code:** copy the `Skills/windows-mcp` folder to `%USERPROFILE%\.claude\skills\windows-mcp`.
- **Claude Desktop:** zip the `Skills/windows-mcp` folder and upload the zip as a skill in
  Claude Desktop's settings.
