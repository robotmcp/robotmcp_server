"""Setup flow for robotmcp-server (browser-based login)."""

import os
import re
import secrets
import socket
import subprocess
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import requests

from config import save_config, update_config_tunnel


# Cloud service URL (configurable via environment variable)
SERVER_URL = os.getenv("ROBOTMCP_CLOUD_URL", "https://app.robotmcp.ai")


def is_wsl() -> bool:
    """Check if running inside WSL."""
    # Check for WSL-specific indicators
    if os.path.exists("/proc/version"):
        try:
            with open("/proc/version", "r") as f:
                version = f.read().lower()
                if "microsoft" in version or "wsl" in version:
                    return True
        except Exception:
            pass
    # Also check WSL_DISTRO_NAME environment variable
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    return False


def open_browser(url: str) -> None:
    """Open URL in browser, handling WSL gracefully."""
    if is_wsl():
        # In WSL, use PowerShell Start-Process which handles URLs with & correctly
        try:
            # PowerShell properly handles URLs with special characters
            result = subprocess.run(
                ["powershell.exe", "-Command", f'Start-Process "{url}"'],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fallback: try wslview (from wslu package)
        try:
            result = subprocess.run(["wslview", url], capture_output=True, timeout=5)
            if result.returncode == 0:
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Last resort: cmd.exe with quoted URL
        try:
            subprocess.run(
                ["cmd.exe", "/c", "start", "", url], capture_output=True, timeout=5
            )
            return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Default: use webbrowser module (suppress stderr for gio errors)
    import os
    import sys

    # Suppress stderr temporarily to hide gio errors
    old_stderr = sys.stderr
    try:
        sys.stderr = open(os.devnull, "w")
        webbrowser.open(url)
    finally:
        sys.stderr.close()
        sys.stderr = old_stderr


def get_wsl_ip() -> str:
    """Get WSL's own IP address that Windows can reach.

    In WSL2, Windows can reach WSL via the IP shown by 'hostname -I'.
    This is the eth0 IP address that's on the virtual network between
    Windows and WSL2.
    """
    # Get WSL's own IP via hostname -I
    try:
        result = subprocess.run(["hostname", "-I"], capture_output=True, text=True)
        if result.returncode == 0:
            ips = result.stdout.strip().split()
            if ips:
                return ips[0]
    except Exception:
        pass

    # Fallback: try ip addr to get eth0 IP
    try:
        result = subprocess.run(
            ["ip", "addr", "show", "eth0"], capture_output=True, text=True
        )
        if result.returncode == 0:
            import re

            match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", result.stdout)
            if match:
                return match.group(1)
    except Exception:
        pass

    return ""


class CallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback from browser."""

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def _handle_callback(self, params: dict):
        """Process callback parameters (shared by GET and POST)."""
        # Extract tokens and user info from callback
        user_id = params.get("user_id", [None])[0]
        email = params.get("email", [None])[0]
        access_token = params.get("access_token", [None])[0]
        refresh_token = params.get("refresh_token", [None])[0]
        name = params.get("name", [None])[0]
        organization = params.get("organization", [None])[0]
        error = params.get("error", [None])[0]

        if error:
            self.server.login_error = error
            self._send_response("Login failed. You can close this window.")
        elif user_id and email and access_token:
            self.server.login_result = {
                "user_id": user_id,
                "email": email,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "name": name,
                "organization": organization,
            }
            self._send_response("Login successful! You can close this window.")
        else:
            self.server.login_error = "Missing credentials"
            self._send_response("Login failed. Missing credentials.")

        # Signal to stop server
        self.server.should_stop = True

    def do_GET(self):
        """Handle callback GET request (legacy support)."""
        parsed = urlparse(self.path)

        if parsed.path == "/callback":
            params = parse_qs(parsed.query)
            self._handle_callback(params)
        else:
            self.send_error(404)

    def do_POST(self):
        """Handle callback POST request (secure - credentials in body, not URL)."""
        parsed = urlparse(self.path)

        if parsed.path == "/callback":
            # Read POST body
            content_length = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_length).decode("utf-8")
            params = parse_qs(post_body)
            self._handle_callback(params)
        else:
            self.send_error(404)

    def _send_response(self, message: str):
        """Send HTML response."""
        html = f"""<!DOCTYPE html>
<html>
<head><title>Login</title>
<style>
body {{ font-family: sans-serif; display: flex; justify-content: center;
       align-items: center; height: 100vh; margin: 0; background: #f5f5f5; }}
.box {{ background: white; padding: 40px; border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; }}
</style>
</head>
<body><div class="box"><h2>{message}</h2></div></body>
</html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())


def find_free_port() -> int:
    """Find an available port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def validate_robot_name(name: str) -> tuple[bool, str]:
    """Validate robot name format locally.

    Returns (is_valid, error_message).
    """
    if not name:
        return False, "Robot name is required"
    if len(name) < 3:
        return False, "Robot name must be at least 3 characters"
    if len(name) > 32:
        return False, "Robot name must be at most 32 characters"
    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
        return False, "Use only lowercase letters, numbers, and hyphens"
    return True, ""


def prompt_robot_name() -> str:
    """Prompt user for robot name with validation."""
    print("\n--- Robot Setup ---")
    print("Enter a unique name for your robot/device.")
    print("This will create: {name}.robotmcp.ai")
    print("Rules: lowercase letters, numbers, hyphens (3-32 chars)\n")

    while True:
        name = input("Robot name: ").strip().lower()
        is_valid, error = validate_robot_name(name)
        if is_valid:
            return name
        print(f"  [X] {error}")
        print()


def fetch_servers(access_token: str) -> dict:
    """Fetch user's existing servers from cloud.

    Returns dict with:
        - success: bool
        - owned: list of owned servers
        - shared: list of shared servers
        - error: error message on failure
    """
    try:
        response = requests.get(
            f"{SERVER_URL}/servers", params={"access_token": access_token}, timeout=30
        )
        return response.json()
    except requests.RequestException as e:
        return {"success": False, "error": f"Network error: {e}"}
    except Exception as e:
        return {"success": False, "error": f"Error: {e}"}


def select_server(owned: list, shared: list) -> dict | None:
    """Display server selection menu.

    Returns:
        - Selected server dict if user chooses existing
        - None if user wants to create new server
    """
    all_servers = []

    if owned:
        print("\n--- Your Servers ---")
        for i, server in enumerate(owned):
            all_servers.append(server)
            status = "active" if server.get("is_active", True) else "inactive"
            print(
                f"  [{len(all_servers)}] {server['robot_name']}.robotmcp.ai ({status})"
            )

    if shared:
        print("\n--- Shared With You ---")
        for i, server in enumerate(shared):
            all_servers.append(server)
            print(f"  [{len(all_servers)}] {server['robot_name']}.robotmcp.ai")

    print("\n  [0] Create a new server")
    print()

    while True:
        try:
            choice = input("Select server (0 for new): ").strip()
            if not choice:
                continue
            num = int(choice)
            if num == 0:
                return None  # Create new
            if 1 <= num <= len(all_servers):
                return all_servers[num - 1]
            print(f"  Please enter 0-{len(all_servers)}")
        except ValueError:
            print("  Please enter a number")


def create_tunnel(
    robot_name: str, user_id: str, access_token: str, force: bool = False
) -> dict:
    """Call cloud API to create Cloudflare tunnel.

    Args:
        robot_name: Unique name for the robot
        user_id: User's Supabase ID
        access_token: User's access token
        force: If True and tunnel exists for same user, return existing tunnel

    Returns dict with:
        - success: bool
        - tunnel_token, tunnel_url: on success
        - error: error message on failure
        - owned_by_user: True if tunnel exists and is owned by this user
    """
    try:
        response = requests.post(
            f"{SERVER_URL}/create-tunnel",
            data={
                "robot_name": robot_name,
                "user_id": user_id,
                "access_token": access_token,
                "force": "true" if force else "false",
            },
            timeout=60,
        )
        return response.json()
    except requests.RequestException as e:
        return {"success": False, "error": f"Network error: {e}"}
    except Exception as e:
        return {"success": False, "error": f"Error: {e}"}


def run_login_flow() -> bool:
    """Run browser-based login flow.

    Returns True if login successful, False otherwise.
    """
    print("\nNo configuration found. Starting setup...\n")

    # Generate session ID and find free port
    session_id = secrets.token_urlsafe(32)
    port = find_free_port()

    # Detect WSL and determine callback host
    running_in_wsl = is_wsl()
    if running_in_wsl:
        wsl_ip = get_wsl_ip()
        # Use WSL's own IP for the callback (Windows browser -> WSL)
        callback_host = wsl_ip if wsl_ip else "localhost"
    else:
        callback_host = "127.0.0.1"

    # Build login URL with the appropriate callback host
    login_url = (
        f"{SERVER_URL}/cli-login?session={session_id}&port={port}&host={callback_host}"
    )

    print("Opening browser for login...")
    print(f"If browser doesn't open, visit:\n  {login_url}\n")

    # Open browser (handles WSL gracefully)
    open_browser(login_url)

    # Start local callback server
    # Bind to 0.0.0.0 to accept connections from any interface (needed for WSL2)
    server = HTTPServer(("0.0.0.0", port), CallbackHandler)
    server.login_result = None
    server.login_error = None
    server.should_stop = False
    server.timeout = 1  # Check every second

    print("Waiting for login callback...", end="", flush=True)

    # Wait for callback (timeout after 5 minutes)
    max_wait = 300
    waited = 0
    while not server.should_stop and waited < max_wait:
        server.handle_request()
        waited += 1

    print()

    if server.login_error:
        print(f"\n[X] Login failed: {server.login_error}")
        return False

    if server.login_result:
        result = server.login_result
        save_config(
            user_id=result["user_id"],
            email=result["email"],
            access_token=result["access_token"],
            refresh_token=result.get("refresh_token"),
        )
        print(f"\n[OK] Logged in as: {result['email']}")
        print("  Config saved to: ~/.robotmcp-server/config.json")

        # Fetch existing servers
        print("\nChecking for existing servers...")
        servers_result = fetch_servers(result["access_token"])

        if servers_result.get("success"):
            owned = servers_result.get("owned", [])
            shared = servers_result.get("shared", [])

            if owned or shared:
                # User has existing servers - offer selection
                selected = select_server(owned, shared)

                if selected:
                    # Use existing server
                    update_config_tunnel(
                        robot_name=selected["robot_name"],
                        tunnel_token=selected["tunnel_token"],
                        tunnel_url=selected["tunnel_url"],
                    )
                    print(f"\n[OK] Selected server: {selected['tunnel_url']}")
                    print("  Tunnel token saved to config.\n")
                    return True
                # else: user wants to create new server, continue below
            else:
                print("  No existing servers found.")
        else:
            # Failed to fetch servers - continue with new server flow
            print(
                f"  Could not fetch servers: {servers_result.get('error', 'Unknown error')}"
            )

        print()  # Spacing before robot name prompt

        # Prompt for robot name and create tunnel (retry on name conflict)
        while True:
            robot_name = prompt_robot_name()
            print(f"\nCreating tunnel for {robot_name}.robotmcp.ai...")

            tunnel_result = create_tunnel(
                robot_name=robot_name,
                user_id=result["user_id"],
                access_token=result["access_token"],
            )

            if tunnel_result.get("success"):
                update_config_tunnel(
                    robot_name=robot_name,
                    tunnel_token=tunnel_result["tunnel_token"],
                    tunnel_url=tunnel_result["tunnel_url"],
                )
                print(f"[OK] Tunnel created: {tunnel_result['tunnel_url']}")
                print("  Tunnel token saved to config.\n")
                return True
            else:
                error = tunnel_result.get("error", "Unknown error")
                print(f"[X] Tunnel creation failed: {error}")

                # Check if name is taken
                if (
                    "already taken" in error.lower()
                    or "already exists" in error.lower()
                ):
                    # Check if owned by same user - offer to reuse
                    if tunnel_result.get("owned_by_user"):
                        print(
                            f"\n  You already own the tunnel '{robot_name}.robotmcp.ai'."
                        )
                        reuse = input("  Reuse this tunnel? (y/n): ").strip().lower()
                        if reuse == "y":
                            print(f"\nReusing tunnel {robot_name}.robotmcp.ai...")
                            # Retry with force=True to get existing tunnel
                            tunnel_result = create_tunnel(
                                robot_name=robot_name,
                                user_id=result["user_id"],
                                access_token=result["access_token"],
                                force=True,
                            )
                            if tunnel_result.get("success"):
                                update_config_tunnel(
                                    robot_name=robot_name,
                                    tunnel_token=tunnel_result["tunnel_token"],
                                    tunnel_url=tunnel_result["tunnel_url"],
                                )
                                print(
                                    f"[OK] Tunnel reused: {tunnel_result['tunnel_url']}"
                                )
                                print("  Tunnel token saved to config.\n")
                                return True
                            else:
                                print(
                                    f"[X] Failed to reuse tunnel: {tunnel_result.get('error')}"
                                )
                                print("  Please try a different name.\n")
                                continue
                        else:
                            print("  Please choose a different name.\n")
                            continue
                    else:
                        # Taken by another user
                        print("  Please choose a different name.\n")
                        continue
                else:
                    # Other error - don't retry
                    print("  You can retry by running: robotmcp-server")
                    return False

    print("\n[X] Login timed out. Please try again.")
    return False
