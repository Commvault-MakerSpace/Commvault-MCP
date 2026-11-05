"""FastMCP server assembly: lifespan owns the Commvault client, tools are registered per area."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import FastMCP

from cv_mcp import __version__
from cv_mcp.api.client import CommvaultClient
from cv_mcp.api.tokens import build_token_store
from cv_mcp.config import Settings

logger = logging.getLogger("cv_mcp.server")

SERVER_NAME = "cv-mcp"
SERVER_INSTRUCTIONS = (
    "Query a Commvault CommCell through the Command Center REST API: jobs, clients, storage, plans, "
    "schedules, users and security posture. Times are epoch seconds and sizes are bytes unless a tool "
    "says otherwise. Tools that change state are only present when the server was started with writes "
    "enabled."
)


def build_client(settings: Settings) -> CommvaultClient:
    """Create a CommvaultClient from settings. Raises TokenError when no tokens are configured."""
    store = build_token_store(
        access_token=settings.access_token,
        refresh_token=settings.refresh_token,
        token_file=settings.token_file,
    )
    return CommvaultClient(
        server_url=settings.server_url,
        token_store=store,
        ssl_verify=settings.verify,
        local_address=settings.local_address,
        timeout=settings.timeout,
        user_agent=f"cv-mcp/{__version__}",
    )


def create_server(settings: Settings) -> FastMCP:
    @asynccontextmanager
    async def lifespan(_server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        client = build_client(settings)
        logger.info(
            "Connected client for %s (writes %s)",
            settings.server_url,
            "on" if settings.allow_writes else "off",
        )
        try:
            yield {"client": client, "settings": settings}
        finally:
            await client.aclose()

    mcp = FastMCP(name=SERVER_NAME, instructions=SERVER_INSTRUCTIONS, version=__version__, lifespan=lifespan)
    register_tools(mcp, settings)
    return mcp


def register_tools(mcp: FastMCP, settings: Settings) -> None:
    """Register read tools always and write tools only when allowed. Filled in per phase 2/3."""
    from cv_mcp.tools import READ_TOOLS, WRITE_TOOLS

    count = 0
    for fn in READ_TOOLS:
        mcp.tool(fn)
        count += 1
    if settings.allow_writes:
        for fn in WRITE_TOOLS:
            mcp.tool(fn)
            count += 1
    logger.info("Registered %d tools", count)
