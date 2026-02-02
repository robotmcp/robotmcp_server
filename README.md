# RobotMCP Server

A modular Model Context Protocol (MCP) server with automatic submodule integration, OAuth 2.1 authentication, Supabase user management, and Cloudflare tunnel support. Works with ChatGPT and Claude.ai.

## Quick Start

**Option 1: Direct install (recommended)**
```bash
# Install via pipx (submodules auto-download on first run)
pipx install git+https://github.com/robotmcp/robotmcp_server.git

# Run (opens browser for first-time setup)
robotmcp-server
```

**Option 2: Clone with submodules**
```bash
# Clone with submodules included
git clone --recursive https://github.com/robotmcp/robotmcp_server.git
pipx install ./robotmcp_server

# Run
robotmcp-server
```

```bash
# Verify everything is working
robotmcp-server verify
```

See [docs/install.md](docs/install.md) for manual installation and troubleshooting.

## Features

- **Submodule Auto-Discovery**: Automatically finds and registers MCP tools from git submodules
- **Auto-Install Dependencies**: Submodule dependencies are installed automatically at startup
- **Streamable HTTP Transport**: Modern MCP transport at `/mcp`
- **OAuth 2.1**: Full flow with PKCE and dynamic client registration
- **Cloudflare Tunnel**: Secure access via `{name}.robotmcp.ai`
- **Creator-Only Access**: Only the server creator can connect
- **Optional OAuth**: Disable with `ENABLE_OAUTH=false`
- **Secure CLI Login**: POST-based credential transfer (not URL params)
- **WSL Support**: Reliable browser opening with PowerShell fallback

## Project Structure

```
robotmcp_server/
├── main.py                    # FastAPI app entry point
├── submodule_integration.py   # Auto-discover & register submodule tools
├── submodule_deps.py          # Auto-install submodule dependencies
├── tools.py                   # Built-in MCP tools (echo, ping)
├── cli.py                     # CLI daemon management
├── config.py                  # Config management (~/.robotmcp-server/)
├── setup.py                   # Browser-based login flow
├── sse.py                     # Legacy SSE endpoints
├── oauth/                     # OAuth module (optional)
│   ├── endpoints.py           # OAuth routes
│   ├── middleware.py          # Token validation
│   ├── jwt_utils.py           # JWT token generation/validation
│   ├── stores.py              # Session stores
│   └── templates.py           # HTML templates
└── ros-mcp-server/            # Example submodule (ROS integration)
```

**Cloud Service:** CLI login and tunnel creation are handled by [robotmcp-cloud](https://github.com/robotmcp/robotmcp_cloud) at `https://app.robotmcp.ai`.

See [docs/project_plan.md](docs/project_plan.md) for architecture details.

## CLI Commands

| Command | Description |
|---------|-------------|
| `robotmcp-server` | Start server in background |
| `robotmcp-server stop` | Stop server and tunnel |
| `robotmcp-server status` | Show current status |
| `robotmcp-server verify` | Comprehensive verification (server, tunnel, DNS, connectivity) |
| `robotmcp-server list` | List installed MCP server modules with compatibility status |
| `robotmcp-server list-tools` | List all available MCP tools from compatible modules |
| `robotmcp-server add <url>` | Add an MCP server module (git submodule) |
| `robotmcp-server remove <name>` | Remove an MCP server module |
| `robotmcp-server update` | Update all MCP server modules to latest |
| `robotmcp-server logout` | Clear credentials and stop |

### Verification Command

The `verify` command performs comprehensive diagnostics:

```bash
robotmcp-server verify
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

## Adding MCP Submodules

The server automatically discovers and integrates MCP tools from git submodules:

```bash
# Add a module using the CLI
robotmcp-server add https://github.com/example/my-mcp-tools.git

# Or add tracking a specific branch
robotmcp-server add -b develop https://github.com/example/my-mcp-tools.git

# List installed modules and their compatibility status
robotmcp-server list

# List all available tools
robotmcp-server list-tools

# Update all modules to latest
robotmcp-server update

# Remove a module
robotmcp-server remove my-mcp-tools
```

Your submodule needs:
1. A `pyproject.toml` with a package name
2. An `integration.py` with a `register(mcp, **kwargs)` function

**Compatibility:** Modules without an integration module will show as "not compatible" in `list` and `list-tools` commands. The server checks for compatibility at startup and warns about incompatible modules.

```python
# my_mcp_tools/integration.py
from fastmcp import FastMCP

def register(mcp: FastMCP, **kwargs) -> None:
    @mcp.tool()
    def my_tool(param: str) -> str:
        """Process a parameter."""
        return f"Result: {param}"
```

**See [docs/submodule-integration.md](docs/submodule-integration.md) for the complete guide** including:
- Full `integration.py` examples with configuration
- How to organize tools, resources, and prompts
- Environment variable configuration
- Testing your submodule

## Custom Tools (without submodules)

To add custom MCP tools directly, edit `tools.py`:

```python
from fastmcp import FastMCP
mcp = FastMCP("my-server")

@mcp.tool()
def my_tool(param: str) -> str:
    return f"Result: {param}"
```

## Documentation

- [Installation Guide](docs/install.md) - Setup, troubleshooting, CLI reference
- [Submodule Integration](docs/submodule-integration.md) - Creating MCP submodules with integration.py
- [Project Plan](docs/project_plan.md) - Architecture, version history
- [Workflow](docs/workflow.md) - Flow diagrams, components

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## License

Copyright (c) 2025 Contoro. All rights reserved.

This software is proprietary and confidential. Unauthorized copying, modification, distribution, or use of this software is strictly prohibited without express written permission.
