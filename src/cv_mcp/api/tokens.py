from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

logger = logging.getLogger("cv_mcp.tokens")


class TokenError(Exception):
    """Raised when tokens are unavailable or invalid."""


class TokenStore(Protocol):
    def get(self) -> tuple[str, str]: ...  # (access_token, refresh_token); raise TokenError if unavailable

    def set(self, access_token: str, refresh_token: str) -> None: ...


class MemoryTokenStore:
    """Holds a pair of tokens in memory. Note: not persisted."""

    def __init__(self, access_token: str, refresh_token: str) -> None:
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._warned = False

    def get(self) -> tuple[str, str]:
        return (self._access_token, self._refresh_token)

    def set(self, access_token: str, refresh_token: str) -> None:
        self._access_token = access_token
        self._refresh_token = refresh_token
        if not self._warned:
            logger.warning(
                "Rotated tokens are held in memory only and will be lost on restart; "
                "set CV_TOKEN_FILE to persist them"
            )
            self._warned = True


class FileTokenStore:
    """JSON file-based token store with atomic writes."""

    def __init__(
        self,
        path: str | os.PathLike,
        *,
        seed: tuple[str, str] | None = None,
    ) -> None:
        self._path = Path(path).expanduser()
        if not self._path.exists():
            if seed is not None:
                access_token, refresh_token = seed
                self.set(access_token, refresh_token)
            else:
                raise TokenError(
                    f"Token file {self._path} does not exist; "
                    "set CV_ACCESS_TOKEN and CV_REFRESH_TOKEN to seed it"
                )

    def get(self) -> tuple[str, str]:
        if not self._path.exists():
            raise TokenError(f"Token file missing: {self._path}")
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            access_token = data["access_token"]
            refresh_token = data["refresh_token"]
            return (access_token, refresh_token)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise TokenError(f"Invalid token file {self._path}: {e}") from e

    def set(self, access_token: str, refresh_token: str) -> None:
        dir_path = self._path.parent
        dir_path.mkdir(parents=True, exist_ok=True)
        tmp_path: str | None = None
        try:
            fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                        "rotated_at": datetime.now(UTC).isoformat(),
                    },
                    f,
                )
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, self._path)
        except Exception as e:
            # Clean up temp file if it still exists
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            raise TokenError(f"Failed to save tokens to {self._path}: {e}") from e
        logger.info("Tokens rotated and saved to %s", self._path)


def build_token_store(
    *,
    access_token: str | None,
    refresh_token: str | None,
    token_file: str | None,
) -> TokenStore:
    if token_file is not None:
        seed = (access_token, refresh_token) if (access_token and refresh_token) else None
        return FileTokenStore(token_file, seed=seed)
    if access_token and refresh_token:
        return MemoryTokenStore(access_token, refresh_token)
    raise TokenError(
        "Set CV_ACCESS_TOKEN and CV_REFRESH_TOKEN, or CV_TOKEN_FILE pointing at an existing token file"
    )
