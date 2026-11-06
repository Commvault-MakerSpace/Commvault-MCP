# cv-mcp

MCP server for Commvault Command Center. It lets Claude Code, Claude Desktop and other MCP clients query a
CommCell (jobs, clients, storage, plans, schedules, users, security posture) through the Command Center REST
API, and operate it only when writes are explicitly enabled.

## Origin

This repository is a clone of the open-source
[Commvault/commvault-mcp-server](https://github.com/Commvault/commvault-mcp-server) project on GitHub, which is
published under the Apache 2.0 license and is open to community development. Issues, feature requests and pull
requests for the upstream project go through its GitHub repository. This copy is maintained by the Product
Experience team for lab work and demos; see [Credits](#credits) for what was ported and `NOTICE` for attribution.

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

## Feature areas

The upstream project organizes its tools into the categories below. Job, Commcell and Client Management are
implemented in this repository today (see [Tools](#tools)); the remaining areas are on the roadmap in `PLAN.md`
or are upstream-only integrations.

| Category | Features |
|----------|----------|
| **Job Management** | • View job details and history<br>• Control jobs (suspend, resume, resubmit, kill)<br>• Monitor job status and performance |
| **Commcell Management** | • Retrieve SLA status and compliance<br>• View security posture and scores<br>• Access storage space utilization metrics<br>• Get commcell details and entity counts |
| **Client Management** | • Access client groups and client information<br>• Manage subclients and client properties<br>• View client associations |
| **Storage Management** | • View storage policies and configurations<br>• Access storage pool information<br>• Monitor storage resources |
| **User Management** | • List users and user groups<br>• Access security associations |
| **Plan Management** | • View plan configurations and details<br>• Access plan components and settings |
| **Schedule Management** | • Access backup schedules<br>• View schedule configurations<br>• Monitor schedule performance |
| **DocuSign Integration** | • Setup Docusign Vault & Workflow<br>• Backup envelopes to Commvault S3 vault<br>• List & restore DocuSign envelope backups |
| **Salesforce Integration** | • Resolve Salesforce org ID to Commvault client<br>• Browse backed-up Salesforce object records from latest snapshot<br>• Filter records with optional WHERE-clause queries<br>• Paginated access to large record sets |

## Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Commvault 11.38 or later for access tokens (the dev lab runs 11.46)
- Network access to the Command Center URL

## Install

```bash
git clone https://pe-ai-l01.eastus2.cloudapp.azure.com:8443/product-experience/cv-mcp.git
cd cv-mcp
uv sync
```

`uv sync` installs Python 3.12 from `.python-version` if it is not already present.

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
      "args": ["run", "--env-file", "C:/Users/zwkru/.config/cv-mcp/lab.env", "cv-mcp", "serve"]
    }
  }
}
```

The `--env-file` path is absolute and machine-specific. After cloning on another machine, change it to the
location of your own env file before opening the project in Claude Code or the Claude desktop app.

`cv-mcp serve --transport http --host 127.0.0.1 --port 8080` exposes Streamable HTTP on `/mcp` for remote
clients; protocol-level authentication for that mode arrives in phase 4.

## Deploy on a Windows lab VM

These steps set up a second copy of the server on a Windows Server 2025 VM that sits on the lab network, for
example to develop and test without the VPN. The Claude desktop app is assumed to be installed already.

1. Install git and uv in PowerShell. Python is not needed separately; `uv sync` fetches 3.12.

   ```powershell
   winget install --id Git.Git -e
   winget install --id astral-sh.uv -e
   ```

2. Clone and sync as in [Install](#install).

3. Create a **new** token pair for the VM in Command Center under Profile > Access tokens. Never copy `lab.env`
   from another machine: the refresh token is single-use, so two servers sharing one pair invalidate each
   other on the first renewal.

4. Create `%USERPROFILE%\.config\cv-mcp\lab.env` from `.env.example`:

   - `CV_SERVER_URL` is the Command Center URL, e.g. `https://commvaultlab.lab.local`
   - the new `CV_ACCESS_TOKEN` and `CV_REFRESH_TOKEN`
   - `CV_TOKEN_FILE=C:/Users/<you>/.config/cv-mcp/tokens.json` so renewals survive restarts
   - `CV_SSL_VERIFY=false`, or export the server certificate and point `CV_CA_BUNDLE` at it
   - leave `CV_LOCAL_ADDRESS` empty; the VM reaches the lab directly

   Restrict the file to your account (the Windows equivalent of `chmod 600`):

   ```powershell
   icacls "$env:USERPROFILE\.config\cv-mcp\lab.env" /inheritance:r /grant:r "$env:USERNAME:F"
   ```

5. If the VM cannot resolve the Command Center hostname, add it to
   `C:\Windows\System32\drivers\etc\hosts`.

6. Verify the connection:

   ```powershell
   uv run --env-file $env:USERPROFILE\.config\cv-mcp\lab.env cv-mcp check
   ```

7. Edit the `--env-file` path in `.mcp.json` to match step 4, then open the repo folder as a project in the
   Claude desktop app. Run `get_jobs_list` once to confirm the server is registered and reachable.

8. Run `uv run pytest` for the offline suite and `uv run pytest -m live` for the lab smoke tests.

Keep `CV_MCP_ALLOW_WRITES=false` until you deliberately want the suspend, kill and run-backup tools registered.

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
