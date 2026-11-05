"""Tool registry: each area module exposes READ_TOOLS and WRITE_TOOLS lists of plain async functions."""

from __future__ import annotations

from collections.abc import Callable

from cv_mcp.tools import clients, commcell, jobs

_AREAS = (commcell, jobs, clients)

READ_TOOLS: list[Callable] = [fn for area in _AREAS for fn in area.READ_TOOLS]
WRITE_TOOLS: list[Callable] = [fn for area in _AREAS for fn in area.WRITE_TOOLS]
