# cv-mcp: MCP server for Commvault Command Center

Plan written 2026-11-05. Status 2026-11-05 night: phases 0 and 1 done; phase 2 demo path done (17 read tools for jobs, CommCell and clients, 6 write tools behind the flag, 98 tests on recorded lab fixtures, all verified live). Next: storage/plans/schedules/users tools, replay mode, demo script. Target: conference demo week of 2026-11-10.

## Goal

A Model Context Protocol (MCP) server that lets Claude (Code, Desktop, LibreChat) query and,
when explicitly enabled, operate a Commvault CommCell through the Command Center REST API.
Hosted on the product-experience GitLab group, owned by this team, independent of the
Commvault GitHub repo that is being retired.

## Starting point: what to pull from Commvault/commvault-mcp-server

Reference clone: `/tmp/cv-ref/commvault-mcp-server` (last upstream commit 4d182bf, 2026-06-19).
Apache 2.0, so code can be copied if the license header and a NOTICE file are kept.
Stack: Python 3.11, `uv`, `fastmcp` 3.2.4 (current release is 4.1.6), `requests`, `keyring`.

### Pull as-is (small edits)

| Upstream file | What it gives us | Notes |
|---|---|---|
| `src/cv_api_client.py` | Base URL `{CC}/commandcenter/api/`, Bearer header with fallback to `Authtoken`, 401 -> `POST V4/AccessToken/Renew` with a lock so the single-use refresh token is never sent twice, retry with backoff | Port to `httpx` async; swap keyring for a pluggable token store |
| `src/wrappers.py` | Response slimming for jobs, client groups, subclients, storage pools, report datasets, SLA, security score, users, groups, schedules, security associations | Keep; these are the hard-won field mappings |
| `src/utils.py` `sanitize_endpoint_path` | Path traversal guard on endpoint strings | Keep |
| `src/server.py` `TokenAuthMiddleware` | Shared-secret gate for HTTP transports, exempts `/.well-known/` | Keep for phase 4 |
| `src/auth/auth_service.py` client-IP / trusted-proxy / backoff logic | Rate limiting of failed auth, X-Forwarded-For handling | Keep for phase 4 |
| `src/auth/jwt_verifier.py` + `OAuthProxy` wiring | OAuth against Commvault 11.42.27+ or Entra | Phase 5, optional |
| `tests/test_*.py` helpers | `extract_response_data`, `assert_no_error_in_response` | Reuse pattern, but tests must not need a live CommCell |

### Pull the endpoint map, rewrite the tools

The seven core tool modules are thin: each is `commvault_api_client.get(path)` plus a wrapper.
The value is the endpoint list below (49 functions upstream, 40 after dropping DocuSign and Salesforce).

| Area | Tools (upstream names) | Command Center API paths |
|---|---|---|
| Jobs | get_jobs_list, get_job_detail, get_failed_jobs, get_job_task_details, get_retention_info_of_a_job, suspend_job, resume_job, resubmit_job, kill_job, create_send_logs_job_for_a_job | `Job`, `Jobs` (POST filter), `Job/{id}/taskdetails`, `Job/{id}/advanceddetails?infoType=1`, `Job/{id}/action/{op}`, `createtask` |
| CommCell | get_commcell_details, get_entity_counts, get_sla_status, get_security_posture, get_security_score, get_storage_space_utilization, create_send_logs_job_for_commcell | `Security/Dashboard`, `cr/reportsplusengine/datasets/<guid>/data` (SLA, utilization, commcell details, entity counts) |
| Clients | get_client_list, get_clientid_from_clientname, get_client_group_list, get_client_group_properties, get_subclient_list, get_subclient_properties, run_backup_for_subclient | `Client`, `getid?clientname=`, `ClientGroup`, `ClientGroup/{id}`, `subclient`, `subclient/{id}`, `subclient/{id}/action/backup` |
| Storage | get_storage_policy_list/properties, get_storage_policy_copy_details/size, get_library_list/properties, get_storage_pool_list, get_mediaagent_list | `V2/StoragePolicy[/{id}[/Copy/{id}[/Size]]]`, `Library[/{id}]`, `StoragePool`, `MediaAgent` |
| Plans | get_plan_list, get_plan_properties | `v4/plan/summary[/{id}]`, `v2/plan?subType=Server...` |
| Schedules | get_schedules_list, get_schedule_properties, enable_schedule, disable_schedule | `Schedules`, `Schedule/{id}`, `Schedules/task/Action/{Enable,Disable}` |
| Users | get_users_list, get_user_properties, get_user_groups_list, get_user_group_properties, get_roles_list, get_my_user_info, get_associated_entities_for_user_or_group, view_entity_permissions, set_user_enabled | `v4/user[/{id}]`, `v4/usergroup[/{id}]`, `v4/role`, `v2/whoami`, `{user|usergroup}/{id}/security`, `Security/{type}/{id}/Permissions`, `user/{id}/{enable|disable}` |

