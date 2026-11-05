import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from cv_mcp.server import create_server
from tests.conftest import call, load_fixture, make_settings


async def test_get_client_list(mcp, api):
    api.get("Client").respond(200, json=load_fixture("clients"))
    result = await call(mcp, "get_client_list")

    assert result["totalClients"] == 17
    first = result["clients"][0]
    assert first == {
        "clientName": "pe-cv-l01",
        "clientId": 2,
        "hostName": "pe-cv-l01.lab.local",
    }

    allowed_keys = {"clientName", "clientId", "hostName", "displayName"}
    for client in result["clients"]:
        assert set(client.keys()) <= allowed_keys


async def test_get_client_id_found(mcp, api):
    api.get("getid").respond(200, json=load_fixture("getid_client"))
    result = await call(mcp, "get_client_id", client_name="pe-cv-l01")

    assert result == {
        "clientName": "pe-cv-l01",
        "clientId": 2,
    }


async def test_get_client_id_not_found(mcp, api):
    api.get("getid").respond(404)
    with pytest.raises(ToolError, match="No client named 'nope'"):
        await call(mcp, "get_client_id", client_name="nope")


async def test_get_client_group_list(mcp, api):
    api.get("ClientGroup").respond(200, json=load_fixture("client_groups"))
    result = await call(mcp, "get_client_group_list")

    assert result["totalClientGroups"] == 12
    first = result["clientGroups"][0]
    assert first == {
        "clientGroupId": 1,
        "clientGroupName": "Infrastructure",
        "clientCount": 4,
        "companyName": None,
    }


async def test_get_client_group_properties(mcp, api):
    api.get("ClientGroup/1").respond(200, json=load_fixture("client_group_detail"))
    result = await call(mcp, "get_client_group_properties", client_group_id=1)

    assert "clientGroupDetail" in result


async def test_get_subclient_list_by_name(mcp, api):
    api.get("subclient").respond(200, json=load_fixture("subclients_client2"))
    result = await call(mcp, "get_subclient_list", client_name="pe-cv-l01")

    assert result["subClientCount"] == 2
    assert result["subClients"][0]["subclientName"] == "default"
    assert result["subClients"][1]["subclientId"] == 4


async def test_get_subclient_list_by_id(mcp, api):
    api.get("subclient").respond(200, json=load_fixture("subclients_client2"))
    result = await call(mcp, "get_subclient_list", client_id=2)

    assert result["subClientCount"] == 2


async def test_get_subclient_list_missing_args(mcp, api):
    with pytest.raises(ToolError, match="client_name or client_id"):
        await call(mcp, "get_subclient_list")


async def test_get_subclient_properties(mcp, api):
    api.get("subclient/2").respond(200, json=load_fixture("subclient_detail"))
    result = await call(mcp, "get_subclient_properties", subclient_id=2)

    assert "subClientProperties" in result


async def test_write_tools_registered_only_with_allow_writes(api):
    async with Client(create_server(make_settings(allow_writes=False))) as client:
        names = {t.name for t in await client.list_tools()}
    assert "get_client_list" in names
    assert "run_backup_for_subclient" not in names
    async with Client(create_server(make_settings(allow_writes=True))) as client:
        names = {t.name for t in await client.list_tools()}
    assert "run_backup_for_subclient" in names


async def test_run_backup_for_subclient_incremental(mcp, api):
    api.post("subclient/2/action/backup").respond(200, json={"jobIds": [123]})
    result = await call(mcp, "run_backup_for_subclient", subclient_id=2)

    assert result == {"jobIds": [123]}


async def test_run_backup_for_subclient_full(mcp, api):
    api.post("subclient/2/action/backup").respond(200, json={"jobIds": [456]})
    result = await call(mcp, "run_backup_for_subclient", subclient_id=2, backup_type="Full")

    assert result == {"jobIds": [456]}
    # Verify query param was sent correctly for Full backup
    request = api.post("subclient/2/action/backup").calls.last.request
    assert "backupLevel" in request.url.params
    assert request.url.params["backupLevel"] == "Full"
