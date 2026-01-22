"""Config management for simple-mcp-server."""

import json
import os
from pathlib import Path
from typing import Optional


CONFIG_DIR = Path.home() / ".simple-mcp-server"
CONFIG_FILE = CONFIG_DIR / "config.json"


class Config:
    """Configuration container."""

    def __init__(self, data: dict = None):
        self.data = data or {}

    @property
    def user_id(self) -> Optional[str]:
        return self.data.get("user_id")

    @property
    def email(self) -> Optional[str]:
        return self.data.get("email")

    @property
    def access_token(self) -> Optional[str]:
        return self.data.get("access_token")

    @property
    def refresh_token(self) -> Optional[str]:
        return self.data.get("refresh_token")

    @property
    def robot_name(self) -> Optional[str]:
        return self.data.get("robot_name")

    @property
    def tunnel_token(self) -> Optional[str]:
        return self.data.get("tunnel_token")

    @property
    def tunnel_url(self) -> Optional[str]:
        return self.data.get("tunnel_url")

    def is_valid(self) -> bool:
        """Check if config has required fields."""
        return bool(self.user_id and self.email and self.access_token)

    def has_tunnel(self) -> bool:
        """Check if tunnel is configured."""
        return bool(self.robot_name and self.tunnel_token)


def load_config() -> Config:
    """Load config from file."""
    if not CONFIG_FILE.exists():
        return Config()

    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
        return Config(data)
    except (json.JSONDecodeError, IOError):
        return Config()


def save_config(
    user_id: str, email: str, access_token: str, refresh_token: str = None
) -> None:
    """Save config to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    data = {
        "user_id": user_id,
        "email": email,
        "access_token": access_token,
        "refresh_token": refresh_token,
    }

    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

    # Set restrictive permissions (owner read/write only)
    os.chmod(CONFIG_FILE, 0o600)


def update_config_tunnel(robot_name: str, tunnel_token: str, tunnel_url: str) -> None:
    """Update existing config with tunnel information."""
    config = load_config()
    if not config.is_valid():
        raise ValueError("Cannot update tunnel: no valid config exists")

    data = config.data.copy()
    data["robot_name"] = robot_name
    data["tunnel_token"] = tunnel_token
    data["tunnel_url"] = tunnel_url

    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

    os.chmod(CONFIG_FILE, 0o600)


def clear_config() -> None:
    """Remove config file."""
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
