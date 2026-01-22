"""CLI entry point for robotmcp-server.

Copyright (c) 2025 Contoro. All rights reserved.

This runs the LOCAL MCP server on the user's machine.
On first run, it opens a browser for login via Railway.
"""

import argparse
import os
import platform
import shutil
import signal
import subprocess
import sys
from importlib.metadata import version as get_version
from pathlib import Path

import requests
import uvicorn
from dotenv import load_dotenv
from supabase import create_client

from config import load_config, clear_config, CONFIG_FILE
from submodule_deps import ensure_submodule_deps

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
    VERSION = get_version("robotmcp-server")
except Exception:
    VERSION = "0.0.0"  # Fallback for development

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

# Cloudflared auto-install settings
CLOUDFLARED_INSTALL_DIR = Path.home() / ".local" / "bin"
CLOUDFLARED_RELEASES_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download"
)

# Daemon settings
CONFIG_DIR = Path.home() / ".robotmcp-server"
PID_FILE = CONFIG_DIR / "server.pid"
LOG_FILE = CONFIG_DIR / "server.log"


# ============== Helper Functions ==============


def fetch_user_info(access_token: str) -> dict:
    """Fetch user info from Supabase using access token."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return {}

    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        response = supabase.auth.get_user(access_token)
        if response and response.user:
            user = response.user
            return {
                "user_id": user.id,
                "email": user.email,
                "name": user.user_metadata.get("name", "")
                if user.user_metadata
                else "",
                "organization": user.user_metadata.get("organization", "")
                if user.user_metadata
                else "",
            }
    except Exception:
        pass
    return {}


def check_cloudflared() -> bool:
    """Check if cloudflared is installed and accessible."""
    return shutil.which("cloudflared") is not None


def check_cloudflared_service() -> bool:
    """Check if cloudflared is running as a Windows service."""
    if platform.system() != "Windows":
        return False
    try:
        result = subprocess.run(
            ["sc", "query", "cloudflared"], capture_output=True, text=True
        )
        return "RUNNING" in result.stdout
    except Exception:
        return False


def check_cloudflared_process() -> bool:
    """Check if any cloudflared tunnel process is running."""
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq cloudflared.exe"],
                capture_output=True,
                text=True,
            )
            return "cloudflared.exe" in result.stdout
        except Exception:
            return False
    else:
        # Linux/macOS: use pgrep
        try:
            result = subprocess.run(
                ["pgrep", "-x", "cloudflared"], capture_output=True, text=True
            )
            return result.returncode == 0
        except Exception:
            return False


def get_cloudflared_logs(lines: int = 20) -> list[str]:
    """Get recent cloudflared log lines."""
    log_file = CONFIG_DIR / "cloudflared.log"
    if not log_file.exists():
        return []
    try:
        with open(log_file, "r") as f:
            all_lines = f.readlines()
            return all_lines[-lines:] if len(all_lines) > lines else all_lines
    except Exception:
        return []


def is_server_running() -> bool:
    """Check if MCP server is already running on port 8766."""
    if platform.system() == "Windows":
        try:
            result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
            for line in result.stdout.split("\n"):
                if ":8766" in line and "LISTENING" in line:
                    return True
        except Exception:
            pass
    else:
        try:
            result = subprocess.run(
                ["lsof", "-ti", ":8766"], capture_output=True, text=True
            )
            return bool(result.stdout.strip())
        except Exception:
            pass
    return False


def run_cloudflared_tunnel(tunnel_token: str) -> subprocess.Popen:
    """Start cloudflared tunnel in background."""
    cloudflared_cmd = get_cloudflared_path()
    return subprocess.Popen(
        [cloudflared_cmd, "tunnel", "run", "--token", tunnel_token],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def kill_cloudflared_processes():
    """Kill any running cloudflared processes started by this CLI."""
    killed = False
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["taskkill", "/F", "/IM", "cloudflared.exe"],
                capture_output=True,
                text=True,
            )
            if "SUCCESS" in result.stdout:
                killed = True
        except Exception:
            pass
    else:
        try:
            result = subprocess.run(
                ["pkill", "-f", "cloudflared tunnel run"], capture_output=True
            )
            killed = result.returncode == 0
        except Exception:
            pass
    return killed


def kill_processes_on_port(port: int) -> bool:
    """Kill any processes listening on the specified port."""
    killed = False
    if platform.system() == "Windows":
        try:
            result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
            for line in result.stdout.split("\n"):
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        try:
                            subprocess.run(
                                ["taskkill", "/F", "/PID", pid], capture_output=True
                            )
                            killed = True
                        except Exception:
                            pass
        except Exception:
            pass
    else:
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"], capture_output=True, text=True
            )
            for pid in result.stdout.strip().split("\n"):
                if pid:
                    subprocess.run(["kill", "-9", pid], capture_output=True)
                    killed = True
        except Exception:
            pass
    return killed


def get_cloudflared_binary_name() -> str | None:
    """Get the correct cloudflared binary name for this platform."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "linux":
        if machine in ("x86_64", "amd64"):
            return "cloudflared-linux-amd64"
        elif machine in ("aarch64", "arm64"):
            return "cloudflared-linux-arm64"
        elif machine.startswith("arm"):
            return "cloudflared-linux-arm"
    elif system == "darwin":
        if machine in ("arm64", "aarch64"):
            return "cloudflared-darwin-arm64"
        else:
            return "cloudflared-darwin-amd64"

    return None  # Windows or unsupported


