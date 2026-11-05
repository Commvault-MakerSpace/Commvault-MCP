import json

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from cv_mcp.server import create_server
from tests.conftest import call, load_fixture, make_settings


async def test_get_commcell_details(mcp, api):
    """Test get_commcell_details returns correct details from CommServ endpoint."""
    api.get("CommServ").respond(200, json=load_fixture("commserv"))

    result = await call(mcp, "get_commcell_details")

    assert result["commCellName"] == "pe-cv-l01.lab.local"
    assert result["commCellId"] == 2
    assert result["hostName"] == "pe-cv-l01.lab.local"
    assert result["version"] == "11 SP46.40"
    assert result["osType"] == "Unix"


async def test_get_sla_status(mcp, api):
    """Test get_sla_status returns SLA counts from the reportsplusengine dataset."""
    api.get(url__regex=r".*/datasets/getslacounts/data.*").respond(200, json=load_fixture("sla_counts"))

    result = await call(mcp, "get_sla_status")

    assert result["Met SLA"] == 8
    assert result["Missed SLA"] == 8
    assert result["Pending Application Investigation"] == 0
    assert result["Pending Infrastructure Investigation"] == 0
    assert result["SLA Percentage"] == 50.0


async def test_get_security_score(mcp, api):
    """Test get_security_score returns score and failure details from Security/Dashboard."""
    api.get("Security/Dashboard").respond(200, json=load_fixture("security_dashboard"))

    result = await call(mcp, "get_security_score")

    assert result["security_score"] == 73
    assert result["checked"] == 26
    assert result["failed"] == 7

    failures = result["failures"]
    assert len(failures) > 0
    assert failures[0]["parameter"] == "Multi-factor authentication"
    assert failures[0]["status"] == 2


async def test_get_security_posture(mcp, api):
    """Test get_security_posture returns summary and parameters without '<' characters."""
    api.get("Security/Dashboard").respond(200, json=load_fixture("security_dashboard"))

    result = await call(mcp, "get_security_posture")

    assert result["summary"] == {"good": 10, "warning": 9, "not following recommendation": 7}
    assert len(result["parameters"]) == 26

    parameters = result["parameters"]
    assert parameters[0]["parameter"] == "Failed login lockout count"

    # Ensure no '<' character exists in the entire JSON representation of the result
    import json

    result_json_str = json.dumps(result)
    assert "<" not in result_json_str


async def test_get_storage_space_utilization(mcp, api):
    """Test get_storage_space_utilization returns storage records with specific fields."""
    api.get(url__regex=r".*/datasets/2b366703-52e1-4775-8047-1f4cfa13d2db/data.*").respond(
        200, json=load_fixture("storage_utilization")
    )

    result = await call(mcp, "get_storage_space_utilization")

    assert result["totalRecordCount"] == 2

    records = result["records"]
    assert len(records) >= 1

    record = records[0]
    assert record["LibraryName"] == "PE Lab Disk Library"
    assert record["TotalSpaceMB"] == 1046016

    # Ensure internal fields are not exposed
    assert "sys_rowid" not in record
    assert "Data Source" not in record


async def test_security_dashboard_500_retries_fail(mcp, api):
    """Test that repeated 500 errors on Security/Dashboard eventually raise ToolError."""
    # Mock the endpoint to return 500 three times (initial + 2 retries)
    route = api.get("Security/Dashboard").respond(500, json={"error": "Internal Server Error"})

    with pytest.raises(ToolError):
        await call(mcp, "get_security_score")

    # The client should have attempted the request 3 times (1 initial + 2 retries)
    assert route.call_count == 3


async def test_write_tools_registered_only_with_allow_writes(api):
    async with Client(create_server(make_settings(allow_writes=False))) as client:
        names = {t.name for t in await client.list_tools()}
    assert "get_sla_status" in names
    assert "send_logs_for_commcell" not in names
    async with Client(create_server(make_settings(allow_writes=True))) as client:
        names = {t.name for t in await client.list_tools()}
    assert "send_logs_for_commcell" in names


async def test_send_logs_for_commcell(mcp, api):
    route = api.post("createtask").respond(200, json={"jobIds": [1]})
    await call(mcp, "send_logs_for_commcell", email="ops@example.com")
    body = json.loads(route.calls.last.request.content)
    opt = body["taskInfo"]["subTasks"][0]["options"]["adminOpts"]["sendLogFilesOption"]
    assert opt["recipientCc"]["emailids"] == ["ops@example.com"]
    assert opt["clients"] == [{"clientId": 2, "clientName": "commserve"}]
