import uuid
from abc import ABC, abstractmethod
from typing import Dict
from app.config import (
    WHATSAPP_MODE,
    META_ACCESS_TOKEN,
    META_PHONE_NUMBER_ID,
    META_GRAPH_VERSION,
)


class WhatsAppSender(ABC):
    @abstractmethod
    def send_text(self, to: str, body: str) -> Dict:
        ...


class FakeWhatsAppSender(WhatsAppSender):
    def send_text(self, to: str, body: str) -> Dict:
        fake_id = f"fake-{uuid.uuid4().hex[:8]}"
        print(f"[FAKE SENDER] to={to} | body={body[:80]}... | id={fake_id}")
        return {
            "provider": "fake",
            "to": to,
            "body": body,
            "message_id": fake_id,
        }


class MetaWhatsAppSender(WhatsAppSender):
    def __init__(self):
        if not META_ACCESS_TOKEN or not META_PHONE_NUMBER_ID:
            raise ValueError(
                "Faltan META_ACCESS_TOKEN o META_PHONE_NUMBER_ID. "
                "Completá las credenciales en .env y usá WHATSAPP_MODE=meta"
            )

    def send_text(self, to: str, body: str) -> Dict:
        import httpx

        url = (
            f"https://graph.facebook.com/{META_GRAPH_VERSION}/"
            f"{META_PHONE_NUMBER_ID}/messages"
        )
        headers = {
            "Authorization": f"Bearer {META_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": body},
        }

        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            return {
                "provider": "meta",
                "to": to,
                "body": body,
                "message_id": data.get("messages", [{}])[0].get("id"),
            }
        except httpx.HTTPStatusError as e:
            error_body = ""
            try:
                error_body = e.response.text
            except Exception:
                pass
            print(f"[META SENDER ERROR] HTTP {e.response.status_code}: {error_body}")
            return {
                "provider": "meta",
                "to": to,
                "body": body,
                "error": True,
                "status_code": e.response.status_code,
                "error_body": error_body,
            }
        except Exception as e:
            print(f"[META SENDER ERROR] {e}")
            return {
                "provider": "meta",
                "to": to,
                "body": body,
                "error": True,
                "error_message": str(e),
            }


def get_sender() -> WhatsAppSender:
    if WHATSAPP_MODE == "meta":
        return MetaWhatsAppSender()
    return FakeWhatsAppSender()
