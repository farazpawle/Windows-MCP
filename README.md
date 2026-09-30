<div align="center">
  <h1>🪟 Windows-MCP</h1>
  <p><b>Let AI agents use your Windows PC: see the screen, click, type, run apps, and manage files, settings and processes.</b></p>

  <a href="https://github.com/farazpawle/Windows-MCP/releases/latest">
    <img src="https://img.shields.io/github/v/release/farazpawle/Windows-MCP" alt="Latest release">
  </a>
  <a href="LICENSE.md">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT">
  </a>
  <img src="https://img.shields.io/badge/python-3.14%2B-blue" alt="Python 3.14+">
  <img src="https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-blue" alt="Platform: Windows 10 and 11">
  <img src="https://img.shields.io/github/last-commit/farazpawle/Windows-MCP" alt="Last commit">
</div>

**Windows-MCP** is an [MCP](https://modelcontextprotocol.io) server that connects AI agents
such as Claude to Windows. It works with any AI model, with or without vision, because it reads
the accessibility information Windows already exposes for every app.

This is an enhanced version of [CursorTouch/Windows-MCP](https://github.com/CursorTouch/Windows-MCP)
with **2 new tools, dozens of new abilities, safety checks, and many reliability fixes**. See
[what's new](docs/whats-new.md).

## 🚀 Install in Claude Desktop

1. Download **`windows-mcp-<version>.mcpb`** from the
   [latest release](https://github.com/farazpawle/Windows-MCP/releases/latest).
2. Double-click it, or drag it onto Claude Desktop (**Settings → Extensions**).
3. Click **Install**. Claude Desktop sets up everything else itself; the first start can take a
   minute.

**Using Claude Code, Gemini CLI, Codex, Qwen Code, Perplexity or another app?** See the
[install guide](docs/install.md). Note that `uvx windows-mcp` installs the *original* version;
this one installs from GitHub:

```shell
uvx --from git+https://github.com/farazpawle/Windows-MCP@v0.9.0 windows-mcp serve
```

## ✨ What it can do

- **See the screen:** fast screenshots, a list of every button, field and menu with positions,
  and text recognition (OCR) for games, remote desktops and apps with no accessibility data.
- **Use the mouse and keyboard:** click (by position or by the element's name), type, scroll,
  drag, press shortcuts, or run up to 20 steps in one call.
- **Wait smartly:** until a window opens, text appears, or the screen settles, instead of
  guessing with fixed pauses.
- **Manage apps and windows:** launch, switch, resize, move between screens, minimize,
  maximize and close.
- **Run the PC directly:** PowerShell, files and folders, the registry, processes, the
  clipboard (text, images, files) and notifications.
- **Read the web:** fetch a page, or read what is open in the browser.

### 🆕 Highlights of this version

| | |
|---|---|
| **Steps** | Up to 20 actions in one call, one approval in Claude Desktop, stops at the first surprise |
| **FindText** | Finds text on screen by OCR and returns where to click |
| **Click by name** | `element="button:Save"`: no screenshot or element list needed first |
| **Safety checks** | Refuses to click when a pop-up covers the target; never clicks off-screen; no stuck keys |
| **Honest replies** | Real errors on failure; replies say what was clicked, what a field now holds, and when a new window or dialog appeared |
| **Smarter waiting** | Wait for on-screen text, a screen change, or the screen to settle |
| **Full window control** | Minimize, maximize, restore, close, list, move to another display |
| **Clipboard** | Images and copied files, not only text |
| **No freezes** | Never reads VS Code-family windows, skips frozen apps instead of hanging |
| **Claude Desktop extension** | A ready-to-install `.mcpb` on every release |
| **Field guide** | A [skill](Skills/windows-mcp/SKILL.md) that teaches agents to use the tools well |

Full list: [what's new](docs/whats-new.md).

## 🔨 Tools

22 tools, each described in the [tools reference](docs/tools.md):

| Group | Tools |
|---|---|
| See the screen | `Screenshot`, `Snapshot`, `FindText`, `DisplayInventory`, `Scrape` |
| Mouse and keyboard | `Click`, `Type`, `MultiEdit`, `MultiSelect`, `Scroll`, `Move`, `Shortcut`, `Steps` |
| Waiting | `WaitFor`, `Wait` |
| Apps and windows | `App` |
| System | `PowerShell`, `FileSystem`, `Registry`, `Process`, `Clipboard`, `Notification` |

## 🎥 Demos

<https://github.com/user-attachments/assets/d0e7ed1d-6189-4de6-838a-5ef8e1cad54e>

<https://github.com/user-attachments/assets/d2b372dc-8d00-4d71-9677-4c64f5987485>

*Demos from the original project.*

## ⚠️ Good to know

- **It has full control of the PC.** PowerShell, files, the registry and processes can make
  changes that cannot be undone. Keep Claude Desktop's approval prompts on for those tools, or
  switch tools off with `--exclude-tools`. For untrusted tasks, use a VM or Windows Sandbox.
- **Approval prompts can steal focus.** In Claude Desktop, each approval brings Claude to the
  front, so a click or keystroke meant for another window can land in the chat. Choose
  "Always allow" for Windows-MCP when you trust the task.
- **VS Code, Cursor, Windsurf and Antigravity windows are handled by screenshot only.** Reading
  their element tree freezes them.
- **Known gaps:** typing long text into Windows 11 Notepad can garble it (writing the file
  directly works), and with several screens a full screenshot can miss a pop-up. Details and
  workarounds are in the [field guide](Skills/windows-mcp/references/known-gaps.md).
- App launch by Start-menu name works best on English Windows.

## 🛠️ For developers

```shell
git clone https://github.com/farazpawle/Windows-MCP.git
cd Windows-MCP
uv sync --extra dev
uv run windows-mcp serve          # stdio server
uv run pytest                     # tests
uv run python mcpb/build.py       # build the Claude Desktop extension into mcpb/
```

- [Remote access and security](docs/remote-access.md): HTTP transports, auth keys, IP
  allowlist, TLS, OAuth, config file, tool selection, action log.
- [Settings](docs/settings.md): every environment variable.
- [Contributing](CONTRIBUTING.md) and the [Security Policy](SECURITY.md).
- Releases: raise the version in `pyproject.toml`, `uv.lock`, `mcpb/manifest.json` and
  `server.json` (and the `@v<version>` in the install commands here and in `docs/`), then push
  a `v<version>` tag. GitHub builds the package and the extension and publishes the release.

## 📊 Telemetry

Windows-MCP sends anonymous usage data (which tools ran and whether they failed). Tool
arguments, outputs and personal data are never sent. Turn it off with
`ANONYMIZED_TELEMETRY=false`, or in the Claude Desktop extension's settings. Details:
[Security Policy](SECURITY.md#telemetry-and-data-privacy).

## 🤝 Connect with the original project

- 📢 Follow CursorTouch on [X](https://x.com/CursorTouch)
- 💬 Join the [CursorTouch Discord](https://discord.com/invite/Aue9Yj2VzS)

<a href="https://trendshift.io/repositories/20935?utm_source=trendshift-badge&amp;utm_medium=badge&amp;utm_campaign=badge-trendshift-20935" target="_blank" rel="noopener noreferrer"><img src="https://trendshift.io/api/badge/trendshift/repositories/20935/daily?language=Python" alt="CursorTouch%2FWindows-MCP | Trendshift" width="250" height="55"/></a>

## Star History

[![Star History Chart](https://star-history.dera.page/svg?repos=CursorTouch/Windows-MCP&type=Date)](https://star-history.dera.page/#CursorTouch/Windows-MCP&Date)

## 👥 Contributors

Thanks to everyone who contributed to the original Windows-MCP! 🎉

<a href="https://github.com/CursorTouch/Windows-MCP/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=CursorTouch/Windows-MCP" />
</a>

Want to contribute to this version? See [Contributing](CONTRIBUTING.md).

## 🪪 License

MIT License. See [LICENSE](LICENSE.md), which keeps the original author's copyright notice.

## 🙏 Acknowledgements

- [CursorTouch/Windows-MCP](https://github.com/CursorTouch/Windows-MCP), the project this
  version is built on.
- [Python-UIAutomation-for-Windows](https://github.com/yinkaisheng/Python-UIAutomation-for-Windows)
  by yinkaisheng, the base of the Windows UI Automation layer.

## Citation

For the original project:

```bibtex
@software{
  author       = {CursorTouch},
  title        = {Windows-MCP: Lightweight open-source project for integrating LLM agents with Windows},
  year         = {2024},
  publisher    = {GitHub},
  url={https://github.com/CursorTouch/Windows-MCP}
}
```
