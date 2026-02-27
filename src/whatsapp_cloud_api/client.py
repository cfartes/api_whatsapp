from __future__ import annotations

import asyncio
import mimetypes
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable

import httpx

from .exceptions import WhatsAppAPIError
from .models import MarkAsReadResponse, MediaInfoResponse, MediaUploadResponse, SendMessageResponse

DEFAULT_RETRY_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
DEFAULT_RETRY_METHODS = frozenset({"GET"})


def _raise_for_api_error(response: httpx.Response, data: Any) -> None:
    if not response.is_error:
        return

    err = data.get("error", {}) if isinstance(data, dict) else {}
    raise WhatsAppAPIError(
        message=err.get("message") or f"HTTP {response.status_code}",
        status_code=response.status_code,
        error_type=err.get("type"),
        code=err.get("code"),
        error_subcode=err.get("error_subcode"),
        fbtrace_id=err.get("fbtrace_id"),
        details=data if isinstance(data, dict) else {"raw": data},
    )


def _parse_json_response(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        data = {}

    _raise_for_api_error(response, data)
    return data if isinstance(data, dict) else {"raw": data}


def _build_media_payload(
    *,
    media_id: str | None,
    link: str | None,
    caption: str | None,
    filename: str | None,
) -> dict[str, Any]:
    if not media_id and not link:
        raise ValueError("media_id or link is required")
    if media_id and link:
        raise ValueError("use only one of media_id or link")

    media_payload: dict[str, Any] = {}
    if media_id:
        media_payload["id"] = media_id
    if link:
        media_payload["link"] = link
    if caption:
        media_payload["caption"] = caption
    if filename:
        media_payload["filename"] = filename
    return media_payload


def _normalize_methods(methods: Iterable[str] | None) -> frozenset[str]:
    if methods is None:
        return DEFAULT_RETRY_METHODS
    return frozenset(method.upper() for method in methods)


def _parse_retry_after_seconds(retry_after: str | None) -> float | None:
    if not retry_after:
        return None

    retry_after = retry_after.strip()
    try:
        seconds = float(retry_after)
        return seconds if seconds > 0 else None
    except ValueError:
        pass

    try:
        parsed_date = parsedate_to_datetime(retry_after)
    except (TypeError, ValueError):
        return None

    if parsed_date.tzinfo is None:
        parsed_date = parsed_date.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    seconds = (parsed_date - now).total_seconds()
    return seconds if seconds > 0 else None


class _RetryMixin:
    max_retries: int
    backoff_factor: float
    max_backoff: float
    retry_status_codes: frozenset[int]
    retry_methods: frozenset[str]

    def _should_retry_method(self, method: str) -> bool:
        return method.upper() in self.retry_methods

    def _get_retry_delay(self, attempt: int, retry_after: str | None) -> float:
        header_delay = _parse_retry_after_seconds(retry_after)
        if header_delay is not None:
            return min(self.max_backoff, header_delay)

        exponential_delay = self.backoff_factor * (2**attempt)
        return min(self.max_backoff, exponential_delay)

    def _should_retry_response(self, response: httpx.Response) -> bool:
        return response.status_code in self.retry_status_codes


class WhatsAppClient(_RetryMixin):
    def __init__(
        self,
        access_token: str,
        phone_number_id: str,
        *,
        api_version: str = "v20.0",
        timeout: float = 20.0,
        base_url: str = "https://graph.facebook.com",
        http_client: httpx.Client | None = None,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        max_backoff: float = 8.0,
        retry_status_codes: Iterable[int] | None = None,
        retry_methods: Iterable[str] | None = None,
    ) -> None:
        if not access_token:
            raise ValueError("access_token is required")
        if not phone_number_id:
            raise ValueError("phone_number_id is required")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")

        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.api_version = api_version
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.max_backoff = max_backoff
        self.retry_status_codes = frozenset(retry_status_codes or DEFAULT_RETRY_STATUS_CODES)
        self.retry_methods = _normalize_methods(retry_methods)

        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(
            base_url=f"{self.base_url}/{self.api_version}",
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "WhatsAppClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def send_text(
        self,
        *,
        to: str,
        body: str,
        preview_url: bool = False,
        context_message_id: str | None = None,
    ) -> SendMessageResponse:
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body, "preview_url": preview_url},
        }
        if context_message_id:
            payload["context"] = {"message_id": context_message_id}
        data = self._request("POST", f"/{self.phone_number_id}/messages", json=payload)
        return SendMessageResponse.model_validate(data)

    def send_template(
        self,
        *,
        to: str,
        name: str,
        language_code: str = "pt_BR",
        components: list[dict[str, Any]] | None = None,
    ) -> SendMessageResponse:
        template: dict[str, Any] = {"name": name, "language": {"code": language_code}}
        if components:
            template["components"] = components

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": template,
        }
        data = self._request("POST", f"/{self.phone_number_id}/messages", json=payload)
        return SendMessageResponse.model_validate(data)

    def send_media(
        self,
        *,
        to: str,
        media_type: str,
        media_id: str | None = None,
        link: str | None = None,
        caption: str | None = None,
        filename: str | None = None,
    ) -> SendMessageResponse:
        media_payload = _build_media_payload(
            media_id=media_id,
            link=link,
            caption=caption,
            filename=filename,
        )
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": media_type,
            media_type: media_payload,
        }
        data = self._request("POST", f"/{self.phone_number_id}/messages", json=payload)
        return SendMessageResponse.model_validate(data)

    def upload_media(
        self,
        *,
        file_path: str | Path,
        mime_type: str | None = None,
        filename: str | None = None,
    ) -> MediaUploadResponse:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"file not found: {path}")

        guessed_mime, _ = mimetypes.guess_type(str(path))
        final_mime = mime_type or guessed_mime or "application/octet-stream"
        final_name = filename or path.name

        with path.open("rb") as file_handle:
            files = {
                "file": (final_name, file_handle, final_mime),
                "messaging_product": (None, "whatsapp"),
            }
            data = self._request(
                "POST",
                f"/{self.phone_number_id}/media",
                files=files,
                content_type_json=False,
            )
        return MediaUploadResponse.model_validate(data)

    def get_media(self, *, media_id: str) -> MediaInfoResponse:
        data = self._request("GET", f"/{media_id}")
        return MediaInfoResponse.model_validate(data)

    def mark_as_read(self, *, message_id: str) -> MarkAsReadResponse:
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        data = self._request("POST", f"/{self.phone_number_id}/messages", json=payload)
        return MarkAsReadResponse.model_validate(data)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        content_type_json: bool = True,
    ) -> dict[str, Any]:
        headers = None
        if not content_type_json:
            headers = {"Authorization": f"Bearer {self.access_token}"}

        attempt = 0
        can_retry_method = self._should_retry_method(method)

        while True:
            try:
                response = self._client.request(
                    method=method,
                    url=path,
                    json=json,
                    files=files,
                    headers=headers,
                )
            except httpx.HTTPError as exc:
                if not can_retry_method or attempt >= self.max_retries:
                    raise WhatsAppAPIError(message=f"HTTP communication error: {exc}") from exc
                delay = self._get_retry_delay(attempt, None)
                if delay > 0:
                    time.sleep(delay)
                attempt += 1
                continue

            if (
                can_retry_method
                and attempt < self.max_retries
                and self._should_retry_response(response)
            ):
                delay = self._get_retry_delay(attempt, response.headers.get("Retry-After"))
                if delay > 0:
                    time.sleep(delay)
                attempt += 1
                continue

            return _parse_json_response(response)


