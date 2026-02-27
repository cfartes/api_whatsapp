from __future__ import annotations

import json

import httpx
import pytest

from whatsapp_cloud_api import AsyncWhatsAppClient
from whatsapp_cloud_api.exceptions import WhatsAppAPIError


@pytest.mark.asyncio
async def test_async_send_text_returns_typed_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/123/messages")
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["text"]["body"] == "mensagem async"
        return httpx.Response(
            status_code=200,
            json={
                "messaging_product": "whatsapp",
                "contacts": [{"input": "5511888888888", "wa_id": "5511888888888"}],
                "messages": [{"id": "wamid.async"}],
            },
        )

    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://graph.facebook.com/v20.0",
    )
    client = AsyncWhatsAppClient("token", "123", http_client=http_client)

    try:
        response = await client.send_text(to="5511888888888", body="mensagem async")
    finally:
        await http_client.aclose()

    assert response.messages[0].id == "wamid.async"


@pytest.mark.asyncio
async def test_async_mark_as_read_returns_success() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, json={"success": True})

    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://graph.facebook.com/v20.0",
    )
    client = AsyncWhatsAppClient("token", "123", http_client=http_client)

    try:
        response = await client.mark_as_read(message_id="wamid.async.1")
    finally:
        await http_client.aclose()

    assert response.success is True


@pytest.mark.asyncio
async def test_async_retry_for_post_when_enabled() -> None:
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                status_code=429,
                headers={"Retry-After": "0"},
                json={"error": {"message": "Rate limit", "code": 4}},
            )
        return httpx.Response(
            status_code=200,
            json={
                "messaging_product": "whatsapp",
                "contacts": [{"input": "5511888888888", "wa_id": "5511888888888"}],
                "messages": [{"id": "wamid.async.retry"}],
            },
        )

    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://graph.facebook.com/v20.0",
    )
    client = AsyncWhatsAppClient(
        "token",
        "123",
        http_client=http_client,
        max_retries=2,
        backoff_factor=0,
        retry_methods={"POST"},
    )

    try:
        response = await client.send_text(to="5511888888888", body="mensagem async")
    finally:
        await http_client.aclose()

    assert call_count == 2
    assert response.messages[0].id == "wamid.async.retry"


@pytest.mark.asyncio
async def test_async_no_retry_for_post_by_default() -> None:
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            status_code=429,
            json={"error": {"message": "Rate limit", "code": 4}},
        )

    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://graph.facebook.com/v20.0",
    )
    client = AsyncWhatsAppClient("token", "123", http_client=http_client, max_retries=3, backoff_factor=0)

    try:
        with pytest.raises(WhatsAppAPIError) as exc_info:
            await client.send_text(to="5511888888888", body="mensagem async")
    finally:
        await http_client.aclose()

    assert call_count == 1
    assert exc_info.value.status_code == 429
