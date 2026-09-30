---
Title: Remote access and security
Description: Running Windows-MCP over the network (SSE or streamable HTTP) safely - bearer-token auth, IP allowlist, CORS, TLS, OAuth 2.0 with PKCE, the config file and the auth helper - plus tool selection, the action log and Scrape's SSRF protection. Local stdio use needs none of this.
---

# Remote access and security

Windows-MCP has **full access to the PC**: PowerShell, files, the registry, processes and every
window. There is no sandbox and no undo. For anything beyond your own desktop, run it in a VM or
Windows Sandbox, switch off the tools you do not need, and read the
[Security Policy](../SECURITY.md).

When a client such as Claude Desktop starts the server itself (stdio, the default), nothing here
is needed.

## Transports

| Transport | Command | Use |
|---|---|---|
| `stdio` (default) | `windows-mcp serve` | The client starts the server itself (Claude Desktop, Claude Code, ...) |
| `sse` | `windows-mcp serve --transport sse --host HOST --port PORT` | Network access with Server-Sent Events |
| `streamable-http` | `windows-mcp serve --transport streamable-http --host HOST --port PORT` | Network access over HTTP streaming (recommended for network use) |

`--stateless-http` runs streamable HTTP without session state, so clients survive a server
restart without a new handshake. The server refuses to listen on a non-local address without
authentication unless you add `--allow-insecure-remote` (not recommended).

A typical secured setup:

```shell
windows-mcp serve --transport streamable-http --host 0.0.0.0 \
  --auth-key "your_secret_token" \
  --ip-allowlist "203.0.113.0/24" \
  --ssl-certfile cert.pem --ssl-keyfile key.pem
```

## Authentication

```shell
windows-mcp serve --transport sse --host 0.0.0.0 --auth-key "your_token"
```

Every request then needs `Authorization: Bearer your_token`.

## IP allowlist

```shell
windows-mcp serve --auth-key "token" --ip-allowlist "203.0.113.0/24,198.51.100.5"
```

Only the listed addresses or ranges (IPv4 and IPv6) may connect.

## CORS

No CORS headers are sent by default, so browsers block other websites from reaching the server,
even on `localhost`. Host-header checks (DNS-rebinding protection) follow the bind address
automatically. To let a browser-based client in, list its origin:

```shell
windows-mcp serve --cors-origins "https://my-client.example.com"
```

## TLS (HTTPS)

```shell
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
windows-mcp serve --ssl-certfile cert.pem --ssl-keyfile key.pem
```

## OAuth 2.0 with PKCE

For clients that sign in with OAuth instead of a fixed key:

```shell
windows-mcp serve --transport streamable-http --host 0.0.0.0 \
  --ssl-certfile ~/.windows-mcp/cert.pem --ssl-keyfile ~/.windows-mcp/key.pem \
  --oauth-client-id my-client --oauth-client-secret my-secret
```

Claude Desktop config:

```json
{
  "mcpServers": {
    "windows-mcp": {
      "type": "http",
      "url": "https://<host>:8000/mcp/",
      "oauth": { "clientId": "my-client", "clientSecret": "my-secret" }
    }
  }
}
```

The server offers `GET /.well-known/oauth-authorization-server`, `GET /oauth/authorize`
(Authorization Code with PKCE, `S256` required) and `POST /oauth/token`. Dynamic client
registration is off: clients must be set up in advance, and redirect addresses must be local
(loopback) only. An auth key and OAuth can be used together.

## Config file

Instead of flags, put the settings in `~/.windows-mcp/config.toml` (or pass `--config <file>`).
Flags given on the command line win.

```toml
[server]
transport    = "streamable-http"
host         = "0.0.0.0"
port         = 8000
auth_key     = "your-secret-key"
ssl_certfile = "cert.pem"   # relative to ~/.windows-mcp/
ssl_keyfile  = "key.pem"

[security]
ip_allowlist        = ["192.168.1.0/24"]
cors_origins        = ["https://my-client.example.com"]   # optional
oauth_client_id     = "my-client"                         # optional
oauth_client_secret = "my-secret"

[tools]
exclude = ["PowerShell", "Registry"]
```

## The `auth` helper

Creates an auth key and writes a working `~/.windows-mcp/config.toml`, then prints a matching
client config:

```shell
windows-mcp auth
windows-mcp auth --transport streamable-http --host 0.0.0.0 --port 8000 --with-tls   # also makes cert.pem and key.pem
```

## Tool selection

All 22 tools are on by default.

```shell
windows-mcp serve --tools "Screenshot,Click,Snapshot"     # only these
windows-mcp serve --exclude-tools "PowerShell,Registry"   # all but these
```

## Action log

Off by default. `--action-log on` (or `WINDOWS_MCP_ACTION_LOG=on`) adds one readable line per
tool call to `~/.windows-mcp/actions.log`: time, tool, arguments, ok or error, duration and the
start of the reply. Give a file path instead of `on` to write elsewhere. Values that look like
secrets (passwords, tokens, keys, `Bearer ...`) are replaced with `[hidden]`; other text,
including what the agent types, is kept. The file is never trimmed.

```text
2026-09-23 23:50:29  PowerShell  command="Write-Output 'password=[hidden] done'" timeout=30  -> ok 0.42s: Response: password=[hidden] done | Status Code: 0
```

## Scrape protection (SSRF)

`Scrape` refuses private, loopback and link-local addresses, URLs containing credentials, and
anything that is not `http` or `https`.
