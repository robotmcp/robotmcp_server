# Repository Restructuring Plan

## Goal

Integrate **ros-mcp-server** (open source) into **robotmcp_server** (proprietary) using git submodule approach.

- ros-mcp-server: Apache 2.0 licensed, ROS MCP tools
- robotmcp_server: Proprietary, OAuth + Cloudflare tunnel infrastructure

## Approach: Refactor-to-Library + Submodule

### Phase 1: Refactor ros-mcp-server

Make ros-mcp-server importable as a library:

```
ros-mcp-server/
├── ros_mcp/                    # NEW package
│   ├── __init__.py
│   ├── tools.py                # All @mcp.tool() definitions
│   ├── server.py               # MCP instance + main()
│   └── websocket.py            # From utils/websocket_manager.py
├── server.py                   # Entry point: from ros_mcp.server import main
└── pyproject.toml              # packages = ["ros_mcp", "ros_mcp.utils"]
```

**Key**: Create `register_ros_tools(mcp, rosbridge_ip, rosbridge_port)` function that registers all tools.

### Phase 2: Integrate into robotmcp_server

1. Add submodule:
   ```bash
   git submodule add https://github.com/robotmcp/ros-mcp-server.git
   ```

2. Create `ros_integration.py`:
   ```python
   import sys, os
   sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ros-mcp-server'))
   from ros_mcp.tools import register_ros_tools
   ```

3. Update `main.py`:
   ```python
   from fastmcp import FastMCP
   from ros_integration import register_ros_tools

   mcp = FastMCP("robotmcp-server")
   register_ros_tools(mcp, rosbridge_ip, rosbridge_port)
   # ... OAuth middleware + FastAPI
   ```

4. Delete `tools.py` (no longer needed)

5. Update `requirements.txt` with ros-mcp dependencies

### Benefits

- ✅ Clean licensing separation (submodule stays Apache 2.0)
- ✅ Easy updates: `git submodule update --remote`
- ✅ Single MCP instance with all tools
- ✅ ros-mcp-server works standalone

