from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BaseResponseModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class Contact(BaseResponseModel):
    input: str | None = None
    wa_id: str | None = None


class Message(BaseResponseModel):
    id: str
    message_status: str | None = None


class SendMessageResponse(BaseResponseModel):
    messaging_product: str = "whatsapp"
    contacts: list[Contact] = Field(default_factory=list)
    messages: list[Message] = Field(default_factory=list)


class MediaUploadResponse(BaseResponseModel):
    id: str


class MediaInfoResponse(BaseResponseModel):
    id: str | None = None
    messaging_product: str | None = None
    url: str | None = None
    mime_type: str | None = None
    sha256: str | None = None
    file_size: int | None = None


class MarkAsReadResponse(BaseResponseModel):
    success: bool = False
