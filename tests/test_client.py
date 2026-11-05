import asyncio
import json

import httpx
import pytest
import respx

from cv_mcp.api.client import CommvaultClient
from cv_mcp.api.exceptions import CommvaultApiError, CommvaultAuthError
from cv_mcp.api.tokens import MemoryTokenStore


@pytest.fixture
async def client():
    token_store = MemoryTokenStore("acc1", "ref1")
    c = CommvaultClient(
        server_url="https://cc.test",
        token_store=token_store,
    )
    yield c
    await c.aclose()


# 1. GET success
@respx.mock
async def test_get_success(client):
    route = respx.get("https://cc.test/commandcenter/api/v2/whoami").respond(200, json={"userName": "admin"})

    result = await client.get("v2/whoami")

    assert result == {"userName": "admin"}
    assert route.call_count == 1
    last_req = route.calls.last.request
    assert last_req.headers["Authorization"] == "Bearer acc1"


# 2. Leading slash is tolerated
@respx.mock
async def test_get_leading_slash_tolerated(client):
    route = respx.get("https://cc.test/commandcenter/api/v2/whoami").respond(200, json={"userName": "admin"})

    result = await client.get("/v2/whoami")

    assert result == {"userName": "admin"}
    assert route.call_count == 1


# 3. Bearer rejected then Authtoken accepted
@respx.mock
async def test_bearer_rejected_then_authtoken_accepted(client):
    route = respx.get("https://cc.test/commandcenter/api/v2/whoami").mock(
        side_effect=[
            httpx.Response(401),
            httpx.Response(200, json={"ok": True}),
        ]
    )

    result = await client.get("v2/whoami")

    assert result == {"ok": True}
    assert route.call_count == 2
    last_req = route.calls.last.request
    assert "Authtoken" in last_req.headers
    assert last_req.headers["Authtoken"] == "acc1"
    assert "Authorization" not in last_req.headers


