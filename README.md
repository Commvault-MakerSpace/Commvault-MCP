# cv-mcp

MCP server for Commvault Command Center. It lets Claude Code, Claude Desktop and other MCP clients query a
CommCell (jobs, clients, storage, plans, schedules, users, security posture) through the Command Center REST
API, and operate it only when writes are explicitly enabled.

## Status

Working against the lab today: project scaffold, async API client with token renewal, token store, the `cv-mcp check`
CLI, and the first three tool areas (jobs, CommCell, clients) with 17 read tools and 6 write tools gated behind
`CV_MCP_ALLOW_WRITES`. Storage, plans, schedules and users tools are next, followed by an offline replay mode for demos.

## Tools

| Area | Read tools | Write tools (flag required) |
|---|---|---|
| CommCell | get_commcell_details, get_sla_status, get_security_posture, get_security_score, get_storage_space_utilization | send_logs_for_commcell |
| Jobs | get_jobs_list, get_failed_jobs, get_job_detail, get_job_task_details, get_job_retention, get_job_events | suspend_job, resume_job, resubmit_job, kill_job, send_logs_for_job |
| Clients | get_client_list, get_client_id, get_client_group_list, get_client_group_properties, get_subclient_list, get_subclient_properties | run_backup_for_subclient |

Times are epoch seconds and sizes are bytes unless a tool says otherwise. Responses are slimmed for the model;
`*_properties` tools return the raw CommServe payload.

## Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Commvault 11.38 or later for access tokens (the dev lab runs 11.46)
- Network access to the Command Center URL

## Install

```bash
uv sync
```

## Configuration

All settings come from `CV_*` environment variables. Keep them in a file outside the repo, for example
`~/.config/cv-mcp/lab.env` with mode 600, and pass it with `--env-file`. See `.env.example`.

| Variable | Meaning |
|---|---|
| `CV_SERVER_URL` | Command Center base URL, e.g. `https://cc.example.com` (no path) |
| `CV_ACCESS_TOKEN` | Access token from Profile > Access tokens |
| `CV_REFRESH_TOKEN` | Matching refresh token; single-use, rotated by the server on renew |
| `CV_TOKEN_FILE` | Optional JSON file where rotated tokens are persisted; seeded from the two variables above |
| `CV_SSL_VERIFY` | `true` (default) or `false` for labs with self-signed certificates |
| `CV_CA_BUNDLE` | Path to a CA bundle or exported server certificate; takes precedence over `CV_SSL_VERIFY` |
| `CV_LOCAL_ADDRESS` | Local IP to bind outgoing connections to, e.g. a VPN adapter address |
| `CV_MCP_ALLOW_WRITES` | `true` registers tools with side effects (suspend/kill jobs, run backups, ...) |
| `CV_LOG_LEVEL` | `INFO` (default) or `DEBUG`; logs go to stderr and never contain tokens |
| `CV_TIMEOUT` | Request timeout in seconds (default 60) |

## Verify the connection

```bash
uv run --env-file ~/.config/cv-mcp/lab.env cv-mcp check
```

Calls `v2/whoami` and `CommServ` and prints the user, CommCell name and version.

## Run with Claude Code

`.mcp.json` in this repo registers the server over stdio:

```json
{
  "mcpServers": {
    "cv-mcp": {
      "command": "uv",
      "args": ["run", "--env-file", "/home/zwkru/.config/cv-mcp/lab.env", "cv-mcp", "serve"]
    }
  }
}
```

`cv-mcp serve --transport http --host 127.0.0.1 --port 8080` exposes Streamable HTTP on `/mcp` for remote
clients; protocol-level authentication for that mode arrives in phase 4.

## Development

```bash
uv run pytest                 # unit tests with respx mocks, no CommServe needed
uv run pytest -m live         # smoke tests against the lab (load the env file first)
uv run ruff check . && uv run ruff format --check .
```

Working agreements for Claude Code are in `CLAUDE.md`; the roadmap and open questions are in `PLAN.md`.

## Credits

The API client, path sanitizer, response shaping and endpoint map are ported from
[Commvault/commvault-mcp-server](https://github.com/Commvault/commvault-mcp-server) (Apache 2.0). See `NOTICE`
and `LICENSE`.
