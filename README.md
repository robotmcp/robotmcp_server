# Simple MCP Server

A Model Context Protocol (MCP) server with OAuth 2.1 authentication, Supabase user management, and Cloudflare tunnel support. Works with ChatGPT and Claude.ai.

## Quick Start

```bash
# Install via pipx
pipx install git+https://github.com/stex2005/robotmcp_server.git

# Run (opens browser for first-time setup)
simple-mcp-server
```

See [docs/install.md](docs/install.md) for manual installation and troubleshooting.

## Features

- **Streamable HTTP Transport**: Modern MCP transport at `/mcp`
- **OAuth 2.1**: Full flow with PKCE and dynamic client registration
- **Cloudflare Tunnel**: Secure access via `{name}.robotmcp.ai`
- **Creator-Only Access**: Only the server creator can connect
- **Optional OAuth**: Disable with `ENABLE_OAUTH=false`
- **Secure CLI Login**: POST-based credential transfer (not URL params)
- **WSL Support**: Reliable browser opening with PowerShell fallback

## Project Structure

```
simple_mcp_server/
├── main.py              # FastAPI app entry point
├── tools.py             # MCP tools (echo, ping) - replace for custom tools
├── cli.py               # CLI daemon management
├── config.py            # Config management (~/.simple-mcp-server/)
├── setup.py             # Browser-based login flow
├── sse.py               # Legacy SSE endpoints
└── oauth/               # OAuth module (optional)
    ├── endpoints.py     # OAuth routes
    ├── middleware.py    # Token validation
    ├── jwt_utils.py     # JWT token generation/validation
    ├── stores.py        # Session stores (auth codes, pending requests)
    └── templates.py     # HTML templates
```

**Cloud Service:** CLI login and tunnel creation are handled by [robotmcp-cloud](https://github.com/robotmcp/robotmcp_cloud) at `https://app.robotmcp.ai`.

See [docs/project_plan.md](docs/project_plan.md) for architecture details.

## CLI Commands

| Command | Description |
|---------|-------------|
| `simple-mcp-server` | Start server in background |
| `simple-mcp-server stop` | Stop server and tunnel |
| `simple-mcp-server status` | Show current status |
| `simple-mcp-server verify` | Comprehensive verification (server, tunnel, DNS, connectivity) |
| `simple-mcp-server logout` | Clear credentials and stop |

### Verification Command

The `verify` command performs comprehensive diagnostics:

```bash
simple-mcp-server verify
```

**Checks performed:**
1. **Configuration** - Verifies tunnel token and configuration exist
2. **Local Server** - Tests server connectivity on `localhost:8766`
3. **Cloudflared Process** - Checks if cloudflared is running
4. **Tunnel Authentication** - Analyzes logs to verify tunnel is authenticated and connected
5. **DNS Resolution** - Verifies DNS record exists and resolves correctly
6. **Tunnel Endpoints** - Tests endpoints through the tunnel (`/`, `/health`)

**Output includes:**
- ✓/✗ status for each check
- Detailed error messages with actionable fixes
- Summary with pass/fail statistics
- Next steps if issues are found

Use this command to diagnose connectivity issues, verify DNS configuration, and ensure your tunnel is working correctly.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anonymous key |
| `SUPABASE_JWT_SECRET` | JWT secret for token validation |
| `ENABLE_OAUTH` | Set `false` to disable OAuth (default: `true`) |
| `ROBOTMCP_CLOUD_URL` | Cloud service URL (default: `https://app.robotmcp.ai`) |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Server info |
| `POST /mcp` | Streamable HTTP transport (recommended) |
| `GET /sse` | Legacy SSE (backward compat) |
| `/.well-known/oauth-authorization-server` | OAuth metadata |

## Connecting MCP Clients

Two endpoints are available:

| Endpoint | Transport | Usage |
|----------|-----------|-------|
| `/mcp` | Streamable HTTP | Try first (recommended) |
| `/sse` | Legacy SSE | Use if /mcp doesn't work |

**Client Compatibility:**
- **Claude.ai**: Works with `/mcp` (recommended)
- **ChatGPT**: Works with `/mcp` (recommended)
- **Legacy clients**: Use `/sse` if `/mcp` doesn't work

Example URL:
```
https://{your-name}.robotmcp.ai/mcp
```

See [docs/workflow.md](docs/workflow.md) for connection flow diagrams.

## Customization

To add custom MCP tools, replace `tools.py`:

```python
from fastmcp import FastMCP
mcp = FastMCP("my-server")

@mcp.tool()
def my_tool(param: str) -> str:
    return f"Result: {param}"
```

For ros-mcp-server merge: replace `tools.py` and set `ENABLE_OAUTH=false`.

## Documentation

- [Installation Guide](docs/install.md) - Setup, troubleshooting, CLI reference
- [Project Plan](docs/project_plan.md) - Architecture, version history
- [Workflow](docs/workflow.md) - Flow diagrams, components

## Version History

- **v1.17.0**: Enhanced `verify` command with comprehensive diagnostics (server, tunnel, DNS, connectivity)
- **v1.16.2**: Use importlib.metadata for version (single source of truth from pyproject.toml)
- **v1.16.1**: Fix SSE endpoint to support shared member access (consistent with /mcp)
- **v1.16.0**: Display version in CLI status output
- **v1.15.0**: Shared member access - users added via dashboard can now connect to shared MCP servers
- **v1.14.0**: Change default port from 8000 to 8766 (**BREAKING**: existing tunnels must be recreated with `simple-mcp-server logout && simple-mcp-server`)
- **v1.13.0**: JWT tokens for stateless OAuth (tokens survive server restarts), endpoint compatibility docs
- **v1.12.0**: Supabase centralized logging (replaces CloudWatch for security)
- **v1.11.0**: AWS CloudWatch logging integration with JSON structured logs
- **v1.10.0**: Comprehensive INFO-level logging for all MCP server activities
- **v1.9.0**: Secure POST-based CLI login, WSL browser fix, Claude theme for OAuth pages
- **v1.8.0**: OAuth templates, CLI improvements
- **v1.7.0**: Cloudflare tunnel integration
- **v1.0.0**: Initial release with OAuth 2.1 and Streamable HTTP

## License

Copyright (c) 2025 Contoro. All rights reserved.

This software is proprietary and confidential. Unauthorized copying, modification, distribution, or use of this software is strictly prohibited without express written permission.
