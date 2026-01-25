"""Centralized logging configuration with Supabase support.

This module provides:
- JSONFormatter for structured logging
- SupabaseHandler for centralized log collection (batched)
- Fallback to stderr-only when Supabase is unavailable
"""

import atexit
import logging
import os
import re
import sys
import threading
import time
from queue import Queue, Empty
from typing import Optional


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def __init__(self, robot_name: str = None, user_id: str = None):
        super().__init__()
        self.robot_name = robot_name or "unknown"
        self.user_id = user_id

    def format(self, record: logging.LogRecord) -> dict:
        # Extract tag from message if present: [TAG] message
        tag = None
        message = record.getMessage()
        tag_match = re.match(r"\[([A-Z_]+)\]\s*(.*)", message)
        if tag_match:
            tag = tag_match.group(1)
            message = tag_match.group(2)

        # Build structured log entry
        log_entry = {
            "robot_name": self.robot_name,
            "user_id": self.user_id,
            "level": record.levelname,
            "tag": tag,
            "message": message,
            "module": record.module,
            "extra": {
                "function": record.funcName,
                "line": record.lineno,
            },
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["extra"]["exception"] = self.formatException(record.exc_info)

        return log_entry


class PlainFormatter(logging.Formatter):
    """Plain text formatter for stderr output (local debugging)."""

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )


class SupabaseFilter(logging.Filter):
    """Filter to only send meaningful logs to Supabase.

    Reduces noise by filtering out:
    - HTTP client logs (recursive from Supabase inserts)
    - MCP internal library logs
    - Repetitive AUTH "Request authorized" logs

    Keeps:
    - Business events with specific tags (TOOL, LOGIN, CONSENT, etc.)
    - WARNING and ERROR level logs
    """

    # Modules to exclude (library noise)
    EXCLUDED_MODULES = {"_client", "server", "streamable_http_manager"}

    # Tags we want to keep (business events)
    ALLOWED_TAGS = {
        "TOOL",
        "LOGIN",
        "CONSENT",
        "REGISTER",
        "TOKEN",
        "AUTHORIZE",
        "STARTUP",
    }

    def filter(self, record: logging.LogRecord) -> bool:
        # Always allow WARNING and above
        if record.levelno >= logging.WARNING:
            return True

        # Exclude noisy modules
        if record.module in self.EXCLUDED_MODULES:
            return False

        # Check for tag in message
        message = record.getMessage()
        tag_match = re.match(r"\[([A-Z_]+)\]", message)
        if tag_match:
            tag = tag_match.group(1)
            # Skip AUTH "Request authorized" (too noisy - logs every request)
            if tag == "AUTH" and "Request authorized" in message:
                return False
            return tag in self.ALLOWED_TAGS

        # No tag = skip (library noise)
        return False


class SupabaseHandler(logging.Handler):
    """Logging handler that batches logs and sends to Supabase.

    Logs are buffered and sent in batches to reduce database writes.
    Flush occurs every flush_interval seconds or when batch_size is reached.
    """

    def __init__(
        self,
        supabase_client,
        robot_name: str,
        user_id: str = None,
        batch_size: int = 20,
        flush_interval: float = 10.0,
    ):
        super().__init__()
        self.supabase = supabase_client
        self.robot_name = robot_name
        self.user_id = user_id
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        self._queue: Queue = Queue()
        self._shutdown = threading.Event()
        self._flush_thread = threading.Thread(target=self._flush_worker, daemon=True)
        self._flush_thread.start()

        # Register cleanup on exit
        atexit.register(self.close)

    def emit(self, record: logging.LogRecord):
        """Queue a log record for batched sending."""
        try:
            # Format the record
            if isinstance(self.formatter, JSONFormatter):
                log_entry = self.formatter.format(record)
            else:
                log_entry = {
                    "robot_name": self.robot_name,
                    "user_id": self.user_id,
                    "level": record.levelname,
                    "tag": None,
                    "message": record.getMessage(),
                    "module": record.module,
                    "extra": {},
                }

            self._queue.put(log_entry)

            # Flush immediately if batch size reached
            if self._queue.qsize() >= self.batch_size:
                self._flush()

        except Exception:
            self.handleError(record)

    def _flush_worker(self):
        """Background thread that flushes logs periodically."""
        while not self._shutdown.is_set():
            time.sleep(self.flush_interval)
            if not self._queue.empty():
                self._flush()

    def _flush(self):
        """Send queued logs to Supabase."""
        logs = []
        try:
            while len(logs) < self.batch_size * 2:  # Don't flush too many at once
                try:
                    logs.append(self._queue.get_nowait())
                except Empty:
                    break

            if logs and self.supabase:
                self.supabase.table("logs").insert(logs).execute()

        except Exception as e:
            # Log to stderr if Supabase fails (avoid recursion)
            print(f"[WARNING] Failed to send logs to Supabase: {e}", file=sys.stderr)

    def close(self):
        """Flush remaining logs and stop the background thread."""
        self._shutdown.set()
        self._flush()  # Final flush
        super().close()


# Global reference to Supabase handler for flushing
_supabase_handler: Optional[SupabaseHandler] = None


def setup_logging(
    robot_name: str = None,
    user_id: str = None,
    supabase_client=None,
) -> logging.Logger:
    """Configure logging with optional Supabase integration.

    Args:
        robot_name: Robot/device name for log identification.
        user_id: User ID for log ownership (from config).
        supabase_client: Supabase client instance for remote logging.

    Returns:
        Configured root logger.

    Behavior:
        - Always adds stderr handler for local debugging
        - Adds Supabase handler if client is provided
        - Graceful fallback if Supabase setup fails
    """
    global _supabase_handler

    robot_name = robot_name or os.getenv("ROBOT_NAME", "unknown")

    # Get root logger and clear existing handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    # Always add stderr handler (plain text for readability)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.INFO)
    stderr_handler.setFormatter(PlainFormatter())
    root_logger.addHandler(stderr_handler)

    # Try to add Supabase handler if client provided
    supabase_enabled = False
    if supabase_client:
        try:
            _supabase_handler = SupabaseHandler(
                supabase_client=supabase_client,
                robot_name=robot_name,
                user_id=user_id,
                batch_size=20,
                flush_interval=10.0,
            )
            _supabase_handler.setLevel(logging.INFO)
            _supabase_handler.setFormatter(JSONFormatter(robot_name, user_id))
            _supabase_handler.addFilter(SupabaseFilter())
            root_logger.addHandler(_supabase_handler)
            supabase_enabled = True
        except Exception as e:
            print(f"[WARNING] Supabase logging setup failed: {e}", file=sys.stderr)

    # Suppress noisy HTTP client logs (Supabase uses httpx)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Log startup info
    logger = logging.getLogger(__name__)
    if supabase_enabled:
        logger.info(f"[STARTUP] Supabase logging enabled for robot: {robot_name}")
    else:
        logger.info("[STARTUP] Supabase logging disabled (no client)")

    return root_logger


def flush_logs():
    """Manually flush any pending logs to Supabase."""
    global _supabase_handler
    if _supabase_handler:
        _supabase_handler._flush()
