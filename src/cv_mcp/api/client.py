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

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from cv_mcp.api.exceptions import CommvaultApiError, CommvaultAuthError
from cv_mcp.api.paths import RENEW_TOKEN, sanitize_endpoint_path
from cv_mcp.api.tokens import TokenStore

logger = logging.getLogger("cv_mcp.api")


class CommvaultClient:
    """Async HTTP client for the Commvault Command Center API."""

    def __init__(
        self,
        *,
        server_url: str,
        token_store: TokenStore,
        ssl_verify: bool | str = True,
        local_address: str | None = None,
        timeout: float = 60.0,
        user_agent: str = "cv-mcp/0.1.0",
    ) -> None:
        self._token_store = token_store
        self._use_bearer = True
        self._refresh_lock = asyncio.Lock()

        base_url = server_url.rstrip("/") + "/commandcenter/api/"

        transport_kwargs: dict[str, Any] = {}
        if local_address is not None:
            transport_kwargs["transport"] = httpx.AsyncHTTPTransport(local_address=local_address)

        self._http = httpx.AsyncClient(
            base_url=base_url,
            verify=ssl_verify,
            timeout=httpx.Timeout(timeout, connect=10.0),
            headers={
                "Accept": "application/json",
                "User-Agent": user_agent,
            },
            **transport_kwargs,
        )

    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json: object | None = None,
        headers: dict[str, str] | None = None,
        max_retries: int = 2,
        retry_delay: float = 1.0,
    ) -> Any:
        # Sanitize endpoint
        try:
            sanitized_endpoint = sanitize_endpoint_path(endpoint)
        except ValueError as e:
            raise CommvaultApiError(status_code=None, message=f"Invalid endpoint: {e}") from e

        # Relative path: httpx merges it onto base_url (".../commandcenter/api/").
        url = sanitized_endpoint.lstrip("/")

        retries = 0
        while retries <= max_retries:
            try:
                # Build auth header
                access_token, _ = self._token_store.get()
                if self._use_bearer:
                    req_headers = {"Authorization": f"Bearer {access_token}"}
                else:
                    req_headers = {"Authtoken": access_token}

                if headers:
                    req_headers.update(headers)

                response = await self._http.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    json=json,
                    headers=req_headers,
                )

                # Handle 401 with Bearer auth fallback
                if response.status_code == 401 and self._use_bearer:
                    logger.info("Bearer auth rejected, falling back to Authtoken header")
                    self._use_bearer = False
                    continue

                # Handle 401 after fallback (refresh token)
                if response.status_code == 401:
                    logger.info("Received 401 Unauthorized. Attempting to refresh token...")
                    refreshed = await self._refresh_tokens()
                    if refreshed:
                        # Retry immediately once with new tokens
                        access_token, _ = self._token_store.get()
                        if self._use_bearer:
                            req_headers = {"Authorization": f"Bearer {access_token}"}
                        else:
                            req_headers = {"Authtoken": access_token}
                        if headers:
                            req_headers.update(headers)

                        response = await self._http.request(
                            method=method.upper(),
                            url=url,
                            params=params,
                            json=json,
                            headers=req_headers,
                        )
                        if response.status_code == 401:
                            raise CommvaultAuthError(
                                401, "Access token rejected and refresh failed; create a new access token"
                            )
                    else:
                        raise CommvaultAuthError(
                            401, "Access token rejected and refresh failed; create a new access token"
                        )

                # Handle other errors
                if response.status_code >= 500 or response.is_error:
                    message, body = self._error_details(response)
                    if response.status_code >= 500:
                        retries += 1
                        if retries > max_retries:
                            raise CommvaultApiError(response.status_code, message, body)
                        backoff = retry_delay * (2 ** (retries - 1))
                        logger.warning(
                            "%s %s failed with HTTP %s, retrying in %.1fs",
                            method.upper(),
                            sanitized_endpoint,
                            response.status_code,
                            backoff,
                        )
                        await asyncio.sleep(backoff)
                        continue

                    # 4xx other than 401
                    raise CommvaultApiError(response.status_code, message, body)

                # Success
                if not response.content:
                    return {}
                try:
                    result = response.json()
                except ValueError as e:
                    raise CommvaultApiError(response.status_code, "Non-JSON response from server") from e

                logger.debug(
                    "%s %s -> %s (%d bytes)",
                    method.upper(),
                    sanitized_endpoint,
                    response.status_code,
                    len(response.content),
                )
                return result

            except httpx.TransportError as e:
                retries += 1
                if retries > max_retries:
                    raise CommvaultApiError(None, f"Connection to {self._http.base_url} failed: {e}") from e
                backoff = retry_delay * (2 ** (retries - 1))
                logger.warning("%s %s: %s, retrying in %.1fs", method.upper(), sanitized_endpoint, e, backoff)
                await asyncio.sleep(backoff)

        raise CommvaultApiError(None, "Retries exhausted")  # unreachable, keeps type checkers happy

    @staticmethod
    def _error_details(response: httpx.Response) -> tuple[str, object | None]:
        """Extract a human-readable message and the parsed body from an error response."""
        body: object | None = None
        try:
            body = response.json()
        except ValueError:
            return response.reason_phrase or f"HTTP {response.status_code}", None
        message: str | None = None
        if isinstance(body, dict):
            err_list = body.get("errList")
            message = (
                body.get("errorMessage")
                or (err_list[0].get("errLogMessage") if isinstance(err_list, list) and err_list else None)
                or body.get("error")
            )
        return str(message) if message else (response.reason_phrase or f"HTTP {response.status_code}"), body

    async def _refresh_tokens(self) -> bool:
        """
        Refresh the access/refresh token pair via /V4/AccessToken/Renew.

        Thread-safety:
            Refresh tokens are single-use on the CommServe. If two tasks call
            this concurrently with the same refresh token, the first wins and
            the second gets HTTP 500 from /V4/AccessToken/Renew, which then
            cascades into "Failed to refresh token" errors for every in-flight
            request.

            To prevent that, we serialize callers on `_refresh_lock` and
            double-check the in-memory access token after acquiring the lock.
            If another task already rotated the token while we were waiting,
            we skip the network call and reuse the freshly stored token.
        """
        # Snapshot the access token BEFORE acquiring the lock.
        snapshot_access_token, _ = self._token_store.get()

        async with self._refresh_lock:
            current_access_token, current_refresh_token = self._token_store.get()

            if current_access_token != snapshot_access_token:
                logger.info(
                    "Access token already refreshed by a concurrent request; "
                    "reusing the rotated token instead of calling /V4/AccessToken/Renew again."
                )
                return True

            try:
                payload = {"accessToken": current_access_token, "refreshToken": current_refresh_token}
                # Use self._http directly: no Authorization header on the renew call.
                response = await self._http.post(RENEW_TOKEN, json=payload)
                if not response.is_success:
                    logger.warning("Token renew failed: HTTP %s", response.status_code)
                    return False
                data = response.json()
                new_access_token = data.get("accessToken")
                new_refresh_token = data.get("refreshToken")
                if not new_access_token or not new_refresh_token:
                    logger.warning("Token renew response did not contain a new token pair")
                    return False
                self._token_store.set(new_access_token, new_refresh_token)
                self._use_bearer = True
                logger.info("Access token renewed")
                return True
            except (httpx.HTTPError, ValueError) as e:
                logger.warning("Token renew failed: %s", type(e).__name__)
                return False

    async def get(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make a GET request to the API."""
        return await self.request("GET", endpoint, params=params, headers=headers)

    async def post(
        self,
        endpoint: str,
        *,
        json: object | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make a POST request to the API."""
        return await self.request("POST", endpoint, json=json, params=params, headers=headers)

    async def put(
        self,
        endpoint: str,
        *,
        json: object | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make a PUT request to the API."""
        return await self.request("PUT", endpoint, json=json, params=params, headers=headers)

    async def delete(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make a DELETE request to the API."""
        return await self.request("DELETE", endpoint, params=params, headers=headers)

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()

    async def __aenter__(self) -> CommvaultClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.aclose()
