from pydantic import BaseModel
from typing import Optional


class BaileysWebhookPayload(BaseModel):
    phone: str
    message: str
    messageId: Optional[str] = None
    senderName: Optional[str] = None


class ZAPIMessageData(BaseModel):
    messageId: Optional[str] = None
    phone: Optional[str] = None
    fromMe: Optional[bool] = False
    momment: Optional[int] = None
    status: Optional[str] = None
    chatName: Optional[str] = None
    senderPhoto: Optional[str] = None
    senderName: Optional[str] = None
    participantPhone: Optional[str] = None
    text: Optional[dict] = None
    image: Optional[dict] = None
    audio: Optional[dict] = None
    document: Optional[dict] = None


class ZAPIWebhookPayload(BaseModel):
    instanceId: Optional[str] = None
    messageId: Optional[str] = None
    phone: Optional[str] = None
    fromMe: Optional[bool] = False
    momment: Optional[int] = None
    status: Optional[str] = None
    chatName: Optional[str] = None
    senderName: Optional[str] = None
    text: Optional[dict] = None
    image: Optional[dict] = None
    audio: Optional[dict] = None
    document: Optional[dict] = None

    def get_text(self) -> Optional[str]:
        if self.text:
            return self.text.get("message")
        return None

    def is_from_me(self) -> bool:
        return bool(self.fromMe)
