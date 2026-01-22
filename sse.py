"""Legacy SSE endpoints for backward compatibility.

This module provides the legacy SSE transport endpoints (/sse, /message)
for older MCP clients that don't support Streamable HTTP.
Uses JWT for stateless token validation - tokens survive server restarts.
"""

import logging

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.responses import Response

from mcp.server.sse import SseServerTransport

from oauth.jwt_utils import verify_access_token
from oauth.middleware import check_shared_access

logger = logging.getLogger(__name__)

# Router for SSE endpoints
router = APIRouter(tags=["sse"])

# SSE transport instance
sse_transport = SseServerTransport("/message")

# These will be set by init_sse_routes()
_server_url: str = ""
_local_config = None
_mcp = None


def init_sse_routes(server_url: str, local_config, mcp_instance):
    """Initialize SSE routes with required dependencies.

    Args:
        server_url: The server URL for OAuth metadata references
        local_config: The local config object with user_id for authorization
        mcp_instance: The FastMCP instance for running the MCP server

    Must be called before including the router in the app.
    """
    global _server_url, _local_config, _mcp
    _server_url = server_url
    _local_config = local_config
    _mcp = mcp_instance


def unauthorized_response(error_description: str) -> JSONResponse:
    """Return 401 with WWW-Authenticate header pointing to resource metadata (RFC 9728)."""
    return JSONResponse(
        {"error": "unauthorized", "error_description": error_description},
        status_code=401,
        headers={
            "WWW-Authenticate": f'Bearer resource_metadata="{_server_url}/.well-known/oauth-protected-resource"'
        },
    )


def forbidden_response(error_description: str) -> JSONResponse:
    """Return 403 Forbidden response for unauthorized access."""
    return JSONResponse(
        {"error": "forbidden", "error_description": error_description}, status_code=403
    )


async def check_authorization(token_data: dict) -> bool:
    """Check if the token belongs to an authorized user (owner or shared member)."""
    creator_user_id = _local_config.user_id if _local_config else None
    connecting_user_id = token_data.get("sub")  # JWT uses 'sub' for user ID

    if not creator_user_id:
        logger.info("[SSE] No creator configured, allowing access")
        return True

    # Fast path: owner always has access
    if connecting_user_id == creator_user_id:
        logger.info(f"[SSE] Request authorized (owner): {token_data.get('email')}")
        return True

    # Check if user is a shared member via robotmcp-cloud API
    robot_name = _local_config.robot_name if _local_config else None
    if robot_name:
        if await check_shared_access(robot_name, connecting_user_id):
            logger.info(
                f"[SSE] Request authorized (shared member): {token_data.get('email')}"
            )
            return True

    logger.warning(f"[SSE] Access denied: user {connecting_user_id} is not authorized")
    raise HTTPException(
        status_code=403, detail="Access denied: not authorized for this server"
    )


@router.get("/sse")
async def sse_endpoint(request: Request) -> Response:
    """Legacy SSE endpoint for MCP client connections (backward compatibility)."""
    logger.info("[SSE] Legacy SSE endpoint hit")
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        logger.info("[SSE] Request rejected: no Bearer token")
        return unauthorized_response("Missing or invalid Authorization header")

    token = auth_header[7:]

    # Verify JWT token (stateless - no storage lookup needed)
    token_data = verify_access_token(token, issuer=_server_url)

    if not token_data:
        logger.info("[SSE] Request rejected: invalid or expired token")
        return unauthorized_response("Invalid or expired token")

    try:
        await check_authorization(token_data)
    except HTTPException as e:
        return forbidden_response(e.detail)

    logger.info(f"[SSE] Connection established for user: {token_data.get('email')}")
    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await _mcp._mcp_server.run(
            streams[0], streams[1], _mcp._mcp_server.create_initialization_options()
        )

    return Response()


@router.post("/message")
async def message_endpoint(request: Request) -> Response:
    """Legacy message endpoint for SSE transport (backward compatibility)."""
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        logger.info("[SSE] Message rejected: no Bearer token")
        return unauthorized_response("Missing or invalid Authorization header")

    token = auth_header[7:]

    # Verify JWT token (stateless - no storage lookup needed)
    token_data = verify_access_token(token, issuer=_server_url)

    if not token_data:
        logger.info("[SSE] Message rejected: invalid or expired token")
        return unauthorized_response("Invalid or expired token")

    try:
        await check_authorization(token_data)
    except HTTPException as e:
        return forbidden_response(e.detail)

    logger.info(f"[SSE] Message received from user: {token_data.get('email')}")
    await sse_transport.handle_post_message(
        request.scope, request.receive, request._send
    )
    return Response()
