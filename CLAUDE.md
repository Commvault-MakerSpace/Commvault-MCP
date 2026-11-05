# cv-mcp working agreements

## Purpose
MCP server for Commvault Command Center (REST API). Lets Claude query a CommCell and, only when
`CV_MCP_ALLOW_WRITES=true`, operate it. Plan and phase status live in `PLAN.md`.

## Stack
Python 3.12 (`.python-version`), `uv`, `fastmcp` 4.x, async `httpx`, `pydantic`, `pytest` + `respx`, `ruff`.
Apache 2.0; code derived from Commvault/commvault-mcp-server is credited in `NOTICE`, keep the license headers.

## Layout
```text
src/cv_mcp/
  cli.py  server.py  config.py  logging.py
  api/client.py   # CommvaultClient: httpx, Bearer->Authtoken fallback, 401 -> renew under lock, retry
  api/tokens.py   # TokenStore: memory or JSON file, never keyring
  api/paths.py    # endpoint constants + sanitize_endpoint_path
  shaping/        # response slimming, one module per area
  tools/          # one module per area: jobs, commcell, clients, storage, plans, schedules, users
tests/fixtures/   # recorded JSON responses; unit tests never call a CommServe
```

## Conventions
- Tool params are `Annotated[T, Field(description=...)]`; docstrings state units (epoch seconds, bytes).
- Tools `raise ToolError(...)` on failure, never return error objects.
- Tools return slimmed dicts from `shaping/`, not raw CommServe payloads.
- Write tools (suspend/kill job, run backup, enable/disable schedule, set user enabled, send logs) are
  registered only when `CV_MCP_ALLOW_WRITES=true`; their descriptions name the side effect; one audit log line per call.
- Logging goes to stderr only (stdout is the stdio MCP transport). Never log tokens, headers or bodies.
- Mechanical work (porting tool bodies, docstrings, fixtures, boilerplate docs) goes to the local Mac mini model via
  `unsloth-mac-job`; review every output against the upstream source before committing.

## Secrets
- Tokens live only in `~/.config/cv-mcp/lab.env` (mode 600) outside the repo. `.env.example` documents names only.
- The refresh token is single-use: never call `V4/AccessToken/Renew` by hand or in tests against the lab.

## Lab access (dev target)
- `https://commvaultlab.lab.local` = 192.168.1.15, CommServe `pe-cv-l01.lab.local`, release 11 SP46.40, self-signed cert.
- The lab is behind the VPN adapter (WSL `eth6`) and its subnet overlaps the home LAN. Per boot:
  `sudo ip route add 192.168.1.15/32 dev eth6`, or set `CV_LOCAL_ADDRESS` to the VPN address. Hostname needs `/etc/hosts`.
- Hosted MCP Service (`/commandcenter/mcp`) is not enabled on this CommServe.

## Testing
- Unit tests use `tests/fixtures/*.json` with `respx`; CI never reaches a CommServe.
- Tests marked `live` are deselected by default; run them with `uv run pytest -m live` after loading the lab env.

## Commands
```bash
uv sync
uv run --env-file ~/.config/cv-mcp/lab.env cv-mcp check   # whoami + CommServe version
uv run --env-file ~/.config/cv-mcp/lab.env cv-mcp serve   # stdio transport
uv run pytest
uv run ruff check . && uv run ruff format --check .
```