class AsyncWhatsAppClient(_RetryMixin):
    def __init__(
        self,
        access_token: str,
        phone_number_id: str,
        *,
        api_version: str = "v20.0",
        timeout: float = 20.0,
        base_url: str = "https://graph.facebook.com",
        http_client: httpx.AsyncClient | None = None,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        max_backoff: float = 8.0,
        retry_status_codes: Iterable[int] | None = None,
        retry_methods: Iterable[str] | None = None,
    ) -> None:
        if not access_token:
            raise ValueError("access_token is required")
        if not phone_number_id:
            raise ValueError("phone_number_id is required")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")

        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.api_version = api_version
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.max_backoff = max_backoff
        self.retry_status_codes = frozenset(retry_status_codes or DEFAULT_RETRY_STATUS_CODES)
        self.retry_methods = _normalize_methods(retry_methods)

        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=f"{self.base_url}/{self.api_version}",
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "AsyncWhatsAppClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def send_text(
        self,
        *,
        to: str,
        body: str,
        preview_url: bool = False,
        context_message_id: str | None = None,
    ) -> SendMessageResponse:
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body, "preview_url": preview_url},
        }
        if context_message_id:
            payload["context"] = {"message_id": context_message_id}
        data = await self._request("POST", f"/{self.phone_number_id}/messages", json=payload)
        return SendMessageResponse.model_validate(data)

    async def send_template(
        self,
        *,
        to: str,
        name: str,
        language_code: str = "pt_BR",
        components: list[dict[str, Any]] | None = None,
    ) -> SendMessageResponse:
        template: dict[str, Any] = {"name": name, "language": {"code": language_code}}
        if components:
            template["components"] = components

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": template,
        }
        data = await self._request("POST", f"/{self.phone_number_id}/messages", json=payload)
        return SendMessageResponse.model_validate(data)

    async def send_media(
        self,
        *,
        to: str,
        media_type: str,
        media_id: str | None = None,
        link: str | None = None,
        caption: str | None = None,
        filename: str | None = None,
    ) -> SendMessageResponse:
        media_payload = _build_media_payload(
            media_id=media_id,
            link=link,
            caption=caption,
            filename=filename,
        )
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": media_type,
            media_type: media_payload,
        }
        data = await self._request("POST", f"/{self.phone_number_id}/messages", json=payload)
        return SendMessageResponse.model_validate(data)

    async def upload_media(
        self,
        *,
        file_path: str | Path,
        mime_type: str | None = None,
        filename: str | None = None,
    ) -> MediaUploadResponse:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"file not found: {path}")

        guessed_mime, _ = mimetypes.guess_type(str(path))
        final_mime = mime_type or guessed_mime or "application/octet-stream"
        final_name = filename or path.name

        with path.open("rb") as file_handle:
            files = {
                "file": (final_name, file_handle, final_mime),
                "messaging_product": (None, "whatsapp"),
            }
            data = await self._request(
                "POST",
                f"/{self.phone_number_id}/media",
                files=files,
                content_type_json=False,
            )
        return MediaUploadResponse.model_validate(data)

    async def get_media(self, *, media_id: str) -> MediaInfoResponse:
        data = await self._request("GET", f"/{media_id}")
        return MediaInfoResponse.model_validate(data)

    async def mark_as_read(self, *, message_id: str) -> MarkAsReadResponse:
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        data = await self._request("POST", f"/{self.phone_number_id}/messages", json=payload)
        return MarkAsReadResponse.model_validate(data)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        content_type_json: bool = True,
    ) -> dict[str, Any]:
        headers = None
        if not content_type_json:
            headers = {"Authorization": f"Bearer {self.access_token}"}

        attempt = 0
        can_retry_method = self._should_retry_method(method)

        while True:
            try:
                response = await self._client.request(
                    method=method,
                    url=path,
                    json=json,
                    files=files,
                    headers=headers,
                )
            except httpx.HTTPError as exc:
                if not can_retry_method or attempt >= self.max_retries:
                    raise WhatsAppAPIError(message=f"HTTP communication error: {exc}") from exc
                delay = self._get_retry_delay(attempt, None)
                if delay > 0:
                    await asyncio.sleep(delay)
                attempt += 1
                continue

            if (
                can_retry_method
                and attempt < self.max_retries
                and self._should_retry_response(response)
            ):
                delay = self._get_retry_delay(attempt, response.headers.get("Retry-After"))
                if delay > 0:
                    await asyncio.sleep(delay)
                attempt += 1
                continue

            return _parse_json_response(response)
