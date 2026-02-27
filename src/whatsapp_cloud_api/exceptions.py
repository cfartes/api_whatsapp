from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WhatsAppAPIError(Exception):
    message: str
    status_code: int | None = None
    error_type: str | None = None
    code: int | None = None
    error_subcode: int | None = None
    fbtrace_id: str | None = None
    details: dict | None = None

    def __str__(self) -> str:
        parts = [self.message]
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        if self.code is not None:
            parts.append(f"code={self.code}")
        if self.error_subcode is not None:
            parts.append(f"subcode={self.error_subcode}")
        if self.error_type:
            parts.append(f"type={self.error_type}")
        return " | ".join(parts)
