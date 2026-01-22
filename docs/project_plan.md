# Project Plan: robotmcp-server

**Copyright (c) 2025 Contoro. All rights reserved.**

---

## Architecture

```
┌──────────────────┐
│    Supabase      │  User accounts, auth API
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐  ┌─────────────────┐
│ Local  │  │ robotmcp-cloud  │  CLI login, tunnel creation
│Computer│  │ app.robotmcp.ai │
│        │  └─────────────────┘
│ MCP    │       ▲
│ Server │       │ Browser (first-run)
└───┬────┘       │
    │ Tunnel  ┌──┴───┐
    ▼         │ CLI  │
┌────────┐    └──────┘
│  MCP   │
│ Client │  ChatGPT, Claude
└────────┘
```

**Cloud Service:** https://github.com/robotmcp/robotmcp_cloud

## Module Structure

```
robotmcp_server/
├── main.py              # FastAPI app entry
├── tools.py             # MCP tools (echo, ping) - replace for custom tools
├── cli.py               # CLI daemon management
├── config.py            # Config management (~/.robotmcp-server/)
├── setup.py             # Browser login flow (uses app.robotmcp.ai)
├── sse.py               # Legacy SSE endpoints
└── oauth/               # OAuth module (optional)
    ├── endpoints.py     # OAuth routes
    ├── middleware.py    # Token validation
    ├── stores.py        # In-memory token stores
    └── templates.py     # HTML templates
```

---

## Status

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Core MCP server with OAuth 2.1 | ✅ Complete |
| 2 | CLI package (pipx install) | ✅ Complete |
| 3 | First-run setup (browser login, tunnel) | ✅ Complete |
| 4 | Creator-only access control | ✅ Complete |
| 5 | Modularization for ros-mcp-server | ✅ Complete |
| 6 | Separate cloud service (robotmcp-cloud) | ✅ Complete |
| 7 | User dashboard | TODO |
| 8 | Multi-user access | TODO |

---

## Version History

| Version | Changes |
|---------|---------|
| 1.8.0 | Separate cloud service to robotmcp-cloud (app.robotmcp.ai) |
| 1.7.0 | Modular architecture, WSL2 support |
| 1.6.0 | ENABLE_OAUTH flag, optional auth |
| 1.5.0 | Background daemon mode |
| 1.4.0 | Auto-download cloudflared |
| 1.3.0 | Creator-only access control |
| 1.2.0 | CLI login, tunnel setup |
| 1.0.0 | Initial release |

---

## For ros-mcp-server Merge

1. Replace `tools.py` with ROS tools
2. Set `ENABLE_OAUTH=false` to disable auth
3. Keep or remove CLI/tunnel as needed
