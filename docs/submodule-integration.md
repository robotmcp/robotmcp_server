# Submodule Integration Guide

This guide explains how to create an MCP submodule that integrates with robotmcp_server.

## Overview

robotmcp_server automatically discovers and integrates MCP tools from git submodules. When the server starts, it:

1. Parses `.gitmodules` to find all submodules
2. Reads each submodule's `pyproject.toml` to get the package name
3. Auto-installs missing dependencies via `pip install -e`
4. Discovers and calls the registration function to register tools, resources, and prompts

## Required Files

Your submodule needs at minimum:

```
my-mcp-tools/
├── pyproject.toml          # Required: defines package name
└── my_mcp_tools/           # Python package (use underscores)
    ├── __init__.py
    └── integration.py      # Recommended: main entry point
```

## pyproject.toml

Your `pyproject.toml` must define a package name:

```toml
[project]
name = "my-mcp-tools"
version = "0.1.0"
description = "My MCP tools for robotmcp_server"
requires-python = ">=3.10"
dependencies = [
    "fastmcp>=2.0.0",
    # Add your dependencies here
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### Optional: Custom Register Function

You can specify a custom register function location:

```toml
[tool.mcp.integration]
register_function = "my_mcp_tools.integration:register"
```

This is optional—by default, the server looks for `<package>/integration.py` with a `register()` function.

## integration.py

This is the main entry point. The server calls `register(mcp, **kwargs)` at startup.

### Minimal Example

```python
"""Integration module for my-mcp-tools."""

from fastmcp import FastMCP


def register(mcp: FastMCP, **kwargs) -> None:
    """Register all tools with the MCP server.

    Args:
        mcp: FastMCP instance to register with
        **kwargs: Ignored (for forward compatibility)
    """
    @mcp.tool()
    def my_tool(message: str) -> str:
        """Process a message and return a result.

        Args:
            message: The input message to process
        """
        return f"Processed: {message}"

    @mcp.tool()
    def another_tool(value: int) -> dict:
        """Perform a calculation.

        Args:
            value: Input number
        """
        return {"result": value * 2, "original": value}
```

### Full Example with Configuration

For more complex submodules, read configuration from environment variables:

```python
"""Integration module for my-mcp-tools.

This module provides the register() function called by robotmcp_server.
Configuration is read from environment variables.
"""

import logging
import os

from fastmcp import FastMCP

from my_mcp_tools.tools import register_all_tools
from my_mcp_tools.resources import register_all_resources
from my_mcp_tools.prompts import register_all_prompts

logger = logging.getLogger(__name__)

# Defaults (can be overridden via environment variables)
DEFAULT_API_URL = "http://localhost:8080"
DEFAULT_TIMEOUT = 30.0


def register(mcp: FastMCP, **kwargs) -> None:
    """Register all tools, resources, and prompts.

    Environment variables:
        MY_TOOLS_API_URL: API endpoint URL (default: http://localhost:8080)
        MY_TOOLS_TIMEOUT: Request timeout in seconds (default: 30.0)

    Args:
        mcp: FastMCP instance to register with
        **kwargs: Ignored (for forward compatibility)
    """
    # Read configuration from environment
    api_url = os.getenv("MY_TOOLS_API_URL", DEFAULT_API_URL)
    timeout = float(os.getenv("MY_TOOLS_TIMEOUT", str(DEFAULT_TIMEOUT)))

    logger.info(f"[MY_TOOLS] Initializing with API at {api_url}")

    # Register all components
    register_all_tools(mcp, api_url=api_url, timeout=timeout)
    register_all_resources(mcp)
    register_all_prompts(mcp)

    logger.info("[MY_TOOLS] Registration complete")
```

## Organizing Tools

For larger submodules, organize tools into categories:

```
my_mcp_tools/
├── __init__.py
├── integration.py
├── tools/
│   ├── __init__.py         # exports register_all_tools()
│   ├── data.py             # data-related tools
│   └── analysis.py         # analysis tools
├── resources/
│   ├── __init__.py         # exports register_all_resources()
│   └── schemas.py
└── prompts/
    ├── __init__.py         # exports register_all_prompts()
    └── templates.py
```

### tools/__init__.py

```python
"""Tool registration for my-mcp-tools."""

from fastmcp import FastMCP

from my_mcp_tools.tools.data import register_data_tools
from my_mcp_tools.tools.analysis import register_analysis_tools


