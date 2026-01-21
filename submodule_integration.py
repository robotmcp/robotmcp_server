"""Auto-discover and integrate MCP tools/resources/prompts from git submodules.

This module scans .gitmodules for submodules with pyproject.toml files and
automatically registers their tools, resources, and prompts with a FastMCP instance.

Submodules can define integration config in pyproject.toml:

    [tool.mcp.integration]
    package = "my_mcp"  # Main package name (auto-detected if not specified)
    register_function = "my_mcp.integration:register"  # Custom registration function

Or follow conventions:
    - <package>/integration.py with register(mcp, **config)
    - <package>/tools/__init__.py with register_all_tools(mcp, ...)
    - <package>/resources/__init__.py with register_all_resources(mcp, ...)
    - <package>/prompts/__init__.py with register_all_prompts(mcp, ...)
"""
import importlib
import inspect
import logging
import sys
from pathlib import Path
from typing import Any, Callable

from fastmcp import FastMCP

from submodule_deps import parse_gitmodules, get_package_name_from_pyproject

logger = logging.getLogger(__name__)


def _load_pyproject_toml(path: Path) -> dict[str, Any]:
    """Load and parse a pyproject.toml file."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    with open(path, "rb") as f:
        return tomllib.load(f)


def _get_integration_config(pyproject: dict[str, Any]) -> dict[str, Any]:
    """Extract MCP integration config from pyproject.toml.

    Looks for [tool.mcp.integration] section.
    """
    return pyproject.get("tool", {}).get("mcp", {}).get("integration", {})


def _import_module_safe(module_name: str) -> Any | None:
    """Safely import a module, returning None if it doesn't exist."""
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


def _get_function_from_path(path: str) -> Callable | None:
    """Get a function from a module:function path string.

    Args:
        path: String like "my_package.module:function_name"

    Returns:
        The function, or None if not found.
    """
    if ":" not in path:
        return None

    module_path, func_name = path.rsplit(":", 1)
    module = _import_module_safe(module_path)
    if module is None:
        return None

    return getattr(module, func_name, None)


def _call_register_function(
    func: Callable,
    mcp: FastMCP,
    config: dict[str, Any],
    submodule_name: str,
) -> bool:
    """Call a registration function with appropriate arguments.

    Inspects the function signature to determine which arguments to pass.
    Supports various signatures:
        - register(mcp)
        - register(mcp, **config)
        - register_all_tools(mcp, ws_manager, ...)
    """
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())

    # Build kwargs based on what the function accepts
    kwargs = {}

    # Always pass mcp as first positional arg
    args = [mcp]

    # Check for specific parameters the function might need
    for param_name in params[1:]:  # Skip first param (mcp)
        param = sig.parameters[param_name]

        # Handle **kwargs
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            kwargs.update(config)
            break

        # Handle specific known parameters
        if param_name in config:
            kwargs[param_name] = config[param_name]
        elif param_name == "ws_manager" and "ws_manager" in config:
            kwargs["ws_manager"] = config["ws_manager"]

    try:
        func(*args, **kwargs)
        return True
    except Exception as e:
        logger.error(f"[INTEGRATION] Failed to call {func.__name__} for {submodule_name}: {e}")
        return False


def _discover_and_register_submodule(
    mcp: FastMCP,
    submodule_path: Path,
    package_name: str,
    integration_config: dict[str, Any],
    global_config: dict[str, Any],
) -> dict[str, bool]:
    """Discover and register tools/resources/prompts from a submodule.

    Returns:
        Dict with 'tools', 'resources', 'prompts' keys indicating success.
    """
    result = {"tools": False, "resources": False, "prompts": False}
    submodule_name = submodule_path.name

    # Merge global config with any submodule-specific config
    config = {**global_config}

    # Check for custom register function in integration config
    if "register_function" in integration_config:
        func = _get_function_from_path(integration_config["register_function"])
        if func:
            logger.info(f"[INTEGRATION] Using custom register function for {submodule_name}")
            if _call_register_function(func, mcp, config, submodule_name):
                result["tools"] = result["resources"] = result["prompts"] = True
            return result

    # Check for integration module with register() function
    integration_module = _import_module_safe(f"{package_name}.integration")
    if integration_module and hasattr(integration_module, "register"):
        logger.info(f"[INTEGRATION] Found {package_name}.integration.register()")
        if _call_register_function(integration_module.register, mcp, config, submodule_name):
            result["tools"] = result["resources"] = result["prompts"] = True
        return result

    # Fall back to convention-based discovery
    # Look for register_all_tools in tools/__init__.py
    tools_module = _import_module_safe(f"{package_name}.tools")
    if tools_module and hasattr(tools_module, "register_all_tools"):
        logger.info(f"[INTEGRATION] Found {package_name}.tools.register_all_tools()")
        result["tools"] = _call_register_function(
            tools_module.register_all_tools, mcp, config, submodule_name
        )

    # Look for register_all_resources in resources/__init__.py
    resources_module = _import_module_safe(f"{package_name}.resources")
    if resources_module and hasattr(resources_module, "register_all_resources"):
        logger.info(f"[INTEGRATION] Found {package_name}.resources.register_all_resources()")
        result["resources"] = _call_register_function(
            resources_module.register_all_resources, mcp, config, submodule_name
        )

    # Look for register_all_prompts in prompts/__init__.py
    prompts_module = _import_module_safe(f"{package_name}.prompts")
    if prompts_module and hasattr(prompts_module, "register_all_prompts"):
        logger.info(f"[INTEGRATION] Found {package_name}.prompts.register_all_prompts()")
        result["prompts"] = _call_register_function(
            prompts_module.register_all_prompts, mcp, config, submodule_name
        )

    return result


