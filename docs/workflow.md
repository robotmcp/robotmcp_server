# Workflow: robotmcp-server

**Copyright (c) 2025 Contoro. All rights reserved.**

---

## Components

| Component | Role |
|-----------|------|
| **Local Computer** | Runs MCP server, handles OAuth, hosts tools |
| **Supabase** | User accounts, authentication |
| **robotmcp-cloud** | CLI login pages, tunnel creation (app.robotmcp.ai) |
| **Cloudflare Tunnel** | Routes `{name}.robotmcp.ai` to local server |
| **MCP Client** | ChatGPT, Claude - connects via tunnel |

---

## First-Run Flow

```
User                CLI              robotmcp-cloud       Supabase
 │                   │               (app.robotmcp.ai)        │
 │ robotmcp-server │                    │                    │
 │──────────────────>│                    │                    │
 │                   │ Open browser       │                    │
 │                   │───────────────────>│                    │
 │                   │                    │ Authenticate       │
 │                   │                    │───────────────────>│
 │                   │                    │<───────────────────│
 │                   │<── callback ───────│                    │
 │                   │                    │                    │
 │ Enter robot name  │                    │                    │
 │<──────────────────│                    │                    │
 │──────────────────>│                    │                    │
 │                   │ Create tunnel      │                    │
 │                   │───────────────────>│                    │
 │                   │<───────────────────│                    │
 │                   │                    │                    │
 │ Server running    │                    │                    │
 │<──────────────────│                    │                    │
```

---

## MCP Client Connection Flow

```
MCP Client          Cloudflare          Local Server        Supabase
 │                    │                    │                   │
 │ GET /mcp           │                    │                   │
 │───────────────────>│───────────────────>│                   │
 │                    │                    │ Validate token    │
 │                    │                    │──────────────────>│
 │                    │                    │<──────────────────│
 │<───────────────────│<───────────────────│                   │
 │                    │                    │                   │
 │ Call MCP tool      │                    │                   │
 │───────────────────>│───────────────────>│                   │
 │<───────────────────│<───────────────────│                   │
```

---

## CLI Commands

```bash
robotmcp-server           # Start (auto-setup on first run)
robotmcp-server stop      # Stop server
robotmcp-server status    # Show status
robotmcp-server logout    # Clear credentials
```

---

## Access Control

- Creator's `user_id` stored in config during setup
- OAuth flow validates connecting user
- Non-creator users receive `403 Forbidden`

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ENABLE_OAUTH` | Set `false` to disable auth (default: `true`) |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anonymous key |
| `ROBOTMCP_CLOUD_URL` | Cloud service URL (default: `https://app.robotmcp.ai`) |

---

## WSL Support

CLI auto-detects WSL and uses the correct IP for browser callback:
- Gets WSL IP via `hostname -I`
- Passes to Railway for callback redirect
- Works with Windows browser + WSL CLI
