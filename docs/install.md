# Installation Guide

**Copyright (c) 2025 Contoro. All rights reserved.**

This guide covers installing and using robotmcp-server (v1.8.0) on your local machine.

> **Note:** CLI login and tunnel creation are handled by the cloud service at `https://app.robotmcp.ai`.

---

## Quick Install (Recommended)

### Option 1: Direct install via pipx

```bash
pipx install git+https://github.com/robotmcp/robotmcp_server.git
```

Submodules (MCP tool packages) are automatically downloaded on first run.

### Option 2: Clone with submodules

```bash
git clone --recursive https://github.com/robotmcp/robotmcp_server.git
pipx install ./robotmcp_server
```

This downloads submodules upfront during clone.

### Run

```bash
robotmcp-server
```

On first run:
- Browser opens for login/signup
- You'll be prompted for a robot name
- Cloudflared auto-downloads if not found
- Server starts at `https://yourname.robotmcp.ai`

### Update

```bash
pipx uninstall robotmcp-server
pipx install git+https://github.com/robotmcp/robotmcp_server.git
```

### Uninstall

```bash
robotmcp-server stop
pipx uninstall robotmcp-server
rm -rf ~/.robotmcp-server  # Remove config (optional)
```

**Note (WSL users):** The CLI automatically detects WSL and handles callback URLs for Windows browser authentication.

---

## Manual Installation

For development or Windows users, follow these steps.

### Prerequisites

Before installing, ensure you have:

1. **Python 3.10+** - Check with `python --version`
2. **Git** - For cloning the repository
3. **cloudflared** - Cloudflare tunnel client (auto-downloads on Linux/macOS, manual install on Windows)

### Installing cloudflared (Windows only, optional for Linux/macOS)

**Windows (winget):**
```powershell
winget install cloudflare.cloudflared
```

**Windows (manual):**
Download from: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/

**macOS (optional - auto-downloads on first run):**
```bash
brew install cloudflared
```

**Linux (optional - auto-downloads on first run):**
```bash
# Debian/Ubuntu (if you prefer system install)
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo apt install ./cloudflared-linux-amd64.deb

# Or direct binary (no sudo needed)
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o ~/.local/bin/cloudflared
chmod +x ~/.local/bin/cloudflared
```

Verify installation:
```bash
cloudflared --version
```

---

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/robotmcp/robotmcp_server.git
cd robotmcp_server
```

### Step 2: Create Virtual Environment

**Windows:**
```powershell
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your Supabase credentials:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_JWT_SECRET=your-jwt-secret
```

---

## First Run

Start the server for the first time:

```bash
python cli.py
```

This will:
1. **Open browser** for login/signup via Supabase
2. **Prompt for robot name** (e.g., `myrobot` becomes `myrobot.robotmcp.ai`)
3. **Create Cloudflare tunnel** automatically
4. **Save configuration** to `~/.robotmcp-server/config.json`
5. **Start the MCP server** in background (daemon mode)

You'll see a startup banner like this:
```
==================================================
  RobotMCP Server
==================================================
  User:   you@example.com
  SSE:    https://myrobot.robotmcp.ai/sse
==================================================
  Copy the SSE URL above to your MCP client
  (ChatGPT, Claude, etc.)

  Server running in background.
  Run 'robotmcp-server stop' to stop.
==================================================
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `robotmcp-server` | Start server in background (default) |
| `robotmcp-server start` | Start server in background |
| `robotmcp-server stop` | Stop server and tunnel |
| `robotmcp-server restart` | Restart the server |
| `robotmcp-server status` | Show current status (PID, log file) |
| `robotmcp-server logout` | Clear credentials and stop |
| `robotmcp-server version` | Show version info |
| `robotmcp-server help` | Show detailed help |

**Note:** The server runs as a background daemon. Logs are written to `~/.robotmcp-server/server.log`.

### Legacy Flag Support

