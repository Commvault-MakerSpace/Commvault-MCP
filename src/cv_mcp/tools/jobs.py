# Modified from Commvault/commvault-mcp-server for cv-mcp.
"""Job management tools for the Commvault MCP server."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import Context
from fastmcp.exceptions import ToolError
from pydantic import Field

from cv_mcp.shaping.jobs import get_basic_job_details, job_detail, job_events
from cv_mcp.tools._common import api_get, api_post, audit_write


async def get_jobs_list(
    ctx: Context,
    lookup_window_seconds: Annotated[
        int,
        Field(
            description="The time window in seconds to look up for jobs. For example, 86400 for the last 24 hours."
        ),
    ] = 86400,
    job_type: Annotated[
        str,
        Field(
            description="The job types to filter by. Multiple types can be provided, comma-separated. If not used, returns backup jobs. Valid values are: Backup, Restore, AUXCOPY, SYNTHFULL, SNAPBACKUP, DATA_VERIFICATION, Online_Content_Index, WORKFLOW, SEND_LOGFILE, DDBOPS, PRUNE, CSDRBKP, PATCHUPDATE"
        ),
    ] = "",
    job_status: Annotated[
        Literal["Active", "Finished", "All"],
        Field(description="The job status to filter by. Valid values are: Active, Finished, All"),
    ] = "All",
    client_id: Annotated[
        int | None,
        Field(
            description="The client id to filter jobs by. Not mandatory. If not provided, jobs for all clients will be returned."
        ),
    ] = None,
    limit: Annotated[int, Field(description="The maximum number of jobs to return. Default is 50.")] = 50,
    offset: Annotated[int, Field(description="The offset for pagination.")] = 0,
) -> dict[str, Any]:
    """Gets the list of jobs filtered by job type/status/clientId in a given lookup window. Times are epoch seconds."""
    params: dict[str, Any] = {
        "jobCategory": job_status,
        "completedJobLookupTime": lookup_window_seconds,
        "limit": limit,
    }
    if offset is not None:
        params["offset"] = offset
    if job_type:
        params["jobFilter"] = job_type
    if client_id is not None:
        params["clientId"] = client_id

    data = await api_get(ctx, "Job", params=params)
    return get_basic_job_details(data)


async def get_failed_jobs(
    ctx: Context,
    lookup_window_seconds: Annotated[
        int,
        Field(
            description="The time window in seconds to look up for jobs. For example, 86400 for the last 24 hours."
        ),
    ] = 86400,
    statuses: Annotated[
        list[str] | None,
        Field(
            description="List of job statuses to filter by. Valid values are: Failed, Killed, Completed w/ one or more errors, Suspended, Pending, Waiting, Running. Defaults to ['Failed'] if not provided."
        ),
    ] = None,
    limit: Annotated[int, Field(description="The maximum number of jobs to return. Default is 50.")] = 50,
    offset: Annotated[int, Field(description="The offset for pagination.")] = 0,
) -> dict[str, Any]:
    """Gets the list of failed jobs in a given lookup window. Times are epoch seconds."""
    payload = {
        "category": 0,
        "pagingConfig": {
            "offset": offset,
            "limit": limit,
        },
        "jobFilter": {
            "completedJobLookupTime": lookup_window_seconds,
            "showAgedJobs": False,
            "statusList": statuses if statuses is not None else ["Failed"],
        },
    }
    data = await api_post(ctx, "Jobs", json=payload)
    return get_basic_job_details(data)


async def get_job_detail(
    ctx: Context,
    job_id: Annotated[int, Field(description="The ID of the job to retrieve.")],
) -> dict[str, Any]:
    """Gets complete details about a job for a given job id."""
    data = await api_get(ctx, f"Job/{job_id}")
    jobs_list = data.get("jobs", [])
    if not jobs_list:
        raise ToolError(f"No job found with id {job_id}")
    return job_detail(jobs_list[0])


async def get_job_task_details(
    ctx: Context,
    job_id: Annotated[int, Field(description="The job id to retrieve task details for.")],
) -> dict[str, Any]:
    """Gets task details for a given job ID."""
    return await api_get(ctx, f"Job/{job_id}/taskdetails")


async def get_job_retention(
    ctx: Context,
    job_id: Annotated[int, Field(description="The job id to retrieve retention info for.")],
) -> dict[str, Any]:
    """Gets retention info for a given job ID. Returns empty for failed or aged jobs."""
    data = await api_get(ctx, f"Job/{job_id}/advanceddetails", params={"infoType": 1})
    return {"jobId": job_id, "retention": data.get("jobRetention") or {}}


async def get_job_events(
    ctx: Context,
    job_id: Annotated[int, Field(description="The job id to retrieve events for.")],
) -> dict[str, Any]:
    """Gets events for a given job ID."""
    data = await api_get(ctx, "Events", params={"jobId": job_id})
    return job_events(data)


async def suspend_job(
    ctx: Context,
    job_id: Annotated[int, Field(description="The ID of the job to suspend.")],
    reason: Annotated[str, Field(description="The reason for suspending the job. Optional.")] = "",
) -> dict[str, Any]:
    """SIDE EFFECT: Suspends/pauses the job with the given job id."""
    audit_write("suspend_job", job_id=job_id, reason=reason)
    payload = {
        "message": 1,
        "jobOpReq": {
            "operationType": 0,
            "jobs": [{"jobId": job_id}],
        },
        "operationDescription": reason,
    }
    return await api_post(ctx, "Jobs/MultiJobOperation", json=payload)


async def resume_job(
    ctx: Context,
    job_id: Annotated[int, Field(description="The ID of the job to resume.")],
) -> dict[str, Any]:
    """SIDE EFFECT: Resumes the job with the given job id."""
    audit_write("resume_job", job_id=job_id)
    return await api_post(ctx, f"Job/{job_id}/Action/Resume", json={})


async def resubmit_job(
    ctx: Context,
    job_id: Annotated[int, Field(description="The ID of the job to resubmit.")],
) -> dict[str, Any]:
    """SIDE EFFECT: Resubmits the job with the given job id."""
    audit_write("resubmit_job", job_id=job_id)
    return await api_post(ctx, f"Job/{job_id}/Action/Resubmit", json={})


async def kill_job(
    ctx: Context,
    job_id: Annotated[int, Field(description="The ID of the job to kill.")],
) -> dict[str, Any]:
    """SIDE EFFECT: Kills the job with the given job id."""
    audit_write("kill_job", job_id=job_id)
    return await api_post(ctx, f"Job/{job_id}/Action/Kill", json={})


async def send_logs_for_job(
    ctx: Context,
    job_id: Annotated[int, Field(description="The job id for which to send logs.")],
    email: Annotated[str, Field(description="The email id to send logs to.")],
) -> dict[str, Any]:
    """SIDE EFFECT: Triggers a new send logs job for the specified job ID and sends logs to the provided email address."""
    audit_write("send_logs_for_job", job_id=job_id, email=email)
    data = {
        "taskInfo": {
            "task": {
                "taskType": 1,
                "initiatedFrom": 1,
                "policyType": 0,
                "taskFlags": {"disabled": False},
            },
            "subTasks": [
                {
                    "subTask": {"subTaskType": 1, "operationType": 5010},
                    "options": {
                        "adminOpts": {
                            "sendLogFilesOption": {
                                "actionLogsEndJobId": 0,
                                "emailSelected": True,
                                "jobid": job_id,
                                "tsDatabase": False,
                                "galaxyLogs": True,
                                "getLatestUpdates": False,
                                "actionLogsStartJobId": 0,
                                "computersSelected": False,
                                "csDatabase": False,
                                "otherDatabases": False,
                                "crashDump": False,
                                "isNetworkPath": False,
                                "saveToFolderSelected": False,
                                "notifyMe": True,
                                "includeJobResults": False,
                                "doNotIncludeLogs": True,
                                "machineInformation": True,
                                "scrubLogFiles": False,
                                "emailSubject": f"Job {job_id} : Send Logs",
                                "osLogs": True,
                                "allUsersProfile": True,
                                "splitFileSizeMB": 512,
                                "actionLogs": False,
                                "includeIndex": False,
                                "databaseLogs": True,
                                "includeDCDB": False,
                                "collectHyperScale": False,
                                "logFragments": False,
                                "uploadLogsSelected": True,
                                "useDefaultUploadOption": True,
                                "enableChunking": True,
                                "collectRFC": False,
                                "collectUserAppLogs": False,
                                "impersonateUser": {"useImpersonation": False},
                                "clients": [
                                    {"clientId": 0, "clientName": "null"},
                                ],
                                "recipientCc": {
                                    "emailids": [email],
                                    "users": [],
                                    "userGroups": [],
                                },
                                "sendLogsOnJobCompletion": False,
                            }
                        }
                    },
                }
            ],
        }
    }
    return await api_post(ctx, "createtask", json=data)


READ_TOOLS = [
    get_jobs_list,
    get_failed_jobs,
    get_job_detail,
    get_job_task_details,
    get_job_retention,
    get_job_events,
]
WRITE_TOOLS = [
    suspend_job,
    resume_job,
    resubmit_job,
    kill_job,
    send_logs_for_job,
]
