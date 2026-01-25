# Phase 2: Integrate ros-mcp-server

**Copyright (c) 2025 Contoro. All rights reserved.**

---

## Goal

Integrate **ros-mcp-server** (open source, Apache 2.0) into **robotmcp-server** (proprietary) using a git submodule and a thin integration layer, preserving OAuth and Cloudflare tunnel infrastructure.

**Prerequisites:** Phase 1 must be complete - ros-mcp-server must be refactored into a library with `register_ros_tools()` function.

---

## Checklist Summary

- [ ] **Step 1:** Add ros-mcp-server as a git submodule
- [ ] **Step 2:** Create `ros_integration.py` integration layer
- [ ] **Step 3:** Update `main.py` to register ROS tools
- [ ] **Step 4:** Remove legacy demo tools (`tools.py`)
- [ ] **Step 5:** Update dependencies in `pyproject.toml`
- [ ] **Verification:** Test submodule initialization
- [ ] **Verification:** Test imports and ROS tools registration
- [ ] **Verification:** Test MCP connection and ROS tools availability
- [ ] **Post-Integration:** Add ROS environment variables
- [ ] **Post-Integration:** Update documentation

---

## Approach

Use git submodule to include ros-mcp-server as a dependency, then register ROS tools into the existing MCP instance via a thin integration layer.

**Benefits:**
- ✅ Clean licensing separation (submodule stays Apache 2.0)
- ✅ Easy updates: `git submodule update --remote`
- ✅ Single MCP instance with all ROS tools
- ✅ ros-mcp-server remains standalone
- ✅ OAuth and Cloudflare tunnel infrastructure preserved

---

## Steps

### Step 1: Add ros-mcp-server as a Submodule

```bash
git submodule add https://github.com/robotmcp/ros-mcp-server.git
git submodule update --init --recursive
```

**Optional but recommended:** Pin the submodule to the Phase 1 "library-ready" commit:

```bash
cd ros-mcp-server
git checkout <phase1-commit-hash>
cd ..
git add ros-mcp-server
git commit -m "Pin ros-mcp-server to Phase 1 library-ready commit"
```

---

### Step 2: Create Integration Layer

Create `ros_integration.py` in the project root:

```python
"""Integration layer for ros-mcp-server submodule.

This module handles importing and registering ROS MCP tools from the
ros-mcp-server submodule into the main MCP instance.
"""
import os
import sys
from pathlib import Path

# Add ros-mcp-server submodule to Python path
_submodule_path = Path(__file__).parent / "ros-mcp-server"
if not _submodule_path.exists():
    raise RuntimeError(
        "ros-mcp-server submodule not found. "
        "Run: git submodule update --init --recursive"
    )

sys.path.insert(0, str(_submodule_path))

# Import ROS tools registration function
from ros_mcp.tools import register_ros_tools

__all__ = ["register_ros_tools"]
```

**Purpose:** This keeps all submodule path handling isolated to one place, making the integration clean and maintainable.

---

### Step 3: Update main.py to Register ROS Tools

Replace the demo tool registration with ROS MCP tool registration.

**Before (current):**
```python
from tools import mcp  # Demo tools (echo, ping)
```

**After:**
```python
from fastmcp import FastMCP
from ros_integration import register_ros_tools

# Create MCP instance
mcp = FastMCP("robotmcp-server")

# Register ROS tools
# Note: rosbridge_ip and rosbridge_port should come from environment
# or config, matching ros-mcp-server's expected interface
rosbridge_ip = os.getenv("ROSBRIDGE_IP", "localhost")
rosbridge_port = int(os.getenv("ROSBRIDGE_PORT", "9090"))

register_ros_tools(
    mcp,
    rosbridge_ip=rosbridge_ip,
    rosbridge_port=rosbridge_port,
)

# Existing OAuth middleware + FastAPI setup remains unchanged
```

**Result:** A single MCP instance hosting all ROS tools, with OAuth and Cloudflare tunnel infrastructure intact.

---

### Step 4: Remove Legacy Demo Tools

1. **Delete `tools.py`** - No longer needed (ping/echo demo tools)

2. **Verify no references remain:**
   ```bash
   grep -r "from tools import" .
   grep -r "import tools" .
   ```

3. **Update imports in `main.py`** - Remove any `from tools import mcp` references

**Note:** ROS MCP tools now replace the previous ping-pong functionality. The MCP instance is created directly in `main.py` and populated with ROS tools.

---

### Step 5: Update Dependencies

Add all required ros-mcp-server dependencies to `requirements.txt` or `pyproject.toml`.

**Check ros-mcp-server's dependencies:**
```bash
cd ros-mcp-server
cat requirements.txt  # or pyproject.toml
cd ..
```

**Add to `pyproject.toml` dependencies:**
```toml
[project]
dependencies = [
    # ... existing dependencies ...
    # Add ros-mcp-server dependencies here
    "rosbridge-suite>=0.11.0",  # Example - check actual deps
    # ... other ros-mcp dependencies ...
]
```

**Ensure compatibility:**
- Verify dependency versions are compatible with existing OAuth/FastAPI stack
- Test that all imports work correctly
- Check for version conflicts

---

## Verification

After completing all steps, verify the integration:

1. **Check submodule is initialized:**
   ```bash
   git submodule status
   ```

2. **Test imports:**
   ```python
   python -c "from ros_integration import register_ros_tools; print('OK')"
   ```

3. **Start server and verify ROS tools are available:**
   ```bash
   robotmcp-server start
   # Check logs for ROS tools registration
   ```

4. **Test MCP connection:**
   - Connect via MCP client (ChatGPT, Claude)
   - Verify ROS tools appear in available tools list
   - Test a ROS tool call

---

## Post-Integration

### Environment Variables

Add ROS-specific configuration to `.env` or `.env.public`:

```bash
# ROS Bridge configuration
ROSBRIDGE_IP=localhost
ROSBRIDGE_PORT=9090
```

### Documentation Updates

Update documentation to reflect:
- ROS tools are now available
- Configuration requirements for ROS Bridge
- How to use ROS tools via MCP clients

---

## Troubleshooting

### Submodule Not Found

```bash
git submodule update --init --recursive
```

### Import Errors

- Verify `ros-mcp-server` submodule is at correct commit (Phase 1 complete)
- Check that `ros_mcp.tools` module exists in submodule
- Verify Python path is correct in `ros_integration.py`

### Dependency Conflicts

- Review `ros-mcp-server` requirements
- Check for version conflicts with existing dependencies
- Consider using virtual environment for testing

---

## Related Documents

- [Repository Restructuring Plan](merge_plan.md) - Overall integration strategy
- [Project Plan](project_plan.md) - Architecture and module structure
- [Installation Guide](install.md) - Setup instructions
