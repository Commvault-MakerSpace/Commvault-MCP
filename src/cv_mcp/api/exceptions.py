from __future__ import annotations

from typing import Any


class CommvaultError(Exception):
    """Base exception for all errors raised by this package."""


class CommvaultApiError(CommvaultError):
    """Exception raised when the API returns an error response.

    Attributes:
        status_code: The HTTP status code returned by the server, or None if
            the error occurred before a response was received (e.g., network
            error or invalid endpoint).
        message: A human-readable description of the error.
        body: The raw response body (parsed JSON or string) when available.
    """

    def __init__(
        self,
        status_code: int | None,
        message: str,
        body: Any = None,
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.body = body
        super().__init__(self.__str__())

    def __str__(self) -> str:
        if self.status_code is not None:
            return f"HTTP {self.status_code}: {self.message}"
        return self.message


class CommvaultAuthError(CommvaultApiError):
    """Exception raised when authentication fails and cannot be recovered."""