For backward compatibility, these flags also work:
```bash
python cli.py --status
python cli.py --stop
python cli.py --logout
python cli.py --version
```

---

## Connecting MCP Clients

### ChatGPT

1. Go to **Settings > Connectors > Add**
2. Enter MCP Server URL: `https://your-robot.robotmcp.ai/mcp`
3. Select **OAuth** authentication
4. Log in with your Supabase account

### Claude.ai

1. Add as an MCP integration
2. Use endpoint: `https://your-robot.robotmcp.ai/mcp`
3. Complete OAuth flow when prompted
4. Log in with your Supabase account

**Important:** Only the server creator can connect. Other users will receive a `403 Forbidden` error.

> **Legacy Support**: SSE endpoint (`/sse`) is still available for backward compatibility with older MCP clients.

---

## Available MCP Tools

Once connected, you can use these tools:

### echo
Echoes back your message.
```
Input: "Hello, world!"
Output: "Echo: Hello, world!"
```

### ping
Tests connectivity to the server.
```
Output: "pong from owner's MCP server"
```

---

## Configuration

Configuration is stored in `~/.robotmcp-server/config.json`:

```json
{
  "user_id": "uuid",
  "email": "you@example.com",
  "access_token": "...",
  "refresh_token": "...",
  "robot_name": "myrobot",
  "tunnel_url": "https://myrobot.robotmcp.ai",
  "tunnel_token": "..."
}
```

To view your current configuration:
```bash
python cli.py status
```

---

## Troubleshooting

### cloudflared Windows Service Conflict

If cloudflared is installed as a Windows service, it may intercept tunnel traffic:

```powershell
# Check status
python cli.py status

# Stop service (Admin Command Prompt)
net stop cloudflared

# Or permanently uninstall the service
cloudflared service uninstall
```

### Port 8766 Already in Use

The CLI automatically cleans up old processes. If issues persist:

```powershell
# Stop via CLI
python cli.py stop

# Or manually find and kill
netstat -ano | findstr :8766
taskkill /F /PID <pid>
```

### Server Not Accessible via Tunnel

1. Check cloudflared is installed: `cloudflared --version`
2. Check tunnel status: `python cli.py status`
3. Ensure no Windows service conflict (see above)
4. Try restarting: `python cli.py restart`

### OAuth Login Issues

1. Clear credentials: `python cli.py logout`
2. Start fresh: `python cli.py start`
3. Check `.env` file has correct Supabase credentials

### "Access denied: not authorized for this server"

This 403 error means you're trying to connect with a different account than the server creator. Only the user who ran the initial setup can connect via MCP clients.

---

## Updating

### pipx Install

```bash
pipx uninstall robotmcp-server
pipx install git+https://github.com/robotmcp/robotmcp_server.git
```

### Manual Install

```bash
cd robotmcp_server
git pull
pip install -r requirements.txt
robotmcp-server restart
```

---

## Uninstalling

### pipx Install

```bash
robotmcp-server stop
pipx uninstall robotmcp-server
rm -rf ~/.robotmcp-server  # Remove config (optional)
```

### Manual Install

```bash
robotmcp-server stop
robotmcp-server logout
cd ..
rm -rf robotmcp_server
```

---

## API Endpoints

For developers integrating with the server:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Server info |
| `/health` | GET | Health check |
| `/mcp` | POST/GET | Streamable HTTP transport (recommended) |
| `/sse` | GET | Legacy MCP SSE connection (backward compat) |
| `/message` | POST | Legacy MCP message handler (backward compat) |
| `/.well-known/oauth-authorization-server` | GET | OAuth metadata |
| `/.well-known/oauth-protected-resource` | GET | Resource metadata |
| `/register` | POST | Dynamic client registration |
| `/authorize` | GET | OAuth authorization |
| `/token` | POST | OAuth token exchange |

---

## Support

For issues and feature requests, visit:
https://github.com/robotmcp/robotmcp_server/issues