def register_all_tools(mcp: FastMCP, api_url: str, timeout: float) -> None:
    """Register all tools with the MCP server.

    Args:
        mcp: FastMCP instance
        api_url: API endpoint URL
        timeout: Request timeout
    """
    register_data_tools(mcp, api_url, timeout)
    register_analysis_tools(mcp, api_url, timeout)
```

### tools/data.py

```python
"""Data tools for my-mcp-tools."""

from fastmcp import FastMCP


def register_data_tools(mcp: FastMCP, api_url: str, timeout: float) -> None:
    """Register data-related tools."""

    @mcp.tool()
    def fetch_data(query: str) -> dict:
        """Fetch data from the API.

        Args:
            query: Search query string
        """
        # Implementation using api_url and timeout
        return {"query": query, "results": []}

    @mcp.tool()
    def save_data(key: str, value: str) -> bool:
        """Save data to the API.

        Args:
            key: Storage key
            value: Data to store
        """
        return True
```

## Resources and Prompts

### Registering Resources

```python
from fastmcp import FastMCP


def register_all_resources(mcp: FastMCP) -> None:
    """Register resources (read-only data sources)."""

    @mcp.resource("config://settings")
    def get_settings() -> str:
        """Return current configuration settings."""
        return "key1=value1\nkey2=value2"

    @mcp.resource("data://schema")
    def get_schema() -> str:
        """Return the data schema."""
        return '{"type": "object", "properties": {}}'
```

### Registering Prompts

```python
from fastmcp import FastMCP


def register_all_prompts(mcp: FastMCP) -> None:
    """Register prompt templates."""

    @mcp.prompt()
    def analyze_data(data_type: str) -> str:
        """Generate a prompt for data analysis.

        Args:
            data_type: Type of data to analyze
        """
        return f"Please analyze the {data_type} data and provide insights."
```

## Configuration

**Important:** Submodules are responsible for their own configuration via environment variables. The main server does not pass configuration to submodules—this keeps the architecture decoupled.

### Setting Environment Variables

Users configure your submodule by setting environment variables before starting the server:

```bash
# In .env file or shell
export MY_TOOLS_API_URL=http://api.example.com
export MY_TOOLS_TIMEOUT=60

# Start server
robotmcp-server
```

### Documentation

Document your environment variables clearly in:
1. Your `integration.py` docstring
2. Your submodule's README.md
3. The function docstring for `register()`

## Alternative Discovery Methods

The server supports three discovery methods (checked in order):

### 1. Custom Register Function (Highest Priority)

Specified in `pyproject.toml`:

```toml
[tool.mcp.integration]
register_function = "my_package.custom_module:my_register_func"
```

### 2. Integration Module (Recommended)

Create `<package>/integration.py` with `register(mcp, **kwargs)`.

### 3. Convention-Based (Fallback)

If no integration.py exists, the server looks for:
- `<package>/tools/__init__.py` → `register_all_tools(mcp)`
- `<package>/resources/__init__.py` → `register_all_resources(mcp)`
- `<package>/prompts/__init__.py` → `register_all_prompts(mcp)`

## Testing Your Submodule

### Standalone Testing

Test your submodule independently:

```python
# test_integration.py
from fastmcp import FastMCP
from my_mcp_tools.integration import register

mcp = FastMCP("test-server")
register(mcp)

# List registered tools
print("Registered tools:", [t.name for t in mcp.list_tools()])
```

### With robotmcp_server

1. Add your submodule:
   ```bash
   git submodule add https://github.com/you/my-mcp-tools.git
   ```

2. Start the server:
   ```bash
   robotmcp-server
   ```

3. Check logs for registration messages:
   ```
   [MY_TOOLS] Initializing with API at http://localhost:8080
   [MY_TOOLS] Registration complete
   ```

## Real-World Example

See `ros-mcp-server/ros_mcp/integration.py` in this repository for a production example that:
- Reads configuration from environment variables
- Creates a WebSocket manager for ROS communication
- Registers tools, resources, and prompts in organized categories
- Uses proper logging for debugging

## Checklist

Before publishing your submodule:

- [ ] `pyproject.toml` has a valid `project.name`
- [ ] `integration.py` has a `register(mcp, **kwargs)` function
- [ ] All tools have docstrings with argument descriptions
- [ ] Environment variables are documented
- [ ] README explains installation and configuration
- [ ] Tested standalone and with robotmcp_server