### Leave behind

- `docusign_tools.py` (1045 lines, needs S3 vault + workflow XML) and `salesforce_tools.py` (423 lines). Out of scope.
- `setup.py` wizard (`rich`, `pyfiglet`, masked input) and the hard `keyring` dependency. WSL has no
  keyring backend (`keyring --list-backends` shows only `fail.Keyring`), so the upstream server cannot even start here.
- `boto3`, `authlib` until OAuth is actually built.
- Upstream bugs not to copy: tools `return ToolError(...)` instead of raising it, so errors reach the model as a
  stringified object; tests call a live CommCell; `get_plan_list` makes two calls where one is enough.

## Requirements

### Environment
- Dev target (confirmed 2026-11-05): `https://commvaultlab.lab.local` = 192.168.1.15, CommServe `pe-cv-l01.lab.local`,
  commCellId 2, release 11 SP46.40 (Linux CommServe). Access token for user `admin` verified against `v2/whoami`.
  Access tokens need 11.38+; the Renew endpoint and 2 h / 14 d token lifetimes described in current docs; OAuth needs 11.42.27+.
- Network from this WSL: the lab is behind the Windows VPN adapter `Lab-PE-Zach-K-2` (WSL `eth6`). The lab subnet
  192.168.1.0/24 overlaps the home LAN on `eth1`, whose route wins, so either `sudo ip route add 192.168.1.15/32 dev eth6`
  (per boot) or bind the client to the VPN address. Hostname resolves on Windows only; add it to `/etc/hosts` in WSL.
- Lab cert is self-signed (CN=CS_GXZUPOK, valid to 2027-08-23). Hosted MCP Service at `/commandcenter/mcp` returns 404
  on this CommServe, so it is not a substitute for this project yet.
- Lab contents: 17 clients, 4 plans, 6 storage pools, ~100 jobs/week with a handful of failures. Enough for the demo.
- A Commvault user for the server. Create an access token with scope All (or Custom, read-only role for phase 2)
  under Profile > Access tokens; save the access token and refresh token once, they are not retrievable later.
  Current tokens live in `~/.config/cv-mcp/lab.env` (mode 600, outside the repo); `.env.example` documents the variable names.
- Self-signed Command Center certs are common in labs: support `CV_CA_BUNDLE` and `CV_SSL_VERIFY=false` for dev only.

### Dev machine (this WSL)
- Python 3.14.4 and uv 0.12.17 present; fastmcp 4.1.6 installs on 3.12 and 3.14. Pin 3.12 in `.python-version` for parity with CI images.
- No `docker` on this machine; container build runs in GitLab CI or on the GitLab VM.
- GitLab remote reachable over HTTPS; the `credential-manager` warning in git output is harmless.

### Stack decision
Python + FastMCP 4.x (same family as upstream so the ported code stays recognisable), `httpx` async client,
`pydantic` models for tool output, `uv` for env and lockfile, `pytest` + `respx` for HTTP mocking.

## Repository layout

```
cv-mcp/
  pyproject.toml  uv.lock  .python-version  .env.example  README.md  PLAN.md  LICENSE  NOTICE
  CLAUDE.md                     # working agreements for Claude Code
  .mcp.json                     # Claude Code stdio registration for local use
  src/cv_mcp/
    __init__.py  server.py  config.py  logging.py
    api/client.py               # CommvaultClient (httpx, auth, renew, retry)
    api/tokens.py               # TokenStore: env -> file (~/.secrets style) -> keyring
    api/paths.py                # endpoint constants (the map above)
    shaping/*.py                # ported wrappers, one module per area
    tools/{jobs,commcell,clients,storage,plans,schedules,users}.py
    resources.py  prompts.py    # commcell://summary, "triage failed backups" etc.
    http/middleware.py          # shared-secret auth (phase 4)
  tests/  fixtures/*.json       # recorded CommCell responses, no live calls in CI
  docker/Dockerfile  .gitlab-ci.yml
```

