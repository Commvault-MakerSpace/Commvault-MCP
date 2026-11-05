# Modified from Commvault/commvault-mcp-server for cv-mcp.
"""CommCell tools for the Commvault MCP server."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import Context
from pydantic import Field

from cv_mcp.shaping.commcell import (
    compute_security_score,
    format_report_dataset_response,
    security_posture,
    transform_sla_data,
)
from cv_mcp.tools._common import api_get, api_post, audit_write


async def get_commcell_details(
    ctx: Context,
) -> dict[str, Any]:
    """CommCell identity: name, id, CommServe host, software version, OS and time zone."""
    data = await api_get(ctx, "CommServ")
    commcell = data.get("commcell", {})
    return {
        "commCellName": commcell.get("commCellName"),
        "commCellId": commcell.get("commCellId"),
        "hostName": data.get("hostName"),
        "version": data.get("csVersionInfo"),
        "osType": data.get("osType"),
        "timeZone": data.get("timeZone"),
    }


async def get_sla_status(
    ctx: Context,
) -> dict[str, Any]:
    """Backup SLA for the whole CommCell: how many protected entities met or missed SLA and the percentage."""
    data = await api_get(
        ctx,
        "cr/reportsplusengine/datasets/getslacounts/data",
        params={
            "cache": "true",
            "parameter.i_dashboardtype": "commcell",
            "datasource": 2,
        },
    )
    return transform_sla_data(data)


async def get_security_posture(
    ctx: Context,
) -> dict[str, Any]:
    """Every security assessment parameter with status, current setting and recommendation. Status 2 means the
    setting does not follow Commvault's recommendation; use get_security_score for just the score."""
    data = await api_get(ctx, "Security/Dashboard")
    return security_posture(data)


async def get_security_score(
    ctx: Context,
) -> dict[str, Any]:
    """Security score 0-100 (share of assessment parameters that follow recommendations) plus the failing ones."""
    data = await api_get(ctx, "Security/Dashboard")
    return compute_security_score(data)


async def get_storage_space_utilization(
    ctx: Context,
) -> dict[str, Any]:
    """
    Retrieves storage space utilization or the amount of data that is in all disk or cloud libraries, and the percentage of storage space that was saved because of compression and deduplication.
    Returns per-library rows; columns named *MB are megabytes, *GB gigabytes, FreeSpacePercentage is a percent, "Date to be Full" is epoch seconds.
    """
    data = await api_get(
        ctx,
        "cr/reportsplusengine/datasets/2b366703-52e1-4775-8047-1f4cfa13d2db/data",
        params={
            "cache": "true",
            "parameter.i_dashboardtype": "commcell",
            "orderby": "'date to be full'",
            "datasource": 2,
        },
    )
    return format_report_dataset_response(data)


async def send_logs_for_commcell(
    ctx: Context,
    email: Annotated[str, Field(description="The email id to send logs to.")],
) -> dict[str, Any]:
    """SIDE EFFECT: Triggers a new send logs job for the specified CommCell and sends logs to the provided email address. If successful, returns the job ID of the created send logs job."""
    audit_write("send_logs_for_commcell", email=email)
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
                                "jobid": 0,
                                "tsDatabase": False,
                                "galaxyLogs": True,
                                "getLatestUpdates": False,
                                "actionLogsStartJobId": 0,
                                "computersSelected": True,
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
                                "emailSubject": "Your CommCell Logs",
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
                                "clients": [{"clientId": 2, "clientName": "commserve"}],
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
    get_commcell_details,
    get_sla_status,
    get_security_posture,
    get_security_score,
    get_storage_space_utilization,
]
WRITE_TOOLS = [send_logs_for_commcell]