def _create_ws_manager_if_needed(config: dict[str, Any], package_name: str) -> dict[str, Any]:
    """Create WebSocketManager for ROS-based submodules if needed.

    This is a special case for ros-mcp-server compatibility.
    """
    if package_name == "ros_mcp" and "ws_manager" not in config:
        try:
            from ros_mcp.utils.websocket import WebSocketManager

            rosbridge_ip = config.get("rosbridge_ip", "127.0.0.1")
            rosbridge_port = config.get("rosbridge_port", 9090)
            default_timeout = config.get("default_timeout", 5.0)

            config["ws_manager"] = WebSocketManager(
                rosbridge_ip, rosbridge_port, default_timeout=default_timeout
            )
            logger.info(f"[INTEGRATION] Created WebSocketManager for ros_mcp")
        except ImportError:
            logger.warning("[INTEGRATION] Could not import WebSocketManager for ros_mcp")

    return config


def discover_and_register_all(
    mcp: FastMCP,
    root: Path | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, dict[str, bool]]:
    """Discover all MCP submodules and register their tools/resources/prompts.

    Args:
        mcp: FastMCP instance to register with
        root: Root directory to scan (defaults to script's parent directory)
        config: Global configuration to pass to all submodules
            Common config keys:
            - rosbridge_ip: IP for ROS bridge (default: "127.0.0.1")
            - rosbridge_port: Port for ROS bridge (default: 9090)

    Returns:
        Dict mapping submodule names to their registration results.
    """
    if root is None:
        root = Path(__file__).parent

    if config is None:
        config = {}

    results = {}

    # Parse .gitmodules to find submodules
    submodules = parse_gitmodules(root)

    if not submodules:
        logger.info("[INTEGRATION] No git submodules found")
        return results

    logger.info(f"[INTEGRATION] Found {len(submodules)} git submodule(s)")

    for submodule in submodules:
        submodule_path = root / submodule["path"]
        pyproject_path = submodule_path / "pyproject.toml"

        # Check if submodule directory exists
        if not submodule_path.exists():
            logger.warning(
                f"[INTEGRATION] Submodule {submodule['name']} directory not found "
                "(run 'git submodule update --init')"
            )
            continue

        # Check if it has pyproject.toml
        if not pyproject_path.exists():
            logger.debug(f"[INTEGRATION] Submodule {submodule['name']} has no pyproject.toml")
            continue

        # Load pyproject.toml
        try:
            pyproject = _load_pyproject_toml(pyproject_path)
        except Exception as e:
            logger.error(f"[INTEGRATION] Failed to load {pyproject_path}: {e}")
            continue

        # Get package name
        package_name = get_package_name_from_pyproject(pyproject_path)
        if not package_name:
            logger.warning(f"[INTEGRATION] Could not determine package name for {submodule['name']}")
            continue

        # Normalize package name (replace - with _)
        package_name = package_name.replace("-", "_")

        # Add submodule to Python path if not already there
        submodule_str = str(submodule_path)
        if submodule_str not in sys.path:
            sys.path.insert(0, submodule_str)

        # Get integration config from pyproject.toml
        integration_config = _get_integration_config(pyproject)

        # Create submodule-specific config (might need ws_manager for ROS)
        submodule_config = _create_ws_manager_if_needed(config.copy(), package_name)

        logger.info(f"[INTEGRATION] Registering {submodule['name']} (package: {package_name})")

        # Discover and register
        results[submodule["name"]] = _discover_and_register_submodule(
            mcp=mcp,
            submodule_path=submodule_path,
            package_name=package_name,
            integration_config=integration_config,
            global_config=submodule_config,
        )

    # Log summary
    registered_count = sum(
        1 for r in results.values() if any(r.values())
    )
    logger.info(f"[INTEGRATION] Registered {registered_count}/{len(results)} submodule(s)")

    return results


# Convenience function for backwards compatibility
def register_all_submodules(
    mcp: FastMCP,
    rosbridge_ip: str = "127.0.0.1",
    rosbridge_port: int = 9090,
    **extra_config,
) -> dict[str, dict[str, bool]]:
    """Register all MCP submodules with the given FastMCP instance.

    This is a convenience function that wraps discover_and_register_all()
    with common ROS configuration.

    Args:
        mcp: FastMCP instance to register with
        rosbridge_ip: IP address of the ROS bridge server
        rosbridge_port: Port of the ROS bridge server
        **extra_config: Additional configuration to pass to submodules

    Returns:
        Dict mapping submodule names to their registration results.
    """
    config = {
        "rosbridge_ip": rosbridge_ip,
        "rosbridge_port": rosbridge_port,
        **extra_config,
    }
    return discover_and_register_all(mcp, config=config)
