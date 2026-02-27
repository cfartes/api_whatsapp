from __future__ import annotations

import hashlib
import hmac


def verify_webhook_challenge(
    *,
    mode: str | None,
    token: str | None,
    challenge: str | None,
    verify_token: str,
) -> tuple[bool, str]:
    if mode == "subscribe" and token == verify_token and challenge is not None:
        return True, challenge
    return False, ""


def verify_webhook_signature(
    *,
    app_secret: str,
    raw_body: bytes,
    x_hub_signature_256: str,
) -> bool:
    if not x_hub_signature_256.startswith("sha256="):
        return False

    expected = hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    received = x_hub_signature_256.split("=", 1)[1]
    return hmac.compare_digest(expected, received)
