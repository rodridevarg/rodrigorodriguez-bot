from dataclasses import dataclass
from typing import Optional


@dataclass
class InboundTextMessage:
    from_number: str
    message_id: str
    text: str
    timestamp: str
    provider: str = "whatsapp"


@dataclass
class StatusEvent:
    status: str
    message_id: str
    timestamp: str
    provider: str = "whatsapp"


@dataclass
class OutgoingTextMessage:
    to: str
    body: str
    message_id: Optional[str] = None
    provider: str = "whatsapp"


@dataclass
class WebhookVerificationRequest:
    mode: str
    verify_token: str
    challenge: str
