# Modified from Commvault/commvault-mcp-server for cv-mcp.
"""Client management tools for the Commvault MCP server."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import Context
from fastmcp.exceptions import ToolError
from pydantic import Field

from cv_mcp.shaping.clients import (
    filter_client_list_response,
    filter_subclient_response,
    get_basic_client_group_details,
)
from cv_mcp.tools._common import api_get, api_post, audit_write


async def get_client_list(
    ctx: Context,
) -> dict[str, Any]:
    """Gets the list of clients. Returns a filtered list of client objects."""
    data = await api_get(ctx, "Client")
    return filter_client_list_response(data)


async def get_client_id(
    ctx: Context,
    client_name: Annotated[str, Field(description="The client name to retrieve client id for.")],
) -> dict[str, Any]:
    """Gets client id for a given client name. Returns the client name and its corresponding ID."""
    try:
        data = await api_get(ctx, "getid", params={"clientname": client_name})
    except ToolError as e:
        if "404" in str(e):
            raise ToolError(f"No client named {client_name!r}") from e
        raise
    if not data.get("clientId"):
        raise ToolError(f"No client named {client_name!r}")
    return {"clientName": client_name, "clientId": data["clientId"]}


async def get_client_group_list(
    ctx: Context,
) -> dict[str, Any]:
    """Gets the list of client groups. Returns basic details for each group."""
    data = await api_get(ctx, "ClientGroup")
    return get_basic_client_group_details(data)


async def get_client_group_properties(
    ctx: Context,
    client_group_id: Annotated[int, Field(description="The client group id to retrieve properties for.")],
) -> dict[str, Any]:
    """Gets properties for a given client group id. Returns raw response data."""
    data = await api_get(ctx, f"ClientGroup/{client_group_id}")
    return data


async def get_subclient_list(
    ctx: Context,
    client_name: Annotated[str, Field(description="The client name to retrieve subclients for.")] = "",
    client_id: Annotated[int | None, Field(description="The client ID to retrieve subclients for.")] = None,
) -> dict[str, Any]:
    """Gets subclient list for a given client name or client id. Returns filtered subclient objects."""
    if not client_name and client_id is None:
        raise ToolError("Either client_name or client_id must be provided.")

    params = {}
    if client_name:
        params["clientName"] = client_name
    if client_id is not None:
        params["clientId"] = client_id

    data = await api_get(ctx, "subclient", params=params)
    return filter_subclient_response(data)


async def get_subclient_properties(
    ctx: Context,
    subclient_id: Annotated[int, Field(description="The subclient id to retrieve properties for.")],
) -> dict[str, Any]:
    """Gets subclient properties for a given subclient id. Returns raw response data."""
    data = await api_get(ctx, f"subclient/{subclient_id}")
    return data


async def run_backup_for_subclient(
    ctx: Context,
    subclient_id: Annotated[int, Field(description="The subclient id to run backup for.")],
    backup_type: Annotated[
        Literal["Full", "Incremental", "Synthetic_Full"],
        Field(
            description="The type of backup to run. Valid values are 'Full', 'Incremental', 'Synthetic_Full'"
        ),
    ] = "Incremental",
) -> dict[str, Any]:
    """SIDE EFFECT: Runs a backup job for the specified subclient with the given backup type. Returns raw response containing the new job id."""
    audit_write("run_backup_for_subclient", subclient_id=subclient_id, backup_type=backup_type)
    data = await api_post(ctx, f"subclient/{subclient_id}/action/backup", params={"backupLevel": backup_type})
    return data


READ_TOOLS = [
    get_client_list,
    get_client_id,
    get_client_group_list,
    get_client_group_properties,
    get_subclient_list,
    get_subclient_properties,
]

WRITE_TOOLS = [
    run_backup_for_subclient,
]
