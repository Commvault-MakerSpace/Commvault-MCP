from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


class ConfigError(Exception):
    """Raised when configuration is invalid."""


def _parse_bool(value: str, *, name: str) -> bool:
    if value.lower() in ("true", "1", "yes"):
        return True
    if value.lower() in ("false", "0", "no"):
        return False
    raise ConfigError(f"Invalid boolean value for {name}: {value!r}")


def load_env_file(path: str | None) -> None:
    if path is not None:
        from dotenv import load_dotenv

        p = os.path.expanduser(path)
        if not os.path.isfile(p):
            raise ConfigError(f"Environment file not found: {p}")
        load_dotenv(p, override=False)


@dataclass(frozen=True)
class Settings:
    server_url: str
    access_token: str | None
    refresh_token: str | None
    token_file: str | None
    ssl_verify: bool = True
    ca_bundle: str | None = None
    local_address: str | None = None
    allow_writes: bool = False
    log_level: str = "INFO"
    timeout: float = 60.0

    @property
    def verify(self) -> bool | str:
        if self.ca_bundle is not None:
            return self.ca_bundle
        return self.ssl_verify

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        if env is None:
            env = os.environ

        server_url = env.get("CV_SERVER_URL", "").strip()
        if not server_url:
            raise ConfigError("CV_SERVER_URL is required and must be set")
        if not (server_url.startswith("http://") or server_url.startswith("https://")):
            raise ConfigError(f"CV_SERVER_URL must start with http:// or https://, got: {server_url!r}")
        server_url = server_url.rstrip("/")

        access_token = env.get("CV_ACCESS_TOKEN", "").strip() or None
        refresh_token = env.get("CV_REFRESH_TOKEN", "").strip() or None
        token_file = env.get("CV_TOKEN_FILE", "").strip() or None

        ssl_verify_str = env.get("CV_SSL_VERIFY", "true").strip().lower()
        ssl_verify = _parse_bool(ssl_verify_str, name="CV_SSL_VERIFY")

        ca_bundle = env.get("CV_CA_BUNDLE", "").strip() or None

        local_address = env.get("CV_LOCAL_ADDRESS", "").strip() or None

        allow_writes_str = env.get("CV_MCP_ALLOW_WRITES", "false").strip().lower()
        allow_writes = _parse_bool(allow_writes_str, name="CV_MCP_ALLOW_WRITES")

        log_level = env.get("CV_LOG_LEVEL", "INFO").strip().upper()

        timeout_str = env.get("CV_TIMEOUT", "60.0").strip()
        try:
            timeout = float(timeout_str)
        except ValueError as e:
            raise ConfigError(f"CV_TIMEOUT must be a number, got: {timeout_str!r}") from e

        return cls(
            server_url=server_url,
            access_token=access_token,
            refresh_token=refresh_token,
            token_file=token_file,
            ssl_verify=ssl_verify,
            ca_bundle=ca_bundle,
            local_address=local_address,
            allow_writes=allow_writes,
            log_level=log_level,
            timeout=timeout,
        )