## Phases

### Phase 0: scaffold (half a day)
uv project, src layout, license + NOTICE crediting upstream, `.env.example`, `CLAUDE.md`, pre-commit (ruff), first push.

### Phase 1: API client and auth (1 day)
- Port `cv_api_client.py` to async httpx. Keep: Bearer first then `Authtoken` fallback, 401 -> renew under lock,
  rotate stored tokens after renew, backoff on 5xx/network.
- `TokenStore` with three backends; default is env vars `CV_ACCESS_TOKEN` / `CV_REFRESH_TOKEN`, with a writable
  JSON file so rotated tokens survive restarts. Never log tokens.
- `cv-mcp check` CLI: calls `v2/whoami`, prints user and CommServe version. First thing to run against the lab.

### Phase 2: read-only tools (2 days)
Done 2026-11-05 for jobs, CommCell, clients. Notes: `get_entity_counts` dropped (its report dataset returns no columns on 11.46); `get_security_posture` and `get_security_score` use `paramName`/`currentSetting`/`recommendation` (categories carry only a numeric `category`); `get_job_events` added via `Events?jobId=`; pendingReason and security text are HTML-stripped. `scripts/record_fixtures.py` records the lab responses used by tests.
Port the 31 read tools in the map. Each tool: typed params with `Annotated[..., Field(description=...)]`, raises
`ToolError` on failure, returns a slimmed dict via the ported wrappers, documents units (epoch seconds, bytes).
Add what upstream lacks: time window and pagination on job queries, `get_job_events`, client-level backup summary.
Mechanical porting of tool bodies and docstrings can go to the local Qwen endpoint; review the output here.

### Phase 3: write tools behind a flag (half a day)
suspend/resume/resubmit/kill job, run backup, enable/disable schedule, set user enabled, send logs.
Registered only when `CV_MCP_ALLOW_WRITES=true`; tool descriptions state the side effect; audit log line per call.

### Phase 4: remote transport (1 day)
Streamable HTTP on `/mcp`, shared-secret middleware ported from upstream, `TRUSTED_PROXY_IPS`, health endpoint.
Target host: the pe-ai-l01 VM behind Nginx Proxy Manager, or a Container App like SitRep. Decide when phase 2 is usable.

### Phase 5: OAuth (optional, later)
Port `OAuthProxy` + `CustomJWTVerifier` once a Commvault 11.42.27+ or Entra OAuth app exists. Not needed for stdio or for a secret-gated remote.

### Phase 6: tests, CI, packaging (1 day)
Unit tests with recorded fixtures per tool, a `--live` marker for smoke tests against the lab, ruff + pytest in
`.gitlab-ci.yml`, Dockerfile built in CI and pushed to the GitLab registry.

### Phase 7: docs and demo
README with Claude Code / Claude Desktop / mcp-remote configs, a scripted demo (failed jobs -> job details -> SLA ->
security score) that doubles as material for the SR-5 "introduce MCP for backup practitioners" piece.

## Open questions (answers change the work)

1. ~~Which CommCell is the dev target, and what release is it on?~~ Answered 2026-11-05: `pe-cv-l01.lab.local`, 11 SP46.40 (see Environment).
2. Read-only first, or are write tools needed for the first demo?
3. Remote hosting target (pe-ai-l01 VM vs Container App) and who the users are beyond this team.
4. Does "deprecated" mean Commvault is steering everyone to the hosted MCP Service package (11.46.20+,
   `https://<CC>/commandcenter/mcp`)? The lab is on 11.46.40 but the endpoint returns 404, so the package is not installed
   there. Worth enabling later as a comparison point.

## Sources

- Upstream repo: https://github.com/Commvault/commvault-mcp-server
- Deploy docs (hosted MCP Service vs self-hosted): https://documentation.commvault.com/v11/software/deploy_commvault_mcp_server.html
- Access tokens for REST APIs: https://documentation.commvault.com/11.44/software/access_tokens_for_rest_apis.html
- Creating an access token: https://documentation.commvault.com/v11/commcell-console/creating_access_token.html
- Renew endpoint: https://api.commvault.com/docs/latest/api/cv/OpenAPI3/renew-accesstoken/
- REST API overview: https://documentation.commvault.com/v11/essential/rest_api_overview.html
