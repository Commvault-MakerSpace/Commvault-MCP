import json

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from cv_mcp.server import create_server
from tests.conftest import call, load_fixture, make_settings


@pytest.mark.asyncio
async def test_get_jobs_list_default(mcp, api):
    api.get("Job").respond(200, json=load_fixture("jobs_7d"))

    result = await call(mcp, "get_jobs_list")

    # Check response structure from fixture
    assert "totalJobsAvailable" in result
    assert "jobsInThisResponse" in result
    assert len(result["jobsInThisResponse"]) == len(load_fixture("jobs_7d")["jobs"])

    # Check request params
    req = api.get("Job").calls.last.request
    assert req.url.params["jobCategory"] == "All"
    assert req.url.params["completedJobLookupTime"] == "86400"
    assert "jobFilter" not in req.url.params
    assert "clientId" not in req.url.params


@pytest.mark.asyncio
async def test_get_jobs_list_with_filters(mcp, api):
    api.get("Job").respond(200, json=load_fixture("jobs_7d"))

    await call(mcp, "get_jobs_list", job_type="Backup,Restore", client_id=2)

    req = api.get("Job").calls.last.request
    assert req.url.params["jobFilter"] == "Backup,Restore"
    assert req.url.params["clientId"] == "2"


@pytest.mark.asyncio
async def test_get_failed_jobs_default(mcp, api):
    api.post("Jobs").respond(200, json=load_fixture("jobs_failed_7d"))

    result = await call(mcp, "get_failed_jobs")

    # Check response from fixture
    assert result["totalJobsAvailable"] == 7
    first_job = result["jobsInThisResponse"][0]
    assert first_job["jobId"] == 18836
    assert first_job["status"] == "Failed"
    assert first_job["clientName"] == "Rbk_192.168.1.83"
    assert (
        "Configured content does not exist. Source: pe-cv-l26, Process: FileScan"
        in first_job["pendingReason"]
    )
    assert "<br/>" not in first_job["pendingReason"]

    # Check request body
    req = api.post("Jobs").calls.last.request
    body = json.loads(req.content)
    assert body["jobFilter"]["statusList"] == ["Failed"]


@pytest.mark.asyncio
async def test_get_failed_jobs_custom_statuses(mcp, api):
    api.post("Jobs").respond(200, json=load_fixture("jobs_failed_7d"))

    await call(mcp, "get_failed_jobs", statuses=["Warning"])

    req = api.post("Jobs").calls.last.request
    body = json.loads(req.content)
    assert body["jobFilter"]["statusList"] == ["Warning"]


@pytest.mark.asyncio
async def test_get_job_detail_success(mcp, api):
    api.get("Job/18836").respond(200, json=load_fixture("job_detail"))

    result = await call(mcp, "get_job_detail", job_id=18836)

    assert result["jobId"] == 18836
    assert result["status"] == "Failed"
    assert "jobAttributes" not in result
    assert "<br/>" not in result.get("pendingReason", "")


@pytest.mark.asyncio
async def test_get_job_detail_not_found(mcp, api):
    api.get("Job/42").respond(200, json={"jobs": []})

    with pytest.raises(ToolError, match="No job found with id 42"):
        await call(mcp, "get_job_detail", job_id=42)


@pytest.mark.asyncio
async def test_get_job_task_details(mcp, api):
    api.get("Job/18836/taskdetails").respond(200, json=load_fixture("job_taskdetails"))

    result = await call(mcp, "get_job_task_details", job_id=18836)

    assert "taskInfo" in result


@pytest.mark.asyncio
async def test_get_job_retention(mcp, api):
    api.get("Job/18836/advanceddetails").respond(200, json=load_fixture("job_retention"))

    result = await call(mcp, "get_job_retention", job_id=18836)

    assert result["jobId"] == 18836
    assert "retention" in result

    req = api.get("Job/18836/advanceddetails").calls.last.request
    assert req.url.params["infoType"] == "1"


@pytest.mark.asyncio
async def test_get_job_events(mcp, api):
    api.get("Events").respond(200, json=load_fixture("job_events"))

    result = await call(mcp, "get_job_events", job_id=18836)

    assert result["totalEvents"] == 2
    events = result["events"]
    # Check sorting by time ascending (implied by fixture order usually, but let's check content)
    assert events[0]["subsystem"] == "FileScan"
    assert events[1]["description"] == "Received failed message for job [18836], phase [Scan]."

    req = api.get("Events").calls.last.request
    assert req.url.params["jobId"] == "18836"


@pytest.mark.asyncio
async def test_suspend_job(mcp, api):
    api.post("Jobs/MultiJobOperation").respond(200, json={"jobIds": [1]})

    await call(mcp, "suspend_job", job_id=18836, reason="maintenance")

    req = api.post("Jobs/MultiJobOperation").calls.last.request
    body = json.loads(req.content)
    assert body["message"] == 1
    assert body["jobOpReq"]["operationType"] == 0
    assert body["jobOpReq"]["jobs"][0]["jobId"] == 18836
    assert body["operationDescription"] == "maintenance"


@pytest.mark.asyncio
async def test_resume_job(mcp, api):
    api.post("Job/18836/Action/Resume").respond(200, json={"jobIds": [1]})

    await call(mcp, "resume_job", job_id=18836)

    req = api.post("Job/18836/Action/Resume").calls.last.request
    assert req.method == "POST"


@pytest.mark.asyncio
async def test_resubmit_job(mcp, api):
    api.post("Job/18836/Action/Resubmit").respond(200, json={"jobIds": [1]})

    await call(mcp, "resubmit_job", job_id=18836)

    req = api.post("Job/18836/Action/Resubmit").calls.last.request
    assert req.method == "POST"


@pytest.mark.asyncio
async def test_kill_job(mcp, api):
    api.post("Job/18836/Action/Kill").respond(200, json={"jobIds": [1]})

    await call(mcp, "kill_job", job_id=18836)

    req = api.post("Job/18836/Action/Kill").calls.last.request
    assert req.method == "POST"


@pytest.mark.asyncio
async def test_send_logs_for_job(mcp, api):
    api.post("createtask").respond(200, json={"jobIds": [1]})

    await call(mcp, "send_logs_for_job", job_id=18836, email="ops@example.com")

    req = api.post("createtask").calls.last.request
    body = json.loads(req.content)
    assert body["taskInfo"]["subTasks"][0]["options"]["adminOpts"]["sendLogFilesOption"]["jobid"] == 18836
    assert body["taskInfo"]["subTasks"][0]["options"]["adminOpts"]["sendLogFilesOption"]["recipientCc"][
        "emailids"
    ] == ["ops@example.com"]


async def test_write_tools_registered_only_with_allow_writes(api):
    async with Client(create_server(make_settings(allow_writes=False))) as client:
        names = {t.name for t in await client.list_tools()}
    assert "get_jobs_list" in names
    assert "suspend_job" not in names
    async with Client(create_server(make_settings(allow_writes=True))) as client:
        names = {t.name for t in await client.list_tools()}
    assert "suspend_job" in names
