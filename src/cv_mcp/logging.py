from __future__ import annotations

import logging as _logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Send cv_mcp logs to stderr (stdout belongs to the stdio MCP transport)."""
    level = level.upper()
    root_logger = _logging.getLogger("cv_mcp")
    # Idempotent: if handlers already exist, do not add another
    if root_logger.handlers:
        return

    handler = _logging.StreamHandler(sys.stderr)
    formatter = _logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(_logging.getLevelNamesMapping().get(level, _logging.INFO))

    # Quiet httpx and httpcore unless DEBUG
    if level.upper() != "DEBUG":
        for name in ("httpx", "httpcore"):
            lib_logger = _logging.getLogger(name)
            lib_logger.setLevel(_logging.WARNING)
