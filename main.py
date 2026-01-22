"""MCP Server - Runs on Local Computer.

This server runs on the user's machine (local computer or robot).
It handles:
- MCP tools via submodule integration
- MCP protocol endpoints via Streamable HTTP (/mcp)
- OAuth flow for MCP clients (optional, via oauth/)
- Legacy SSE endpoints for backward compatibility (/sse, /message)
- CLI login endpoints (/cli-login, /cli-signup)

MCP clients (ChatGPT, Claude, etc.) connect directly to this server
via Cloudflare tunnel. Railway is NOT involved in MCP traffic.
"""

import os
import logging
from importlib.metadata import version as get_version
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware import Middleware
from supabase import create_client, Client

from config import load_config

# Load environment: .env (local override) or .env.public (bundled defaults)
_env_file = Path(".env")
if _env_file.exists():
    load_dotenv(_env_file)
else:
    # Load bundled .env.public from package directory
    _package_dir = Path(__file__).parent
    _public_env = _package_dir / ".env.public"
    if _public_env.exists():
        load_dotenv(_public_env)

# Version from pyproject.toml (single source of truth)
try:
    VERSION = get_version("simple-mcp-server")
except Exception:
    VERSION = "0.0.0"  # Fallback for development

# Environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

# Transport configuration (aligned with ros-mcp-server)
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "streamable-http")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8766"))

# OAuth toggle - set to "false" for ros-mcp-server mode (no auth)
ENABLE_OAUTH = os.getenv("ENABLE_OAUTH", "true").lower() == "true"

# Initialize Supabase client
supabase: Client = None
if SUPABASE_URL and SUPABASE_ANON_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Load local config (needed for robot_name and user_id in logging)
local_config = load_config()

# Initialize logging with Supabase support (centralized log collection)
from logging_config import setup_logging  # noqa: E402

setup_logging(
    robot_name=local_config.robot_name,
    user_id=local_config.user_id,
    supabase_client=supabase,
)
logger = logging.getLogger(__name__)

logger.info(
    f"[STARTUP] Config loaded - valid: {local_config.is_valid()}, email: {local_config.email}"
)

# SERVER_URL: Use tunnel URL if available (for local MCP server), otherwise fallback to env/default
# This is critical for OAuth - MCP clients need to authenticate on THIS server, not Railway
SERVER_URL = local_config.tunnel_url or os.getenv(
    "SERVER_URL", "https://simplemcpserver-production-e610.up.railway.app"
)
logger.info(f"[STARTUP] SERVER_URL: {SERVER_URL}")
logger.info(f"[STARTUP] OAuth enabled: {ENABLE_OAUTH}")
logger.info("[STARTUP] Submodule auto-discovery enabled")

# ============== FastMCP Server ==============
from fastmcp import FastMCP  # noqa: E402
from submodule_integration import register_all_submodules  # noqa: E402

# Create MCP instance
mcp = FastMCP("simple-mcp-server")

# Auto-discover and register tools/resources/prompts from all git submodules
register_all_submodules(mcp)

# ============== OAuth Authentication Middleware for MCP ==============
from oauth.middleware import MCPOAuthMiddleware  # noqa: E402

# ============== Streamable HTTP MCP App ==============
# Create FastMCP app with OAuth middleware BEFORE FastAPI app
# (We need the lifespan from mcp_http_app for FastAPI)
#
# Endpoint compatibility:
#   - /mcp (Streamable HTTP): Recommended for all clients
#   - /sse (Legacy SSE): Fallback if /mcp doesn't work
#
mcp_http_app = mcp.http_app(
    path="/",  # Route at root of mounted app
    transport="streamable-http",
    middleware=[Middleware(MCPOAuthMiddleware)] if ENABLE_OAUTH else [],
)

# ============== FastAPI App ==============
# Pass MCP app's lifespan to FastAPI for proper initialization
app = FastAPI(
    title="Simple MCP Server",
    description="MCP server with ROS integration and OAuth 2.1",
    version=VERSION,
    lifespan=mcp_http_app.lifespan,  # Required for FastMCP task group initialization
)

# Add CORS middleware for browser-based MCP client access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount MCP app at /mcp
app.mount("/mcp", mcp_http_app)

# ============== Include Routers ==============

# OAuth endpoints (optional)
if ENABLE_OAUTH:
    from oauth.endpoints import router as oauth_router, init_oauth_routes

    init_oauth_routes(SERVER_URL, supabase)
    app.include_router(oauth_router)

# Legacy SSE endpoints
from sse import router as sse_router, init_sse_routes  # noqa: E402

init_sse_routes(SERVER_URL, local_config, mcp)
app.include_router(sse_router)

# Note: CLI login endpoints moved to robotmcp_cloud service


# ============== Server Info Endpoints ==============


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway."""
    return {"status": "healthy", "service": "mcp-server", "transport": MCP_TRANSPORT}


@app.get("/")
async def root():
    """Root endpoint with server info."""
    response = {
        "name": "Simple MCP Server",
        "version": VERSION,
        "transport": MCP_TRANSPORT,
        "endpoints": {
            "streamable_http": "/mcp",
            "sse": "/sse",
        },
        "client_compatibility": {
            "recommended": "/mcp",
            "fallback": "/sse (use if /mcp doesn't work)",
        },
        "tools": "Auto-discovered from submodules",
        "oauth_enabled": ENABLE_OAUTH,
    }
    if ENABLE_OAUTH:
        response["oauth"] = {
            "protected_resource": f"{SERVER_URL}/.well-known/oauth-protected-resource",
            "authorization_server": f"{SERVER_URL}/.well-known/oauth-authorization-server",
        }
    return response


# ============== Main Entry Point ==============

if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting MCP server with transport: {MCP_TRANSPORT}")
    logger.info("Streamable HTTP endpoint: /mcp")
    logger.info("Legacy SSE endpoint: /sse")
    uvicorn.run(app, host=MCP_HOST, port=MCP_PORT)
