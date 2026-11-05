"""Shared fixtures: an in-process MCP client over the real server with HTTP mocked by respx."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import pytest
import respx
from fastmcp import Client

from cv_mcp.config import Settings
from cv_mcp.server import create_server

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://cc.test/commandcenter/api/"


def load_fixture(name: str) -> Any:
    """Recorded CommServe response from tests/fixtures/<name>.json."""
    return json.loads((FIXTURES / f"{name}.json").read_text())


def make_settings(**overrides: Any) -> Settings:
    base = dict(server_url="https://cc.test", access_token="acc", refresh_token="ref", token_file=None)
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def api() -> Iterator[respx.MockRouter]:
    """respx router bound to the Command Center API base; routes are given relative paths."""
    with respx.mock(base_url=BASE, assert_all_called=False) as router:
        yield router


@pytest.fixture
async def mcp(api: respx.MockRouter) -> AsyncIterator[Client]:
    """Connected in-process MCP client with write tools enabled."""
    async with Client(create_server(make_settings(allow_writes=True))) as client:
        yield client


async def call(client: Client, tool: str, **args: Any) -> Any:
    """Call a tool and return its structured result."""
    result = await client.call_tool(tool, args)
    return result.data
