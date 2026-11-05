"""Helpers shared by tool modules: fetch the client from the MCP context and map API errors to ToolError."""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import Context
from fastmcp.exceptions import ToolError

from cv_mcp.api.client import CommvaultClient
from cv_mcp.api.exceptions import CommvaultError

audit = logging.getLogger("cv_mcp.audit")


def client_from(ctx: Context) -> CommvaultClient:
    """Return the shared CommvaultClient created by the server lifespan."""
    return ctx.lifespan_context["client"]


async def api_get(ctx: Context, endpoint: str, *, params: dict[str, Any] | None = None) -> Any:
    """GET an endpoint and convert API failures into ToolError so the model sees a clean message."""
    try:
        return await client_from(ctx).get(endpoint, params=params)
    except CommvaultError as e:
        raise ToolError(str(e)) from e


async def api_post(
    ctx: Context, endpoint: str, *, json: object | None = None, params: dict[str, Any] | None = None
) -> Any:
    """POST to an endpoint and convert API failures into ToolError."""
    try:
        return await client_from(ctx).post(endpoint, json=json, params=params)
    except CommvaultError as e:
        raise ToolError(str(e)) from e


def audit_write(tool: str, **fields: Any) -> None:
    """One log line per state-changing tool call."""
    audit.info("%s %s", tool, " ".join(f"{k}={v}" for k, v in fields.items()))
