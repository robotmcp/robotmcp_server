"""MCP Tools for robotmcp-server.

This module defines the MCP tools (echo, ping) that are exposed to clients.
For ros-mcp-server merge, replace these with ROS-specific tools.
"""

import logging

from fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Create the FastMCP server instance
mcp = FastMCP("robotmcp-server")


@mcp.tool()
def echo(message: str) -> str:
    """Echo back the input message.

    Args:
        message: The message to echo back

    Returns:
        The echoed message with a prefix
    """
    logger.info(f"[TOOL] echo invoked, message length: {len(message)}")
    return f"Echo: {message}"


@mcp.tool()
def ping() -> str:
    """Simple ping tool to test connectivity.

    Returns:
        A pong response
    """
    logger.info("[TOOL] ping invoked")
    return "pong from Mok's computer"
