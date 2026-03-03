"""OAuth middleware for MCP endpoints.

Validates Bearer tokens and enforces access control.
- Server creator always has access
- Shared members (via server_members table) also have access
Uses JWT for stateless token validation - tokens survive server restarts.
"""

import logging
import os

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from config import load_config
from oauth.jwt_utils import verify_access_token

logger = logging.getLogger(__name__)

# Load config for access check
_config = load_config()

# Cloud service URL for access checks
ROBOTMCP_CLOUD_URL = os.getenv("ROBOTMCP_CLOUD_URL", "https://app.robotmcp.ai")


def get_server_url() -> str:
    """Get the server URL for OAuth metadata."""
    url = _config.tunnel_url
    if not url:
        raise RuntimeError("No tunnel URL configured. Run 'robotmcp-server' to complete setup.")
    return url


async def check_shared_access(robot_name: str, user_id: str) -> bool:
    """Check if user has shared access via robotmcp-cloud API."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{ROBOTMCP_CLOUD_URL}/api/check-access",
                params={"robot_name": robot_name, "user_id": user_id},
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("allowed", False)
    except Exception as e:
        logger.warning(f"[AUTH] Error checking shared access via cloud: {e}")
    return False


class MCPOAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to validate OAuth Bearer tokens for Streamable HTTP MCP endpoint."""

    async def dispatch(self, request: Request, call_next):
        server_url = get_server_url()

        # Check Bearer token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.info("[AUTH] Request rejected: no Bearer token")
            return JSONResponse(
                {
                    "error": "unauthorized",
                    "error_description": "Missing or invalid Authorization header",
                },
                status_code=401,
                headers={
                    "WWW-Authenticate": f'Bearer resource_metadata="{server_url}/.well-known/oauth-protected-resource"'
                },
            )

        token = auth_header[7:]

        # Verify JWT token (stateless - no storage lookup needed)
        token_data = verify_access_token(token, issuer=server_url)

        if not token_data:
            logger.info("[AUTH] Request rejected: invalid or expired token")
            return JSONResponse(
                {
                    "error": "unauthorized",
                    "error_description": "Invalid or expired token",
                },
                status_code=401,
                headers={
                    "WWW-Authenticate": f'Bearer resource_metadata="{server_url}/.well-known/oauth-protected-resource"'
                },
            )

        # Check authorization (creator or shared member)
        creator_user_id = _config.user_id
        connecting_user_id = token_data.get("sub")  # JWT uses 'sub' for user ID

        # Fast path: creator always has access
        if connecting_user_id == creator_user_id:
            logger.info(f"[AUTH] Request authorized (owner): {token_data.get('email')}")
            return await call_next(request)

        # Check if user is a shared member via robotmcp-cloud API
        if _config.robot_name:
            if await check_shared_access(_config.robot_name, connecting_user_id):
                logger.info(
                    f"[AUTH] Request authorized (shared member): {token_data.get('email')}"
                )
                return await call_next(request)

        logger.warning(
            f"[AUTH] Access denied: user {connecting_user_id} is not authorized"
        )
        return JSONResponse(
            {
                "error": "forbidden",
                "error_description": "Access denied: not authorized for this server",
            },
            status_code=403,
        )
