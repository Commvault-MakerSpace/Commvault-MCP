"""Record real CommServe responses into tests/fixtures/ for unit tests and replay mode.

Run: CV_SSL_VERIFY=false uv run --env-file ~/.config/cv-mcp/lab.env python scripts/record_fixtures.py [names...]
Read-only: only GET and the POST Jobs filter are used.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from cv_mcp.api.exceptions import CommvaultError
from cv_mcp.config import Settings
from cv_mcp.server import build_client

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

# name -> (method, endpoint, params, json)
STATIC = {
    "whoami": ("GET", "v2/whoami", None, None),
    "commserv": ("GET", "CommServ", None, None),
    "jobs_7d": ("GET", "Job", {"jobCategory": "All", "completedJobLookupTime": 604800, "limit": 50, "offset": 0}, None),
    "jobs_failed_7d": (
        "POST",
        "Jobs",
        None,
        {
            "category": 0,
            "pagingConfig": {"offset": 0, "limit": 50},
            "jobFilter": {"completedJobLookupTime": 604800, "showAgedJobs": False, "statusList": ["Failed"]},
        },
    ),
    "sla_counts": (
        "GET",
        "cr/reportsplusengine/datasets/getslacounts/data",
        {"cache": "true", "parameter.i_dashboardtype": "commcell", "datasource": 2},
        None,
    ),
    "security_dashboard": ("GET", "Security/Dashboard", None, None),
    "storage_utilization": (
        "GET",
        "cr/reportsplusengine/datasets/2b366703-52e1-4775-8047-1f4cfa13d2db/data",
        {"cache": "true", "parameter.i_dashboardtype": "commcell", "orderby": "'date to be full'", "datasource": 2},
        None,
    ),
    "commcell_details": ("GET", "cr/reportsplusengine/datasets/a0f077a5-2dfe-4010-a957-57a24cae89a8/data", None, None),
    "entity_counts": (
        "GET",
        "cr/reportsplusengine/datasets/d0a73c45-b06d-4358-8d7e-d55d428ba75c/data",
        {"cache": "true", "parameter.i_dashboardtype": "commcell", "datasource": 2},
        None,
    ),
    "clients": ("GET", "Client", None, None),
    "client_groups": ("GET", "ClientGroup", None, None),
    "getid_client": ("GET", "getid", {"clientname": "pe-cv-l01"}, None),
    "subclients_client2": ("GET", "subclient", {"clientId": 2}, None),
    "storage_pools": ("GET", "StoragePool", None, None),
    "storage_policies": ("GET", "V2/StoragePolicy", None, None),
    "libraries": ("GET", "Library", None, None),
    "mediaagents": ("GET", "MediaAgent", None, None),
    "plans_summary": ("GET", "v4/plan/summary", None, None),
    "schedules": ("GET", "Schedules", None, None),
    "users": ("GET", "v4/user", None, None),
    "usergroups": ("GET", "v4/usergroup", None, None),
    "roles": ("GET", "v4/role", None, None),
}


async def main(only: set[str]) -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    failures = 0
    async with build_client(Settings.from_env()) as client:
        results: dict[str, object] = {}
        for name, (method, endpoint, params, body) in STATIC.items():
            if only and name not in only:
                continue
            try:
                data = await client.request(method, endpoint, params=params, json=body)
            except CommvaultError as e:
                print(f"FAIL {name}: {e}")
                failures += 1
                continue
            results[name] = data
            (FIXTURES / f"{name}.json").write_text(json.dumps(data, indent=1))
            size = len(json.dumps(data))
            print(f"ok   {name}: {size} bytes")
        # Derived: details for the first failed job and the first subclient
        failed = results.get("jobs_failed_7d", {}).get("jobs") or []
        if failed:
            jid = failed[0]["jobSummary"]["jobId"]
            for name, endpoint, params in (
                ("job_detail", f"Job/{jid}", None),
                ("job_taskdetails", f"Job/{jid}/taskdetails", None),
                ("job_retention", f"Job/{jid}/advanceddetails", {"infoType": 1}),
                ("job_events", "Events", {"jobId": jid}),
            ):
                try:
                    data = await client.get(endpoint, params=params)
                    (FIXTURES / f"{name}.json").write_text(json.dumps(data, indent=1))
                    print(f"ok   {name} (job {jid}): {len(json.dumps(data))} bytes")
                except CommvaultError as e:
                    print(f"FAIL {name}: {e}")
                    failures += 1
        subs = results.get("subclients_client2", {}).get("subClientProperties") or []
        if subs:
            sid = subs[0]["subClientEntity"]["subclientId"]
            try:
                data = await client.get(f"subclient/{sid}")
                (FIXTURES / "subclient_detail.json").write_text(json.dumps(data, indent=1))
                print(f"ok   subclient_detail ({sid}): {len(json.dumps(data))} bytes")
            except CommvaultError as e:
                print(f"FAIL subclient_detail: {e}")
                failures += 1
        groups = results.get("client_groups", {}).get("groups") or []
        if groups:
            gid = groups[0].get("Id") or groups[0].get("clientGroup", {}).get("clientGroupId")
            try:
                data = await client.get(f"ClientGroup/{gid}")
                (FIXTURES / "client_group_detail.json").write_text(json.dumps(data, indent=1))
                print(f"ok   client_group_detail ({gid}): {len(json.dumps(data))} bytes")
            except CommvaultError as e:
                print(f"FAIL client_group_detail: {e}")
                failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(set(sys.argv[1:]))))
