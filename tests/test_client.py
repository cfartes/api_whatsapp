from __future__ import annotations

import json

import httpx
import pytest

from whatsapp_cloud_api import WhatsAppClient
from whatsapp_cloud_api.exceptions import WhatsAppAPIError


def test_send_text_returns_typed_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/123/messages")
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["type"] == "text"
        return httpx.Response(
            status_code=200,
            json={
                "messaging_product": "whatsapp",
                "contacts": [{"input": "5511999999999", "wa_id": "5511999999999"}],
                "messages": [{"id": "wamid.test"}],
            },
        )

    http_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://graph.facebook.com/v20.0",
    )
    client = WhatsAppClient("token", "123", http_client=http_client)

    try:
        response = client.send_text(to="5511999999999", body="oi")
    finally:
        http_client.close()

    assert response.messages[0].id == "wamid.test"
    assert response.contacts[0].wa_id == "5511999999999"


def test_mark_as_read_returns_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/123/messages")
        return httpx.Response(status_code=200, json={"success": True})

    http_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://graph.facebook.com/v20.0",
    )
    client = WhatsAppClient("token", "123", http_client=http_client)

    try:
        response = client.mark_as_read(message_id="wamid.1")
    finally:
        http_client.close()

    assert response.success is True


def test_api_error_raises_whatsapp_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=400,
            json={
                "error": {
                    "message": "Invalid parameter",
                    "type": "OAuthException",
                    "code": 100,
                    "error_subcode": 2494010,
                    "fbtrace_id": "trace-id",
                }
            },
        )

    http_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://graph.facebook.com/v20.0",
    )
    client = WhatsAppClient("token", "123", http_client=http_client)

    try:
        with pytest.raises(WhatsAppAPIError) as exc_info:
            client.send_text(to="5511999999999", body="oi")
    finally:
        http_client.close()

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == 100


def test_no_retry_for_post_by_default() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            status_code=429,
            json={"error": {"message": "Rate limit", "code": 4}},
        )

    http_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://graph.facebook.com/v20.0",
    )
    client = WhatsAppClient("token", "123", http_client=http_client, max_retries=3, backoff_factor=0)

    try:
        with pytest.raises(WhatsAppAPIError) as exc_info:
            client.send_text(to="5511999999999", body="oi")
    finally:
        http_client.close()

    assert call_count == 1
    assert exc_info.value.status_code == 429


def test_retry_for_post_when_enabled() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
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
                "contacts": [{"input": "5511999999999", "wa_id": "5511999999999"}],
                "messages": [{"id": "wamid.retry"}],
            },
        )

    http_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://graph.facebook.com/v20.0",
    )
    client = WhatsAppClient(
        "token",
        "123",
        http_client=http_client,
        max_retries=2,
        backoff_factor=0,
        retry_methods={"POST"},
    )

    try:
        response = client.send_text(to="5511999999999", body="oi")
    finally:
        http_client.close()

    assert call_count == 2
    assert response.messages[0].id == "wamid.retry"
