---
Title: Rewrite the README for this fork and move detail into docs/
Description: The README was upstream's (841 lines, PyPI install, 21 tools, Python 3.13). Rewrite it users-first for this fork (install the Claude Desktop extension from GitHub Releases, what it can do, what is new versus the original), keep upstream's demos, community links, star chart, contributors and citation, credit CursorTouch. Detail moves to docs/: tools, install per client (fork installs via uvx --from git+...@<tag>, verified), remote access and security, settings, what's new.
Total Tasks: 8
---

# Tasks

1. Write `docs/tools.md`: all 22 tools by group, main options, from `Skills/windows-mcp/references/`.
2. Write `docs/install.md`: Claude Desktop extension, manual config, MSIX, Claude Code, WSL, Gemini CLI, Codex, Qwen, Perplexity, Autohand, from source, run at login, field guide.
3. Write `docs/remote-access.md`: transports, auth, allowlist, CORS, TLS, OAuth, config file, `auth` helper, SSRF, tool selection, action log.
4. Write `docs/settings.md`: every environment variable and the extension's settings screen.
5. Write `docs/whats-new.md`: features and fixes versus the original PyPI release.
6. Rewrite `README.md`: users first, links to the five docs, original sections kept, credit.
7. Check every relative link in the README and docs resolves to a file.
8. Commit and push.

## Verification

- Every `docs/*.md` has `Title` and `Description` frontmatter.
- Every relative link target exists (script check).
- Install command `uvx --from git+https://github.com/farazpawle/Windows-MCP@v0.9.0 windows-mcp serve --help` runs (done 2026-09-30).
- Tool count and names match `mcpb/manifest.json` (22).
- [User] Look over the rendered page on GitHub and say whether the tone and order suit you (a judgement call about look and feel).
