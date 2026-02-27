from __future__ import annotations

import hashlib
import hmac

from whatsapp_cloud_api.webhook import verify_webhook_challenge, verify_webhook_signature


def test_verify_webhook_challenge_success() -> None:
    ok, challenge = verify_webhook_challenge(
        mode="subscribe",
        token="abc",
        challenge="12345",
        verify_token="abc",
    )
    assert ok is True
    assert challenge == "12345"


def test_verify_webhook_challenge_failure() -> None:
    ok, challenge = verify_webhook_challenge(
        mode="subscribe",
        token="errado",
        challenge="12345",
        verify_token="abc",
    )
    assert ok is False
    assert challenge == ""


def test_verify_webhook_signature_success() -> None:
    secret = "app-secret"
    body = b'{"entry":[]}'
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    signature = f"sha256={digest}"

    assert verify_webhook_signature(
        app_secret=secret,
        raw_body=body,
        x_hub_signature_256=signature,
    )


def test_verify_webhook_signature_failure() -> None:
    assert not verify_webhook_signature(
        app_secret="app-secret",
        raw_body=b"{}",
        x_hub_signature_256="sha256=invalid",
    )
