# --------------------------------------------------------------------------
# Copyright Commvault Systems, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# --------------------------------------------------------------------------
# Modified from Commvault/commvault-mcp-server for cv-mcp.
"""Slim job payloads for the model. Times are epoch seconds, sizes are bytes."""

from __future__ import annotations

import re
from typing import Any

_HTML_TAG = re.compile(r"<[^>]+>")

# Nested blobs in jobSummary that carry no value for an operator reading a job.
_DETAIL_DROP = frozenset(
    {
        "jobAttributes",
        "jobAttributesEx",
        "securityAssemblyEntity",
        "extRetentionFlags",
        "runbookTemplate",
        "replicationGroupEntity",
        "taskEntity",
        "subTaskEntity",
        "company",
        "dataSource",
    }
)


def clean_text(value: Any) -> Any:
    """Strip HTML tags (CommServe uses <br/> in pendingReason) and collapse whitespace."""
    if not isinstance(value, str):
        return value
    return " ".join(_HTML_TAG.sub(" ", value).split())


def job_summary(job: dict[str, Any]) -> dict[str, Any]:
    """Slim one Job list entry: ids, status, type, client, times (epoch seconds), size (bytes), reason."""
    summary = job.get("jobSummary", {})
    result: dict[str, Any] = {
        "jobId": summary.get("jobId"),
        "status": summary.get("status"),
        "jobType": summary.get("jobType"),
        "backupLevelName": summary.get("backupLevelName"),
        "jobStartTime": summary.get("jobStartTime"),
        "jobEndTime": summary.get("jobEndTime"),
        "clientName": summary.get("destinationClient", {}).get("clientName"),
        "storagePolicyName": summary.get("storagePolicy", {}).get("storagePolicyName"),
    }
    subclient = summary.get("subclient") or {}
    extras = {
        "percentComplete": summary.get("percentComplete"),
        "sizeOfApplication": summary.get("sizeOfApplication"),
        "subclientName": summary.get("subclientName") or subclient.get("subclientName"),
        "appTypeName": summary.get("appTypeName"),
        "pendingReason": clean_text(summary.get("pendingReason")),
        "failureReason": clean_text(summary.get("failureReason")),
    }
    result.update({k: v for k, v in extras.items() if v not in (None, "")})
    return result


def get_basic_job_details(api_response: dict[str, Any]) -> dict[str, Any]:
    """Slim a Job list response; keeps the unpaged total so the model knows when to page."""
    jobs = api_response.get("jobs", [])
    return {
        "totalJobsAvailable": api_response.get("totalRecordsWithoutPaging", 0),
        "jobsInThisResponse": [job_summary(job) for job in jobs],
    }


def job_detail(job: dict[str, Any]) -> dict[str, Any]:
    """Full jobSummary minus internal blobs and empty values; pendingReason is HTML-stripped."""
    summary = job.get("jobSummary", {})
    out: dict[str, Any] = {}
    for key, value in summary.items():
        if key in _DETAIL_DROP or value in (None, "", {}, []):
            continue
        out[key] = clean_text(value) if key in ("pendingReason", "failureReason") else value
    return out


def job_events(api_response: dict[str, Any]) -> dict[str, Any]:
    """Events for one job: time (epoch seconds), severity code (higher is worse), subsystem, description."""
    events = []
    for ev in api_response.get("commservEvents", []):
        events.append(
            {
                "time": ev.get("timeSource"),
                "severity": ev.get("severity"),
                "eventCode": ev.get("eventCodeString"),
                "subsystem": ev.get("subsystem"),
                "description": clean_text(ev.get("description")),
            }
        )
    events.sort(key=lambda e: e.get("time") or 0)
    return {"totalEvents": len(events), "events": events}