def install_cloudflared() -> bool:
    """Auto-download cloudflared for Linux/macOS."""
    binary_name = get_cloudflared_binary_name()
    if not binary_name:
        return False

    url = f"{CLOUDFLARED_RELEASES_URL}/{binary_name}"
    dest = CLOUDFLARED_INSTALL_DIR / "cloudflared"

    print("Downloading cloudflared...")
    print(f"  From: {url}")
    print(f"  To:   {dest}")

    try:
        CLOUDFLARED_INSTALL_DIR.mkdir(parents=True, exist_ok=True)

        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()

        with open(dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Make executable
        dest.chmod(0o755)

        print("  Done!")

        # Offer to add ~/.local/bin to PATH
        if not is_local_bin_in_path():
            print("\n  ~/.local/bin is not in your PATH.")
            try:
                response = input("  Add to ~/.bashrc? (y/n): ").strip().lower()
                if response == "y":
                    if add_to_bashrc():
                        print("  Added to ~/.bashrc")
                        print("  Run: source ~/.bashrc  (or restart terminal)")
                    else:
                        print("  Failed to update ~/.bashrc")
            except (EOFError, KeyboardInterrupt):
                pass  # Non-interactive mode, skip

        return True
    except Exception as e:
        print(f"  Failed: {e}")
        return False


def is_local_bin_in_path() -> bool:
    """Check if ~/.local/bin is in PATH."""
    local_bin = str(CLOUDFLARED_INSTALL_DIR)
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    # Check both expanded and unexpanded forms
    return any(local_bin in p or ".local/bin" in p for p in path_dirs)


def add_to_bashrc() -> bool:
    """Add ~/.local/bin to PATH in ~/.bashrc."""
    bashrc = Path.home() / ".bashrc"
    export_line = '\n# Added by robotmcp-server\nexport PATH="$HOME/.local/bin:$PATH"\n'

    try:
        # Check if already added
        if bashrc.exists():
            content = bashrc.read_text()
            if ".local/bin" in content:
                return True  # Already there

        # Append to bashrc
        with open(bashrc, "a") as f:
            f.write(export_line)
        return True
    except Exception:
        return False


def get_cloudflared_path() -> str:
    """Get the path to cloudflared binary."""
    # Check system PATH first
    system_path = shutil.which("cloudflared")
    if system_path:
        return system_path

    # Check ~/.local/bin
    local_path = CLOUDFLARED_INSTALL_DIR / "cloudflared"
    if local_path.exists():
        return str(local_path)

    return "cloudflared"  # Fallback


def ensure_cloudflared() -> bool:
    """Ensure cloudflared is available, auto-install if needed."""
    # Check system PATH
    if check_cloudflared():
        return True

    # Check if in ~/.local/bin but not in PATH
    local_bin = CLOUDFLARED_INSTALL_DIR / "cloudflared"
    if local_bin.exists():
        print(f"\n[INFO] cloudflared found at {local_bin}")
        print('  Add to PATH: export PATH="$HOME/.local/bin:$PATH"')
        return True

    # Auto-install on Linux/macOS
    if platform.system() in ("Linux", "Darwin"):
        print("\n[INFO] cloudflared not found. Installing automatically...")
        if install_cloudflared():
            print('\n[INFO] Add to PATH: export PATH="$HOME/.local/bin:$PATH"')
            print("  Or add to ~/.bashrc for permanent PATH update.\n")
            return True

    return False


# ============== Daemon Functions ==============


def save_pid(pid: int):
    """Save daemon PID to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(pid))


def read_pid() -> int | None:
    """Read daemon PID from file."""
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except (ValueError, OSError):
            pass
    return None


def clear_pid():
    """Remove PID file."""
    if PID_FILE.exists():
        PID_FILE.unlink()


def is_process_running(pid: int) -> bool:
    """Check if a process with given PID is running."""
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True
            )
            return str(pid) in result.stdout
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)  # Signal 0 just checks if process exists
            return True
        except OSError:
            return False


def is_daemon_running() -> tuple[bool, int | None]:
    """Check if daemon is running. Returns (is_running, pid)."""
    pid = read_pid()
    if pid and is_process_running(pid):
        return True, pid
    return False, None


def stop_daemon() -> bool:
    """Stop the running daemon."""
    running, pid = is_daemon_running()
    if not running:
        return False

    try:
        if platform.system() == "Windows":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
        clear_pid()
        return True
    except Exception:
        return False


def daemonize():
    """Fork and daemonize the current process (Unix only)."""
    if platform.system() == "Windows":
        return  # Windows doesn't support fork

    # First fork
    pid = os.fork()
    if pid > 0:
        # Parent exits
        sys.exit(0)

    # Decouple from parent environment
    os.setsid()
    os.umask(0)

    # Second fork
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    # Redirect standard file descriptors to log file
    sys.stdout.flush()
    sys.stderr.flush()

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    log_fd = open(LOG_FILE, "a")
    os.dup2(log_fd.fileno(), sys.stdout.fileno())
    os.dup2(log_fd.fileno(), sys.stderr.fileno())


# ============== CLI Commands ==============


def cmd_start():
    """Start the MCP server in background."""
    from setup import run_login_flow

    # Check if already running
    running, pid = is_daemon_running()
    if running:
        print(f"Server is already running (PID: {pid})")
        print("  Use 'robotmcp-server stop' to stop it first")
        return

    config = load_config()

    # First-run setup
    if not config.is_valid():
        success = run_login_flow()
        if not success:
            print("\n[ERROR] Setup failed. Please try again.")
            sys.exit(1)
        config = load_config()
    else:
        print(f"Logged in as: {config.email}")

    # Check tunnel config
    if not config.has_tunnel():
        print("\n[ERROR] Tunnel not configured.")
        print("  Run: robotmcp-server logout")
        print("  Then: robotmcp-server start")
        sys.exit(1)

    # Check cloudflared (auto-install on Linux/macOS if needed)
    if not ensure_cloudflared():
        print("\n[ERROR] cloudflared not found and auto-install failed.")
        print(
            "  Install manually: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
        )
        sys.exit(1)

    # Warn about cloudflared service
    if check_cloudflared_service():
        print("\n[WARNING] cloudflared Windows service is running!")
        print("  This may cause conflicts. Stop it with:")
        print("  > net stop cloudflared  (as Admin)")
        print()

    # Auto-discover and install submodule dependencies
    if not ensure_submodule_deps():
        print("\n[WARNING] Some submodule dependencies failed to install.")
        print("  The server may not work correctly.")
        print("  Try manually: pip install -e ./ros-mcp-server")
        print()

    # Cleanup old processes
    print("\nCleaning up old processes...")
    if kill_cloudflared_processes():
        print("  - Stopped old cloudflared processes")
    if kill_processes_on_port(8766):
        print("  - Stopped old server on port 8766")

    # Print startup banner BEFORE daemonizing (so user sees it)
    mcp_url = f"{config.tunnel_url}/mcp"
    sse_url = f"{config.tunnel_url}/sse"
    print("\n" + "=" * 60)
    print("  RobotMCP Server - Started")
    print("=" * 60)
    print(f"  User:    {config.email}")
    print()
    print("  Endpoints:")
    print(f"    /mcp  {mcp_url}")
    print(f"    /sse  {sse_url}")
    print()
    print("  +------------------------------------------------------+")
    print("  |  HOW TO CONNECT YOUR AI CLIENT                       |")
    print("  +------------------------------------------------------+")
    print()
    print("  1. Try /mcp first (recommended):")
    print(f"     {mcp_url}")
    print()
    print("  2. If /mcp doesn't work, use /sse instead:")
    print(f"     {sse_url}")
    print()
    print("  Note: Use /sse if /mcp doesn't work with your client.")
    print("        Claude.ai works with both endpoints.")
    print()
    print("=" * 60)
    print(f"  Log:    {LOG_FILE}")
    print("  Stop:   robotmcp-server stop")
    print("  Status: robotmcp-server status")
    print("=" * 60 + "\n")

    # Daemonize on Unix, use subprocess on Windows
    if platform.system() == "Windows":
        # Windows: start in a new process
        script_path = Path(__file__).resolve()
        cmd = [sys.executable, str(script_path), "_daemon"]
        proc = subprocess.Popen(
            cmd,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS,
            stdout=open(LOG_FILE, "a"),
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
        )
        save_pid(proc.pid)
        print(f"Server started in background (PID: {proc.pid})")
    else:
        # Unix: fork and daemonize
        pid = os.fork()
        if pid > 0:
            # Parent process - wait a moment then exit
            import time

            time.sleep(1)  # Give child time to start
            # Read the PID saved by child
            child_pid = read_pid()
            if child_pid:
                print(f"Server started in background (PID: {child_pid})")
            else:
                print("Server started in background")
            return

        # Child process continues
        os.setsid()
        os.umask(0)

        # Second fork
        pid = os.fork()
        if pid > 0:
            sys.exit(0)

        # Save our PID
        save_pid(os.getpid())

        # Redirect stdout/stderr to log file
        sys.stdout.flush()
        sys.stderr.flush()
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        log_fd = open(LOG_FILE, "a")
        os.dup2(log_fd.fileno(), sys.stdout.fileno())
        os.dup2(log_fd.fileno(), sys.stderr.fileno())

        # Run the server
        _run_server(config)


def _run_server(config):
    """Internal function to run the server (called by daemon)."""
    tunnel_process = None

    def signal_handler(sig, frame):
        if tunnel_process:
            tunnel_process.terminate()
            tunnel_process.wait()
        clear_pid()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start tunnel
    tunnel_process = run_cloudflared_tunnel(config.tunnel_token)

    try:
        uvicorn.run("main:app", host="0.0.0.0", port=8766, log_level="info")
    finally:
        if tunnel_process:
            tunnel_process.terminate()
            tunnel_process.wait()
        clear_pid()


def cmd_stop():
    """Stop the MCP server and tunnel."""
    print("Stopping MCP server...")

    # Try to stop daemon first
    stopped_daemon = stop_daemon()
    if stopped_daemon:
        print("  - Daemon stopped")

    # Also clean up any orphaned processes
    stopped_server = kill_processes_on_port(8766)
    stopped_tunnel = kill_cloudflared_processes()

    if stopped_daemon or stopped_server or stopped_tunnel:
        if stopped_server and not stopped_daemon:
            print("  - Server stopped")
        if stopped_tunnel:
            print("  - Tunnel stopped")
        print("\nServer stopped successfully.")
    else:
        print("  No running server found.")


def cmd_restart():
    """Restart the MCP server."""
    print("Restarting MCP server...\n")
    cmd_stop()
    print()
    cmd_start()


def cmd_login():
    """Login to RobotMCP (browser-based OAuth)."""
    from setup import run_login_flow

    config = load_config()

    # Check if already logged in
    if config.is_valid():
        print(f"\nAlready logged in as: {config.email}")
        response = input("Re-login with a different account? [y/N]: ").strip().lower()
        if response != "y":
            print("Login cancelled.")
            return

        # Stop server if running before re-login
        running, pid = is_daemon_running()
        if running:
            print("\nStopping running server first...")
            cmd_stop()
            print()

    # Run login flow
    success = run_login_flow()
    if success:
        config = load_config()
        print(f"Logged in as: {config.email}")
        print(f"Robot URL: {config.tunnel_url}")
        print("\nRun 'robotmcp-server start' to start the server.")
    else:
        print("\n[ERROR] Login failed. Please try again.")
        sys.exit(1)


def cmd_status():
    """Show current status."""
    config = load_config()

    print("\n" + "=" * 50)
    print(f"  RobotMCP Server Status (v{VERSION})")
    print("=" * 50)

    # Account
    print("\n[Account]")
    if config.is_valid():
        print("  Status:   Logged in")
        print(f"  Email:    {config.email}")
        print(f"  User ID:  {config.user_id[:8]}...")
        if SUPABASE_URL and SUPABASE_ANON_KEY:
            user_info = fetch_user_info(config.access_token)
            if user_info:
                if user_info.get("name"):
                    print(f"  Name:     {user_info['name']}")
                if user_info.get("organization"):
                    print(f"  Org:      {user_info['organization']}")
    else:
        print("  Status:   Not logged in")
        print("  Action:   Run 'robotmcp-server start' to log in")

    # Tunnel
    print("\n[Tunnel]")
    if config.has_tunnel():
        print("  Status:   Configured")
        print(f"  Name:     {config.robot_name}")
        print(f"  URL:      {config.tunnel_url}")
        print()
        print("  Endpoints (try /mcp first, use /sse if not working):")
        print(f"    /mcp  {config.tunnel_url}/mcp")
        print(f"    /sse  {config.tunnel_url}/sse")
    else:
        print("  Status:   Not configured")

    # Server
    print("\n[Server]")
    running, pid = is_daemon_running()
    if running:
        print(f"  Status:   Running (PID: {pid})")
        print(f"  Log:      {LOG_FILE}")
    elif is_server_running():
        print("  Status:   Running on port 8766 (not managed)")
    else:
        print("  Status:   Not running")

    # Cloudflared
    print("\n[Cloudflared]")
    local_bin = CLOUDFLARED_INSTALL_DIR / "cloudflared"
    if check_cloudflared():
        print("  Status:   Installed (system)")
        print(f"  Path:     {shutil.which('cloudflared')}")
    elif local_bin.exists():
        print("  Status:   Installed (local)")
        print(f"  Path:     {local_bin}")
    else:
        print("  Status:   Not installed")
        print(
            "  Install:  https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
        )

    # Show tunnel process status
    if check_cloudflared_process():
        print("  Tunnel:   Running")
    else:
        print("  Tunnel:   Not running")

    # Windows service warning (only on Windows)
    if platform.system() == "Windows" and check_cloudflared_service():
        print("  WARNING:  Windows service running (may cause conflicts!)")
        print("            Stop with: net stop cloudflared")

    # Config
    print("\n[Config]")
    print(f"  File:     {CONFIG_FILE}")
    print(f"  Exists:   {CONFIG_FILE.exists()}")

    print("\n" + "=" * 50 + "\n")


def cmd_verify():
    """Comprehensive verification of server, tunnel, and connectivity."""
    config = load_config()

    print("\n" + "=" * 70)
    print("  Comprehensive Tunnel & Server Verification")
    print("=" * 70)

    # Initialize results tracking
    results = {
        "config": False,
        "server_local": False,
        "cloudflared": False,
        "tunnel_auth": False,
        "dns": False,
        "tunnel_endpoints": False,
    }

    # ========== 1. Configuration Check ==========
    print("\n[1] Configuration")
    print("-" * 70)
    if not config.has_tunnel():
        print("  ✗ Tunnel not configured")
        print("  → Run: robotmcp-server start")
        print("\n" + "=" * 70)
        return
    results["config"] = True
    print("  ✓ Configuration found")
    print(f"    Robot Name:  {config.robot_name}")
    print(f"    Tunnel URL:  {config.tunnel_url}")
    print(
        f"    Token:       {'Present' if config.tunnel_token else 'Missing'} ({len(config.tunnel_token) if config.tunnel_token else 0} chars)"
    )

    tunnel_url = config.tunnel_url
    from urllib.parse import urlparse

    parsed = urlparse(tunnel_url)
    hostname = parsed.hostname

    # ========== 2. Local Server Test ==========
    print("\n[2] Local Server Connection")
    print("-" * 70)
    running, pid = is_daemon_running()
    if running:
        print(f"  ✓ Server process running (PID: {pid})")
    elif is_server_running():
        print("  ✓ Server running on port 8766 (not managed)")
    else:
        print("  ✗ Server not running")
        print("  → Run: robotmcp-server start")
        print("\n" + "=" * 70)
        return

    # Test local HTTP connection
    try:
        response = requests.get("http://localhost:8766/health", timeout=2)
        if response.status_code == 200:
            print("  ✓ Local server responding")
            print(f"    http://localhost:8766/health → HTTP {response.status_code}")
            results["server_local"] = True
        else:
            print(f"  ⚠ Local server responding with HTTP {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("  ✗ Cannot connect to localhost:8766")
        print("  → Check if server is actually running")
    except Exception as e:
        print(f"  ✗ Error testing local server: {str(e)[:50]}")

    # ========== 3. Cloudflared Process ==========
    print("\n[3] Cloudflared Process")
    print("-" * 70)
    if check_cloudflared_process():
        print("  ✓ Cloudflared process running")
        results["cloudflared"] = True

        # Check cloudflared version
        cloudflared_path = get_cloudflared_path()
        try:
            result = subprocess.run(
                [cloudflared_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                version = result.stdout.split("\n")[0] if result.stdout else "unknown"
                print(f"    Version: {version}")
        except Exception:
            pass
    else:
        print("  ✗ Cloudflared process not running")
        print("  → Run: robotmcp-server start")
        print("\n" + "=" * 70)
        return

    # ========== 4. Tunnel Authentication & Status ==========
    print("\n[4] Tunnel Authentication & Status")
    print("-" * 70)
    logs = get_cloudflared_logs(100)
    auth_ok = False
    connections = 0

    for line in logs:
        if "Settings: map[token:" in line:
            print("  ✓ Token loaded by cloudflared")
            auth_ok = True
        if "Registered tunnel connection" in line:
            connections += 1
            import re

            match = re.search(r"connection=([a-f0-9-]+)", line)
            if match:
                conn_id = match.group(1)[:8]
                print(f"  ✓ Tunnel connection registered: {conn_id}...")
        if "Updated to new configuration" in line:
            import json
            import re

            json_match = re.search(r'config="({[^"]+})"', line)
            if json_match:
                try:
                    config_json = json_match.group(1).replace('\\"', '"')
                    config_data = json.loads(config_json)
                    if "ingress" in config_data:
                        print("  ✓ Configuration received from Cloudflare")
                        for rule in config_data["ingress"]:
                            h = rule.get("hostname", "*")
                            s = rule.get("service", "unknown")
                            if h != "*":
                                print(f"    Rule: {h} → {s}")
                except Exception:
                    pass
        if "ERR" in line and any(
            x in line.lower()
            for x in ["auth", "unauthorized", "forbidden", "401", "403"]
        ):
            print("  ✗ Authentication error in logs")
            print(f"    {line.strip()[:80]}")
            auth_ok = False

    if auth_ok and connections > 0:
        print("  ✓ Authentication: SUCCESS")
        print(f"  ✓ Active connections: {connections}")
        results["tunnel_auth"] = True
    else:
        print("  ⚠ Authentication status unclear")
        if not auth_ok:
            print("    → Check cloudflared logs for errors")

    # ========== 5. DNS Resolution ==========
    print("\n[5] DNS Resolution")
    print("-" * 70)
    if hostname:
        try:
            import socket

            ip_addresses = socket.gethostbyname_ex(hostname)
            print(f"  ✓ DNS record exists for {hostname}")
            print(f"    Resolves to: {', '.join(ip_addresses[2][:3])}")

            # Check if Cloudflare IPs
            cf_ips = [
                ip
                for ip in ip_addresses[2]
                if any(ip.startswith(p) for p in ["104.", "172.", "198.", "173."])
            ]
            if cf_ips:
                print("    → Cloudflare IP detected ✓")
            else:
                print("    ⚠ IPs don't look like Cloudflare")

            results["dns"] = True
        except socket.gaierror as e:
            print(f"  ✗ DNS resolution failed: {e}")
            print(f"    Domain: {hostname}")
            print("    → DNS record missing! Add CNAME in Cloudflare:")
            print(f"       Name: {config.robot_name}")
            print("       Target: <tunnel-id>.cfargotunnel.com")
            print("       Proxy: Proxied (orange cloud) ✓")
            results["dns"] = False
        except Exception as e:
            print(f"  ✗ DNS check error: {e}")
            results["dns"] = False
    else:
        print("  ✗ Invalid tunnel URL")
        results["dns"] = False

    # ========== 6. Tunnel Endpoint Tests ==========
    print("\n[6] Tunnel Endpoint Tests")
    print("-" * 70)
    if not results["dns"]:
        print("  ⚠ Skipping tunnel tests (DNS not configured)")
        print("    → Fix DNS first, then re-run verify")
    else:
        endpoints = [
            ("/", "Root endpoint"),
            ("/health", "Health check"),
        ]

        all_endpoints_ok = True
        for endpoint, description in endpoints:
            url = f"{tunnel_url}{endpoint}"
            try:
                response = requests.get(url, timeout=15, allow_redirects=True)
                if response.status_code == 200:
                    print(
                        f"  ✓ {endpoint:15} {description:20} HTTP {response.status_code}"
                    )
                else:
                    print(
                        f"  ⚠ {endpoint:15} {description:20} HTTP {response.status_code}"
                    )
                    if response.status_code in [502, 503]:
                        print("      → Cloudflared can't reach localhost:8766")
                    all_endpoints_ok = False
            except requests.exceptions.Timeout:
                print(f"  ✗ {endpoint:15} {description:20} Timeout (15s)")
                all_endpoints_ok = False
            except requests.exceptions.ConnectionError as e:
                error_msg = str(e)
                print(f"  ✗ {endpoint:15} {description:20} Connection failed")
                if "Name or service not known" in error_msg or "nodename" in error_msg:
                    print("      → DNS resolution issue")
                elif "Connection refused" in error_msg:
                    print("      → Tunnel not accepting connections")
                elif "Max retries" in error_msg:
                    print("      → Cannot reach tunnel endpoint")
                all_endpoints_ok = False
            except requests.exceptions.SSLError as e:
                print(f"  ✗ {endpoint:15} {description:20} SSL Error")
                print(f"      → {str(e)[:60]}")
                all_endpoints_ok = False
            except Exception as e:
                print(f"  ✗ {endpoint:15} {description:20} Error: {str(e)[:50]}")
                all_endpoints_ok = False

        results["tunnel_endpoints"] = all_endpoints_ok

    # ========== Summary ==========
    print("\n" + "=" * 70)
    print("  Verification Summary")
    print("=" * 70)

    total_checks = len(results)
    passed_checks = sum(1 for v in results.values() if v)

    print(f"\n  Checks passed: {passed_checks}/{total_checks}")
    print("\n  Status:")
    print(f"    [1] Configuration:        {'✓' if results['config'] else '✗'}")
    print(f"    [2] Local Server:         {'✓' if results['server_local'] else '✗'}")
    print(f"    [3] Cloudflared Process:  {'✓' if results['cloudflared'] else '✗'}")
    print(f"    [4] Tunnel Authentication: {'✓' if results['tunnel_auth'] else '✗'}")
    print(f"    [5] DNS Resolution:       {'✓' if results['dns'] else '✗'}")
    print(
        f"    [6] Tunnel Endpoints:     {'✓' if results['tunnel_endpoints'] else '✗'}"
    )

    if all(results.values()):
        print("\n  ✓ All checks passed! Your MCP server is fully operational.")
        print("\n  Access your server at:")
        print(f"    {tunnel_url}/mcp")
        print(f"    {tunnel_url}/sse")
    else:
        print("\n  ⚠ Some checks failed. See details above.")
        print("\n  Next steps:")
        if not results["dns"]:
            print("    1. Add DNS CNAME record in Cloudflare dashboard")
            print("       → Go to: https://dash.cloudflare.com")
            print("       → Domain: robotmcp.ai → DNS → Records")
            print(
                f"       → Add: {config.robot_name} CNAME → <tunnel-id>.cfargotunnel.com"
            )
        if not results["tunnel_endpoints"] and results["dns"]:
            print(
                "    1. Check cloudflared logs: tail -f ~/.robotmcp-server/cloudflared.log"
            )
            print("    2. Verify server is running: curl http://localhost:8766/health")
        if not results["server_local"]:
            print("    1. Start server: robotmcp-server start")
        print("    2. Re-run verification: robotmcp-server verify")

    print("=" * 70 + "\n")


def cmd_logout():
    """Log out and clear credentials."""
    config = load_config()

    if not config.is_valid():
        print("Not logged in.")
        return

    email = config.email

    # Stop server first
    print("Stopping server...")
    kill_processes_on_port(8766)
    kill_cloudflared_processes()

    # Clear config
    clear_config()
    print(f"\nLogged out: {email}")
    print(f"Config removed: {CONFIG_FILE}")


def cmd_version():
    """Show version information."""
    print(f"robotmcp-server v{VERSION}")
    print("Copyright (c) 2025 Contoro. All rights reserved.")


def cmd_add(repo_url: str, branch: str | None = None):
    """Add a git submodule (MCP tool package).

    Args:
        repo_url: Git repository URL to add as submodule
        branch: Optional branch to track
    """
    # Extract submodule name from repo URL
    # e.g., https://github.com/example/mcp-tools.git -> mcp-tools
    repo_name = repo_url.rstrip("/").rstrip(".git").split("/")[-1]

    # Get the directory where this script is located (package root)
    package_dir = Path(__file__).parent.resolve()

    # Check if already exists
    submodule_path = package_dir / repo_name
    if submodule_path.exists():
        print(f"[ERROR] Directory already exists: {submodule_path}")
        print(f"  Remove it first: rm -rf {submodule_path}")
        sys.exit(1)

    # Build git submodule add command
    cmd = ["git", "submodule", "add"]
    if branch:
        cmd.extend(["-b", branch])
    cmd.append(repo_url)
    cmd.append(repo_name)

    print(f"Adding submodule: {repo_name}")
    if branch:
        print(f"  Branch: {branch}")
    print(f"  URL: {repo_url}")
    print(f"  Path: {submodule_path}")
    print()

    try:
        result = subprocess.run(
            cmd,
            cwd=package_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print("[ERROR] Failed to add submodule:")
            if result.stderr:
                print(f"  {result.stderr.strip()}")
            sys.exit(1)

        print("Submodule added successfully!")
        print()

        # Initialize and update the submodule
        print("Initializing submodule...")
        subprocess.run(
            ["git", "submodule", "update", "--init", "--recursive", repo_name],
            cwd=package_dir,
            check=True,
        )

        # Check if submodule has pyproject.toml (indicates it's a Python package)
        pyproject = submodule_path / "pyproject.toml"
        if pyproject.exists():
            print()
            print(f"[INFO] Found pyproject.toml in {repo_name}")
            print("  Dependencies will be auto-installed on next 'robotmcp-server start'")
            print(f"  Or install manually: pip install -e {submodule_path}")
        else:
            print()
            print(f"[WARNING] No pyproject.toml found in {repo_name}")
            print("  This submodule may not be a valid MCP tool package")

        print()
        print("Next steps:")
        print("  1. Commit the changes: git add .gitmodules && git commit -m 'Add submodule'")
        print("  2. Restart the server: robotmcp-server restart")

    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Command failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        sys.exit(1)


def cmd_help():
    """Show detailed help."""
    print("""
RobotMCP Server - Local MCP server with OAuth
Copyright (c) 2025 Contoro. All rights reserved.

USAGE:
    robotmcp-server <command>

COMMANDS:
    start       Start the MCP server in background
    stop        Stop the running server and tunnel
    restart     Restart the server
    status      Show current status and configuration
    verify      Test tunnel connectivity and endpoints
    login       Log in to RobotMCP (browser OAuth)
    logout      Log out and clear stored credentials
    add         Add a git submodule (MCP tool package)
    version     Show version information
    help        Show this help message

EXAMPLES:
    # Start server (runs in background)
    robotmcp-server start

    # Check server status
    robotmcp-server status

    # Stop the server
    robotmcp-server stop

    # Add a submodule with specific branch
    robotmcp-server add -b main https://github.com/example/mcp-tools.git

    # View logs
    tail -f ~/.robotmcp-server/server.log

QUICK START:
    1. Run 'robotmcp-server start' (or 'login' to login without starting)
    2. Log in via browser (opens automatically)
    3. Select existing server or enter a new robot name (e.g., 'myrobot')
    4. Server starts in background at https://myrobot.robotmcp.ai
    5. Copy the MCP URL to ChatGPT/Claude (use SSE URL if MCP doesn't work)

For more information, see: https://github.com/robotmcp/robotmcp_server
""")


# ============== Main Entry Point ==============


def main():
    """Main entry point for CLI."""
    # Internal command for Windows daemon subprocess
    if len(sys.argv) > 1 and sys.argv[1] == "_daemon":
        config = load_config()
        if config.is_valid() and config.has_tunnel():
            _run_server(config)
        return

    parser = argparse.ArgumentParser(
        prog="robotmcp-server",
        description="RobotMCP Server - Local MCP server with OAuth",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  robotmcp-server start
  robotmcp-server status
  robotmcp-server stop
  robotmcp-server add -b main https://github.com/example/mcp-tools.git
""",
    )

    # Legacy flags for backward compatibility
    parser.add_argument("--status", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--stop", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--logout", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--version", "-v", action="store_true", help=argparse.SUPPRESS)

    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Simple commands (no additional arguments)
    subparsers.add_parser("start", help="Start the MCP server in background")
    subparsers.add_parser("stop", help="Stop the running server and tunnel")
    subparsers.add_parser("restart", help="Restart the server")
    subparsers.add_parser("status", help="Show current status and configuration")
    subparsers.add_parser("verify", help="Test tunnel connectivity and endpoints")
    subparsers.add_parser("login", help="Log in to RobotMCP (browser OAuth)")
    subparsers.add_parser("logout", help="Log out and clear stored credentials")
    subparsers.add_parser("version", help="Show version information")
    subparsers.add_parser("help", help="Show detailed help message")

    # Add command with arguments
    add_parser = subparsers.add_parser(
        "add",
        help="Add a git submodule (MCP tool package)",
        description="Add a git submodule to extend the server with additional MCP tools.",
    )
    add_parser.add_argument(
        "-b", "--branch",
        metavar="BRANCH",
        help="Branch to track (e.g., main, develop)",
    )
    add_parser.add_argument(
        "repo_url",
        metavar="REPO_URL",
        help="Git repository URL (e.g., https://github.com/example/mcp-tools.git)",
    )

    args = parser.parse_args()

    # Handle legacy flags
    if args.status:
        cmd_status()
    elif args.stop:
        cmd_stop()
    elif args.logout:
        cmd_logout()
    elif args.version:
        cmd_version()
    # Handle commands
    elif args.command == "start":
        cmd_start()
    elif args.command == "stop":
        cmd_stop()
    elif args.command == "restart":
        cmd_restart()
    elif args.command == "status":
        cmd_status()
    elif args.command == "login":
        cmd_login()
    elif args.command == "logout":
        cmd_logout()
    elif args.command == "verify":
        cmd_verify()
    elif args.command == "version":
        cmd_version()
    elif args.command == "help":
        cmd_help()
    elif args.command == "add":
        cmd_add(args.repo_url, args.branch)
    elif args.command is None:
        # Default to start if no command given
        cmd_start()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
