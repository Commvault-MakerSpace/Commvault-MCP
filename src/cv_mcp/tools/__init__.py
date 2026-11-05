"""Tool registry. Each area module exposes READ_TOOLS and WRITE_TOOLS lists of plain functions."""

from __future__ import annotations

from collections.abc import Callable

READ_TOOLS: list[Callable] = []
WRITE_TOOLS: list[Callable] = []