# 4. Refresh after 401 on both auth styles
@respx.mock
async def test_refresh_after_401_on_both_auth_styles(client):
    whoami_route = respx.get("https://cc.test/commandcenter/api/v2/whoami").mock(
        side_effect=[
            httpx.Response(401),
            httpx.Response(401),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    renew_route = respx.post("https://cc.test/commandcenter/api/V4/AccessToken/Renew").respond(
        200, json={"accessToken": "acc2", "refreshToken": "ref2"}
    )

    result = await client.get("v2/whoami")

    assert result == {"ok": True}
    assert renew_route.call_count == 1
    renew_req = renew_route.calls.last.request
    assert json.loads(renew_req.content) == {"accessToken": "acc1", "refreshToken": "ref1"}
    assert "Authorization" not in renew_req.headers

    access_token, refresh_token = client._token_store.get()
    assert access_token == "acc2"
    assert refresh_token == "ref2"

    last_whoami_req = whoami_route.calls.last.request
    assert last_whoami_req.headers["Authorization"] == "Bearer acc2"


# 5. Refresh failure raises CommvaultAuthError
@respx.mock
async def test_refresh_failure_raises_auth_error(client):
    respx.get("https://cc.test/commandcenter/api/v2/whoami").mock(
        side_effect=[
            httpx.Response(401),
            httpx.Response(401),
        ]
    )
    respx.post("https://cc.test/commandcenter/api/V4/AccessToken/Renew").respond(500)

    with pytest.raises(CommvaultAuthError) as exc_info:
        await client.get("v2/whoami")

    assert exc_info.value.status_code == 401


# 6. Concurrent 401s renew only once
@respx.mock
async def test_concurrent_401s_renew_only_once(client):
    respx.get("https://cc.test/commandcenter/api/Client").mock(
        side_effect=[
            httpx.Response(401),
            httpx.Response(200, json={"id": 1}),
        ]
    )
    respx.get("https://cc.test/commandcenter/api/Job").mock(
        side_effect=[
            httpx.Response(401),
            httpx.Response(200, json={"id": 2}),
        ]
    )
    renew_route = respx.post("https://cc.test/commandcenter/api/V4/AccessToken/Renew").respond(
        200, json={"accessToken": "acc_new", "refreshToken": "ref_new"}
    )

    results = await asyncio.gather(
        client.get("Client"),
        client.get("Job"),
    )

    assert results == [{"id": 1}, {"id": 2}]
    assert renew_route.call_count == 1


# 7. 5xx retried then succeeds
@respx.mock
async def test_5xx_retried_then_succeeds(client):
    route = respx.get("https://cc.test/commandcenter/api/Client").mock(
        side_effect=[
            httpx.Response(502),
            httpx.Response(503),
            httpx.Response(200, json={"ok": True}),
        ]
    )

    result = await client.request("GET", "Client", retry_delay=0.0)

    assert result == {"ok": True}
    assert route.call_count == 3


# 8. 5xx exhausted raises CommvaultApiError
@respx.mock
async def test_5xx_exhausted_raises_api_error(client):
    route = respx.get("https://cc.test/commandcenter/api/Client").mock(
        side_effect=[
            httpx.Response(502),
            httpx.Response(503),
        ]
    )

    with pytest.raises(CommvaultApiError) as exc_info:
        await client.request("GET", "Client", max_retries=1, retry_delay=0.0)

    assert exc_info.value.status_code == 503
    assert route.call_count == 2


# 9. 4xx not retried
@respx.mock
async def test_4xx_not_retried(client):
    route = respx.get("https://cc.test/commandcenter/api/Client").respond(
        404, json={"errorMessage": "No such client"}
    )

    with pytest.raises(CommvaultApiError) as exc_info:
        await client.get("Client")

    assert str(exc_info.value) == "HTTP 404: No such client"
    assert route.call_count == 1


# 10. Error message from errList
@respx.mock
async def test_error_message_from_errlist(client):
    respx.get("https://cc.test/commandcenter/api/Client").respond(
        400, json={"errList": [{"errLogMessage": "Bad filter"}]}
    )

    with pytest.raises(CommvaultApiError) as exc_info:
        await client.get("Client")

    assert str(exc_info.value) == "HTTP 400: Bad filter"


# 11. Transport error retried then succeeds / exhausted
@respx.mock
async def test_transport_error_retried_then_succeeds(client):
    route = respx.get("https://cc.test/commandcenter/api/Client").mock(
        side_effect=[
            httpx.ConnectError("boom"),
            httpx.Response(200, json={"ok": True}),
        ]
    )

    result = await client.request("GET", "Client", retry_delay=0.0)

    assert result == {"ok": True}
    assert route.call_count == 2


@respx.mock
async def test_transport_error_exhausted_raises_api_error(client):
    respx.get("https://cc.test/commandcenter/api/Client").mock(
        side_effect=[
            httpx.ConnectError("boom"),
        ]
    )

    with pytest.raises(CommvaultApiError) as exc_info:
        await client.request("GET", "Client", max_retries=0, retry_delay=0.0)

    assert exc_info.value.status_code is None


# 12. Non-JSON 200 body raises CommvaultApiError
@respx.mock
async def test_non_json_200_raises_api_error(client):
    respx.get("https://cc.test/commandcenter/api/Client").respond(200, content=b"not json")

    with pytest.raises(CommvaultApiError) as exc_info:
        await client.get("Client")

    assert str(exc_info.value) == "HTTP 200: Non-JSON response from server"


# 13. Empty 200 body returns {}
@respx.mock
async def test_empty_200_body_returns_dict(client):
    respx.get("https://cc.test/commandcenter/api/Client").respond(200, content=b"")

    result = await client.get("Client")

    assert result == {}


# 14. Path traversal endpoint raises CommvaultApiError before HTTP call
@respx.mock
async def test_path_traversal_raises_api_error(client):
    with pytest.raises(CommvaultApiError) as exc_info:
        await client.get("Client/../etc")

    assert "Invalid endpoint" in str(exc_info.value)
    assert respx.calls.call_count == 0
