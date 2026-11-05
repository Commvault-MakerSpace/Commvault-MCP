"""Command line entry point: `cv-mcp check` and `cv-mcp serve`."""

from __future__ import annotations

import argparse
import asyncio
import sys

from cv_mcp import __version__
from cv_mcp.api.exceptions import CommvaultError
from cv_mcp.api.paths import COMMSERV, WHOAMI
from cv_mcp.api.tokens import TokenError
from cv_mcp.config import ConfigError, Settings, load_env_file
from cv_mcp.logging import configure_logging


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cv-mcp", description="MCP server for Commvault Command Center")
    p.add_argument("--version", action="version", version=f"cv-mcp {__version__}")
    p.add_argument("--env-file", help="dotenv file to load before reading CV_* variables")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="verify connectivity and the access token (whoami + CommServe version)")
    serve = sub.add_parser("serve", help="run the MCP server")
    serve.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    serve.add_argument("--host", default="127.0.0.1", help="bind address for http transport")
    serve.add_argument("--port", type=int, default=8080, help="port for http transport")
    serve.add_argument("--path", default="/mcp", help="URL path for http transport")
    return p


async def _check(settings: Settings) -> int:
    from cv_mcp.server import build_client

    async with build_client(settings) as client:
        me = await client.get(WHOAMI)
        cs = await client.get(COMMSERV)
    commcell = cs.get("commcell", {})
    print(f"server:   {settings.server_url}")
    print(f"user:     {me.get('userName')} ({me.get('fullName')}, id {me.get('userId')})")
    cc_id, cc_host = commcell.get("commCellId"), cs.get("hostName")
    print(f"commcell: {commcell.get('commCellName')} (id {cc_id}, host {cc_host})")
    print(f"version:  {cs.get('csVersionInfo')}")
    print(f"writes:   {'enabled' if settings.allow_writes else 'disabled'}")
    return 0


def _serve(settings: Settings, args: argparse.Namespace) -> int:
    from cv_mcp.server import create_server

    mcp = create_server(settings)
    if args.transport == "stdio":
        mcp.run(transport="stdio", show_banner=False)
    else:
        mcp.run(transport="http", host=args.host, port=args.port, path=args.path, show_banner=False)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        load_env_file(args.env_file)
        settings = Settings.from_env()
    except ConfigError as e:
        print(f"cv-mcp: {e}", file=sys.stderr)
        return 2
    configure_logging(settings.log_level)
    try:
        if args.command == "check":
            return asyncio.run(_check(settings))
        return _serve(settings, args)
    except (TokenError, CommvaultError) as e:
        print(f"cv-mcp: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
