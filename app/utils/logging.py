"""
app/utils/logging.py

Centralised logging configuration for Praxis AI.

Call `configure_logging()` once at application startup (in main.py lifespan).
This sets up:
  - A structured, coloured console formatter for development.
  - A plain JSON-like formatter for production (EC2 / CloudWatch friendly).
  - Per-module log level overrides to silence noisy third-party libraries.
  - Request-ID injection: every log record inside an async request context
    automatically includes the X-Request-ID header value.

Usage:
    from app.utils.logging import configure_logging
    configure_logging()
"""

import logging
import logging.config
import os
import sys
import time
import uuid
from contextvars import ContextVar

# ---------------------------------------------------------------------------
# Request-ID context variable — set by RequestLoggingMiddleware per request
# ---------------------------------------------------------------------------

_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id_var.get()


def set_request_id(request_id: str) -> None:
    _request_id_var.set(request_id)


# ---------------------------------------------------------------------------
# Custom formatter — adds request_id, colours in dev, plain text in prod
# ---------------------------------------------------------------------------

_RESET = "\033[0m"
_BOLD = "\033[1m"

_LEVEL_COLOURS = {
    "DEBUG":    "\033[36m",   # cyan
    "INFO":     "\033[32m",   # green
    "WARNING":  "\033[33m",   # yellow
    "ERROR":    "\033[31m",   # red
    "CRITICAL": "\033[35m",   # magenta
}


class PraxisFormatter(logging.Formatter):
    """
    Single formatter that switches between coloured (dev) and plain (prod) output.
    Always includes: timestamp | level | request_id | logger_name | message
    """

    def __init__(self, use_colour: bool = True):
        super().__init__()
        self.use_colour = use_colour

    def format(self, record: logging.LogRecord) -> str:
        # Inject request_id from context var
        record.request_id = _request_id_var.get()

        ts = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        level = record.levelname
        name = record.name
        msg = record.getMessage()

        # Format exception if present
        exc_text = ""
        if record.exc_info:
            exc_text = "\n" + self.formatException(record.exc_info)

        if self.use_colour:
            colour = _LEVEL_COLOURS.get(level, "")
            level_str = f"{colour}{_BOLD}{level:<8}{_RESET}"
            rid = f"\033[90m[{record.request_id}]{_RESET}"
            name_str = f"\033[90m{name}{_RESET}"
            return f"{ts} {level_str} {rid} {name_str}: {msg}{exc_text}"
        else:
            return f"{ts} {level:<8} [{record.request_id}] {name}: {msg}{exc_text}"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def configure_logging(log_level: str | None = None) -> None:
    """
    Configure logging for the entire application.

    Reads LOG_LEVEL from environment (default: INFO).
    Auto-detects whether to use colour output based on TTY / NO_COLOR env var.
    """
    level_name = (log_level or os.getenv("LOG_LEVEL", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    # Colour: on when stdout is a TTY and NO_COLOR is not set
    use_colour = sys.stdout.isatty() and not os.getenv("NO_COLOR")

    formatter = PraxisFormatter(use_colour=use_colour)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Root logger
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # ── Per-library level overrides ──────────────────────────────────
    # Silence extremely verbose third-party modules; set WARNING unless debug
    noisy_libs = [
        "httpx", "httpcore", "openai", "langchain",
        "langchain_core", "langchain_openai", "langgraph",
        "qdrant_client", "asyncpg", "uvicorn.access",
        "fastembed", "llama_parse",
    ]
    for lib in noisy_libs:
        logging.getLogger(lib).setLevel(
            logging.DEBUG if level <= logging.DEBUG else logging.WARNING
        )

    # Keep uvicorn error log at ERROR level always
    logging.getLogger("uvicorn.error").setLevel(logging.ERROR)

    # Our own namespaces — honour the configured level
    for ns in ("app", "agents", "prompts"):
        logging.getLogger(ns).setLevel(level)

    logging.getLogger(__name__).info(
        "[logging] Configured: level=%s colour=%s", level_name, use_colour
    )
